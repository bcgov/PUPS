"""
Create editor workspaces.

A workspace is a new file geodatabase with the same schema as production.
It can start empty, or with copies of production records (all of them,
or only those for selected authorizations). SPATIAL_ID is copied with
each record, so QA and promotion can match it back to production.
"""

import getpass
import re
from datetime import datetime
from pathlib import Path

import arcpy

from epups import builder, config, schema


def workspace_gdb_name(label):
    """Build a unique workspace name such as ws_6812345_20261021_143000.gdb."""
    safe_label = re.sub(r"[^A-Za-z0-9_]", "_", label).strip("_") or "workspace"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"ws_{safe_label}_{timestamp}.gdb"


def authorization_where_clause(authorization_ids):
    ids = ", ".join(str(int(value)) for value in authorization_ids)
    return f"AUTHORIZATIONID IN ({ids})"


def create_workspace(
    label,
    folder=None,
    copy_all=False,
    authorization_ids=None,
    production_path=None,
):
    """
    Create a workspace and return its geodatabase path.

    copy_all: copy every production record.
    authorization_ids: copy only records for these authorizations.
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

    where_clause = None
    if authorization_ids:
        where_clause = authorization_where_clause(authorization_ids)

    if copying:
        production = builder.object_paths(production_path)

        print("\nCopying from production")
        print(f"  Source: {production_path}")
        print(f"  Filter: {where_clause or 'all records'}")

        spatial_count = builder.copy_records(
            production["spatial"], paths["spatial"], where_clause
        )
        version_count = builder.copy_records(
            production["version"], paths["version"], where_clause
        )

        print(f"  Polygons copied: {spatial_count}")
        print(f"  Version rows copied: {version_count}")

    _write_workspace_info(
        paths["workspace_info"],
        gdb_path.name,
        source_path=str(production_path) if copying else None,
        copy_filter=where_clause,
    )

    return gdb_path


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
