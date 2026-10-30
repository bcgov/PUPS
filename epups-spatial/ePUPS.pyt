"""
ePUPS toolbox for ArcGIS Pro.

To have it in every project: Catalog pane > Toolboxes > right-click > Add
Toolbox, pick this file (X:\\epups-spatial\\ePUPS.pyt), then right-click it >
Add To Favorites. Workspace projects also have it attached. The tools call the
epups package next to it, the same code as the scripts in scripts/, so both
give the same result.

Tools, in the order they are used. People are identified by users.UserID.
1. Create Workspace          - copy of production, set up in the open project (or a new one)
2. Start or Resume Permit    - editor: new permit (ID assigned) or an existing one; then draw
3. Finish or Save Draft      - editor, after saving: submit for review, or keep as a draft
4. Check Workspace (QA)      - checker: QA/QC checks, results written onto each polygon
5. Review Permit Version     - reviewer: approve a submitted version, or return it
"""

import contextlib
import importlib
import subprocess
import sys
import tempfile
from pathlib import Path

import arcpy

TOOLBOX_FOLDER = Path(__file__).resolve().parent
if str(TOOLBOX_FOLDER) not in sys.path:
    sys.path.insert(0, str(TOOLBOX_FOLDER))

from epups import (  # noqa: E402
    attribute_rules, builder, config, drawing, project, review, rules, schema, validation,
    versioning, workspace,
)

# Imported after arcpy, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402

# Dependencies first, so a reload picks up changed code in the right order.
_MODULES = (config, schema, rules, builder, attribute_rules, workspace, project, versioning,
            validation, review, drawing)

IN_THIS_PROJECT = "Set it up in this project"
NEW_PROJECT_OPEN = "Make a separate project and open it"
NEW_PROJECT = "Make a separate project, don't open it"
START_NEW = "Start a new permit"
EDIT_EXISTING = "Edit an existing permit"
RESUME_DRAFT = "Resume a draft"
SAVE_DRAFT = "Save as draft (come back to it later)"
SUBMIT = "Finish and submit for review"
APPROVE = "Approve"
RETURN = "Return to editor"
SOURCE_TYPES = list(schema.DOMAINS["ePup_Source_Type"]["values"])
DETAILS = "New polygon details"

# Longest permit list shown before asking the editor to search.
LIST_LIMIT = 200
# Seconds the permit list is reused while a tool dialog is open. Reading it
# compares every polygon with production, which is slow to repeat on each keystroke.
CACHE_SECONDS = 60
_permit_cache = {}


def _permits(gdb):
    """versioning.permits(gdb), reused for CACHE_SECONDS."""
    now = datetime.now()
    cached = _permit_cache.get(gdb)
    if cached and (now - cached[0]).total_seconds() < CACHE_SECONDS:
        return cached[1]
    permits = versioning.permits(gdb)
    _permit_cache[gdb] = (now, permits)
    return permits


def _reload():
    """Pro keeps imported modules until it restarts. Reload so code changes on the share apply."""
    for module in _MODULES:
        importlib.reload(module)
    _permit_cache.clear()  # the tool about to run changes the permits


class _ToMessages:
    """Sends print() output from the epups package to the tool's messages."""

    def __init__(self):
        self._buffer = ""

    def write(self, text):
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            arcpy.AddMessage(line)

    def flush(self):
        if self._buffer:
            arcpy.AddMessage(self._buffer)
            self._buffer = ""


@contextlib.contextmanager
def _messages():
    writer = _ToMessages()
    with contextlib.redirect_stdout(writer):
        yield
    writer.flush()


def _parameter(label, name, datatype, required=False, category=None, value=None, choices=None,
               multi_value=False):
    param = arcpy.Parameter(
        displayName=label,
        name=name,
        datatype=datatype,
        parameterType="Required" if required else "Optional",
        direction="Input",
        category=category,
        multiValue=multi_value,
    )
    if choices is not None:
        param.filter.type = "ValueList"
        param.filter.list = choices
    if value is not None:
        param.value = value
    return param


