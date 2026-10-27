"""
Apply the ePUPS attribute rules to a geodatabase.

Rules are defined in epups/rules.py and written in arcade/. Run once per
geodatabase (production and each workspace that needs them). Rules that
already exist are reported and skipped, so reruns are safe.

Examples (run with ArcGIS Pro's Python on the VDI):
    apply_attribute_rules.py "\\\\...\\epups_spatial_dev.gdb"
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import builder, rules  # noqa: E402

ARCADE_FOLDER = PROJECT_ROOT / "arcade"


def parse_args():
    parser = argparse.ArgumentParser(description="Apply ePUPS attribute rules.")
    parser.add_argument("gdb", help="Geodatabase path to apply the rules to.")
    return parser.parse_args()


def ensure_global_ids(paths):
    """Attribute rules need a GlobalID field on each table they apply to."""
    needs_global_id = [
        str(paths[key]) for key in ("spatial", "version", "users")
        if "GlobalID" not in {field.name for field in arcpy.ListFields(str(paths[key]))}
    ]

    if not needs_global_id:
        print("GlobalID already present on all tables.")
        return

    arcpy.management.AddGlobalIDs(needs_global_id)
    for table in needs_global_id:
        print(f"  Added GlobalID: {Path(table).name}")


def apply_rule(table_path, rule):
    script_path = ARCADE_FOLDER / rule["file"]
    script_expression = script_path.read_text(encoding="utf-8")

    kwargs = {
        "triggering_events": rule["events"],
        "description": rule["name"],
    }
    if rule.get("message"):
        kwargs["error_message"] = rule["message"]
    if rule.get("error_number"):
        kwargs["error_number"] = rule["error_number"]
    if rule.get("field"):
        kwargs["field"] = rule["field"]

    arcpy.management.AddAttributeRule(
        str(table_path), rule["name"], rule["type"], script_expression, **kwargs
    )


def main():
    args = parse_args()
    paths = builder.object_paths(args.gdb)

    print("=" * 60)
    print(f"Applying attribute rules to: {args.gdb}")
    print("=" * 60)

    ensure_global_ids(paths)

    failed = 0
    for rule in rules.RULES:
        table_path = paths[rule["table"]]
        label = f"{rule['name']} on {table_path.name}"

        try:
            apply_rule(table_path, rule)
            print(f"  Added: {label}")
        except arcpy.ExecuteError as error:
            failed += 1
            print(f"  FAILED: {label}\n    {error}")

    print("=" * 60)
    print("Done." if not failed else f"{failed} rule(s) failed. See messages above.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
