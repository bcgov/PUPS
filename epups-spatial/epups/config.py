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

# Blank ArcGIS Pro project copied for each workspace's project, saved in Pro
# zoomed to BC (see docs/WORKSPACE_SETUP.md). Without it, the blank project
# that ships with ArcGIS Pro is used, and it opens over Australia.
PROJECT_TEMPLATE = PROJECT_DATA_ROOT / "templates" / "epups_workspace_template.aprx"

# The ePUPS toolbox on the share. Projects point here, so they work for anyone
# with access, whatever drive letters they have mapped.
SHARED_TOOLBOX = PROJECT_DATA_ROOT.parent / "tools" / "PUPS" / "epups-spatial" / "ePUPS.pyt"

# Shared, read-only ArcGIS Pro project with the ePUPS toolbox attached. Editors
# open it to run Create Workspace; it is never a workspace itself. Made by
# scripts/make_starter_project.py.
STARTER_PROJECT = PROJECT_DATA_ROOT / "ePUPS_Start.aprx"

# QA reports and the reference data log (git ignored).
LOG_FOLDER = Path(__file__).resolve().parent.parent / "logs"