def _save_reminder():
    """
    Inside ArcGIS Pro, a tool's changes join Pro's edit session and reach the
    workspace only when the edits are saved. Ctrl+S saves the project, not the edits.
    """
    arcpy.AddWarning("To keep these changes, click Edit tab > Save (Manage Edits). "
                     "Ctrl+S only saves the project, not the edits.")


def _make_project_in_new_process(gdb_path, open_project):
    """
    Make the workspace's separate project with scripts/create_project.py, in
    its own ArcGIS Pro Python process. Made in this Pro session, the .aprx
    would stay open here, and the new Pro window would open it read-only.
    Returns the project path.
    """
    propy = Path(arcpy.GetInstallInfo()["InstallDir"]) / "bin" / "Python" / "Scripts" / "propy.bat"
    command = [str(propy), str(TOOLBOX_FOLDER / "scripts" / "create_project.py"), str(gdb_path)]
    if open_project:
        command.append("--open")
    # propy.bat fails when started from a \\ network folder, so start it from a local one.
    result = subprocess.run(command, cwd=tempfile.gettempdir(), capture_output=True, text=True)
    for line in result.stdout.splitlines():
        arcpy.AddMessage(line)
    if result.returncode != 0:
        raise RuntimeError(f"Making the project failed:\n{result.stderr or result.stdout}")
    return Path(gdb_path).with_suffix(".aprx")


def _in_starter_project():
    """True if the open project is the shared starter project, which must not become a workspace."""
    try:
        return project.is_starter_project(arcpy.mp.ArcGISProject("CURRENT").filePath)
    except (OSError, RuntimeError, ValueError):
        return False


def _current_workspace():
    """The open project's default geodatabase, if it's an ePUPS workspace."""
    try:
        gdb = arcpy.mp.ArcGISProject("CURRENT").defaultGeodatabase
    except (OSError, RuntimeError, ValueError):
        return None
    return gdb if gdb and workspace.is_workspace(gdb) else None


def _workspace_parameter():
    param = _parameter("Workspace", "workspace", "DEWorkspace", required=True, value=_current_workspace())
    param.filter.list = ["Local Database"]
    return param


def _person_parameter(label, name, required=True):
    return _parameter(label, name, "GPLong", required=required)


def _valid_workspace(param):
    """The workspace path if the parameter holds an ePUPS workspace, else None."""
    if not param.valueAsText:
        return None
    gdb = Path(param.valueAsText)
    if gdb.resolve() == Path(config.PRODUCTION_PATH).resolve():
        return None
    if not (arcpy.Exists(str(builder.object_paths(gdb)["spatial"])) and workspace.is_workspace(gdb)):
        return None
    return str(gdb)


def _check_workspace(param):
    """Error on the parameter if it isn't an ePUPS workspace, or is production."""
    if not param.valueAsText:
        return
    gdb = Path(param.valueAsText)
    if gdb.resolve() == Path(config.PRODUCTION_PATH).resolve():
        param.setErrorMessage("This is the production database. Choose a workspace.")
    elif _valid_workspace(param) is None:
        param.setErrorMessage("Not an ePUPS workspace (no ePup_Spatial or Workspace_Info).")


def _default_person(workspace_param, person_param):
    """Fill a person ID from the workspace's editor, unless the user has typed one."""
    gdb = _valid_workspace(workspace_param)
    if gdb and person_param.value is None and not person_param.altered:
        editor = workspace.read_info(gdb).get("EDITOR_ID")
        if editor is not None:
            person_param.value = editor


def _check_person(param):
    """Warn if production's users table lists people and this ID isn't one of them."""
    if param.value is None:
        return
    users = builder.object_paths(config.PRODUCTION_PATH)["users"]
    if not arcpy.Exists(str(users)):
        return
    with arcpy.da.SearchCursor(str(users), ["UserID"]) as cursor:
        known = {row[0] for row in cursor}
    if known and int(param.value) not in known:
        param.setWarningMessage(f"User ID {param.value} is not in the production users table.")


