"""
Diagnose why a geometry problem is not reported.

Lists the polygons in a workspace, then runs arcpy.management.CheckGeometry
twice: once into in_memory (as epups/validation.py does) and once into a
table inside the workspace. Test data only. The table it writes is deleted
at the end.

Run on the VDI:
    propy.bat tests\\diagnose_geometry.py "<path to workspace .gdb>"
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import builder  # noqa: E402


def list_polygons(spatial_path):
    print("Polygons:")
    with arcpy.da.SearchCursor(str(spatial_path), ["OID@", "SPATIAL_ID", "SHAPE@"]) as cursor:
        for oid, spatial_id, shape in cursor:
            if shape is None:
                print(f"  OID {oid} SPATIAL_ID {spatial_id}: geometry is None")
                continue
            print(
                f"  OID {oid} SPATIAL_ID {spatial_id}: "
                f"parts {shape.partCount}, points {shape.pointCount}, area {shape.area:.1f}"
            )


def run_check(spatial_path, output_table, label):
    if arcpy.Exists(output_table):
        arcpy.management.Delete(output_table)

    arcpy.management.CheckGeometry(str(spatial_path), output_table)

    with arcpy.da.SearchCursor(output_table, ["FEATURE_ID", "PROBLEM"]) as cursor:
        rows = list(cursor)

    print(f"\nCheckGeometry to {label}: {len(rows)} problem row(s)")
    for feature_id, problem in rows:
        print(f"  FEATURE_ID {feature_id}: {problem}")

    arcpy.management.Delete(output_table)


def main():
    if len(sys.argv) != 2:
        print('Usage: diagnose_geometry.py "<path to workspace .gdb>"')
        sys.exit(2)

    gdb_path = Path(sys.argv[1])
    spatial_path = builder.object_paths(gdb_path)["spatial"]

    list_polygons(spatial_path)
    run_check(spatial_path, "in_memory\\geom_debug", "in_memory")
    run_check(spatial_path, str(gdb_path / "geom_debug"), "workspace table")


if __name__ == "__main__":
    main()
