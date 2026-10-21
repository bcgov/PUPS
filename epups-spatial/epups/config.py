"""
Shared paths for the ePUPS spatial tools.

Production is a development file geodatabase on the share until the
production server is chosen. When it is, change PRODUCTION_PATH to its
connection (for example, an .sde connection file).
"""

from pathlib import Path

PROJECT_DATA_ROOT = Path(
    r"\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\source_data"
)

# Stand-in for production until the production server is decided.
PRODUCTION_FOLDER = PROJECT_DATA_ROOT / "epups_spatial_dev"
PRODUCTION_GDB_NAME = "epups_spatial_dev.gdb"
PRODUCTION_PATH = PRODUCTION_FOLDER / PRODUCTION_GDB_NAME

# Default folder for editor workspaces. Can be overridden per run.
WORKSPACE_ROOT = PROJECT_DATA_ROOT / "epups_workspaces"