def _leading_id(text):
    """The number a dropdown entry starts with, for example 6812345 from '6812345 - 3 polygons'."""
    try:
        return int(str(text).split()[0])
    except (IndexError, ValueError):
        return None


def _permit_label(permit):
    """How a permit appears in the dropdowns."""
    text = f"{permit.authorization_id} - {permit.polygons} polygons"
    if permit.current_number is not None:
        text += f", current version {permit.current_number}"
    version = permit.open_version
    if version is not None:
        state = {versioning.DRAFT: "draft in progress", versioning.SUBMITTED: "submitted",
                 versioning.APPROVED: "approved"}.get(version.status, version.status.lower())
        text += f", version {version.number} {state}"
    elif permit.edited:
        text += ", edited"
    return text


class Toolbox:
    def __init__(self):
        self.label = "ePUPS"
        self.alias = "epups"
        self.tools = [CreateWorkspace, StartPermit, FinishPermit, CheckWorkspace, ReviewPermitVersion]


class CreateWorkspace:
    def __init__(self):
        self.label = "1. Create Workspace"
        self.description = (
            "Creates an editor workspace (ePUPS_Temp_Workspace, numbered if taken) with the "
            "production schema, rules and records. By default it sets up the project you have "
            "open: a map of the workspace over protected lands and the BC boundary, opened on "
            "BC, with the workspace as the default geodatabase, ready to digitize. Or it makes "
            "a separate project for the workspace."
        )

    def getParameterInfo(self):
        return [
            _person_parameter("Editor ID (your user ID)", "editor_id", required=False),
            _parameter("Only copy these authorizations (blank: all of production)",
                       "authorizations", "GPLong", multi_value=True),
            _parameter("Start empty (new permits only)", "empty", "GPBoolean", value=False),
            _parameter("Workspace name", "name", "GPString", value=workspace.DEFAULT_NAME),
            _parameter("Folder", "folder", "DEFolder", value=str(config.WORKSPACE_ROOT)),
            _parameter("Where to work", "where", "GPString", required=True,
                       value=NEW_PROJECT_OPEN if _in_starter_project() else IN_THIS_PROJECT,
                       choices=[IN_THIS_PROJECT, NEW_PROJECT_OPEN, NEW_PROJECT]),
            arcpy.Parameter(displayName="Workspace", name="output_workspace", datatype="DEWorkspace",
                            parameterType="Derived", direction="Output"),
        ]

    def updateMessages(self, parameters):
        _check_person(parameters[0])
        authorizations, empty = parameters[1], parameters[2]
        if empty.value and authorizations.values:
            empty.setErrorMessage("Start empty, or list authorizations to copy, not both.")
        if parameters[5].valueAsText == IN_THIS_PROJECT and _in_starter_project():
            parameters[5].setErrorMessage(
                "This is the shared starter project, so it can't become your workspace. "
                "Choose 'Make a separate project and open it'.")

    def execute(self, parameters, messages):
        _reload()
        editor_id = parameters[0].value
        authorizations = [int(value) for value in (parameters[1].values or [])]
        empty = bool(parameters[2].value)
        where = parameters[5].valueAsText
        with _messages():
            gdb_path = workspace.create_workspace(
                parameters[3].valueAsText or None,
                folder=parameters[4].valueAsText or None,
                copy_all=not (empty or authorizations),
                authorization_ids=authorizations or None,
                editor_id=int(editor_id) if editor_id is not None else None,
            )
            if where == IN_THIS_PROJECT:
                map_name = project.set_up_current_project(gdb_path)
        parameters[6].value = str(gdb_path)
        arcpy.AddMessage(f"Workspace ready: {gdb_path}")

        if where == IN_THIS_PROJECT:
            arcpy.AddMessage(f"This project now has the '{map_name}' map, and the workspace is its "
                             "default geodatabase. Save the project (Ctrl+S) to come back to it later.")
            arcpy.AddMessage("Next: 2. Start or Resume Permit.")
            return

        arcpy.AddMessage("Making the workspace's project (about half a minute)...")
        aprx_path = _make_project_in_new_process(gdb_path, open_project=where == NEW_PROJECT_OPEN)
        arcpy.AddMessage(f"Project: {aprx_path}")
        if where == NEW_PROJECT_OPEN:
            arcpy.AddMessage("It opens in a new ArcGIS Pro window. Close this one and work there.")


