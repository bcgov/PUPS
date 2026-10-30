"""
Permit versions in an editor workspace.

A version is one revision of an authorization's polygons. When an
authorization's polygons are added, changed or deleted in a workspace, it gets
a new version: VERSION_NUMBER one above its highest, status DRAFT, not current.
Every polygon of that authorization in the workspace moves onto the new
version, so it holds the whole permit as edited.

A workspace makes at most one new version per authorization. A version "made
in this workspace" is one whose VERSION_ID is not in production. Running
finish_edits() again reuses it, so later edits join the same version.

Edits are found by comparing the workspace with production, polygon by
SPATIAL_ID, so they are only seen once they are saved.

Who did what is recorded by users.UserID: CREATED_BY when the version is made,
LAST_EDITED_BY when edits are finished, and REVIEWED_BY at sign-off
(epups/review.py). The new version is not made current here; that happens
when it is promoted to production (not built yet).

New VERSION_IDs are one above the highest in the workspace and production.
Two workspaces made at the same time can hand out the same VERSION_ID, as
with SPATIAL_ID (see docs/WORKSPACE_SETUP.md).
"""

import getpass
from collections import Counter, namedtuple
from pathlib import Path

import arcpy

from epups import builder, config, schema, workspace

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402

# A version's life in its workspace:
#   DRAFT      being edited; the editor can save and come back later
#   SUBMITTED  the editor finished it; waiting for QA and review
#   APPROVED   the reviewer signed it off; waiting for promotion
# Returning it to the editor, or the editor resuming it, sets it back to DRAFT.
DRAFT = "DRAFT"
SUBMITTED = "SUBMITTED"
APPROVED = "APPROVED"
OPEN_STATUSES = (DRAFT, SUBMITTED, APPROVED)

# Polygon fields compared with production to find edits. SPATIAL_ID is the
# match key, AREA_HA is calculated from the shape, VERSION_ID is compared
# through the authorization it belongs to, and the QA fields are written by
# the QA check rather than by the editor.
NOT_COMPARED = {
    "SPATIAL_ID", "VERSION_ID", "AREA_HA",
    "GEOMETRY_QA_STATUS", "QA_CHECKED_DATE", "QA_CHECKED_BY", "QA_NOTE", "OUT_OF_BOUNDARY_FLAG",
}
COMPARED_FIELDS = [field["name"] for field in schema.SPATIAL_FIELDS if field["name"] not in NOT_COMPARED]

# Polygon fields Start or Resume Permit sets defaults for (Workspace_Info.DEFAULT_<name>).
SOURCE_DEFAULT_FIELDS = ("SOURCE_TYPE", "SOURCE_REFERENCE", "SOURCE_DATE", "SOURCE_NOTE")

VERSION_FIELDS = ["VERSION_ID", "AUTHORIZATIONID", "VERSION_NUMBER", "VERSION_STATUS", "IS_CURRENT", "CREATED_BY"]
Version = namedtuple("Version", ["version_id", "authorization_id", "number", "status", "is_current", "created_by"])

# One authorization's new version after finish_edits().
# created: False if the version already existed (made earlier in this workspace).
# moved: polygons moved onto it this time. edits: what was found, one line each.
FinishResult = namedtuple("FinishResult", ["version", "created", "moved", "edits"])

# One authorization in a workspace, for the toolbox's lists. open_version: the
# version made in this workspace (DRAFT, SUBMITTED or APPROVED), or None.
# edited: polygons added, changed or deleted since copied from production.
Permit = namedtuple("Permit", ["authorization_id", "polygons", "current_number", "open_version", "edited"])


def read_versions(version_path):
    """{VERSION_ID: Version} for a version table, or {} if it doesn't exist."""
    if not arcpy.Exists(str(version_path)):
        return {}
    with arcpy.da.SearchCursor(str(version_path), VERSION_FIELDS) as cursor:
        return {row[0]: Version(*row) for row in cursor if row[0] is not None}


def workspace_versions_made(workspace_versions, production_versions):
    """The newest open version (DRAFT or APPROVED) made in the workspace, per authorization."""
    made = {}
    for version in workspace_versions.values():
        if version.version_id in production_versions or version.status not in OPEN_STATUSES:
            continue
        newest = made.get(version.authorization_id)
        if newest is None or version.version_id > newest.version_id:
            made[version.authorization_id] = version
    return made


