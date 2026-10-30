"""
Check that editing a permit saves it as a new version.

Test data only. Needs the dev production database seeded by seed_production.py
(authorization 6812345: version 1 with polygons 1 and 2, version 2 with
polygon 3). Makes its own workspace, versioning_test (numbered if taken), with
no ArcGIS Pro project, and leaves it in place for a look afterwards.
reset_dev_data.py removes it.

Run on the VDI:
    propy.bat tests\\test_versioning.py

Steps checked:
1. A fresh copy has no edits.
2. Shrinking polygon 1 is found as an edit of authorization 6812345, and QA
   reports it as not yet saved as a new version.
3. Finish Permit Edits makes version number 3 (one above production's 2) and
   moves all three polygons onto it.
4. Running it again makes no second version.
5. A polygon drawn afterwards with its IDs left at 0 joins the new version.
6. QA no longer reports unfinished edits.
7. Editing an existing permit is refused without a change reason. A new
   permit needs none: it gets the next authorization ID and version 1,
   created by editor 7, and a polygon drawn next is linked to it with the
   source details.
8. Saving it as a draft stops new polygons going to it; resuming needs no
   change reason; finishing submits it for review.
9. QA with checker 9 writes PASS or FAIL onto the polygons, with the checker.
10. Reviewer 9 approves the new permit; approving 6812345 is refused, because
    its polygon 3 crosses the protected-land edge.
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import builder, config, review, validation, versioning, workspace  # noqa: E402

AUTHORIZATION = 6812345
EDITOR = 7
CHECKER = 9
SOURCE_REFERENCE = "TEST-REF-1"
EDITED_SPATIAL_ID = 1
SHRINK_METRES = 5
NEW_POLYGON_FIELDS = ["SHAPE@", "SPATIAL_ID", "VERSION_ID", "SOURCE_TYPE",
                      "GEOMETRY_QA_STATUS", "OUT_OF_BOUNDARY_FLAG"]


def inner_square(paths, shrink):
    """A shape inside polygon 1, so it is inside protected land too."""
    with arcpy.da.SearchCursor(str(paths["spatial"]), ["SHAPE@"],
                               where_clause=f"SPATIAL_ID = {EDITED_SPATIAL_ID}") as cursor:
        return next(cursor)[0].buffer(-shrink)


def last_polygon(paths, fields):
    with arcpy.da.SearchCursor(str(paths["spatial"]), fields,
                               sql_clause=(None, "ORDER BY OBJECTID DESC")) as cursor:
        return next(cursor)


def check(results, passed, label):
    results.append(passed)
    print(f"  {'PASS' if passed else 'FAIL'}  {label}")


def main():
    production = config.PRODUCTION_PATH
    production_versions = versioning.read_versions(builder.object_paths(production)["version"])
    expected_number = max(
        (v.number for v in production_versions.values() if v.authorization_id == AUTHORIZATION),
        default=None,
    )
    if expected_number is None:
        print(f"Authorization {AUTHORIZATION} not in production. Run tests\\seed_production.py first.")
        sys.exit(2)
    expected_number += 1

    print("=" * 60)
    print("Versioning test")
    print("=" * 60)
    gdb_path = workspace.create_workspace("versioning_test", authorization_ids=[AUTHORIZATION])
    paths = builder.object_paths(gdb_path)
    results = []

    print("\n1. Fresh copy")
    edits = versioning.edited_authorizations(gdb_path)
    check(results, edits == {}, f"no edits found ({edits or 'none'})")

    print("\n2. Edit polygon 1")
    with arcpy.da.UpdateCursor(str(paths["spatial"]), ["SHAPE@"],
                               where_clause=f"SPATIAL_ID = {EDITED_SPATIAL_ID}") as cursor:
        for row in cursor:
            row[0] = row[0].buffer(-SHRINK_METRES)
            cursor.updateRow(row)
    edits = versioning.edited_authorizations(gdb_path)
    check(results, list(edits) == [AUTHORIZATION], f"edit found: {edits}")
    unfinished = validation.check_new_versions(gdb_path, production)
    check(results, len(unfinished) == 1, f"QA reports it unfinished ({len(unfinished)} issue)")

    print("\n3. Finish Permit Edits")
    results_1 = versioning.finish_edits(gdb_path, editor_id=EDITOR)
    version = results_1[0].version if results_1 else None
    check(results, len(results_1) == 1 and results_1[0].created,
          f"one new version made: {version}")
    check(results, version is not None and version.number == expected_number,
          f"VERSION_NUMBER {version.number if version else None} (expected {expected_number})")
    with arcpy.da.SearchCursor(str(paths["spatial"]), ["SPATIAL_ID", "VERSION_ID"]) as cursor:
        on_version = {spatial_id: version_id for spatial_id, version_id in cursor}
    all_moved = version is not None and set(on_version.values()) == {version.version_id}
    check(results, all_moved, f"all polygons on the new version: {on_version}")
    with arcpy.da.SearchCursor(str(paths["version"]), ["CREATED_BY", "LAST_EDITED_BY"],
                               where_clause=f"VERSION_ID = {version.version_id if version else -1}") as cursor:
        people = next(cursor, (None, None))
    check(results, people == (EDITOR, EDITOR), f"CREATED_BY and LAST_EDITED_BY {people} (expected {EDITOR})")

    print("\n4. Finish again")
    results_2 = versioning.finish_edits(gdb_path, editor_id=EDITOR)
    check(results, len(results_2) == 1 and not results_2[0].created and results_2[0].moved == 0,
          "no second version, nothing moved")

    print("\n5. New polygon with IDs left at 0")
    with arcpy.da.InsertCursor(str(paths["spatial"]), NEW_POLYGON_FIELDS) as cursor:
        cursor.insertRow((inner_square(paths, SHRINK_METRES * 4), 0, 0, "GIS_DIGITIZED", "NOT_CHECKED", 0))
    spatial_id, version_id = last_polygon(paths, ["SPATIAL_ID", "VERSION_ID"])
    check(results, version is not None and version_id == version.version_id,
          f"new polygon SPATIAL_ID {spatial_id} linked to VERSION_ID {version_id}")

    print("\n6. QA after finishing")
    unfinished = validation.check_new_versions(gdb_path, production)
    check(results, unfinished == [], f"no unfinished edits ({len(unfinished)} issues)")

    print("\n7. New permit")
    try:
        # 7000001 is in production but has no version made here, so this makes one.
        versioning.start_authorization(gdb_path, 7000001, editor_id=EDITOR)
        refused_without_reason = False
    except ValueError:
        refused_without_reason = True
    check(results, refused_without_reason, "editing an existing permit is refused without a change reason")
    expected_authorization = versioning.next_authorization_id(gdb_path)
    new_version, created = versioning.start_new_permit(
        gdb_path, editor_id=EDITOR,
        source_defaults={"SOURCE_TYPE": "GEOMARK", "SOURCE_REFERENCE": SOURCE_REFERENCE},
    )
    check(results, created and new_version.number == 1 and new_version.created_by == EDITOR
          and new_version.authorization_id == expected_authorization,
          f"authorization {new_version.authorization_id} assigned (expected {expected_authorization}), "
          f"version 1, created by {new_version.created_by}")
    with arcpy.da.InsertCursor(str(paths["spatial"]), NEW_POLYGON_FIELDS) as cursor:
        cursor.insertRow((inner_square(paths, SHRINK_METRES * 8), 0, 0, "GIS_DIGITIZED", "NOT_CHECKED", 0))
    new_polygon = last_polygon(paths, ["SPATIAL_ID", "VERSION_ID", "SOURCE_TYPE", "SOURCE_REFERENCE"])
    check(results, new_polygon[1:] == (new_version.version_id, "GEOMARK", SOURCE_REFERENCE),
          f"new polygon got VERSION_ID, SOURCE_TYPE, SOURCE_REFERENCE {new_polygon[1:]}")

    print("\n8. Save as draft, resume, finish")
    draft, _ = versioning.close_permit(gdb_path, new_version.authorization_id, submit=False, editor_id=EDITOR)
    active = workspace.read_info(gdb_path).get("ACTIVE_VERSION_ID")
    check(results, draft.status == "DRAFT" and active is None,
          f"saved as {draft.status}; active version now {active}")
    resumed, created = versioning.start_authorization(gdb_path, new_version.authorization_id, editor_id=EDITOR)
    check(results, not created and resumed.version_id == new_version.version_id,
          f"resumed without a change reason: VERSION_ID {resumed.version_id}")
    submitted, _ = versioning.close_permit(gdb_path, new_version.authorization_id, submit=True, editor_id=EDITOR)
    listed = [v.version_id for v in review.reviewable_versions(gdb_path)]
    check(results, submitted.status == "SUBMITTED" and listed == [new_version.version_id],
          f"submitted; versions to review: {listed}")

    print("\n9. QA with results written to polygons")
    issues = validation.run_all(gdb_path, production)
    written, failed = validation.write_results(gdb_path, issues, CHECKER)
    with arcpy.da.SearchCursor(str(paths["spatial"]), ["SPATIAL_ID", "GEOMETRY_QA_STATUS", "QA_CHECKED_BY"]) as cursor:
        statuses = {spatial_id: (status, checker) for spatial_id, status, checker in cursor}
    check(results, failed == 0 and statuses.get(3, (None, None))[0] == "FAIL"
          and statuses.get(new_polygon[0]) == ("PASS", CHECKER),
          f"{written} written; polygon 3 FAIL, new polygon PASS by {CHECKER}: {statuses}")

    print("\n10. Review")
    approved = review.review_version(gdb_path, new_version.version_id, CHECKER, approve=True)
    with arcpy.da.SearchCursor(str(paths["version"]), ["VERSION_STATUS", "REVIEWED_BY"],
                               where_clause=f"VERSION_ID = {new_version.version_id}") as cursor:
        reviewed = next(cursor)
    check(results, approved.approved and reviewed == ("APPROVED", CHECKER),
          f"new permit approved: {reviewed}")
    versioning.close_permit(gdb_path, AUTHORIZATION, submit=True, editor_id=EDITOR)
    refused = review.review_version(gdb_path, version.version_id, CHECKER, approve=True)
    check(results, not refused.approved and bool(refused.blocking),
          f"approval of {AUTHORIZATION} refused: {len(refused.blocking)} blocking errors")

    print("=" * 60)
    print(f"Workspace left for inspection: {gdb_path}")
    passed = sum(results)
    print(f"{passed} of {len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
