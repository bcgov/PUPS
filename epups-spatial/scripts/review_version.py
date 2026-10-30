"""
Reviewer sign-off on a permit version made in a workspace.

Approve it (QA runs first, and approval is refused if the version's polygons
have errors), or return it to the editor with a note. Records the reviewer's
user ID and the date. Without a VERSION_ID, lists the versions to review.
See epups/review.py.

Examples (run with ArcGIS Pro's Python on the VDI):
    review_version.py "<workspace.gdb>"                                   # list
    review_version.py "<workspace.gdb>" 4 --reviewer 9 --approve
    review_version.py "<workspace.gdb>" 4 --reviewer 9 --return "Polygon 6 overlaps the lake"
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arcpy  # noqa: E402

from epups import review  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Approve or return a permit version.")
    parser.add_argument("workspace", help="Workspace geodatabase path.")
    parser.add_argument("version", nargs="?", type=int, help="VERSION_ID to review. Omit to list.")
    parser.add_argument("--reviewer", type=int, help="Your user ID (users.UserID).")
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--approve", action="store_true", help="Approve the version.")
    decision.add_argument("--return", dest="return_note", metavar="NOTE",
                          help="Return the version to the editor, with what to fix.")
    parser.add_argument("--note", help="Note to record with an approval.")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("ePUPS Spatial - Review Permit Version")
    print("=" * 60)

    if not arcpy.Exists(args.workspace):
        print(f"Workspace not found: {args.workspace}")
        sys.exit(2)

    if args.version is None:
        versions = review.reviewable_versions(args.workspace)
        print("Versions to review:" if versions else "No versions to review. Run finish_edits.py first.")
        for v in versions:
            print(f"  VERSION_ID {v.version_id}: authorization {v.authorization_id}, version {v.number}, "
                  f"{v.status}, created by {v.created_by}")
        return

    if args.reviewer is None or not (args.approve or args.return_note):
        print("Give --reviewer, and --approve or --return \"note\".")
        sys.exit(2)

    approve = args.approve
    result = review.review_version(
        args.workspace, args.version, args.reviewer, approve,
        note=args.note if approve else args.return_note,
    )
    version = result.version
    label = f"authorization {version.authorization_id}, version {version.number} (VERSION_ID {version.version_id})"
    if result.same_person:
        print(f"Warning: reviewer {args.reviewer} also created this version.")
    if approve and not result.approved:
        print(f"Not approved: {len(result.blocking)} errors on {label}:")
        for issue in result.blocking:
            print(f"  {issue.severity:<8} {issue.check:<14} {issue.record}: {issue.message}")
        sys.exit(1)
    print(f"{'Approved' if approve else 'Returned to the editor'}: {label}, {result.polygons} polygons.")
    print("=" * 60)


if __name__ == "__main__":
    main()