def permits(gdb_path, production_path=None):
    """Every authorization in the workspace, sorted, as Permit."""
    production_path = production_path or config.PRODUCTION_PATH
    paths = builder.object_paths(gdb_path)
    workspace_versions = read_versions(paths["version"])
    production_versions = read_versions(builder.object_paths(production_path)["version"])
    made = workspace_versions_made(workspace_versions, production_versions)

    with arcpy.da.SearchCursor(str(paths["spatial"]), ["VERSION_ID"]) as cursor:
        polygon_counts = Counter(
            workspace_versions[row[0]].authorization_id for row in cursor if row[0] in workspace_versions
        )
    edited = edited_authorizations(gdb_path, production_path)

    result = []
    for authorization_id in sorted({v.authorization_id for v in workspace_versions.values()}):
        current = [v.number for v in workspace_versions.values()
                   if v.authorization_id == authorization_id and v.is_current == 1]
        result.append(Permit(
            authorization_id,
            polygon_counts.get(authorization_id, 0),
            max(current) if current else None,
            made.get(authorization_id),
            authorization_id in edited,
        ))
    return result


def next_authorization_id(gdb_path, production_path=None):
    """One above the highest AUTHORIZATIONID in production and the workspace."""
    production_path = production_path or config.PRODUCTION_PATH
    known = (list(read_versions(builder.object_paths(gdb_path)["version"]).values())
             + list(read_versions(builder.object_paths(production_path)["version"]).values()))
    return max((v.authorization_id or 0 for v in known), default=0) + 1


def edited_authorizations(gdb_path, production_path=None):
    """
    Authorizations whose polygons were added, changed or deleted in the
    workspace, compared with production. Returns {AUTHORIZATIONID: [edit, ...]}.
    """
    production_path = production_path or config.PRODUCTION_PATH
    paths = builder.object_paths(gdb_path)
    production = builder.object_paths(production_path)

    workspace_versions = read_versions(paths["version"])
    production_versions = read_versions(production["version"])

    # Only the polygons of versions copied into the workspace can have been
    # edited or deleted there.
    copied = [version_id for version_id in workspace_versions if version_id in production_versions]
    before = {}
    if copied and arcpy.Exists(str(production["spatial"])):
        before = _read_polygons(production["spatial"], workspace.version_id_where_clause(copied))
    after = _read_polygons(paths["spatial"])

    edits = {}

    def note(versions, version_id, message):
        version = versions.get(version_id)
        if version is not None:
            edits.setdefault(version.authorization_id, []).append(message)

    for spatial_id, (version_id, shape, *values) in after.items():
        if spatial_id not in before:
            note(workspace_versions, version_id, f"SPATIAL_ID {spatial_id} added")
            continue

        old_version_id, old_shape, *old_values = before[spatial_id]
        if not _same_shape(shape, old_shape):
            note(workspace_versions, version_id, f"SPATIAL_ID {spatial_id} reshaped")
        elif values != old_values:
            note(workspace_versions, version_id, f"SPATIAL_ID {spatial_id} attributes changed")

        old_version = production_versions.get(old_version_id)
        new_version = workspace_versions.get(version_id)
        if old_version and new_version and old_version.authorization_id != new_version.authorization_id:
            note(production_versions, old_version_id,
                 f"SPATIAL_ID {spatial_id} moved to authorization {new_version.authorization_id}")
            note(workspace_versions, version_id,
                 f"SPATIAL_ID {spatial_id} moved from authorization {old_version.authorization_id}")

    for spatial_id, (old_version_id, *_) in before.items():
        if spatial_id not in after:
            note(production_versions, old_version_id, f"SPATIAL_ID {spatial_id} deleted")

    return edits


def start_authorization(
    gdb_path,
    authorization_id,
    production_path=None,
    change_reason=None,
    editor_id=None,
    effective_date=None,
    source_defaults=None,
    require_reason=True,
):
    """
    Start or resume editing a permit. Makes its new DRAFT version if this
    workspace hasn't already (a change reason is then required, unless
    require_reason is False, as for a new permit), or resumes the one it has,
    setting it back to DRAFT if it was submitted or approved. Makes that
    version the active one, so polygons drawn after this are linked to it
    (auto_version_id.arcade).

    editor_id: users.UserID, stored as the version's CREATED_BY and as the
    workspace's editor. source_defaults: {"SOURCE_TYPE": ..., "SOURCE_REFERENCE":
    ..., "SOURCE_DATE": ..., "SOURCE_NOTE": ...}, copied onto new polygons.

    Returns (Version, created). created is False if the version already existed.
    """
    if (require_reason and not (change_reason or "").strip()
            and needs_change_reason(gdb_path, authorization_id, production_path)):
        raise ValueError("A change reason is needed when editing an existing permit (it makes a new version).")

    version, created = _ensure_version(
        gdb_path, authorization_id, production_path, change_reason, editor_id, effective_date
    )
    if version.status != DRAFT:
        _set_version_fields(builder.object_paths(gdb_path), version.version_id, VERSION_STATUS=DRAFT)
        version = version._replace(status=DRAFT)
    defaults = source_defaults or {}
    values = {
        "ACTIVE_VERSION_ID": version.version_id,
        **{f"DEFAULT_{name}": defaults.get(name) for name in SOURCE_DEFAULT_FIELDS},
    }
    if editor_id is not None:
        values["EDITOR_ID"] = editor_id
    workspace.update_info(gdb_path, **values)
    return version, created


