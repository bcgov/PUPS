"""
Create editor workspaces.

A workspace is a new file geodatabase with the same schema as production.
It can start empty, or with copies of production records (all of them,
or only those for selected authorizations).

Authorization is held on the version table. To copy by authorization, the
version rows are copied first, then only the polygons whose VERSION_ID
belongs to those versions. SPATIAL_ID is copied with each polygon, so QA
and promotion can match it back to production.
"""

import getpass
import re
from datetime import datetime
from pathlib import Path

import arcpy

from epups import attribute_rules, builder, config, schema


DEFAULT_NAME = "ePUPS_Temp_Workspace"


def workspace_gdb_name(folder, name=None):
    """
    Pick a free workspace name in folder: ePUPS_Temp_Workspace.gdb, then
    ePUPS_Temp_Workspace_1.gdb, _2 and so on. A name counts as taken if its
    .gdb or its ArcGIS Pro project (.aprx) exists, so the two stay paired.
    """
    base = re.sub(r"[^A-Za-z0-9_]", "_", name or DEFAULT_NAME).strip("_") or DEFAULT_NAME
    candidate, number = base, 0
    while (folder / f"{candidate}.gdb").exists() or (folder / f"{candidate}.aprx").exists():
        number += 1
        candidate = f"{base}_{number}"
    return f"{candidate}.gdb"


def authorization_where_clause(authorization_ids):
    ids = ", ".join(str(int(value)) for value in authorization_ids)
    return f"AUTHORIZATIONID IN ({ids})"


def version_id_where_clause(version_ids):
    if not version_ids:
        return "1 = 0"  # no matching versions, so no polygons

    ids = ", ".join(str(int(value)) for value in version_ids)
    return f"VERSION_ID IN ({ids})"


def create_workspace(
    name=None,
    folder=None,
    copy_all=False,
    authorization_ids=None,
    production_path=None,
    apply_rules=True,
    editor_id=None,
):
    """
    Create a workspace and return its geodatabase path.

    name: workspace name. Default: ePUPS_Temp_Workspace. A number is added
    if the name is already used in the folder.
    editor_id: users.UserID of the editor, stored in Workspace_Info as the
    default for the toolbox tools.
    apply_rules: add the attribute rules. Only test code that needs to write
    bad records passes False; editors always get the rules.
    copy_all: copy every production record.
    authorization_ids: copy only versions and polygons for these authorizations.
    Neither: the workspace starts empty.
    """
    if copy_all and authorization_ids:
        raise ValueError("Use copy_all or authorization_ids, not both.")

    folder = Path(folder) if folder else config.WORKSPACE_ROOT
    production_path = Path(production_path) if production_path else config.PRODUCTION_PATH
    copying = copy_all or bool(authorization_ids)

    if copying and not arcpy.Exists(str(production_path)):
        raise FileNotFoundError(f"Production database not found: {production_path}")

    gdb_path = builder.create_file_gdb(folder, workspace_gdb_name(folder, name))
    paths = builder.build_schema(gdb_path, include_workspace_info=True)
    if apply_rules:
        # New IDs start above production's, even for records not copied.
        values = attribute_rules.workspace_values(production_path)
        print(f"\nNew SPATIAL_IDs will start above {values['SPATIAL_ID_FLOOR']} "
              f"and new VERSION_IDs above {values['VERSION_ID_FLOOR']} (highest in production)")
        attribute_rules.apply_all(gdb_path, values)

    version_filter = None
    if authorization_ids:
        version_filter = authorization_where_clause(authorization_ids)

    if copying:
        production = builder.object_paths(production_path)

        print("\nCopying from production")
        print(f"  Source: {production_path}")
        print(f"  Filter: {version_filter or 'all records'}")

        version_count = builder.copy_records(
            production["version"], paths["version"], version_filter
        )
        print(f"  Version rows copied: {version_count}")

        spatial_filter = None
        if authorization_ids:
            version_ids = _version_ids(production["version"], version_filter)
            spatial_filter = version_id_where_clause(version_ids)

        spatial_count = builder.copy_records(
            production["spatial"], paths["spatial"], spatial_filter
        )
        print(f"  Polygons copied: {spatial_count}")

    _write_workspace_info(
        paths["workspace_info"],
        gdb_path.name,
        source_path=str(production_path) if copying else None,
        copy_filter=version_filter,
        editor_id=editor_id,
    )

    return gdb_path


def is_workspace(gdb_path):
    return arcpy.Exists(str(builder.object_paths(gdb_path)["workspace_info"]))


def read_info(gdb_path):
    """The workspace's Workspace_Info row as a dict, or {} if it has none."""
    table = builder.object_paths(gdb_path)["workspace_info"]
    if not arcpy.Exists(str(table)):
        return {}
    fields = [field.name for field in arcpy.ListFields(str(table)) if field.type not in ("OID", "GlobalID")]
    with arcpy.da.SearchCursor(str(table), fields) as cursor:
        row = next(cursor, None)
    return dict(zip(fields, row)) if row else {}


def update_info(gdb_path, **values):
    """
    Set fields on the workspace's Workspace_Info row, for example
    update_info(gdb, EDITOR_ID=7). Raises ValueError for a workspace made with
    an older schema that lacks the fields.
    """
    table = builder.object_paths(gdb_path)["workspace_info"]
    if not arcpy.Exists(str(table)):
        raise ValueError(f"Not an ePUPS workspace (no {schema.WORKSPACE_INFO_TABLE_NAME}): {gdb_path}")

    existing = {field.name.upper() for field in arcpy.ListFields(str(table))}
    missing = [name for name in values if name.upper() not in existing]
    if missing:
        raise ValueError(
            f"This workspace was made with an older version of the tools (no {', '.join(missing)}). "
            "Create a new workspace."
        )

    fields = list(values)
    with arcpy.da.UpdateCursor(str(table), fields) as cursor:
        for row in cursor:
            cursor.updateRow([values[name] for name in fields])
            return



def highest_spatial_id(production_path):
    """Highest SPATIAL_ID in production, or 0 if production or its polygons are missing."""
    spatial = builder.object_paths(production_path)["spatial"]
    if not arcpy.Exists(str(spatial)):
        return 0
    with arcpy.da.SearchCursor(str(spatial), ["SPATIAL_ID"]) as cursor:
        return max((row[0] for row in cursor if row[0] is not None), default=0)


def highest_version_id(production_path):
    """Highest VERSION_ID in production, or 0 if production or its versions are missing."""
    version = builder.object_paths(production_path)["version"]
    if not arcpy.Exists(str(version)):
        return 0
    with arcpy.da.SearchCursor(str(version), ["VERSION_ID"]) as cursor:
        return max((row[0] for row in cursor if row[0] is not None), default=0)


def _version_ids(version_path, where_clause):
    with arcpy.da.SearchCursor(str(version_path), ["VERSION_ID"], where_clause=where_clause) as cursor:
        return [row[0] for row in cursor]


def _write_workspace_info(table_path, workspace_name, source_path, copy_filter, editor_id=None):
    fields = [
        "WORKSPACE_NAME",
        "SCHEMA_VERSION",
        "CREATED_DATE",
        "CREATED_BY_LOGIN",
        "SOURCE_PATH",
        "COPY_FILTER",
        "EDITOR_ID",
    ]
    row = (
        workspace_name,
        schema.SCHEMA_VERSION,
        datetime.now(),
        getpass.getuser(),
        source_path,
        copy_filter,
        editor_id,
    )

    with arcpy.da.InsertCursor(str(table_path), fields) as cursor:
        cursor.insertRow(row)
