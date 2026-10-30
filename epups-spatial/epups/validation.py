"""
QA/QC checks for an editor workspace, run before its records go to production.

Each check returns a list of Issue. An ERROR must be fixed before promotion.
A WARNING needs a reviewer decision but does not block promotion.

Geometry checks use arcpy.management.CheckGeometry. Area checks assume the
spatial reference is in metres (EPSG:3005).
"""

import re
from collections import Counter, namedtuple
from pathlib import Path

import arcpy

from epups import builder, config, schema, versioning

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402

ERROR = "ERROR"
WARNING = "WARNING"

# Checks whose errors are about the whole workspace, not one polygon.
WORKSPACE_CHECKS = ("schema-version", "structure", "spatial-reference")

# How an issue names a polygon: "OBJECTID 3" or "ePup_Spatial OBJECTID 3",
# "SPATIAL_ID 5", or a whole authorization, "AUTHORIZATIONID 6812345".
_POLYGON_RECORD = re.compile(rf"^(?:{schema.SPATIAL_FC_NAME} )?OBJECTID (\d+)$")
_SPATIAL_ID_RECORD = re.compile(r"^SPATIAL_ID (-?\d+)$")
_AUTHORIZATION_RECORD = re.compile(r"^AUTHORIZATIONID (\d+)$")

# GEOMETRY_QA_STATUS values written back (domain ePup_Geometry_QA_Status).
QA_PASS, QA_NEEDS_REVIEW, QA_FAIL = "PASS", "NEEDS_REVIEW", "FAIL"
QA_NOTE_LENGTH = 500

Issue = namedtuple("Issue", ["severity", "check", "record", "message"])

# ArcGIS reports field types with these names.
ARCGIS_TYPE_NAMES = {
    "LONG": "Integer",
    "SHORT": "SmallInteger",
    "TEXT": "String",
    "DATE": "Date",
    "DOUBLE": "Double",
}

GEOMETRY_TEMP_TABLE = "in_memory\\qa_geometry_problems"
SQUARE_METRES_PER_HECTARE = 10000.0


def run_all(gdb_path, production_path=None):
    """Run every check on a workspace. Returns a list of Issue."""
    paths = builder.object_paths(gdb_path)

    issues = check_schema_version(gdb_path)
    issues += check_structure(paths)
    issues += check_extra_datasets(gdb_path)

    # Attribute and geometry checks would fail on a broken structure, so stop here.
    if any(issue.severity == ERROR for issue in issues):
        return issues

    issues += check_spatial_reference(paths["spatial"])
    issues += check_geometry(paths["spatial"])
    issues += check_attributes(paths["users"], schema.USERS_FIELDS)
    issues += check_attributes(paths["version"], schema.VERSION_TABLE_FIELDS)
    issues += check_attributes(paths["spatial"], schema.SPATIAL_FIELDS)
    issues += check_unique_spatial_ids(paths["spatial"])
    issues += check_unique_version_numbers(paths["version"])
    issues += check_version_links(paths)
    issues += check_area(paths["spatial"])
    issues += check_reference_coverage(paths["spatial"], production_path or config.PRODUCTION_PATH)
    issues += check_new_versions(gdb_path, production_path or config.PRODUCTION_PATH)

    return issues


def count_by_severity(issues):
    counts = Counter(issue.severity for issue in issues)
    return counts.get(ERROR, 0), counts.get(WARNING, 0)


def issues_by_polygon(gdb_path, issues):
    """{OBJECTID: [Issue, ...]} for every polygon in the workspace, including those with no issues."""
    paths = builder.object_paths(gdb_path)
    versions = versioning.read_versions(paths["version"])

    with arcpy.da.SearchCursor(str(paths["spatial"]), ["OID@", "SPATIAL_ID", "VERSION_ID"]) as cursor:
        polygons = list(cursor)

    by_polygon = {oid: [] for oid, _, _ in polygons}
    for issue in issues:
        match = _POLYGON_RECORD.match(issue.record)
        if match:
            oid = int(match.group(1))
            if oid in by_polygon:
                by_polygon[oid].append(issue)
            continue
        match = _SPATIAL_ID_RECORD.match(issue.record)
        if match:
            targets = [oid for oid, spatial_id, _ in polygons if spatial_id == int(match.group(1))]
        else:
            match = _AUTHORIZATION_RECORD.match(issue.record)
            if not match:
                continue
            targets = [
                oid for oid, _, version_id in polygons
                if version_id in versions and versions[version_id].authorization_id == int(match.group(1))
            ]
        for oid in targets:
            by_polygon[oid].append(issue)
    return by_polygon