def start_new_permit(gdb_path, change_reason=None, production_path=None, **kwargs):
    """
    Start a permit that isn't in production or the workspace. Its authorization
    ID is assigned: one above the highest in production and the workspace. The
    change reason is optional. Takes the same keyword arguments as
    start_authorization(). Returns (Version, created).
    """
    authorization_id = next_authorization_id(gdb_path, production_path)
    reason = change_reason or "New permit"
    return start_authorization(gdb_path, authorization_id, production_path, reason,
                               require_reason=False, **kwargs)


def needs_change_reason(gdb_path, authorization_id, production_path=None):
    """True if starting this permit makes a new version (rather than resuming one)."""
    production_path = production_path or config.PRODUCTION_PATH
    workspace_versions = read_versions(builder.object_paths(gdb_path)["version"])
    production_versions = read_versions(builder.object_paths(production_path)["version"])
    return authorization_id not in workspace_versions_made(workspace_versions, production_versions)


def close_permit(gdb_path, authorization_id, submit, editor_id=None, production_path=None, change_reason=None,
                 effective_date=None):
    """
    End an editing session on a permit, after the edits are saved. Runs
    finish_edits() first, so every edited permit has its version and all its
    polygons on it. Then this permit's version is SUBMITTED for review if
    submit is True, or left as DRAFT to come back to. Stops new polygons going
    to it until it is started again. effective_date, if given, is stored as the
    version's SPATIAL_EFFECTIVE_DATE.

    Returns (Version, [FinishResult, ...]). Raises ValueError if the permit has
    no version made in this workspace, or if it is submitted with no polygons.
    """
    production_path = production_path or config.PRODUCTION_PATH
    results = finish_edits(gdb_path, production_path, change_reason, editor_id)
    paths = builder.object_paths(gdb_path)
    workspace_versions = read_versions(paths["version"])
    production_versions = read_versions(builder.object_paths(production_path)["version"])
    version = workspace_versions_made(workspace_versions, production_versions).get(authorization_id)
    if version is None:
        raise ValueError(f"Authorization {authorization_id} has no version in this workspace. "
                         "Start it, or edit its polygons, first.")

    if submit:
        with arcpy.da.SearchCursor(str(paths["spatial"]), ["OID@"],
                                   where_clause=f"VERSION_ID = {int(version.version_id)}") as cursor:
            if next(cursor, None) is None:
                raise ValueError(f"Authorization {authorization_id} has no polygons to submit.")

    status = SUBMITTED if submit else DRAFT
    values = {"VERSION_STATUS": status, "LAST_EDITED_BY": editor_id, "LAST_EDITED_DATE": datetime.now()}
    if effective_date is not None:
        values["SPATIAL_EFFECTIVE_DATE"] = effective_date
    _set_version_fields(paths, version.version_id, **values)
    if workspace.read_info(gdb_path).get("ACTIVE_VERSION_ID") == version.version_id:
        workspace.update_info(gdb_path, ACTIVE_VERSION_ID=None)
    return version._replace(status=status), results


def finish_edits(gdb_path, production_path=None, change_reason=None, editor_id=None):
    """
    Give each edited authorization its new version and move all its polygons
    onto it. Run after the edits are saved. Records editor_id as LAST_EDITED_BY
    (and CREATED_BY on versions it makes). Returns a list of FinishResult,
    empty if nothing was edited.
    """
    paths = builder.object_paths(gdb_path)
    results = []

    for authorization_id, edits in sorted(edited_authorizations(gdb_path, production_path).items()):
        # The version row is written before the polygons move, so the
        # VERSION_LINK rule can see it when they do.
        version, created = _ensure_version(gdb_path, authorization_id, production_path, change_reason, editor_id)
        moved = _move_polygons(paths, authorization_id, version.version_id)
        _set_version_fields(paths, version.version_id, LAST_EDITED_BY=editor_id, LAST_EDITED_DATE=datetime.now())
        results.append(FinishResult(version, created, moved, edits))

    return results


