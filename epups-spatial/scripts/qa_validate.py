"""
Check an ePUPS editor workspace before its records go to production.

Writes a report to epups-spatial\\logs. Exits with code 1 if any ERROR is
found, so a failed check stops any follow-on promotion step.

Examples (run with ArcGIS Pro's Python on the VDI):
    qa_validate.py "X:\\...\\epups_workspaces\\ws_test_copy_20261021_114557.gdb"
    qa_validate.py ws_a.gdb ws_b.gdb
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import config, schema, validation  # noqa: E402

# Imported after arcpy. datetime.now() failed on the VDI with this import above
# arcpy; cause not confirmed, so keep this order.
from datetime import datetime  # noqa: E402

LOG_FOLDER = PROJECT_ROOT / "logs"


def parse_args():
    parser = argparse.ArgumentParser(description="QA/QC check for ePUPS workspaces.")
    parser.add_argument(
        "workspaces",
        nargs="+",
        help="Workspace geodatabase path(s) to check.",
    )
    return parser.parse_args()


def write_report(gdb_path, issues, timestamp):
    LOG_FOLDER.mkdir(parents=True, exist_ok=True)
    errors, warnings = validation.count_by_severity(issues)
    result = "PASS" if errors == 0 else "FAIL"

    report_path = LOG_FOLDER / f"qa_{Path(gdb_path).stem}_{timestamp:%Y%m%d_%H%M%S}.txt"

    lines = [
        "ePUPS workspace QA report",
        f"Workspace: {gdb_path}",
        f"Run: {timestamp:%Y-%m-%d %H:%M:%S}",
        f"Schema version: {schema.SCHEMA_VERSION}",
        f"Result: {result} ({errors} errors, {warnings} warnings)",
        "",
    ]

    if issues:
        lines.append(f"{'Severity':<9} {'Check':<18} {'Record':<26} Message")
        lines.append("-" * 90)
        for issue in issues:
            lines.append(
                f"{issue.severity:<9} {issue.check:<18} {issue.record:<26} {issue.message}"
            )
    else:
        lines.append("No issues found.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path, result, errors, warnings


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
        report_path, result, errors, warnings = write_report(gdb_path, issues, timestamp)

        for issue in issues:
            print(f"  {issue.severity:<8} {issue.check:<18} {issue.record}: {issue.message}")

        print(f"  Result: {result} ({errors} errors, {warnings} warnings)")
        print(f"  Report: {report_path}")

        if errors:
            any_failed = True

    print("=" * 60)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
