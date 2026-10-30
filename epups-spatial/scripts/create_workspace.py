"""
Create an ePUPS editor workspace.

A workspace is a new file geodatabase with the production schema and a copy
of the production records, where an editor drafts polygons to be QA'd and
appended to production. An ArcGIS Pro project for it, with the ePUPS
toolbox, is saved alongside and opened, ready to digitize.

The workspace is named ePUPS_Temp_Workspace. If that name is taken, a
number is added: ePUPS_Temp_Workspace_1, _2 and so on.

Examples (run with ArcGIS Pro's Python on the VDI):
    create_workspace.py                        # every production record
    create_workspace.py --editor 7             # your user ID, filled in by the toolbox
    create_workspace.py --copy-auth 6812345    # only these authorizations
    create_workspace.py --empty                # no records, for new permits only
    create_workspace.py --folder "D:\\work\\epups"
    create_workspace.py --no-open              # make the project, don't open Pro
    create_workspace.py --no-project           # geodatabase only
    create_workspace.py --name rules_demo      # a different name, for tests
"""

import argparse
import os
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epups import config, project, workspace  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Create an ePUPS editor workspace.")
    parser.add_argument(
        "--name",
        help=f"Workspace name. Default: {workspace.DEFAULT_NAME}",
    )
    parser.add_argument(
        "--editor",
        type=int,
        help="Your user ID (users.UserID). The toolbox tools fill it in from here.",
    )
    parser.add_argument(
        "--folder",
        help=f"Output folder. Default: {config.WORKSPACE_ROOT}",
    )

    # Default: copy every production record.
    copy_group = parser.add_mutually_exclusive_group()
    copy_group.add_argument(
        "--copy-auth",
        nargs="+",
        type=int,
        metavar="AUTHORIZATIONID",
        help="Copy production records for these authorizations only.",
    )
    copy_group.add_argument(
        "--empty",
        action="store_true",
        help="Copy no production records (for new permits only).",
    )

    parser.add_argument(
        "--no-project",
        action="store_true",
        help="Create the geodatabase only, without an ArcGIS Pro project.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Create the ArcGIS Pro project but don't open it.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("ePUPS Spatial - Create Editor Workspace")
    print("=" * 60)

    gdb_path = workspace.create_workspace(
        args.name,
        folder=args.folder,
        copy_all=not (args.empty or args.copy_auth),
        authorization_ids=args.copy_auth,
        editor_id=args.editor,
    )

    aprx_path = None if args.no_project else project.create_project(gdb_path)

    print(f"\nSUCCESS: Workspace ready: {gdb_path}")
    if aprx_path:
        print(f"Project: {aprx_path}")
        print("In ArcGIS Pro, use the ePUPS toolbox (Catalog > Toolboxes), in order:")
        print("  2. Start or Resume Permit, draw and save, 3. Finish or Save Draft,")
        print("  4. Check Workspace (QA), 5. Review Permit Version")
    print("=" * 60)

    if aprx_path and not args.no_open:
        print("Opening ArcGIS Pro...")
        os.startfile(str(aprx_path))


if __name__ == "__main__":
    main()
