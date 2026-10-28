"""
Delete the DEV production database and the editor test workspaces, so the
demo data can be rebuilt from scratch.

Test data only. Refuses to run unless production is the dev stand-in (its
name contains "_dev"), and only deletes ws_*.gdb folders in the workspace
folder. Close ArcGIS Pro first, or the geodatabases will be locked.

Run on the VDI from X:\\epups-spatial:
    propy.bat tests\\reset_dev_data.py          (lists what would be deleted)
    propy.bat tests\\reset_dev_data.py --yes    (deletes it)

Then rebuild: build_production.py, fetch_reference_data.py,
tests\\seed_production.py, build_topology.py.
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import config  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Delete dev production and test workspaces.")
    parser.add_argument("--yes", action="store_true", help="Delete. Without it, only list.")
    return parser.parse_args()


def main():
    args = parse_args()

    if "_dev" not in config.PRODUCTION_GDB_NAME:
        print(f"Refusing: production is not the dev stand-in: {config.PRODUCTION_PATH}")
        sys.exit(2)

    targets = []
    if arcpy.Exists(str(config.PRODUCTION_PATH)):
        targets.append(config.PRODUCTION_PATH)
    targets += sorted(config.WORKSPACE_ROOT.glob("ws_*.gdb"))

    print("=" * 60)
    print("Reset dev data")
    print("=" * 60)
    if not targets:
        print("Nothing to delete.")
        return

    for path in targets:
        print(f"  {path}")

    if not args.yes:
        print("\nNothing deleted. Rerun with --yes to delete these.")
        return

    print()
    for path in targets:
        arcpy.management.Delete(str(path))
        print(f"Deleted: {path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