class StartPermit:
    def __init__(self):
        self.label = "2. Start or Resume Permit"
        self.description = (
            "Choose what you're doing. Start a new permit: it gets the next authorization ID "
            "automatically. Edit an existing permit: search for it or use a polygon selected "
            "on the map, and say why it's changing; it gets its next version. Resume a draft: "
            "carry on with one you saved. A 'Drawing:' layer for the permit then appears at "
            "the top of the map, with its own template in Create Features: draw with it as "
            "usual, and the polygons are added to that permit."
        )

    def getParameterInfo(self):
        return [
            _workspace_parameter(),
            _person_parameter("Editor ID (your user ID)", "editor_id"),
            _parameter("Action", "action", "GPString", required=True, value=START_NEW,
                       choices=[START_NEW, EDIT_EXISTING, RESUME_DRAFT]),
            _parameter("Search authorization ID", "search", "GPString"),
            _parameter("Use the polygon selected on the map", "use_selected", "GPBoolean", value=False),
            _parameter("Permit", "permit", "GPString", choices=[]),
            _parameter("Change reason (required when editing an existing permit)", "change_reason", "GPString"),
            _parameter("Source type", "source_type", "GPString", category=DETAILS,
                       value="GIS_DIGITIZED", choices=SOURCE_TYPES),
            _parameter("Source reference (for example a Geomark or file number)",
                       "source_reference", "GPString", category=DETAILS),
            _parameter("Source date", "source_date", "GPDate", category=DETAILS),
            _parameter("Source note", "source_note", "GPString", category=DETAILS),
        ]

    def updateParameters(self, parameters):
        workspace_param, editor, action, search, use_selected, permit, reason = parameters[:7]
        _default_person(workspace_param, editor)
        choice = action.valueAsText
        editing = choice == EDIT_EXISTING

        search.enabled = editing
        use_selected.enabled = editing
        permit.enabled = choice in (EDIT_EXISTING, RESUME_DRAFT)
        reason.enabled = choice != RESUME_DRAFT

        gdb = _valid_workspace(workspace_param)
        if not gdb or not permit.enabled:
            return

        items = _permits(gdb)
        if choice == RESUME_DRAFT:
            items = [item for item in items
                     if item.open_version and item.open_version.status == versioning.DRAFT]
        else:
            if use_selected.value:
                selected = set(drawing.selected_authorizations(gdb))
                items = [item for item in items if item.authorization_id in selected]
            if search.valueAsText:
                items = [item for item in items if search.valueAsText.strip() in str(item.authorization_id)]

        labels = [_permit_label(item) for item in items[:LIST_LIMIT]]
        permit.filter.list = labels
        if permit.valueAsText not in labels:
            permit.value = labels[0] if len(labels) == 1 else None

    def updateMessages(self, parameters):
        _check_workspace(parameters[0])
        _check_person(parameters[1])
        gdb = _valid_workspace(parameters[0])
        action, search, use_selected, permit, reason = parameters[2:7]
        if not gdb:
            return
        choice = action.valueAsText

        if choice == START_NEW:
            action.setWarningMessage(
                f"The new permit will be authorization {versioning.next_authorization_id(gdb)}.")
            return

        if not permit.filter.list:
            if choice == RESUME_DRAFT:
                permit.setErrorMessage("No drafts in this workspace.")
            elif use_selected.value:
                permit.setErrorMessage("Select a permit polygon on the map first (Map tab > Select).")
            elif search.valueAsText:
                permit.setErrorMessage(f"No authorization contains '{search.valueAsText}'.")
            else:
                permit.setErrorMessage("No permits in this workspace.")
        elif not permit.valueAsText:
            more = len(_permits(gdb)) > LIST_LIMIT and not search.valueAsText
            permit.setErrorMessage("Choose the permit." + (" Type in Search to narrow the list." if more else ""))
        elif (choice == EDIT_EXISTING and not (reason.valueAsText or "").strip()
              and versioning.needs_change_reason(gdb, _leading_id(permit.valueAsText))):
            reason.setErrorMessage("Say why the permit is changing.")

    def execute(self, parameters, messages):
        _reload()
        gdb_path = parameters[0].valueAsText
        choice = parameters[2].valueAsText
        options = {
            "editor_id": int(parameters[1].value),
            "source_defaults": {
                "SOURCE_TYPE": parameters[7].valueAsText,
                "SOURCE_REFERENCE": parameters[8].valueAsText,
                "SOURCE_DATE": parameters[9].value,
                "SOURCE_NOTE": parameters[10].valueAsText,
            },
        }
        reason = parameters[6].valueAsText
        if choice == START_NEW:
            version, created = versioning.start_new_permit(gdb_path, reason, **options)
        else:
            authorization_id = _leading_id(parameters[5].valueAsText)
            version, created = versioning.start_authorization(
                gdb_path, authorization_id,
                change_reason=reason if choice == EDIT_EXISTING else None, **options
            )

        if created:
            arcpy.AddMessage(f"Started authorization {version.authorization_id}: version {version.number} "
                             f"(VERSION_ID {version.version_id}, DRAFT), created by {version.created_by}.")
        else:
            arcpy.AddMessage(f"Resumed authorization {version.authorization_id}: version {version.number} "
                             f"(VERSION_ID {version.version_id}), back to DRAFT.")

        layer = drawing.show_permit(builder.object_paths(gdb_path)["spatial"], version)
        if layer:
            arcpy.AddMessage(f"Draw with the '{layer}' template in Create Features "
                             "(Edit tab > Create).")
        else:
            arcpy.AddMessage("Draw in ePup_Spatial with Create Features.")
        arcpy.AddMessage("When done, click Edit tab > Save, then run 3. Finish or Save Draft.")
        _save_reminder()


