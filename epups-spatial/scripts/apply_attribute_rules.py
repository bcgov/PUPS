"""
Apply the ePUPS attribute rules to a geodatabase.

Normally not needed: build_production.py and create_workspace.py apply the
rules automatically. Use this script to add the rules to an older geodatabase
that was built before they were automatic.

Examples (run with ArcGIS Pro's Python on the VDI):
    apply_attribute_rules.py "\\\\...\\epups_spatial_dev.gdb"
"""

import argparse
import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from epups import attribute_rules  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Apply ePUPS attribute rules.")
    parser.add_argument("gdb", help="Geodatabase path to apply the rules to.")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print(f"Applying attribute rules to: {args.gdb}")
    print("=" * 60)

    failed = attribute_rules.apply_all(args.gdb)

    print("=" * 60)
    print("Done." if not failed else f"{failed} rule(s) failed. See messages above.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
