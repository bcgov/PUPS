"""
Build the ePUPS spatial schema in a geodatabase.

Used for both production and editor workspaces, so they always match.
Every function leaves existing objects and fields unchanged.

Written against file geodatabases. Enterprise geodatabases qualify
object names with the owner (for example OWNER.ePup_Spatial), which
object_paths() will need to handle once the production server is known.
"""

from pathlib import Path

import arcpy

from epups import schema


def object_paths(gdb_path):
    gdb_path = Path(gdb_path)
    dataset = gdb_path / schema.FEATURE_DATASET_NAME

    return {
        "dataset": dataset,
        "spatial": dataset / schema.SPATIAL_FC_NAME,
        "version": gdb_path / schema.VERSION_TABLE_NAME,
        "workspace_info": gdb_path / schema.WORKSPACE_INFO_TABLE_NAME,
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
    """Create any missing ePUPS objects, fields and domains in gdb_path."""
    if not arcpy.Exists(str(gdb_path)):
        raise FileNotFoundError(f"Geodatabase not found: {gdb_path}")

    paths = object_paths(gdb_path)
    spatial_reference = arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID)

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

    print("\nStatus domain")
    _ensure_status_domain(gdb_path, paths["spatial"])

    if include_workspace_info:
        print("\nWorkspace info table")
        _ensure_table(gdb_path, schema.WORKSPACE_INFO_TABLE_NAME)
        add_missing_fields(paths["workspace_info"], schema.WORKSPACE_INFO_FIELDS)

    return paths


def add_missing_fields(table_path, field_defs):
    existing = {field.name.upper() for field in arcpy.ListFields(str(table_path))}

    for field in field_defs:
        name = field["name"]

        if name.upper() in existing:
            print(f"  Field already exists: {name}")
            continue

        kwargs = {
            "field_alias": field["alias"],
            "field_is_nullable": "NULLABLE" if field["nullable"] else "NON_NULLABLE",
        }
        if "length" in field:
            kwargs["field_length"] = field["length"]

        arcpy.management.AddField(str(table_path), name, field["type"], **kwargs)
        print(f"  Added field: {name}")


def copy_records(source_path, target_path, where_clause=None):
    """Append records from source to target. Returns the number copied."""
    kwargs = {"schema_type": "TEST"}
    if where_clause:
        kwargs["expression"] = where_clause

    before = int(arcpy.management.GetCount(str(target_path))[0])
    arcpy.management.Append(str(source_path), str(target_path), **kwargs)
    after = int(arcpy.management.GetCount(str(target_path))[0])

    return after - before


def _ensure_table(gdb_path, table_name):
    table_path = Path(gdb_path) / table_name

    if arcpy.Exists(str(table_path)):
        print(f"  Already exists: {table_path}")
    else:
        arcpy.management.CreateTable(str(gdb_path), table_name)
        print(f"  Created: {table_path}")


def _ensure_status_domain(gdb_path, spatial_path):
    domains = {domain.name for domain in arcpy.da.ListDomains(str(gdb_path))}

    if schema.SPATIAL_STATUS_DOMAIN in domains:
        print(f"  Domain already exists: {schema.SPATIAL_STATUS_DOMAIN}")
    else:
        arcpy.management.CreateDomain(
            str(gdb_path),
            schema.SPATIAL_STATUS_DOMAIN,
            "ePUPS spatial workflow status",
            "TEXT",
            "CODED",
        )
        for value in schema.SPATIAL_STATUS_VALUES:
            arcpy.management.AddCodedValueToDomain(
                str(gdb_path), schema.SPATIAL_STATUS_DOMAIN, value, value
            )
        print(f"  Created domain: {schema.SPATIAL_STATUS_DOMAIN}")

    for field in arcpy.ListFields(str(spatial_path), "SPATIAL_STATUS"):
        if field.domain == schema.SPATIAL_STATUS_DOMAIN:
            print("  Domain already assigned to SPATIAL_STATUS")
            return

    arcpy.management.AssignDomainToField(
        str(spatial_path), "SPATIAL_STATUS", schema.SPATIAL_STATUS_DOMAIN
    )
    print("  Assigned domain to SPATIAL_STATUS")
