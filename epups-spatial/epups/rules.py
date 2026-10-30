"""
Attribute rule definitions for the ePUPS spatial database.

Each rule points at an Arcade file in arcade/. Constraint rules must return
true to allow a change; calculation rules return the value to store.
ArcGIS runs calculation rules before constraint rules, so an ID assigned by
AUTO_SPATIAL_ID or AUTO_VERSION_ID is in place when the constraints check it.

An Arcade file can contain {{NAME}} placeholders, filled from the values
passed to attribute_rules.apply_all() (see attribute_rules.DEFAULT_VALUES)
and from the rule's own "values".

"table" is a key from builder.object_paths(): "spatial", "version", or "users".
"workspace_only": the rule reads Workspace_Info, so it is only added to
workspaces, not production.

Attribute rules are applied with scripts/apply_attribute_rules.py. They run
inside ArcGIS Pro when someone edits, so they do not stop scripts that
write data in a different way (for example Append). Test them with
tests/test_attribute_rules.py.
"""

INSERT_UPDATE = "INSERT;UPDATE"
INSERT = "INSERT"

RULES = [
    {
        "table": "spatial",
        "name": "PK_SPATIAL_ID",
        "type": "CONSTRAINT",
        "file": "pk_spatial_id.arcade",
        "events": INSERT_UPDATE,
        "error_number": 1001,
        "message": "SPATIAL_ID must be unique.",
    },
    {
        "table": "version",
        "name": "PK_VERSION_ID",
        "type": "CONSTRAINT",
        "file": "pk_version_id.arcade",
        "events": INSERT_UPDATE,
        "error_number": 1002,
        "message": "VERSION_ID must be unique.",
    },
    {
        "table": "users",
        "name": "PK_USER_ID",
        "type": "CONSTRAINT",
        "file": "pk_users_id.arcade",
        "events": INSERT_UPDATE,
        "error_number": 1003,
        "message": "UserID must be unique.",
    },
    {
        "table": "version",
        "name": "UNIQUE_VERSION_NUMBER",
        "type": "CONSTRAINT",
        "file": "unique_version_number.arcade",
        "events": INSERT_UPDATE,
        "error_number": 1004,
        "message": "This version number already exists for this authorization.",
    },
    {
        "table": "version",
        "name": "ONE_CURRENT_VERSION",
        "type": "CONSTRAINT",
        "file": "one_current_version.arcade",
        "events": INSERT_UPDATE,
        "error_number": 1005,
        "message": "This authorization already has a current version.",
    },
    {
        "table": "spatial",
        "name": "SPATIAL_ID_GIVEN",
        "type": "CONSTRAINT",
        "file": "spatial_id_given.arcade",
        "events": INSERT_UPDATE,
        "error_number": 1006,
        "message": "SPATIAL_ID must be given (a number above 0).",
    },
    {
        "table": "version",
        "name": "VERSION_ID_GIVEN",
        "type": "CONSTRAINT",
        "file": "version_id_given.arcade",
        "events": INSERT_UPDATE,
        "error_number": 1007,
        "message": "VERSION_ID must be given (a number above 0).",
    },
    {
        "table": "spatial",
        "name": "VERSION_LINK",
        "type": "CONSTRAINT",
        "file": "version_link.arcade",
        "events": INSERT_UPDATE,
        "error_number": 1008,
        "message": (
            "This polygon has no version to belong to. Run the Start or Resume Permit "
            "tool first, or set VERSION_ID to a row in ePup_Spatial_Version."
        ),
    },
    {
        "table": "spatial",
        "name": "AUTO_SPATIAL_ID",
        "type": "CALCULATION",
        "file": "auto_spatial_id.arcade",
        "events": INSERT,
        "field": "SPATIAL_ID",
        "message": None,
    },
    {
        "table": "spatial",
        "name": "AUTO_VERSION_ID",
        "type": "CALCULATION",
        "file": "auto_version_id.arcade",
        "events": INSERT,
        "field": "VERSION_ID",
        "message": None,
        "workspace_only": True,
    },
    {
        "table": "spatial",
        "name": "DEFAULT_SOURCE_TYPE",
        "type": "CALCULATION",
        "file": "source_type_default.arcade",
        "events": INSERT,
        "field": "SOURCE_TYPE",
        "message": None,
        "workspace_only": True,
    },
    *[
        {
            "table": "spatial",
            "name": f"DEFAULT_{field}",
            "type": "CALCULATION",
            "file": "source_default.arcade",
            "events": INSERT,
            "field": field,
            "message": None,
            "workspace_only": True,
            "values": {"FIELD": field},
        }
        for field in ("SOURCE_REFERENCE", "SOURCE_DATE", "SOURCE_NOTE")
    ],
    {
        "table": "spatial",
        "name": "CALC_AREA_HA",
        "type": "CALCULATION",
        "file": "area_ha.arcade",
        "events": INSERT_UPDATE,
        "field": "AREA_HA",
        "message": None,
    },
]
