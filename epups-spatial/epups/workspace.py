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


def workspace_gdb_name(label):
    """Build a unique workspace name such as ws_6812345_20261021_143000.gdb."""
    safe_label = re.sub(r"[^A-Za-z0-9_]", "_", label).strip("_") or "workspace"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"ws_{safe_label}_{timestamp}.gdb"


def authorization_where_clause(authorization_ids):
    ids = ", ".join(str(int(value)) for value in authorization_ids)
    return f"AUTHORIZATIONID IN ({ids})"


def version_id_where_clause(version_ids):
    if not version_ids:
        return "1 = 0"  # no matching versions, so no polygons

    ids = ", ".join(str(int(value)) for value in version_ids)
    return f"VERSION_ID IN ({ids})"


def create_workspace(
    label,
    folder=None,
    copy_all=False,
    authorization_ids=None,
    production_path=None,
    apply_rules=True,
):
    """
    Create a workspace and return its geodatabase path.

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

    gdb_path = builder.create_file_gdb(folder, workspace_gdb_name(label))
    paths = builder.build_schema(gdb_path, include_workspace_info=True)
    if apply_rules:
        attribute_rules.apply_all(gdb_path)

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
    )

    return gdb_path


def _version_ids(version_path, where_clause):
    with arcpy.da.SearchCursor(str(version_path), ["VERSION_ID"], where_clause=where_clause) as cursor:
        return [row[0] for row in cursor]


def _write_workspace_info(table_path, workspace_name, source_path, copy_filter):
    fields = [
        "WORKSPACE_NAME",
        "SCHEMA_VERSION",
        "CREATED_DATE",
        "CREATED_BY_LOGIN",
        "SOURCE_PATH",
        "COPY_FILTER",
    ]
    row = (
        workspace_name,
        schema.SCHEMA_VERSION,
        datetime.now(),
        getpass.getuser(),
        source_path,
        copy_filter,
    )

    with arcpy.da.InsertCursor(str(table_path), fields) as cursor:
        cursor.insertRow(row)
