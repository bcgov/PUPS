"""
Start or resume a permit in a workspace, so new polygons go to it.

"new" starts a new permit: its authorization ID is assigned (one above the
highest in production and the workspace) and it gets version 1; --reason is
optional. An existing authorization gets its next version, which needs
--reason, or resumes the one already made in this workspace (back to DRAFT).
Recorded as created by the editor. Polygons drawn after this are linked to it
and get the source details given here. See epups/versioning.py.

Examples (run with ArcGIS Pro's Python on the VDI):
    start_authorization.py "<workspace.gdb>" new --editor 7
    start_authorization.py "<workspace.gdb>" 6812345 --editor 7 --reason "Trail realigned" --source-type GEOMARK --source-ref GM12345
    start_authorization.py "<workspace.gdb>" 6812345 --editor 7          # resume its draft
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arcpy  # noqa: E402

from epups import schema, versioning  # noqa: E402

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402


def date_arg(text):
    return datetime.strptime(text, "%Y-%m-%d")


def parse_args():
    parser = argparse.ArgumentParser(description="Start editing an authorization in a workspace.")
    parser.add_argument("workspace", help="Workspace geodatabase path.")
    parser.add_argument("authorization", help='AUTHORIZATIONID, or "new" for a new permit.')
    parser.add_argument("--editor", type=int, required=True, help="Your user ID (users.UserID).")
    parser.add_argument("--reason", help="Change reason. Required when editing an existing permit.")
    parser.add_argument("--source-type", default="GIS_DIGITIZED",
                        choices=schema.DOMAINS["ePup_Source_Type"]["values"],
                        help="Source type for new polygons.")
    parser.add_argument("--source-ref", help="Source reference for new polygons.")
    parser.add_argument("--source-date", type=date_arg, help="Source date for new polygons, YYYY-MM-DD.")
    parser.add_argument("--source-note", help="Source note for new polygons.")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("ePUPS Spatial - Start or Resume Permit")
    print("=" * 60)

    if not arcpy.Exists(args.workspace):
        print(f"Workspace not found: {args.workspace}")
        sys.exit(2)

    options = {
        "editor_id": args.editor,
        "source_defaults": {
            "SOURCE_TYPE": args.source_type,
            "SOURCE_REFERENCE": args.source_ref,
            "SOURCE_DATE": args.source_date,
            "SOURCE_NOTE": args.source_note,
        },
    }
    try:
        if args.authorization.lower() == "new":
            version, created = versioning.start_new_permit(args.workspace, args.reason, **options)
        else:
            version, created = versioning.start_authorization(
                args.workspace, int(args.authorization), change_reason=args.reason, **options
            )
    except ValueError as error:
        print(error)
        sys.exit(2)

    state = "Started" if created else "Resumed"
    print(f"{state} authorization {version.authorization_id}: version {version.number} "
          f"(VERSION_ID {version.version_id}, {version.status}), created by {version.created_by}")
    print("New polygons you draw are linked to it. When done, save, then run finish_edits.py.")
    print("=" * 60)


if __name__ == "__main__":
    main()
