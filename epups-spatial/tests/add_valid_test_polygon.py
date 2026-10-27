"""
Add one VALID test polygon inside a protected area, in the DEV production database.

It looks at the largest protected areas in Ref_Protected_Lands, finds a square
that sits fully inside one of them, and adds it to ePup_Spatial with
SPATIAL_ID 9001 under VERSION_ID 1 (from seed_production.py).

Test data only. Refuses to run if SPATIAL_ID 9001 already exists.

Run on the VDI from X:\\epups-spatial:
    propy.bat tests\\add_valid_test_polygon.py

Then validate ePUPS_Topology again. SPATIAL_ID 9001 should not appear
in the Error Inspector. The four seeded polygons (1-4) should still fail.
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import builder, config, schema  # noqa: E402

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402

TEST_SPATIAL_ID = 9001
TEST_VERSION_ID = 1
SQUARE_SIZES_METRES = (200, 100, 50, 20)
PARKS_TO_TRY = 50


def square_around(x, y, size):
    half = size / 2.0
    corners = [
        arcpy.Point(x - half, y - half),
        arcpy.Point(x + half, y - half),
        arcpy.Point(x + half, y + half),
        arcpy.Point(x - half, y + half),
        arcpy.Point(x - half, y - half),
    ]
    return arcpy.Polygon(
        arcpy.Array(corners), arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID)
    )


def find_square_inside(parks):
    for park in parks[:PARKS_TO_TRY]:
        center = park.trueCentroid
        for size in SQUARE_SIZES_METRES:
            square = square_around(center.X, center.Y, size)
            if park.contains(square):
                return square
    return None


def main():
    gdb_path = config.PRODUCTION_PATH
    paths = builder.object_paths(gdb_path)
    protected = str(paths["dataset"] / "Ref_Protected_Lands")
    spatial = str(paths["spatial"])

    with arcpy.da.SearchCursor(spatial, ["SPATIAL_ID"]) as cursor:
        if any(row[0] == TEST_SPATIAL_ID for row in cursor):
            raise RuntimeError(f"SPATIAL_ID {TEST_SPATIAL_ID} already exists. Nothing added.")

    with arcpy.da.SearchCursor(protected, ["SHAPE@"]) as cursor:
        parks = [row[0] for row in cursor if row[0] is not None]
    parks.sort(key=lambda shape: shape.area, reverse=True)

    square = find_square_inside(parks)
    if square is None:
        raise RuntimeError(
            f"No square fit inside the largest {PARKS_TO_TRY} protected areas. "
            "Try again with more parks or smaller squares."
        )

    now = datetime.now()
    fields = [
        "SHAPE@", "SPATIAL_ID", "VERSION_ID", "SOURCE_TYPE",
        "GEOMETRY_QA_STATUS", "OUT_OF_BOUNDARY_FLAG", "AREA_HA",
    ]
    row = (
        square,
        TEST_SPATIAL_ID,
        TEST_VERSION_ID,
        "GIS_DIGITIZED",
        "NOT_CHECKED",
        0,
        square.area / 10000.0,
    )
    # The polygon class is part of ePUPS_Topology, so changes need an edit session.
    editor = arcpy.da.Editor(str(gdb_path))
    editor.startEditing(False, False)
    editor.startOperation()
    try:
        with arcpy.da.InsertCursor(spatial, fields) as cursor:
            cursor.insertRow(row)
        editor.stopOperation()
        editor.stopEditing(True)
    except Exception:
        editor.stopOperation()
        editor.stopEditing(False)
        raise

    print("=" * 60)
    print(f"Added valid test polygon SPATIAL_ID {TEST_SPATIAL_ID}")
    print(f"  Size: {square.area / 10000.0:.4f} ha")
    print(f"  Centre: {square.trueCentroid.X:.1f}, {square.trueCentroid.Y:.1f}")
    print(f"  Added at: {now:%Y-%m-%d %H:%M:%S}")
    print("Validate ePUPS_Topology again in the Error Inspector.")
    print("=" * 60)


if __name__ == "__main__":
    main()