def write_results(gdb_path, issues, checker_id=None):
    """
    Write the QA result onto each polygon: GEOMETRY_QA_STATUS (FAIL on any
    error, NEEDS_REVIEW on warnings only, else PASS), QA_CHECKED_DATE,
    QA_CHECKED_BY (users.UserID), QA_NOTE (the messages), and
    OUT_OF_BOUNDARY_FLAG (1 if outside protected land or BC).

    Returns (written, failed). A polygon the attribute rules won't save (for
    example a duplicate SPATIAL_ID) is counted as failed; its errors are still
    in the report.
    """
    by_polygon = issues_by_polygon(gdb_path, issues)
    now = datetime.now()
    fields = ["OID@", "GEOMETRY_QA_STATUS", "QA_CHECKED_DATE", "QA_CHECKED_BY", "QA_NOTE", "OUT_OF_BOUNDARY_FLAG"]
    written = failed = 0

    with arcpy.da.UpdateCursor(str(builder.object_paths(gdb_path)["spatial"]), fields) as cursor:
        for row in cursor:
            found = by_polygon.get(row[0], [])
            if any(issue.severity == ERROR for issue in found):
                status = QA_FAIL
            elif found:
                status = QA_NEEDS_REVIEW
            else:
                status = QA_PASS
            note = "; ".join(f"{issue.severity} {issue.check}: {issue.message}" for issue in found)
            outside = int(any(issue.check == "reference" and issue.severity == ERROR for issue in found))
            try:
                cursor.updateRow([row[0], status, now, checker_id, note[:QA_NOTE_LENGTH] or None, outside])
                written += 1
            except RuntimeError:
                failed += 1
    return written, failed


