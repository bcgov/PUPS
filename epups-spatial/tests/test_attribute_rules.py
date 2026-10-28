"""
Check that the attribute rules reject bad records and calculate AREA_HA.

Run against a FRESH workspace, after apply_attribute_rules.py has been run on it.
It adds test rows to the workspace it is given, so do not run it on production
or on a workspace you are still using.

Run on the VDI:
    propy.bat tests\\test_attribute_rules.py "<path to a fresh workspace .gdb>"

Each bad insert should be rejected (PASS). The area case should succeed and
AREA_HA should be about 1.0 hectare for a 100 m x 100 m square.
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import builder, schema  # noqa: E402

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402

VERSION_FIELDS = [
    "VERSION_ID", "AUTHORIZATIONID", "VERSION_NUMBER", "VERSION_STATUS",
    "IS_CURRENT", "CREATED_DATE", "CREATED_BY",
]
SPATIAL_FIELDS = [
    "SHAPE@", "SPATIAL_ID", "VERSION_ID", "SOURCE_TYPE",
    "GEOMETRY_QA_STATUS", "OUT_OF_BOUNDARY_FLAG", "AREA_HA",
]
USER_FIELDS = ["UserID", "UserFirstName", "UserLastName", "UserInitials"]


def square(x, y, size=100):
    corners = [
        arcpy.Point(x, y),
        arcpy.Point(x + size, y),
        arcpy.Point(x + size, y + size),
        arcpy.Point(x, y + size),
        arcpy.Point(x, y),
    ]
    return arcpy.Polygon(arcpy.Array(corners), arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID))


def try_insert(table_path, fields, row):
    """Returns None if ArcGIS accepted the row, otherwise the error message."""
    try:
        with arcpy.da.InsertCursor(str(table_path), fields) as cursor:
            cursor.insertRow(row)
        return None
    except Exception as error:
        return str(error)


def report(results, label, rejected_expected, error):
    rejected = error is not None
    passed = rejected == rejected_expected
    results.append(passed)

    outcome = "PASS" if passed else "FAIL"
    detail = (error or "accepted").splitlines()[0]
    print(f"  {outcome}  {label}: {detail}")


def main():
    if len(sys.argv) != 2:
        print('Usage: test_attribute_rules.py "<path to a fresh workspace .gdb>"')
        sys.exit(2)

    gdb_path = Path(sys.argv[1])
    paths = builder.object_paths(gdb_path)
    now = datetime.now()
    results = []

    print("=" * 60)
    print(f"Attribute rule tests: {gdb_path}")
    print("=" * 60)

    # Stop here if the workspace path is wrong. Otherwise every insert fails with
    # "cannot open" and the bad-insert checks would wrongly report PASS.
    missing = [name for name in ("users", "version", "spatial") if not arcpy.Exists(str(paths[name]))]
    if missing:
        print(f"Cannot find these tables: {', '.join(missing)}. Check the workspace path.")
        sys.exit(2)

    # Baseline rows the bad inserts will be compared against. If one fails, the
    # later checks mean nothing, so stop.
    user_row = (1, "Test", "User", "TU")
    print("\nBaseline")
    error = try_insert(paths["users"], USER_FIELDS, user_row)
    print(f"  users row 1: {'added' if error is None else error.splitlines()[0]}")
    baseline_failed = error is not None

    baseline_version = (101, 9001, 1, "DRAFT", 1, now, 1)
    error = try_insert(paths["version"], VERSION_FIELDS, baseline_version)
    print(f"  version 101 (auth 9001, number 1, current): "
          f"{'added' if error is None else error.splitlines()[0]}")
    baseline_failed = baseline_failed or error is not None

    baseline_spatial = (square(0, 0), 501, 101, "GIS_DIGITIZED", "NOT_CHECKED", 0, None)
    error = try_insert(paths["spatial"], SPATIAL_FIELDS, baseline_spatial)
    print(f"  polygon SPATIAL_ID 501: {'added' if error is None else error.splitlines()[0]}")
    baseline_failed = baseline_failed or error is not None

    if baseline_failed:
        print("A baseline row was rejected. Use a fresh workspace and check the rules before rerunning.")
        sys.exit(1)

    print("\nRules that should reject a bad insert")
    report(results, "duplicate SPATIAL_ID 501",
           True, try_insert(paths["spatial"], SPATIAL_FIELDS,
                            (square(300, 0), 501, 101, "GIS_DIGITIZED", "NOT_CHECKED", 0, None)))
    report(results, "duplicate VERSION_ID 101",
           True, try_insert(paths["version"], VERSION_FIELDS,
                            (101, 9002, 1, "DRAFT", 0, now, 1)))
    report(results, "duplicate version number 1 for auth 9001",
           True, try_insert(paths["version"], VERSION_FIELDS,
                            (102, 9001, 1, "DRAFT", 0, now, 1)))
    report(results, "second current version for auth 9001",
           True, try_insert(paths["version"], VERSION_FIELDS,
                            (103, 9001, 2, "DRAFT", 1, now, 1)))
    report(results, "duplicate UserID 1",
           True, try_insert(paths["users"], USER_FIELDS, (1, "Other", "User", "OU")))

    print("\nRules that should accept a valid insert")
    report(results, "non-current version 2 for auth 9001",
           False, try_insert(paths["version"], VERSION_FIELDS,
                             (104, 9001, 2, "DRAFT", 0, now, 1)))
    report(results, "new polygon SPATIAL_ID 502 with AREA_HA empty",
           False, try_insert(paths["spatial"], SPATIAL_FIELDS,
                             (square(300, 0), 502, 101, "GIS_DIGITIZED", "NOT_CHECKED", 0, None)))

    print("\nArea calculation")
    with arcpy.da.SearchCursor(str(paths["spatial"]), ["SPATIAL_ID", "AREA_HA"],
                               where_clause="SPATIAL_ID = 502") as cursor:
        area = next((row[1] for row in cursor), None)

    area_ok = area is not None and abs(area - 1.0) < 0.001
    results.append(area_ok)
    print(f"  {'PASS' if area_ok else 'FAIL'}  AREA_HA for 100 m square: {area}")

    print("=" * 60)
    passed = sum(results)
    print(f"{passed} of {len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
