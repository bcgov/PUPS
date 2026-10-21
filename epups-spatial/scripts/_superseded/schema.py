"""
Central schema definitions for the ePUPS spatial database.

Plain data only: no ArcPy import, so the field lists can be reviewed
without ArcGIS. scripts/create_spatial_tables.py applies these definitions.

Managed by ArcGIS and not listed here:
- OBJECTID (auto-generated)
- Shape / SHAPE geometry field (created with the feature class)

Keep database creation logic in scripts/create_spatial_tables.py.
"""

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
        "notes": "PROVISIONAL. Purpose not yet confirmed.",
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
