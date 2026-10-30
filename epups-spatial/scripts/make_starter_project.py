"""
Make the shared ePUPS starter project (source_data\\ePUPS_Start.aprx).

Editors double-click it to open ArcGIS Pro with the ePUPS toolbox already
attached, and run 1. Create Workspace from it. It shows protected lands and
the BC boundary on the topographic basemap, opened on BC. It is read-only, and
Create Workspace makes each workspace its own project rather than changing it.

Run once, and again after the template or the toolbox location changes. It
replaces the existing starter, so close it in ArcGIS Pro first.

Example (run with ArcGIS Pro's Python on the VDI):
    make_starter_project.py
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epups import project  # noqa: E402


def main():
    print("=" * 60)
    print("ePUPS Spatial - Make Starter Project")
    print("=" * 60)
    starter = project.create_starter_project()
    print(f"\nSUCCESS: Editors open {starter}")
    print("=" * 60)


if __name__ == "__main__":
    main()