class FinishPermit:
    def __init__(self):
        self.label = "3. Finish or Save Draft"
        self.description = (
            "Run after saving your edits. Save as draft keeps the permit's version as a "
            "DRAFT to come back to (Start or Resume Permit). Finish submits it for QA and "
            "review. Either way, every edited permit gets its version and all its polygons "
            "move onto it, and you are recorded as the last editor."
        )

    def getParameterInfo(self):
        return [
            _workspace_parameter(),
            _person_parameter("Editor ID (your user ID)", "editor_id"),
            _parameter("Permit", "permit", "GPString", required=True, choices=[]),
            _parameter("What next", "decision", "GPString", required=True,
                       value=SAVE_DRAFT, choices=[SAVE_DRAFT, SUBMIT]),
            _parameter("Spatial effective date", "effective_date", "GPDate"),
        ]

    def updateParameters(self, parameters):
        workspace_param, editor, permit = parameters[:3]
        _default_person(workspace_param, editor)
        gdb = _valid_workspace(workspace_param)
        if gdb and (workspace_param.altered or not permit.filter.list):
            items = [item for item in _permits(gdb)
                     if item.edited or (item.open_version and item.open_version.status == versioning.DRAFT)]
            permit.filter.list = [_permit_label(item) for item in items]
            # Default to the permit being drawn.
            active = versioning.new_polygon_version(gdb)
            if permit.value is None and active is not None:
                matches = [label for label in permit.filter.list if _leading_id(label) == active.authorization_id]
                if matches:
                    permit.value = matches[0]

    def updateMessages(self, parameters):
        _check_workspace(parameters[0])
        _check_person(parameters[1])
        if _valid_workspace(parameters[0]) and not parameters[2].filter.list:
            parameters[2].setErrorMessage("No permits with edits or drafts. Start a permit and draw first, "
                                          "and save your edits.")

    def execute(self, parameters, messages):
        _reload()
        gdb_path = parameters[0].valueAsText
        submit = parameters[3].valueAsText == SUBMIT
        version, results = versioning.close_permit(
            gdb_path, _leading_id(parameters[2].valueAsText), submit, editor_id=int(parameters[1].value),
            effective_date=parameters[4].value,
        )
        for result in results:
            moved = f", {result.moved} polygons moved onto it" if result.moved else ""
            arcpy.AddMessage(f"Authorization {result.version.authorization_id}, version "
                             f"{result.version.number}: {'; '.join(result.edits)}{moved}")
        drawing.clear()

        label = f"Authorization {version.authorization_id}, version {version.number} (VERSION_ID {version.version_id})"
        if submit:
            arcpy.AddMessage(f"{label}: SUBMITTED for review. Next: 4. Check Workspace (QA).")
        else:
            arcpy.AddMessage(f"{label}: saved as DRAFT. To carry on, run 2. Start or Resume Permit "
                             "and pick it from the list.")

        # Editing another permit's polygons (for example moving one to fix QA) gives
        # that permit a draft too. Say so, or it sits unnoticed and unreviewed.
        others = sorted({result.version.authorization_id for result in results}
                        - {version.authorization_id})
        if others:
            arcpy.AddWarning(f"Polygons of other permits were edited too: {', '.join(map(str, others))}. "
                             "Each now has a DRAFT version. To have them reviewed, resume each one "
                             "and finish it.")
        _save_reminder()


