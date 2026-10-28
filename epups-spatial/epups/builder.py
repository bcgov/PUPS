"""
Build the ePUPS spatial schema in a geodatabase.

Used for both production and editor workspaces, so they always match.
Every function leaves existing objects and fields unchanged, except that
a missing domain link is added to an existing field.

Written against file geodatabases. Enterprise geodatabases qualify
object names with the owner (for example OWNER.ePup_Spatial), which
object_paths() will need to handle once the production server is known.
"""

from pathlib import Path

import arcpy

from epups import schema

COPY_VIEW_NAME = "epups_copy_source"


def object_paths(gdb_path):
    gdb_path = Path(gdb_path)
    dataset = gdb_path / schema.FEATURE_DATASET_NAME

    return {
        "dataset": dataset,
        "spatial": dataset / schema.SPATIAL_FC_NAME,
        "version": gdb_path / schema.VERSION_TABLE_NAME,
        "users": gdb_path / schema.USERS_TABLE_NAME,
        "workspace_info": gdb_path / schema.WORKSPACE_INFO_TABLE_NAME,
        # Kept in the feature dataset, alongside the polygon class it relates.
        "relationship": dataset / schema.RELATIONSHIP_CLASS_NAME,
    }


def create_file_gdb(folder, name):
    """Create a new file geodatabase. Refuses to overwrite."""
    folder = Path(folder)
    if not name.lower().endswith(".gdb"):
        name += ".gdb"
    gdb_path = folder / name

    if arcpy.Exists(str(gdb_path)):
        raise FileExistsError(
            f"Geodatabase already exists; nothing was overwritten:\n{gdb_path}"
        )

    folder.mkdir(parents=True, exist_ok=True)
    arcpy.management.CreateFileGDB(str(folder), name)

    if not arcpy.Exists(str(gdb_path)):
        raise RuntimeError(
            f"ArcPy did not report the geodatabase as existing:\n{gdb_path}"
        )

    print(f"Created geodatabase: {gdb_path}")
    return gdb_path


def build_schema(gdb_path, include_workspace_info=False):
    """Create any missing ePUPS objects, fields, indexes and domains in gdb_path."""
    if not arcpy.Exists(str(gdb_path)):
        raise FileNotFoundError(f"Geodatabase not found: {gdb_path}")

    paths = object_paths(gdb_path)
    spatial_reference = arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID)

    print("\nDomains")
    _ensure_domains(gdb_path)

    print("\nFeature dataset")
    if arcpy.Exists(str(paths["dataset"])):
        print(f"  Already exists: {paths['dataset']}")
    else:
        arcpy.management.CreateFeatureDataset(
            str(gdb_path), schema.FEATURE_DATASET_NAME, spatial_reference
        )
        print(f"  Created: {paths['dataset']}")

    print("\nVersion table")
    _ensure_table(gdb_path, schema.VERSION_TABLE_NAME)
    add_missing_fields(paths["version"], schema.VERSION_TABLE_FIELDS)
    add_missing_indexes(paths["version"], schema.VERSION_INDEXES)

    print("\nUsers table")
    _ensure_table(gdb_path, schema.USERS_TABLE_NAME)
    add_missing_fields(paths["users"], schema.USERS_FIELDS)
    add_missing_indexes(paths["users"], schema.USERS_INDEXES)

    print("\nPolygon feature class")
    if arcpy.Exists(str(paths["spatial"])):
        print(f"  Already exists: {paths['spatial']}")
    else:
        arcpy.management.CreateFeatureclass(
            str(paths["dataset"]),
            schema.SPATIAL_FC_NAME,
            "POLYGON",
            spatial_reference=spatial_reference,
        )
        print(f"  Created: {paths['spatial']}")
    add_missing_fields(paths["spatial"], schema.SPATIAL_FIELDS)
    add_missing_indexes(paths["spatial"], schema.SPATIAL_INDEXES)

    print("\nRelationship class")
    _ensure_version_relationship(paths)

    if include_workspace_info:
        print("\nWorkspace info table")
        _ensure_table(gdb_path, schema.WORKSPACE_INFO_TABLE_NAME)
        add_missing_fields(paths["workspace_info"], schema.WORKSPACE_INFO_FIELDS)

    return paths


