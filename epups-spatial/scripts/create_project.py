"""
Make the ArcGIS Pro project for an existing workspace (the .aprx next to it).

The toolbox's Create Workspace runs this in a separate process when it makes
a separate project. Made inside ArcGIS Pro, the project file stays open in
that Pro session, and the new Pro window then opens it read-only. Run on its
own, it also remakes a project for a workspace whose .aprx was deleted.

Examples (run with ArcGIS Pro's Python on the VDI):
    create_project.py "<workspace.gdb>"
    create_project.py "<workspace.gdb>" --open
"""

import argparse
import os
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epups import project  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Make the ArcGIS Pro project for a workspace.")
    parser.add_argument("workspace", help="Workspace geodatabase path.")
    parser.add_argument("--open", action="store_true", help="Open the project in ArcGIS Pro.")
    return parser.parse_args()


def main():
    args = parse_args()
    aprx_path = project.create_project(args.workspace)
    if args.open:
        print("Opening ArcGIS Pro...")
        os.startfile(str(aprx_path))


if __name__ == "__main__":
    main()
