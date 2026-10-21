"""
Create an ePUPS editor workspace.

A workspace is a new file geodatabase with the production schema, where
an editor drafts polygons to be QA'd and appended to production.

Examples (run with ArcGIS Pro's Python on the VDI):
    create_workspace.py my_edits
    create_workspace.py auth_6812345 --copy-auth 6812345
    create_workspace.py full_copy --copy-all
    create_workspace.py my_edits --folder "D:\\work\\epups"
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epups import config, workspace  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Create an ePUPS editor workspace.")
    parser.add_argument(
        "label",
        help="Short label for the workspace name, such as an authorization ID or task.",
    )
    parser.add_argument(
        "--folder",
        help=f"Output folder. Default: {config.WORKSPACE_ROOT}",
    )

    copy_group = parser.add_mutually_exclusive_group()
    copy_group.add_argument(
        "--copy-all",
        action="store_true",
        help="Copy every production record into the workspace.",
    )
    copy_group.add_argument(
        "--copy-auth",
        nargs="+",
        type=int,
        metavar="AUTHORIZATIONID",
        help="Copy production records for these authorizations only.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("ePUPS Spatial - Create Editor Workspace")
    print("=" * 60)

    gdb_path = workspace.create_workspace(
        args.label,
        folder=args.folder,
        copy_all=args.copy_all,
        authorization_ids=args.copy_auth,
    )

    print(f"\nSUCCESS: Workspace ready: {gdb_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
