"""
Create a workspace with deliberately bad records, to confirm qa_validate.py catches them.

Test data only. Do not use for real work. Run on the VDI:
    propy.bat tests\\make_bad_workspace.py

Then run qa_validate.py on the printed workspace path. It should report
FAIL and exit with code 1. Expected findings:
- ERROR geometry: the polygon with no shape is empty
- ERROR spatial-id: SPATIAL_ID 1 appears twice
- ERROR version-link: VERSION_ID 999 has no version row
- ERROR version-number: none expected (version numbers are unique here)
- WARNING version-link: authorization 1 has two current versions
- WARNING area: AREA_HA 5.0 does not match the 1.0 ha square
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import builder, schema, workspace  # noqa: E402

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402


def square(x, y):
    corners = [
        arcpy.Point(x, y),
        arcpy.Point(x + 100, y),
        arcpy.Point(x + 100, y + 100),
        arcpy.Point(x, y + 100),
        arcpy.Point(x, y),
    ]
    return arcpy.Polygon(arcpy.Array(corners), arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID))


def main():
    gdb_path = workspace.create_workspace("qa_negative")
    paths = builder.object_paths(gdb_path)
    now = datetime.now()

    # Version rows: two current versions for authorization 1 (warning).
    version_fields = [
        "VERSION_ID", "AUTHORIZATIONID", "VERSION_NUMBER", "VERSION_STATUS",
        "IS_CURRENT", "CREATED_DATE", "CREATED_BY",
    ]
    version_rows = [
        (1, 1, 1, "DRAFT", 1, now, 1),
        (2, 1, 2, "DRAFT", 1, now, 1),
    ]
    with arcpy.da.InsertCursor(str(paths["version"]), version_fields) as cursor:
        for row in version_rows:
            cursor.insertRow(row)

    # Polygon rows:
    # - empty geometry, and SPATIAL_ID 1 duplicated (error)
    # - orphan VERSION_ID 999 (error)
    # - AREA_HA that does not match the geometry (warning)
    # A self-intersecting polygon is not used: ArcGIS splits it into valid
    # parts on insert, so it is not a usable negative test.
    spatial_fields = [
        "SHAPE@", "SPATIAL_ID", "VERSION_ID", "SOURCE_TYPE",
        "GEOMETRY_QA_STATUS", "OUT_OF_BOUNDARY_FLAG", "AREA_HA",
    ]
    spatial_rows = [
        (None, 1, 1, "GIS_DIGITIZED", "NOT_CHECKED", 0, None),
        (square(200, 0), 1, 1, "GIS_DIGITIZED", "NOT_CHECKED", 0, 1.0),
        (square(400, 0), 3, 999, "GIS_DIGITIZED", "NOT_CHECKED", 0, 1.0),
        (square(600, 0), 4, 1, "GIS_DIGITIZED", "NOT_CHECKED", 0, 5.0),
    ]
    with arcpy.da.InsertCursor(str(paths["spatial"]), spatial_fields) as cursor:
        for row in spatial_rows:
            cursor.insertRow(row)

    print("=" * 60)
    print("Bad test workspace created. Run qa_validate.py on:")
    print(gdb_path)
    print("=" * 60)


if __name__ == "__main__":
    main()
