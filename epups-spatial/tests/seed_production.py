"""
Put test records into the DEV production database, so the copy tests have data to copy.

Test data only. Refuses to run if production already has version rows, so it
cannot add to real records. Do not run against a real production database.

Creates:
- authorization 6812345: version 1 (PUBLISHED, current) with polygons 1 and 2;
  version 2 (DRAFT, not current) with polygon 3
- authorization 7000001: version 3 (PUBLISHED, current) with polygon 4

Run on the VDI after build_production.py:
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
    production = config.PRODUCTION_PATH
    if not arcpy.Exists(str(production)):
        raise FileNotFoundError(f"Production database not found: {production}")

    paths = builder.object_paths(production)

    with arcpy.da.SearchCursor(str(paths["version"]), ["VERSION_ID"]) as cursor:
        if any(True for _ in cursor):
            raise RuntimeError("Production already has version rows. Nothing was added.")

    now = datetime.now()

    version_fields = [
        "VERSION_ID", "AUTHORIZATIONID", "VERSION_NUMBER", "VERSION_STATUS",
        "IS_CURRENT", "CREATED_DATE", "CREATED_BY",
    ]
    version_rows = [
        (1, 6812345, 1, "PUBLISHED", 1, now, 1),
        (2, 6812345, 2, "DRAFT", 0, now, 1),
        (3, 7000001, 1, "PUBLISHED", 1, now, 1),
    ]
    with arcpy.da.InsertCursor(str(paths["version"]), version_fields) as cursor:
        for row in version_rows:
            cursor.insertRow(row)

    spatial_fields = [
        "SHAPE@", "SPATIAL_ID", "VERSION_ID", "SOURCE_TYPE",
        "GEOMETRY_QA_STATUS", "OUT_OF_BOUNDARY_FLAG", "AREA_HA",
    ]
    spatial_rows = [
        (square(0, 0), 1, 1, "GIS_DIGITIZED", "PASS", 0, 1.0),
        (square(200, 0), 2, 1, "GIS_DIGITIZED", "PASS", 0, 1.0),
        (square(400, 0), 3, 2, "GIS_DIGITIZED", "NOT_CHECKED", 0, 1.0),
        (square(600, 0), 4, 3, "GIS_DIGITIZED", "PASS", 0, 1.0),
    ]
    with arcpy.da.InsertCursor(str(paths["spatial"]), spatial_fields) as cursor:
        for row in spatial_rows:
            cursor.insertRow(row)

    print("=" * 60)
    print("Seeded dev production: 3 versions, 4 polygons.")
    print("Authorization 6812345: versions 1-2, polygons 1-3")
    print("Authorization 7000001: version 3, polygon 4")
    print("=" * 60)


if __name__ == "__main__":
    main()
