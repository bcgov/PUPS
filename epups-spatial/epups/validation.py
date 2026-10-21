"""
QA/QC checks for an editor workspace, run before its records go to production.

Each check returns a list of Issue. An ERROR must be fixed before promotion.
A WARNING needs a reviewer decision but does not block promotion.

Geometry checks use arcpy.management.CheckGeometry.
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
}

GEOMETRY_TEMP_TABLE = "in_memory\\qa_geometry_problems"


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
    issues += check_attributes(paths["spatial"])
    issues += check_unique_spatial_ids(paths["spatial"])
    issues += check_version_links(paths)

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
    """Objects and fields exist with the expected types and domain."""
    issues = []

    for key, name, field_defs in (
        ("version", schema.VERSION_TABLE_NAME, schema.VERSION_TABLE_FIELDS),
        ("spatial", schema.SPATIAL_FC_NAME, schema.SPATIAL_FIELDS),
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


def check_attributes(spatial_path):
    """Required values are filled in and SPATIAL_STATUS is a known value.

    Empty geometry is reported by check_geometry, so it is not checked here.
    """
    required = [field["name"] for field in schema.SPATIAL_FIELDS if not field["nullable"]]
    cursor_fields = ["OID@"] + required
    status_index = cursor_fields.index("SPATIAL_STATUS") if "SPATIAL_STATUS" in required else None

    issues = []
    with arcpy.da.SearchCursor(str(spatial_path), cursor_fields) as cursor:
        for row in cursor:
            oid, values = row[0], row[1:]
            record = f"OBJECTID {oid}"

            for name, value in zip(required, values):
                if value is None or (isinstance(value, str) and not value.strip()):
                    issues.append(Issue(ERROR, "required", record, f"Missing value: {name}"))

            if status_index is not None:
                status = row[status_index]
                if status is not None and status not in schema.SPATIAL_STATUS_VALUES:
                    issues.append(Issue(
                        ERROR, "domain", record, f"Invalid SPATIAL_STATUS: {status}"))

    return issues


def check_unique_spatial_ids(spatial_path):
    with arcpy.da.SearchCursor(str(spatial_path), ["SPATIAL_ID"]) as cursor:
        ids = [row[0] for row in cursor if row[0] is not None]

    return [
        Issue(ERROR, "spatial-id", f"SPATIAL_ID {value}",
              f"Duplicate SPATIAL_ID appears {count} times")
        for value, count in Counter(ids).items() if count > 1
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
