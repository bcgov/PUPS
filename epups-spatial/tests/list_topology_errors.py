"""
List the topology errors exported by scripts/build_topology.py.

Reads logs\\topology_errors.gdb and prints every error row, with each field
except the geometry. Read only: it does not change the topology or production.

Run on the VDI from X:\\epups-spatial:
    propy.bat tests\\list_topology_errors.py
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

ERROR_GDB = PROJECT_ROOT / "logs" / "topology_errors.gdb"
ERROR_BASENAME = "topology_errors"  # must match build_topology.py


def main():
    if not arcpy.Exists(str(ERROR_GDB)):
        print(f"No error export found: {ERROR_GDB}")
        print("Run scripts\\build_topology.py first.")
        sys.exit(2)

    print("=" * 60)
    print(f"Topology errors in: {ERROR_GDB}")
    print("=" * 60)

    total = 0
    for suffix in ("point", "line", "poly"):
        error_class = ERROR_GDB / f"{ERROR_BASENAME}_{suffix}"
        if not arcpy.Exists(str(error_class)):
            continue

        fields = [
            field.name for field in arcpy.ListFields(str(error_class))
            if field.type != "Geometry" and field.name != "OBJECTID"
        ]
        print(f"\n{error_class.name}")
        with arcpy.da.SearchCursor(str(error_class), fields) as cursor:
            for row in cursor:
                total += 1
                print("  " + ", ".join(f"{name}={value}" for name, value in zip(fields, row)))

    print("\n" + "=" * 60)
    print(f"{total} topology error(s) listed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