def add_missing_fields(table_path, field_defs):
    existing = {field.name.upper(): field for field in arcpy.ListFields(str(table_path))}

    for field in field_defs:
        name = field["name"]

        if name.upper() in existing:
            print(f"  Field already exists: {name}")
            _assign_domain_if_missing(table_path, field, existing[name.upper()])
            continue

        kwargs = {
            "field_alias": field["alias"],
            "field_is_nullable": "NULLABLE" if field["nullable"] else "NON_NULLABLE",
        }
        if "length" in field:
            kwargs["field_length"] = field["length"]

        arcpy.management.AddField(str(table_path), name, field["type"], **kwargs)
        print(f"  Added field: {name}")

        if field.get("default") is not None:
            arcpy.management.AssignDefaultToField(str(table_path), name, field["default"])

        if field.get("domain"):
            arcpy.management.AssignDomainToField(str(table_path), name, field["domain"])
            print(f"    Assigned domain: {field['domain']}")


def add_missing_indexes(table_path, index_defs):
    existing = {index.name for index in arcpy.Describe(str(table_path)).indexes}

    for index in index_defs:
        name = index["name"]

        if name in existing:
            print(f"  Index already exists: {name}")
            continue

        arcpy.management.AddIndex(
            str(table_path),
            ";".join(index["fields"]),
            name,
            "UNIQUE" if index["unique"] else "NON_UNIQUE",
        )
        print(f"  Added index: {name}")


def copy_records(source_path, target_path, where_clause=None):
    """
    Append records from source to target, optionally only those matching where_clause.
    Returns the number of records added.

    Append has no where clause of its own, so the filter goes on a layer or
    table view, which is appended instead.
    """
    where_clause = where_clause or ""

    if arcpy.Describe(str(source_path)).dataType == "FeatureClass":
        arcpy.management.MakeFeatureLayer(str(source_path), COPY_VIEW_NAME, where_clause)
    else:
        arcpy.management.MakeTableView(str(source_path), COPY_VIEW_NAME, where_clause)

    before = int(arcpy.management.GetCount(str(target_path))[0])
    try:
        arcpy.management.Append(COPY_VIEW_NAME, str(target_path), "TEST")
    finally:
        arcpy.management.Delete(COPY_VIEW_NAME)
    after = int(arcpy.management.GetCount(str(target_path))[0])

    return after - before


def _ensure_table(gdb_path, table_name):
    table_path = Path(gdb_path) / table_name

    if arcpy.Exists(str(table_path)):
        print(f"  Already exists: {table_path}")
    else:
        arcpy.management.CreateTable(str(gdb_path), table_name)
        print(f"  Created: {table_path}")


def _ensure_version_relationship(paths):
    """
    Simple one-to-many relationship: version (origin) to polygons (destination).
    It shows the link in ArcGIS Pro. It does not cascade deletes or enforce the
    key; the attribute rules and QA do the checking.
    """
    if arcpy.Exists(str(paths["relationship"])):
        print(f"  Already exists: {paths['relationship']}")
        return

    arcpy.management.CreateRelationshipClass(
        str(paths["version"]),
        str(paths["spatial"]),
        str(paths["relationship"]),
        "SIMPLE",
        "Polygons",
        "Version",
        "NONE",
        "ONE_TO_MANY",
        "NONE",
        schema.RELATIONSHIP_KEY,
        schema.RELATIONSHIP_KEY,
    )
    print(f"  Created: {paths['relationship']}")


def _ensure_domains(gdb_path):
    existing = {domain.name for domain in arcpy.da.ListDomains(str(gdb_path))}

    for name, spec in schema.DOMAINS.items():
        if name in existing:
            print(f"  Domain already exists: {name}")
            continue

        arcpy.management.CreateDomain(
            str(gdb_path), name, spec["description"], spec["field_type"], "CODED"
        )
        for value in spec["values"]:
            arcpy.management.AddCodedValueToDomain(str(gdb_path), name, value, value)
        print(f"  Created domain: {name}")


def _assign_domain_if_missing(table_path, field_def, existing_field):
    domain = field_def.get("domain")

    if domain and existing_field.domain != domain:
        arcpy.management.AssignDomainToField(str(table_path), field_def["name"], domain)
        print(f"  Assigned domain {domain} to existing field {field_def['name']}")
