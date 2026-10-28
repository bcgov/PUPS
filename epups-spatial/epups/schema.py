"""
Central schema definitions for the ePUPS spatial database.

Plain data only: no ArcPy import, so the field lists can be reviewed
without ArcGIS. epups/builder.py applies these definitions to both
production and editor workspaces.

Source: co-worker's DBML diagram (current design, flexible).

Managed by ArcGIS and not listed here:
- OBJECTID (auto-generated, reassigned when records are copied or appended)
- SHAPE geometry field (created with the feature class)
- Shape_Area / Shape_Length (ArcGIS keeps these; AREA_HA is the stored hectare value)

Not created here: corral.pu_authorization. It lives in CORRAL and is only
referenced by AUTHORIZATIONID.
"""

# Bump when fields, domains, indexes or relationships change, so QA can detect stale workspaces.
SCHEMA_VERSION = "0.3"

SPATIAL_REFERENCE_WKID = 3005  # NAD 1983 BC Environment Albers, metres

FEATURE_DATASET_NAME = "SpatialData"
SPATIAL_FC_NAME = "ePup_Spatial"
VERSION_TABLE_NAME = "ePup_Spatial_Version"
USERS_TABLE_NAME = "users"
WORKSPACE_INFO_TABLE_NAME = "Workspace_Info"  # workspaces only

# One version has many polygons, linked on VERSION_ID. Lets ArcGIS Pro show a
# polygon's version (and so its authorization) when you identify it.
RELATIONSHIP_CLASS_NAME = "ePup_Version_Polygons"
RELATIONSHIP_KEY = "VERSION_ID"

# Coded value domains (picklists). Each field lists its domain by name.
DOMAINS = {
    "ePup_Version_Status": {
        "description": "Workflow status of a permit version",
        "field_type": "TEXT",
        "values": ("DRAFT", "APPROVED", "PUBLISHED", "SUPERSEDED", "EXPIRED"),
    },
    "ePup_Source_Type": {
        "description": "How a polygon was sourced",
        "field_type": "TEXT",
        "values": ("GEOMARK", "GIS_DIGITIZED", "IMPORTED", "MANUAL_CORRECTION", "OTHER"),
    },
    "ePup_Geometry_QA_Status": {
        "description": "Result of geometry QA on a polygon",
        "field_type": "TEXT",
        "values": ("NOT_CHECKED", "PASS", "NEEDS_REVIEW", "FAIL"),
    },
}

# Each field: name, ArcGIS type (LONG, SHORT, TEXT, DATE, DOUBLE), length (TEXT only),
# nullable, alias, domain (optional), default (optional), notes.
# Booleans from the DBML are SHORT 0/1, because file geodatabases have no boolean type.

VERSION_TABLE_FIELDS = [
    {
        "name": "VERSION_ID",
        "type": "LONG",
        "nullable": False,
        "alias": "Version ID",
        "notes": "Primary key. DBML says auto-increment; file GDB has none. Generation open.",
    },
    {
        "name": "AUTHORIZATIONID",
        "type": "LONG",
        "nullable": False,
        "alias": "Authorization ID",
        "notes": "References corral.pu_authorization.AUTHORIZATIONID.",
    },
    {
        "name": "VERSION_NUMBER",
        "type": "LONG",
        "nullable": False,
        "alias": "Version number",
        "notes": "Unique per authorization (see VERSION_INDEXES).",
    },
    {
        "name": "VERSION_STATUS",
        "type": "TEXT",
        "length": 16,
        "nullable": False,
        "alias": "Version status",
        "domain": "ePup_Version_Status",
        "default": "DRAFT",
        "notes": "Includes SUPERSEDED.",
    },
    {
        "name": "IS_CURRENT",
        "type": "SHORT",
        "nullable": False,
        "alias": "Is current",
        "default": 0,
        "notes": "Boolean as 0/1.",
    },
    {
        "name": "CHANGE_REASON",
        "type": "TEXT",
        "length": 500,
        "nullable": True,
        "alias": "Change reason",
        "notes": "",
    },
    {
        "name": "SPATIAL_EFFECTIVE_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "Spatial effective date",
        "notes": "",
    },
    {
        "name": "CREATED_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "Created date",
        "notes": "",
    },
    {
        "name": "CREATED_BY",
        "type": "LONG",
        "nullable": True,
        "alias": "Created by",
        "notes": "References users.UserID.",
    },
    {
        "name": "LAST_EDITED_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "Last edited date",
        "notes": "",
    },
    {
        "name": "LAST_EDITED_BY",
        "type": "LONG",
        "nullable": True,
        "alias": "Last edited by",
        "notes": "References users.UserID.",
    },
    {
        "name": "REVIEWED_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "Reviewed date",
        "notes": "",
    },
    {
        "name": "REVIEWED_BY",
        "type": "LONG",
        "nullable": True,
        "alias": "Reviewed by",
        "notes": "References users.UserID.",
    },
    {
        "name": "SYNC_CONFLICT",
        "type": "SHORT",
        "nullable": False,
        "alias": "Sync conflict",
        "default": 0,
        "notes": "Boolean as 0/1.",
    },
    {
        "name": "CONFLICT_NOTE",
        "type": "TEXT",
        "length": 500,
        "nullable": True,
        "alias": "Conflict note",
        "notes": "",
    },
    {
        "name": "CONFLICT_RESOLVED_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "Conflict resolved date",
        "notes": "",
    },
    {
        "name": "CONFLICT_RESOLVED_BY",
        "type": "LONG",
        "nullable": True,
        "alias": "Conflict resolved by",
        "notes": "References users.UserID.",
    },
]

