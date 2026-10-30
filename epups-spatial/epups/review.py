"""
Reviewer sign-off on a permit version made in a workspace.

Only SUBMITTED versions (finished by the editor) are reviewed. A reviewer
either approves the version (VERSION_STATUS APPROVED) or returns it to the
editor (back to DRAFT, with the reviewer's note added to CHANGE_REASON). Both
record REVIEWED_BY (users.UserID) and REVIEWED_DATE.

Approval runs the QA checks first and is refused if any of the version's
polygons have an error, or the workspace itself does (structure, schema
version, spatial reference). Errors on other permits in the workspace don't
block it.

An approved version stays not current until it is promoted to production,
where the old version becomes SUPERSEDED (promotion is not built yet). Edits
made after approval are not detected; QA runs again at promotion.
"""

from collections import namedtuple

import arcpy

from epups import builder, config, validation, versioning

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402

CHANGE_REASON_LENGTH = 500

ReviewResult = namedtuple("ReviewResult", ["version", "approved", "blocking", "same_person", "polygons"])


def reviewable_versions(gdb_path, production_path=None):
    """SUBMITTED versions made in this workspace, sorted by authorization."""
    production_path = production_path or config.PRODUCTION_PATH
    workspace_versions = versioning.read_versions(builder.object_paths(gdb_path)["version"])
    production_versions = versioning.read_versions(builder.object_paths(production_path)["version"])
    made = versioning.workspace_versions_made(workspace_versions, production_versions)
    return [made[authorization_id] for authorization_id in sorted(made)
            if made[authorization_id].status == versioning.SUBMITTED]


def review_version(gdb_path, version_id, reviewer_id, approve, note=None, production_path=None):
    """
    Approve or return a version. Returns ReviewResult. If approve is True but
    QA found blocking errors, nothing is changed: approved is False and
    blocking lists the errors.
    """
    production_path = production_path or config.PRODUCTION_PATH
    paths = builder.object_paths(gdb_path)
    versions = versioning.read_versions(paths["version"])
    version = versions.get(version_id)
    if version is None:
        raise ValueError(f"VERSION_ID {version_id} not found in this workspace.")
    if version.status != versioning.SUBMITTED:
        raise ValueError(f"VERSION_ID {version_id} is {version.status}, not SUBMITTED. "
                         "The editor finishes it first (Finish or Save Draft).")

    with arcpy.da.SearchCursor(str(paths["spatial"]), ["OID@"],
                               where_clause=f"VERSION_ID = {int(version_id)}") as cursor:
        polygon_oids = [row[0] for row in cursor]

    same_person = version.created_by is not None and version.created_by == reviewer_id

    if approve:
        issues = validation.run_all(gdb_path, production_path)
        by_polygon = validation.issues_by_polygon(gdb_path, issues)
        blocking = [issue for issue in issues
                    if issue.severity == validation.ERROR and issue.check in validation.WORKSPACE_CHECKS]
        for oid in polygon_oids:
            blocking += [issue for issue in by_polygon.get(oid, []) if issue.severity == validation.ERROR]
        if blocking:
            return ReviewResult(version, False, blocking, same_person, len(polygon_oids))

    fields = ["VERSION_STATUS", "REVIEWED_BY", "REVIEWED_DATE", "CHANGE_REASON"]
    now = datetime.now()
    with arcpy.da.UpdateCursor(str(paths["version"]), fields,
                               where_clause=f"VERSION_ID = {int(version_id)}") as cursor:
        for status, _, _, reason in cursor:
            if approve:
                status = versioning.APPROVED
                added = f"Approved by reviewer {reviewer_id}: {note}" if note else None
            else:
                status = versioning.DRAFT
                added = f"Returned by reviewer {reviewer_id} on {now:%Y-%m-%d}: {note or 'no note'}"
            if added:
                reason = f"{reason}. {added}" if reason else added
            cursor.updateRow([status, reviewer_id, now, (reason or "")[:CHANGE_REASON_LENGTH] or None])

    return ReviewResult(version, approve, [], same_person, len(polygon_oids))
