"""
QA/QC checks for an editor workspace, run before its records go to production.

Each check returns a list of Issue. An ERROR must be fixed before promotion.
A WARNING needs a reviewer decision but does not block promotion.

Geometry checks use arcpy.management.CheckGeometry. Area checks assume the
spatial reference is in metres (EPSG:3005).
"""

from collections import Counter, namedtuple
from pathlib import Path

import arcpy

from epups import builder, schema

ERROR = "ERROR"
WARNING = "WARNING"

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

    return issues


def count_by_severity(issues):
    counts = Counter(issue.severity for issue in issues)
    return counts.get(ERROR, 0), counts.get(WARNING, 0)


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

    return issues


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

    return [
        Issue(ERROR, "spatial-id", f"SPATIAL_ID {value}",
              f"Duplicate SPATIAL_ID appears {count} times")
        for value, count in Counter(ids).items() if count > 1
    ]


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
