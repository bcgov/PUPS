"""
Central schema definitions for the ePUPS spatial database.

Plain data only: no ArcPy import, so the field lists can be reviewed
without ArcGIS. epups/builder.py applies these definitions to both
production and editor workspaces.

Managed by ArcGIS and not listed here:
- OBJECTID (auto-generated, reassigned when records are copied or appended)
- Shape / SHAPE geometry field (created with the feature class)
"""

# Bump when fields or domains change, so QA can detect stale workspaces.
SCHEMA_VERSION = "0.1"

SPATIAL_REFERENCE_WKID = 3005  # NAD 1983 BC Environment Albers

FEATURE_DATASET_NAME = "SpatialData"
SPATIAL_FC_NAME = "ePup_Spatial"
VERSION_TABLE_NAME = "ePup_Spatial_Version"
WORKSPACE_INFO_TABLE_NAME = "Workspace_Info"  # workspaces only

SPATIAL_STATUS_DOMAIN = "ePup_Spatial_Status"
SPATIAL_STATUS_VALUES = ("DRAFT", "APPROVED", "PUBLISHED", "EXPIRED")

# Each field: name, ArcGIS type, length (TEXT only), nullable, alias, notes.
# Proposed fields for review. Notes flag anything still unconfirmed.

VERSION_TABLE_FIELDS = [
    {
        "name": "VERSION_ID",
        "type": "LONG",
        "nullable": False,
        "alias": "Version ID",
        "notes": "Unique per version. Generation method still open.",
    },
    {
        "name": "AUTHORIZATIONID",
        "type": "LONG",
        "nullable": False,
        "alias": "Authorization ID",
        "notes": "References corral.pu_authorization.AUTHORIZATIONID. Confirm source type.",
    },
    {
        "name": "IS_CURRENT",
        "type": "SHORT",
        "nullable": False,
        "alias": "Is current",
        "notes": "1 = current version, 0 = superseded. Proposed, not in the PDF.",
    },
    {
        "name": "CREATED_DATE",
        "type": "DATE",
        "nullable": False,
        "alias": "Created date",
        "notes": "Proposed, not in the PDF.",
    },
    {
        "name": "CREATED_BY",
        "type": "LONG",
        "nullable": False,
        "alias": "Created by",
        "notes": "References users.UserID. Source of user IDs still open.",
    },
]

SPATIAL_FIELDS = [
    {
        "name": "SPATIAL_ID",
        "type": "LONG",
        "nullable": False,
        "alias": "Spatial ID",
        "notes": (
            "Stable polygon ID that survives copying between production and "
            "workspaces (OBJECTID does not). Generation method still open."
        ),
    },
    {
        "name": "AUTHORIZATIONID",
        "type": "LONG",
        "nullable": False,
        "alias": "Authorization ID",
        "notes": "References corral.pu_authorization.AUTHORIZATIONID (one to many).",
    },
    {
        "name": "VERSION_ID",
        "type": "LONG",
        "nullable": False,
        "alias": "Version ID",
        "notes": "References ePup_Spatial_Version.VERSION_ID.",
    },
    {
        "name": "SPATIAL_STATUS",
        "type": "TEXT",
        "length": 16,
        "nullable": False,
        "alias": "Spatial status",
        "domain": SPATIAL_STATUS_DOMAIN,
        "notes": "Coded domain: DRAFT, APPROVED, PUBLISHED, EXPIRED.",
    },
    {
        "name": "CREATED_DATE",
        "type": "DATE",
        "nullable": False,
        "alias": "Created date",
        "notes": "",
    },
    {
        "name": "CREATED_BY",
        "type": "LONG",
        "nullable": False,
        "alias": "Created by",
        "notes": "References users.UserID.",
    },
    {
        "name": "LAST_EDITED_DATE",
        "type": "DATE",
        "nullable": False,
        "alias": "Last edited date",
        "notes": "",
    },
    {
        "name": "LAST_EDITED_BY",
        "type": "LONG",
        "nullable": False,
        "alias": "Last edited by",
        "notes": "References users.UserID.",
    },
    {
        "name": "REVIEWED_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "Reviewed date",
        "notes": "Empty if not reviewed.",
    },
    {
        "name": "REVIEWED_BY",
        "type": "LONG",
        "nullable": True,
        "alias": "Reviewed by",
        "notes": "References users.UserID. Empty if not reviewed.",
    },
    {
        "name": "SPATIAL_EFFECTIVE_DATE",
        "type": "DATE",
        "nullable": True,
        "alias": "Spatial effective date",
        "notes": "Required or not is still a pending workflow decision.",
    },
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
        "notes": "OS login name. Not users.UserID, whose source is still open.",
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
        "notes": "Where clause used for copying. Empty if none copied or all copied.",
    },
]