class CheckWorkspace:
    def __init__(self):
        self.label = "4. Check Workspace (QA)"
        self.description = (
            "Runs the QA/QC checks on a workspace and writes a report to the logs folder. "
            "With 'Write results to polygons', each polygon gets its QA status (PASS, "
            "NEEDS_REVIEW or FAIL), the checker's ID, the date, and the problems found. "
            "Errors must be fixed before the version can be approved."
        )

    def getParameterInfo(self):
        return [
            _workspace_parameter(),
            _person_parameter("Checker ID (your user ID)", "checker_id"),
            _parameter("Write results to polygons", "write_results", "GPBoolean", value=True),
            arcpy.Parameter(displayName="Report", name="report", datatype="DEFile",
                            parameterType="Derived", direction="Output"),
        ]

    # The checker ID is not filled from the editor's: the checker types their own.

    def updateMessages(self, parameters):
        _check_workspace(parameters[0])
        _check_person(parameters[1])

    def execute(self, parameters, messages):
        _reload()
        gdb_path = parameters[0].valueAsText
        checker_id = int(parameters[1].value)
        with _messages():
            issues = validation.run_all(gdb_path, config.PRODUCTION_PATH)
        report_path, result, errors, warnings = validation.write_report(
            gdb_path, issues, datetime.now()
        )
        parameters[3].value = str(report_path)

        for issue in issues:
            line = f"{issue.severity:<8} {issue.check:<14} {issue.record}: {issue.message}"
            if issue.severity == validation.ERROR:
                arcpy.AddWarning(line)
            else:
                arcpy.AddMessage(line)

        if parameters[2].value:
            written, failed = validation.write_results(gdb_path, issues, checker_id)
            arcpy.AddMessage(f"QA results written to {written} polygons (GEOMETRY_QA_STATUS, QA_ columns).")
            if failed:
                arcpy.AddWarning(f"{failed} polygons could not be updated; fix their errors first.")

        failing = sorted(
            oid for oid, found in validation.issues_by_polygon(gdb_path, issues).items()
            if any(issue.severity == validation.ERROR for issue in found)
        )
        layer = drawing.show_qa_failures(builder.object_paths(gdb_path)["spatial"], failing)
        if layer:
            arcpy.AddMessage(f"Failing polygons (OBJECTID {', '.join(str(oid) for oid in failing)}) are "
                             f"selected and shown in red in the '{layer}' layer. Right-click it > "
                             "Zoom To Layer to find them.")
        arcpy.AddMessage(f"Report: {report_path}")

        # QA ran correctly either way, so a FAIL is a warning, not a tool failure.
        summary = f"{result}: {errors} errors, {warnings} warnings"
        if errors:
            arcpy.AddWarning(summary)
        else:
            arcpy.AddMessage(summary)
            arcpy.AddMessage("Next: 5. Review Permit Version.")
        if parameters[2].value:
            _save_reminder()