VERSION_INDEXES = [
    {"name": "IX_Version_Authorization", "fields": ["AUTHORIZATIONID"], "unique": False},
    {"name": "IX_Version_AuthNumber", "fields": ["AUTHORIZATIONID", "VERSION_NUMBER"], "unique": True},
]

SPATIAL_FIELDS = [
    {
        "name": "SPATIAL_ID",
        "type": "LONG",
        "nullable": False,
        "alias": "Spatial ID",
        "notes": "Stable polygon ID that survives copying between production and workspaces. Unique.",
    },
    {
        "name": "VERSION_ID",
        "type": "LONG",
        "nullable": False,
        "alias": "Version ID",
        "notes": "References ePup_Spatial_Version.VERSION_ID. Authorization is reached through it.",
    },
    {
        "name": "SOURCE_TYPE",
        "type": "TEXT",
        "length": 20,
        "nullable": False,
        "alias": "Source type",
        "domain": "ePup_Source_Type",
        "default": "GIS_DIGITIZED",
        "notes": "",
    },
    {
        "name": "SOURCE_REFERENCE",
        "type": "TEXT",
        "length": 255,
        "nullable": True,
        "alias": "Source reference",
        "notes": "Indexed.",
    },
    {
        "name": "SOURCE_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "Source date",
        "notes": "",
    },
    {
        "name": "SOURCE_NOTE",
        "type": "TEXT",
        "length": 500,
        "nullable": True,
        "alias": "Source note",
        "notes": "",
    },
    {
        "name": "GEOMETRY_QA_STATUS",
        "type": "TEXT",
        "length": 16,
        "nullable": False,
        "alias": "Geometry QA status",
        "domain": "ePup_Geometry_QA_Status",
        "default": "NOT_CHECKED",
        "notes": "The QA tool could write this back.",
    },
    {
        "name": "QA_CHECKED_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "QA checked date",
        "notes": "",
    },
    {
        "name": "QA_CHECKED_BY",
        "type": "LONG",
        "nullable": True,
        "alias": "QA checked by",
        "notes": "References users.UserID.",
    },
    {
        "name": "QA_NOTE",
        "type": "TEXT",
        "length": 500,
        "nullable": True,
        "alias": "QA note",
        "notes": "",
    },
    {
        "name": "OUT_OF_BOUNDARY_FLAG",
        "type": "SHORT",
        "nullable": False,
        "alias": "Out of boundary",
        "default": 0,
        "notes": "Boolean as 0/1.",
    },
    {
        "name": "BOUNDARY_REVIEW_NOTE",
        "type": "TEXT",
        "length": 500,
        "nullable": True,
        "alias": "Boundary review note",
        "notes": "",
    },
    {
        "name": "AREA_HA",
        "type": "DOUBLE",
        "nullable": True,
        "alias": "Area (ha)",
        "notes": (
            "Hectares, from SHAPE (EPSG:3005 metres / 10000). Set by the tool, "
            "checked by QA. Empty until calculated."
        ),
    },
]

SPATIAL_INDEXES = [
    {"name": "IX_Spatial_ID", "fields": ["SPATIAL_ID"], "unique": True},
    {"name": "IX_Spatial_Version", "fields": ["VERSION_ID"], "unique": False},
    {"name": "IX_Spatial_SourceRef", "fields": ["SOURCE_REFERENCE"], "unique": False},
]

USERS_FIELDS = [
    {
        "name": "UserID",
        "type": "LONG",
        "nullable": False,
        "alias": "User ID",
        "notes": "Primary key. Source of user IDs still open.",
    },
    {
        "name": "UserFirstName",
        "type": "TEXT",
        "length": 100,
        "nullable": True,
        "alias": "First name",
        "notes": "",
    },
    {
        "name": "UserLastName",
        "type": "TEXT",
        "length": 100,
        "nullable": True,
        "alias": "Last name",
        "notes": "",
    },
    {
        "name": "UserInitials",
        "type": "TEXT",
        "length": 10,
        "nullable": True,
        "alias": "Initials",
        "notes": "",
    },
]

USERS_INDEXES = [
    {"name": "IX_Users_UserID", "fields": ["UserID"], "unique": True},
]

# One row per workspace, written when the workspace is created.
# Lets QA see where a workspace came from without asking the editor.
WORKSPACE_INFO_FIELDS = [
    {
        "name": "WORKSPACE_NAME",
        "type": "TEXT",
        "length": 100,
        "nullable": False,
        "alias": "Workspace name",
        "notes": "",
    },
    {
        "name": "SCHEMA_VERSION",
        "type": "TEXT",
        "length": 20,
        "nullable": False,
        "alias": "Schema version",
        "notes": "SCHEMA_VERSION at creation time.",
    },
    {
        "name": "CREATED_DATE",
        "type": "DATE",
        "nullable": False,
        "alias": "Created date",
        "notes": "",
    },
    {
        "name": "CREATED_BY_LOGIN",
        "type": "TEXT",
        "length": 50,
        "nullable": False,
        "alias": "Created by (login)",
        "notes": "OS login name. Not users.UserID.",
    },
    {
        "name": "SOURCE_PATH",
        "type": "TEXT",
        "length": 500,
        "nullable": True,
        "alias": "Copied from",
        "notes": "Production path records were copied from. Empty if none copied.",
    },
    {
        "name": "COPY_FILTER",
        "type": "TEXT",
        "length": 500,
        "nullable": True,
        "alias": "Copy filter",
        "notes": "Where clause used on the version table. Empty if none copied or all copied.",
    },
]
