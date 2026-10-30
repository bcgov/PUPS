"""
Attribute rules for ePUPS geodatabases.

Applies the rules in epups/rules.py to a geodatabase. build_production.py and
create_workspace.py call apply_all(), so production and every new workspace
carry the same rules. Rules that already exist have their Arcade updated to
the current file, so reruns are safe and bring fixes to existing databases.
"""

from pathlib import Path

import arcpy

from epups import builder, rules

ARCADE_FOLDER = Path(__file__).resolve().parent.parent / "arcade"

# Values for the {{NAME}} placeholders in the Arcade files.
# SPATIAL_ID_FLOOR: new SPATIAL_IDs start above this. Production uses 0;
# a workspace passes production's highest SPATIAL_ID.
# VERSION_ID_FLOOR: versions above this were made in the workspace, and new
# polygons go to the newest of them. A workspace passes production's highest
# VERSION_ID.
DEFAULT_VALUES = {"SPATIAL_ID_FLOOR": 0, "VERSION_ID_FLOOR": 0}


def workspace_values(production_path):
    """Placeholder values for a workspace made from production_path."""
    # Imported here: workspace imports this module.
    from epups import workspace

    return {
        "SPATIAL_ID_FLOOR": workspace.highest_spatial_id(production_path),
        "VERSION_ID_FLOOR": workspace.highest_version_id(production_path),
    }


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


def rule_script(rule, values):
    script_expression = (ARCADE_FOLDER / rule["file"]).read_text(encoding="utf-8")
    for name, value in {**values, **rule.get("values", {})}.items():
        script_expression = script_expression.replace("{{" + name + "}}", str(value))
    return script_expression


def apply_rule(table_path, rule, values):
    script_expression = rule_script(rule, values)

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


def _is_duplicate(error):
    """ArcGIS reports an existing rule as ERROR 002541, "Duplicate attribute rule name"."""
    message = str(error).lower()
    return "002541" in message or "duplicate attribute rule" in message or "already" in message


def apply_all(gdb_path, values=None):
    """
    Apply every rule to gdb_path. Returns the number of rules that failed.

    values: overrides for DEFAULT_VALUES, such as {"SPATIAL_ID_FLOOR": 4}.
    """
    paths = builder.object_paths(gdb_path)
    values = {**DEFAULT_VALUES, **(values or {})}

    print("\nAttribute rules")
    ensure_global_ids(paths)

    is_workspace = arcpy.Exists(str(paths["workspace_info"]))

    failed = 0
    for rule in rules.RULES:
        if rule.get("workspace_only") and not is_workspace:
            continue
        table_path = paths[rule["table"]]
        label = f"{rule['name']} on {table_path.name}"

        try:
            apply_rule(table_path, rule, values)
            print(f"  Added rule: {label}")
        except arcpy.ExecuteError as error:
            if not _is_duplicate(error):
                failed += 1
                print(f"  FAILED: {label}\n    {error}")
                continue
            # Already there: bring its Arcade and message up to date, so fixes
            # reach existing databases.
            alter = {"script_expression": rule_script(rule, values)}
            if rule.get("message"):
                alter["error_message"] = rule["message"]
            try:
                arcpy.management.AlterAttributeRule(str(table_path), rule["name"], **alter)
                print(f"  Updated existing rule: {label}")
            except arcpy.ExecuteError as alter_error:
                failed += 1
                print(f"  FAILED to update: {label}\n    {alter_error}")

    return failed