class ReviewPermitVersion:
    def __init__(self):
        self.label = "5. Review Permit Version"
        self.description = (
            "Reviewer sign-off on a submitted version. Approve it, or return it to the "
            "editor with a note (it goes back to DRAFT). Approval runs QA first and is "
            "refused if the version's polygons have errors. Records the reviewer's ID and the date."
        )

    def getParameterInfo(self):
        return [
            _workspace_parameter(),
            _person_parameter("Reviewer ID (your user ID)", "reviewer_id"),
            _parameter("Version to review", "version", "GPString", required=True, choices=[]),
            _parameter("Decision", "decision", "GPString", required=True,
                       value=APPROVE, choices=[APPROVE, RETURN]),
            _parameter("Note (required when returning)", "note", "GPString"),
        ]

    def updateParameters(self, parameters):
        workspace_param, version = parameters[0], parameters[2]
        gdb = _valid_workspace(workspace_param)
        if gdb and (workspace_param.altered or not version.filter.list):
            version.filter.list = [
                f"{item.version_id} - authorization {item.authorization_id}, version {item.number}, "
                f"created by {item.created_by}"
                for item in review.reviewable_versions(gdb)
            ]

    def updateMessages(self, parameters):
        _check_workspace(parameters[0])
        _check_person(parameters[1])
        version = parameters[2]
        if _valid_workspace(parameters[0]) and not version.filter.list:
            version.setErrorMessage("No submitted versions. The editor runs 3. Finish or Save Draft "
                                    "and chooses Finish.")
        if parameters[3].valueAsText == RETURN and not parameters[4].valueAsText:
            parameters[4].setErrorMessage("Say what the editor needs to fix.")

    def execute(self, parameters, messages):
        _reload()
        gdb_path = parameters[0].valueAsText
        reviewer_id = int(parameters[1].value)
        version_id = _leading_id(parameters[2].valueAsText)
        approve = parameters[3].valueAsText == APPROVE
        with _messages():
            result = review.review_version(
                gdb_path, version_id, reviewer_id, approve, note=parameters[4].valueAsText
            )

        version = result.version
        label = f"authorization {version.authorization_id}, version {version.number} (VERSION_ID {version.version_id})"
        if result.same_person:
            arcpy.AddWarning(f"Reviewer {reviewer_id} also created this version. "
                             "A second person should normally review it.")
        if approve and not result.approved:
            for issue in result.blocking:
                arcpy.AddWarning(f"{issue.severity:<8} {issue.check:<14} {issue.record}: {issue.message}")
            arcpy.AddError(f"Not approved: {len(result.blocking)} errors on {label}. "
                           "Return it to the editor to fix, or fix and run QA, then review again.")
            return
        if approve:
            arcpy.AddMessage(f"Approved {label}, {result.polygons} polygons, by reviewer {reviewer_id}.")
            arcpy.AddMessage("It becomes current when it is promoted to production (not built yet).")
        else:
            arcpy.AddMessage(f"Returned {label} to the editor. It is a DRAFT again; the note is in CHANGE_REASON.")
        _save_reminder()