def write_report(gdb_path, issues, timestamp, folder=None):
    """Write the QA report to folder (default config.LOG_FOLDER). Returns (path, result, errors, warnings)."""
    folder = Path(folder) if folder else config.LOG_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    errors, warnings = count_by_severity(issues)
    result = "PASS" if errors == 0 else "FAIL"

    report_path = folder / f"qa_{Path(gdb_path).stem}_{timestamp:%Y%m%d_%H%M%S}.txt"

    lines = [
        "ePUPS workspace QA report",
        f"Workspace: {gdb_path}",
        f"Run: {timestamp:%Y-%m-%d %H:%M:%S}",
        f"Schema version: {schema.SCHEMA_VERSION}",
        f"Result: {result} ({errors} errors, {warnings} warnings)",
        "",
    ]

    if issues:
        lines.append(f"{'Severity':<9} {'Check':<18} {'Record':<26} Message")
        lines.append("-" * 90)
        for issue in issues:
            lines.append(
                f"{issue.severity:<9} {issue.check:<18} {issue.record:<26} {issue.message}"
            )
    else:
        lines.append("No issues found.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path, result, errors, warnings


def check_schema_version(gdb_path):
    info_path = builder.object_paths(gdb_path)["workspace_info"]

    if not arcpy.Exists(str(info_path)):
        return [Issue(
            WARNING, "schema-version", "Workspace_Info",
            "Table not found; this may not be a workspace. Schema version not checked.",
        )]

    with arcpy.da.SearchCursor(str(info_path), ["SCHEMA_VERSION"]) as cursor:
        versions = {row[0] for row in cursor if row[0]}

    if versions == {schema.SCHEMA_VERSION}:
        return []

    return [Issue(
        ERROR, "schema-version", "Workspace_Info",
        f"Workspace schema version {sorted(versions) or 'unknown'} does not match "
        f"current schema {schema.SCHEMA_VERSION}. Recreate the workspace.",
    )]


def check_structure(paths):
    """Objects and fields exist with the expected types and domain links."""
    issues = []

    for key, name, field_defs in (
        ("version", schema.VERSION_TABLE_NAME, schema.VERSION_TABLE_FIELDS),
        ("spatial", schema.SPATIAL_FC_NAME, schema.SPATIAL_FIELDS),
        ("users", schema.USERS_TABLE_NAME, schema.USERS_FIELDS),
    ):
        path = paths[key]

        if not arcpy.Exists(str(path)):
            issues.append(Issue(ERROR, "structure", name, f"Missing object: {name}"))
            continue

        fields = {field.name.upper(): field for field in arcpy.ListFields(str(path))}

        for definition in field_defs:
            field_name = definition["name"]
            field = fields.get(field_name.upper())

            if field is None:
                issues.append(Issue(
                    ERROR, "structure", name, f"Missing field: {field_name}"))
                continue

            expected_type = ARCGIS_TYPE_NAMES[definition["type"]]
            if field.type != expected_type:
                issues.append(Issue(
                    ERROR, "structure", name,
                    f"{field_name} is {field.type}, expected {expected_type}"))

            if definition.get("domain") and field.domain != definition["domain"]:
                issues.append(Issue(
                    ERROR, "structure", name,
                    f"{field_name} is not linked to domain {definition['domain']}"))

    # The relationship only helps people read the data, so a missing one is a warning.
    if not arcpy.Exists(str(paths["relationship"])):
        issues.append(Issue(
            WARNING, "structure", schema.RELATIONSHIP_CLASS_NAME,
            "Missing relationship class between versions and polygons"))

    return issues


def check_extra_datasets(gdb_path):
    """
    Tables and feature classes that aren't part of the ePUPS schema, such as the
    Links table ArcGIS Pro's Transform tool leaves behind. They don't affect the
    checks, but shouldn't be handed over.
    """
    expected = {
        name.lower() for name in (
            schema.SPATIAL_FC_NAME, schema.VERSION_TABLE_NAME, schema.USERS_TABLE_NAME,
            schema.WORKSPACE_INFO_TABLE_NAME,
        )
    }
    found = []
    for _, _, names in arcpy.da.Walk(str(gdb_path), datatype=["FeatureClass", "Table"]):
        found += [name for name in names if name.lower() not in expected]

    return [
        Issue(WARNING, "structure", name,
              "Not part of the ePUPS schema (left by an editing tool?). Delete it before hand-over.")
        for name in sorted(found)
    ]


def check_spatial_reference(spatial_path):
    wkid = arcpy.Describe(str(spatial_path)).spatialReference.factoryCode

    if wkid == schema.SPATIAL_REFERENCE_WKID:
        return []

    return [Issue(
        ERROR, "spatial-reference", schema.SPATIAL_FC_NAME,
        f"WKID {wkid}, expected {schema.SPATIAL_REFERENCE_WKID}",
    )]


def check_geometry(spatial_path):
    if arcpy.Exists(GEOMETRY_TEMP_TABLE):
        arcpy.management.Delete(GEOMETRY_TEMP_TABLE)

    arcpy.management.CheckGeometry(str(spatial_path), GEOMETRY_TEMP_TABLE)

    issues = []
    with arcpy.da.SearchCursor(GEOMETRY_TEMP_TABLE, ["FEATURE_ID", "PROBLEM"]) as cursor:
        for feature_id, problem in cursor:
            issues.append(Issue(
                ERROR, "geometry", f"OBJECTID {feature_id}", problem))

    arcpy.management.Delete(GEOMETRY_TEMP_TABLE)
    return issues


def check_attributes(table_path, field_defs):
    """
    Required values are filled in, and coded fields hold a value from their domain.

    Empty geometry is reported by check_geometry, so it is not checked here.
    """
    required = [field["name"] for field in field_defs if not field["nullable"]]
    domain_fields = {field["name"]: field["domain"] for field in field_defs if field.get("domain")}
    check_names = list(dict.fromkeys(required + list(domain_fields)))
    table_name = Path(str(table_path)).name

    issues = []
    with arcpy.da.SearchCursor(str(table_path), ["OID@"] + check_names) as cursor:
        for row in cursor:
            record = f"{table_name} OBJECTID {row[0]}"
            values = dict(zip(check_names, row[1:]))

            for name in required:
                value = values[name]
                if value is None or (isinstance(value, str) and not value.strip()):
                    issues.append(Issue(ERROR, "required", record, f"Missing value: {name}"))

            for name, domain in domain_fields.items():
                value = values[name]
                if value is not None and value not in schema.DOMAINS[domain]["values"]:
                    issues.append(Issue(
                        ERROR, "domain", record, f"Invalid {name}: {value} (not in {domain})"))

    return issues


def check_unique_spatial_ids(spatial_path):
    with arcpy.da.SearchCursor(str(spatial_path), ["SPATIAL_ID"]) as cursor:
        ids = [row[0] for row in cursor if row[0] is not None]

    issues = [
        Issue(ERROR, "spatial-id", f"SPATIAL_ID {value}",
              f"Duplicate SPATIAL_ID appears {count} times")
        for value, count in Counter(ids).items() if count > 1
    ]
    # ArcGIS Pro fills an empty number field with 0, so 0 means it was never set.
    issues += [
        Issue(ERROR, "spatial-id", f"SPATIAL_ID {value}", "SPATIAL_ID must be above 0")
        for value in sorted(set(ids)) if value <= 0
    ]
    return issues


def check_unique_version_numbers(version_path):
    with arcpy.da.SearchCursor(str(version_path), ["AUTHORIZATIONID", "VERSION_NUMBER"]) as cursor:
        pairs = [row for row in cursor if None not in row]

    return [
        Issue(ERROR, "version-number",
              f"AUTHORIZATIONID {authorization_id} VERSION_NUMBER {number}",
              f"Duplicate version number appears {count} times")
        for (authorization_id, number), count in Counter(pairs).items() if count > 1
    ]


def check_version_links(paths):
    """Every polygon points to a version row, and each authorization has at most one current version."""
    with arcpy.da.SearchCursor(str(paths["version"]),
                               ["VERSION_ID", "AUTHORIZATIONID", "IS_CURRENT"]) as cursor:
        version_rows = list(cursor)

    known_versions = {row[0] for row in version_rows}

    with arcpy.da.SearchCursor(str(paths["spatial"]), ["OID@", "VERSION_ID"]) as cursor:
        issues = [
            Issue(ERROR, "version-link", f"OBJECTID {oid}",
                  f"VERSION_ID {version_id} not found in {schema.VERSION_TABLE_NAME}")
            for oid, version_id in cursor
            if version_id is not None and version_id not in known_versions
        ]

    current_counts = Counter(
        authorization_id for _, authorization_id, is_current in version_rows
        if is_current == 1
    )
    issues += [
        Issue(WARNING, "version-link", f"AUTHORIZATIONID {authorization_id}",
              f"{count} current versions; expected at most one")
        for authorization_id, count in current_counts.items() if count > 1
    ]

    return issues


def check_area(spatial_path):
    """AREA_HA should be filled in and match the geometry (metres to hectares)."""
    issues = []

    with arcpy.da.SearchCursor(str(spatial_path), ["OID@", "SHAPE@", "AREA_HA"]) as cursor:
        for oid, shape, area_ha in cursor:
            if shape is None:
                continue  # reported by check_geometry

            record = f"OBJECTID {oid}"

            if area_ha is None:
                issues.append(Issue(WARNING, "area", record, "AREA_HA not calculated"))
                continue

            expected_ha = shape.area / SQUARE_METRES_PER_HECTARE
            tolerance = max(0.01, expected_ha * 0.001)

            if abs(area_ha - expected_ha) > tolerance:
                issues.append(Issue(
                    WARNING, "area", record,
                    f"AREA_HA {area_ha:.4f} differs from geometry {expected_ha:.4f} ha"))

    return issues


def check_reference_coverage(spatial_path, production_path):
    """
    Every polygon must sit inside protected land and inside the BC boundary.

    The reference layers are read from production, so workspaces are checked
    against the same boundaries that the production topology uses.
    """
    dataset = builder.object_paths(production_path)["dataset"]
    references = (
        ("Ref_Protected_Lands", "outside protected land"),
        ("Ref_BC_Boundary", "outside the BC boundary"),
    )
    union_table = "in_memory\\epups_ref_union"
    issues = []

    for name, problem in references:
        reference = dataset / name

        if not arcpy.Exists(str(reference)):
            issues.append(Issue(
                WARNING, "reference", name,
                f"{name} not found in production; not checked. Run fetch_reference_data.py."))
            continue

        if arcpy.Exists(union_table):
            arcpy.management.Delete(union_table)
        arcpy.management.Dissolve(str(reference), union_table)

        with arcpy.da.SearchCursor(union_table, ["SHAPE@"]) as cursor:
            union_shape = next((row[0] for row in cursor), None)

        with arcpy.da.SearchCursor(str(spatial_path), ["OID@", "SHAPE@"]) as cursor:
            for oid, shape in cursor:
                if shape is None:
                    continue  # reported by check_geometry
                if union_shape is None or not union_shape.contains(shape):
                    issues.append(Issue(ERROR, "reference", f"OBJECTID {oid}", f"Polygon is {problem}"))

        arcpy.management.Delete(union_table)

    return issues


def check_new_versions(gdb_path, production_path):
    """Edited authorizations must have their new version (Finish or Save Draft)."""
    if not arcpy.Exists(str(builder.object_paths(production_path)["version"])):
        return [Issue(
            WARNING, "new-version", "production",
            "Production not found; edits not checked for a new version.")]

    return [
        Issue(ERROR, "new-version", f"AUTHORIZATIONID {authorization_id}",
              f"Edited ({'; '.join(edits)}) but not saved as a new version. "
              "Run Finish or Save Draft.")
        for authorization_id, edits in sorted(versioning.unfinished_edits(gdb_path, production_path).items())
    ]
