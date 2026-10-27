"""
Attribute rule definitions for the ePUPS spatial database.

Each rule points at an Arcade file in arcade/. Constraint rules must return
true to allow a change; calculation rules return the value to store.

"table" is a key from builder.object_paths(): "spatial", "version", or "users".

Attribute rules are applied with scripts/apply_attribute_rules.py. They run
inside ArcGIS Pro when someone edits, so they do not stop scripts that
write data in a different way (for example Append). Test them with
tests/test_attribute_rules.py.
"""

INSERT_UPDATE = "INSERT;UPDATE"

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
        "name": "CALC_AREA_HA",
        "type": "CALCULATION",
        "file": "area_ha.arcade",
        "events": INSERT_UPDATE,
        "field": "AREA_HA",
        "message": None,
    },
]
