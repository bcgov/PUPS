"""
Finish a permit, or save it as a draft, after saving your edits in ArcGIS Pro.

Every authorization with polygons added, changed or deleted gets its new
version (VERSION_NUMBER one higher), and all its polygons move onto it.
With --permit, that permit's version is then SUBMITTED for review (--submit)
or kept as a DRAFT to come back to (the default). Running it again is safe:
later edits join the same version. See epups/versioning.py.

Examples (run with ArcGIS Pro's Python on the VDI):
    finish_edits.py "<workspace.gdb>" --editor 7 --permit 6812345            # save as draft
    finish_edits.py "<workspace.gdb>" --editor 7 --permit 6812345 --submit   # finish
    finish_edits.py "<workspace.gdb>" --editor 7                             # versions only
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arcpy  # noqa: E402

from epups import versioning  # noqa: E402

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402


def date_arg(text):
    return datetime.strptime(text, "%Y-%m-%d")


def parse_args():
    parser = argparse.ArgumentParser(description="Finish a permit or save it as a draft.")
    parser.add_argument("workspace", help="Workspace geodatabase path.")
    parser.add_argument("--editor", type=int, required=True,
                        help="Your user ID (users.UserID), recorded as LAST_EDITED_BY.")
    parser.add_argument("--permit", type=int, help="AUTHORIZATIONID to finish or save as a draft.")
    parser.add_argument("--submit", action="store_true", help="Finish and submit for review.")
    parser.add_argument("--effective-date", type=date_arg,
                        help="Spatial effective date for the permit's version, YYYY-MM-DD.")
    parser.add_argument("--reason", help="Change reason for versions made now.")
    return parser.parse_args()


def print_results(results):
    if not results:
        print("No edits found. Save your edits in ArcGIS Pro first (Edit tab, Save).")
        return
    for result in results:
        version = result.version
        state = "New version" if result.created else "Version"
        print(f"\nAuthorization {version.authorization_id}: {state} {version.number} "
              f"(VERSION_ID {version.version_id})")
        for edit in result.edits:
            print(f"  {edit}")
        print(f"  Polygons moved onto it: {result.moved}")


def main():
    args = parse_args()

    print("=" * 60)
    print("ePUPS Spatial - Finish or Save Draft")
    print("=" * 60)

    if not arcpy.Exists(args.workspace):
        print(f"Workspace not found: {args.workspace}")
        sys.exit(2)

    if args.permit is None:
        if args.submit:
            print("Give --permit with --submit.")
            sys.exit(2)
        print_results(versioning.finish_edits(args.workspace, change_reason=args.reason, editor_id=args.editor))
    else:
        try:
            version, results = versioning.close_permit(
                args.workspace, args.permit, args.submit, editor_id=args.editor, change_reason=args.reason,
                effective_date=args.effective_date,
            )
        except ValueError as error:
            print(error)
            sys.exit(2)
        print_results(results)
        print(f"\nAuthorization {version.authorization_id}, version {version.number}: {version.status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
