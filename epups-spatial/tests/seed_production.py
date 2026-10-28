"""
Put demo test records into the DEV production database.

Test data only. Refuses to run if production already has version rows, so it
cannot add to real records. Do not run against a real production database.

The polygons are placed around a real protected area, so each check has
something to show:
- polygons 1 and 2: fully inside protected land (pass)
- polygon 3: crosses the edge of protected land (fails the protected-land rule)
- polygon 4: outside protected land but inside BC (fails the protected-land rule)
All four are inside the BC boundary. Each is a 100 m square (1 ha).

Records:
- authorization 6812345: version 1 (PUBLISHED, current) with polygons 1 and 2;
  version 2 (DRAFT, not current) with polygon 3
- authorization 7000001: version 3 (PUBLISHED, current) with polygon 4

AREA_HA is left empty, so the CALC_AREA_HA attribute rule fills it.

Run on the VDI after build_production.py and fetch_reference_data.py, and
before build_topology.py:
    propy.bat tests\\seed_production.py
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

PROTECTED_LANDS = "Ref_Protected_Lands"
BC_BOUNDARY = "Ref_BC_Boundary"
SQUARE_SIZE = 100            # metres, so each polygon is 1 ha
EDGE_PRECISION = 50          # metres; the crossing square overlaps the last inside one
OUTSIDE_STEP = 500           # metres between tries for the outside square
OUTSIDE_TRIES = 40           # give up on a park after 20 km past its edge
# Medium-sized parks have simpler outlines, so the checks stay fast.
PARK_AREA_RANGE = (1e6, 1e8)  # square metres: 1 to 100 km2
PARKS_TO_TRY = 50
DISSOLVE_TEMP = "in_memory\\epups_seed_union"


def square_around(x, y, size=SQUARE_SIZE):
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


def dissolved_shape(feature_class):
    """One shape covering every feature, as the topology and QA see the layer."""
    if arcpy.Exists(DISSOLVE_TEMP):
        arcpy.management.Delete(DISSOLVE_TEMP)
    arcpy.management.Dissolve(str(feature_class), DISSOLVE_TEMP)
    with arcpy.da.SearchCursor(DISSOLVE_TEMP, ["SHAPE@"]) as cursor:
        shape = next((row[0] for row in cursor), None)
    arcpy.management.Delete(DISSOLVE_TEMP)
    return shape


def place_squares(park, protected, bc):
    """
    Look east from a point inside the park. Returns (inside, inside, crossing,
    outside) squares, or None if this park doesn't give all four.

    The edge is found by halving the distance (about 15 checks against this one
    park). The merged protected-land and BC shapes are large and slow, so they
    are only checked for the final candidates.
    """
    start = park.labelPoint

    def square_at(distance):
        return square_around(start.X + distance, start.Y)

    # Two inside squares, 200 m apart.
    inside = [square_at(0), square_at(200)]
    if not all(park.contains(square) for square in inside):
        return None

    # Last inside square (low) and a square fully east of the park (high).
    low = 200
    high = park.extent.XMax - start.X + SQUARE_SIZE
    while high - low > EDGE_PRECISION:
        middle = (low + high) / 2.0
        if park.contains(square_at(middle)):
            low = middle
        else:
            high = middle
    # Overlaps the last inside square, so it is partly inside the park.
    crossing = square_at(high)

    # A neighbouring protected area could cover the crossing square; skip the park then.
    if protected.contains(crossing):
        return None
    if not all(bc.contains(square) for square in inside + [crossing]):
        return None  # near the coast or the border; try another park

    for step in range(1, OUTSIDE_TRIES + 1):
        outside = square_at(high + step * OUTSIDE_STEP)
        if protected.disjoint(outside):
            return (*inside, crossing, outside) if bc.contains(outside) else None

    return None


def insert_rows(gdb_path, paths, version_rows, spatial_rows):
    version_fields = [
        "VERSION_ID", "AUTHORIZATIONID", "VERSION_NUMBER", "VERSION_STATUS",
        "IS_CURRENT", "CREATED_DATE", "CREATED_BY",
    ]
    spatial_fields = [
        "SHAPE@", "SPATIAL_ID", "VERSION_ID", "SOURCE_TYPE",
        "GEOMETRY_QA_STATUS", "OUT_OF_BOUNDARY_FLAG", "AREA_HA",
    ]

    # An edit session, so this also works if the polygon class is already in a topology.
    editor = arcpy.da.Editor(str(gdb_path))
    editor.startEditing(False, False)
    editor.startOperation()
    try:
        with arcpy.da.InsertCursor(str(paths["version"]), version_fields) as cursor:
            for row in version_rows:
                cursor.insertRow(row)
        with arcpy.da.InsertCursor(str(paths["spatial"]), spatial_fields) as cursor:
            for row in spatial_rows:
                cursor.insertRow(row)
        editor.stopOperation()
        editor.stopEditing(True)
    except Exception:
        editor.stopOperation()
        editor.stopEditing(False)
        raise


def main():
    production = config.PRODUCTION_PATH
    if not arcpy.Exists(str(production)):
        raise FileNotFoundError(f"Production database not found: {production}")

    paths = builder.object_paths(production)
    for name in (PROTECTED_LANDS, BC_BOUNDARY):
        if not arcpy.Exists(str(paths["dataset"] / name)):
            raise FileNotFoundError(f"{name} not found. Run fetch_reference_data.py first.")

    with arcpy.da.SearchCursor(str(paths["version"]), ["VERSION_ID"]) as cursor:
        if any(True for _ in cursor):
            raise RuntimeError("Production already has version rows. Nothing was added.")

    print("=" * 60)
    print("Seeding dev production with demo test records")
    print("=" * 60)
    print("Merging reference layers (this can take a minute)...")
    protected = dissolved_shape(paths["dataset"] / PROTECTED_LANDS)
    bc = dissolved_shape(paths["dataset"] / BC_BOUNDARY)

    with arcpy.da.SearchCursor(str(paths["dataset"] / PROTECTED_LANDS), ["SHAPE@"]) as cursor:
        parks = [row[0] for row in cursor if row[0] is not None]
    smallest, largest = PARK_AREA_RANGE
    parks = [park for park in parks if smallest <= park.area <= largest]
    parks.sort(key=lambda shape: shape.area, reverse=True)

    squares = None
    for number, park in enumerate(parks[:PARKS_TO_TRY], start=1):
        print(f"  Trying park {number} ({park.area / 1e6:.1f} km2)...")
        squares = place_squares(park, protected, bc)
        if squares:
            break
    if squares is None:
        raise RuntimeError(
            f"Could not place the demo squares around {PARKS_TO_TRY} protected areas "
            "of 1 to 100 km2. Nothing was added."
        )

    now = datetime.now()
    version_rows = [
        (1, 6812345, 1, "PUBLISHED", 1, now, 1),
        (2, 6812345, 2, "DRAFT", 0, now, 1),
        (3, 7000001, 1, "PUBLISHED", 1, now, 1),
    ]
    inside_1, inside_2, crossing, outside = squares
    spatial_rows = [
        (inside_1, 1, 1, "GIS_DIGITIZED", "NOT_CHECKED", 0, None),
        (inside_2, 2, 1, "GIS_DIGITIZED", "NOT_CHECKED", 0, None),
        (crossing, 3, 2, "GIS_DIGITIZED", "NOT_CHECKED", 0, None),
        (outside, 4, 3, "GIS_DIGITIZED", "NOT_CHECKED", 0, None),
    ]
    insert_rows(production, paths, version_rows, spatial_rows)

    labels = ("inside", "inside", "crosses the edge", "outside protected land")
    print("\nSeeded 3 versions and 4 polygons:")
    for (shape, spatial_id, version_id, *_), label in zip(spatial_rows, labels):
        centre = shape.trueCentroid
        print(f"  SPATIAL_ID {spatial_id} (version {version_id}): {label}, "
              f"centre {centre.X:.0f}, {centre.Y:.0f}")
    print("\nAuthorization 6812345: versions 1-2, polygons 1-3")
    print("Authorization 7000001: version 3, polygon 4")
    print("Expected topology errors: 2 (polygons 3 and 4, protected-land rule).")
    print("=" * 60)


if __name__ == "__main__":
    main()