def new_polygon_version(gdb_path, production_path=None):
    """
    The version new polygons are linked to (auto_version_id.arcade): the active
    version set by Start or Resume Permit, or else the newest made in this
    workspace. None if neither exists.
    """
    production_path = production_path or config.PRODUCTION_PATH
    workspace_versions = read_versions(builder.object_paths(gdb_path)["version"])
    active = workspace.read_info(gdb_path).get("ACTIVE_VERSION_ID")
    if active in workspace_versions:
        return workspace_versions[active]
    production_versions = read_versions(builder.object_paths(production_path)["version"])
    made_here = [v for v in workspace_versions.values() if v.version_id not in production_versions]
    return max(made_here, key=lambda v: v.version_id, default=None)


def unfinished_edits(gdb_path, production_path=None):
    """
    Edited authorizations not yet on their new version: no version made in this
    workspace, or some of their polygons not on it. For QA.
    Returns {AUTHORIZATIONID: [edit, ...]}.
    """
    production_path = production_path or config.PRODUCTION_PATH
    paths = builder.object_paths(gdb_path)
    workspace_versions = read_versions(paths["version"])
    production_versions = read_versions(builder.object_paths(production_path)["version"])
    made = workspace_versions_made(workspace_versions, production_versions)

    with arcpy.da.SearchCursor(str(paths["spatial"]), ["VERSION_ID"]) as cursor:
        polygon_versions = [row[0] for row in cursor]

    unfinished = {}
    for authorization_id, edits in edited_authorizations(gdb_path, production_path).items():
        version = made.get(authorization_id)
        off_version = [
            version_id for version_id in polygon_versions
            if version_id in workspace_versions
            and workspace_versions[version_id].authorization_id == authorization_id
            and (version is None or version_id != version.version_id)
        ]
        if version is None or off_version:
            unfinished[authorization_id] = edits
    return unfinished


def _ensure_version(gdb_path, authorization_id, production_path, change_reason, editor_id, effective_date=None):
    """The authorization's open version made in this workspace, made now if needed. Returns (Version, created)."""
    production_path = production_path or config.PRODUCTION_PATH
    paths = builder.object_paths(gdb_path)
    workspace_versions = read_versions(paths["version"])
    production_versions = read_versions(builder.object_paths(production_path)["version"])

    existing = workspace_versions_made(workspace_versions, production_versions).get(authorization_id)
    if existing:
        return existing, False

    known = list(workspace_versions.values()) + list(production_versions.values())
    version = Version(
        version_id=max((v.version_id for v in known), default=0) + 1,
        authorization_id=authorization_id,
        number=max((v.number or 0 for v in known if v.authorization_id == authorization_id),
                   default=0) + 1,
        status=DRAFT,
        is_current=0,
        created_by=editor_id,
    )
    reason = change_reason or f"Edited in workspace {Path(gdb_path).stem} by {getpass.getuser()}"

    fields = VERSION_FIELDS + ["SYNC_CONFLICT", "CHANGE_REASON", "CREATED_DATE", "SPATIAL_EFFECTIVE_DATE"]
    row = (*version, 0, reason, datetime.now(), effective_date)
    with arcpy.da.InsertCursor(str(paths["version"]), fields) as cursor:
        cursor.insertRow(row)

    return version, True


def _set_version_fields(paths, version_id, **values):
    fields = list(values)
    with arcpy.da.UpdateCursor(str(paths["version"]), fields,
                               where_clause=f"VERSION_ID = {int(version_id)}") as cursor:
        for row in cursor:
            cursor.updateRow([values[name] for name in fields])


def _read_polygons(spatial_path, where_clause=None):
    """{SPATIAL_ID: (VERSION_ID, shape, *COMPARED_FIELDS)}"""
    fields = ["SPATIAL_ID", "VERSION_ID", "SHAPE@"] + COMPARED_FIELDS
    with arcpy.da.SearchCursor(str(spatial_path), fields, where_clause=where_clause) as cursor:
        return {row[0]: row[1:] for row in cursor if row[0] is not None}


def _same_shape(shape, other):
    if shape is None or other is None:
        return shape is other
    return shape.equals(other)


def _move_polygons(paths, authorization_id, version_id):
    """Move every polygon of an authorization onto version_id. Returns how many moved."""
    others = [
        other.version_id for other in read_versions(paths["version"]).values()
        if other.authorization_id == authorization_id and other.version_id != version_id
    ]
    if not others:
        return 0

    moved = 0
    with arcpy.da.UpdateCursor(str(paths["spatial"]), ["VERSION_ID"],
                               where_clause=workspace.version_id_where_clause(others)) as cursor:
        for row in cursor:
            row[0] = version_id
            cursor.updateRow(row)
            moved += 1
    return moved
