"""
Check an ePUPS editor workspace before its records go to production.

Writes a report to epups-spatial\\logs. Exits with code 1 if any ERROR is
found, so a failed check stops any follow-on promotion step. With --checker,
also writes the result onto each polygon.

Examples (run with ArcGIS Pro's Python on the VDI):
    qa_validate.py "X:\\...\\epups_workspaces\\ePUPS_Temp_Workspace.gdb"
    qa_validate.py "<workspace.gdb>" --checker 9
    qa_validate.py ws_a.gdb ws_b.gdb
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import config, validation  # noqa: E402

# Imported after arcpy. datetime.now() failed on the VDI with this import above
# arcpy; cause not confirmed, so keep this order.
from datetime import datetime  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="QA/QC check for ePUPS workspaces.")
    parser.add_argument(
        "workspaces",
        nargs="+",
        help="Workspace geodatabase path(s) to check.",
    )
    parser.add_argument(
        "--checker",
        type=int,
        help="Your user ID. Writes the results onto each polygon (QA status, checked by, date, notes).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    timestamp = datetime.now()
    any_failed = False

    print("=" * 60)
    print("ePUPS Spatial - Workspace QA/QC")
    print("=" * 60)

    production = Path(config.PRODUCTION_PATH).resolve()

    for workspace in args.workspaces:
        gdb_path = Path(workspace)
        print(f"\nChecking: {gdb_path}")

        if not arcpy.Exists(str(gdb_path)):
            print("  Not found. Skipped.")
            any_failed = True
            continue

        if gdb_path.resolve() == production:
            print("  This is the production database. Refusing to QA it as a workspace.")
            any_failed = True
            continue

        issues = validation.run_all(gdb_path, config.PRODUCTION_PATH)
        report_path, result, errors, warnings = validation.write_report(gdb_path, issues, timestamp)

        for issue in issues:
            print(f"  {issue.severity:<8} {issue.check:<18} {issue.record}: {issue.message}")

        if args.checker is not None:
            written, failed = validation.write_results(gdb_path, issues, args.checker)
            print(f"  Results written to {written} polygons"
                  + (f"; {failed} could not be updated" if failed else ""))

        print(f"  Result: {result} ({errors} errors, {warnings} warnings)")
        print(f"  Report: {report_path}")

        if errors:
            any_failed = True

    print("=" * 60)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
