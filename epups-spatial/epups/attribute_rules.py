"""
Attribute rules for ePUPS geodatabases.

Applies the rules in epups/rules.py to a geodatabase. build_production.py and
create_workspace.py call apply_all(), so production and every new workspace
carry the same rules. Rules that already exist are skipped, so reruns are safe.
"""

from pathlib import Path

import arcpy

from epups import builder, rules

ARCADE_FOLDER = Path(__file__).resolve().parent.parent / "arcade"


def ensure_global_ids(paths):
    """Attribute rules need a GlobalID field on each table they apply to."""
    needs_global_id = [
        str(paths[key]) for key in ("spatial", "version", "users")
        if "GlobalID" not in {field.name for field in arcpy.ListFields(str(paths[key]))}
    ]

    if not needs_global_id:
        print("  GlobalID already present on all tables.")
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


def apply_all(gdb_path):
    """Apply every rule to gdb_path. Returns the number of rules that failed."""
    paths = builder.object_paths(gdb_path)

    print("\nAttribute rules")
    ensure_global_ids(paths)

    failed = 0
    for rule in rules.RULES:
        table_path = paths[rule["table"]]
        label = f"{rule['name']} on {table_path.name}"

        try:
            apply_rule(table_path, rule)
            print(f"  Added rule: {label}")
        except arcpy.ExecuteError as error:
            if "already" in str(error).lower():
                print(f"  Already present: {label}")
            else:
                failed += 1
                print(f"  FAILED: {label}\n    {error}")

    return failed
