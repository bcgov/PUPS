# Editing, checking and reviewing ePUPS permits

Written for: editors, checkers and reviewers who work on permit polygons in ArcGIS Pro on the VDI.

A workspace is a temporary copy of the ePUPS spatial database. The editor drafts changes there and saves them as a new permit version. A checker runs QA, and a reviewer approves the version. Only then does it move toward production. Nobody changes production directly.

Everyone is identified by their **user ID** (a number, `users.UserID`), not their name. The tools record who did each step.

## Before you start

- Use the VDI, where ArcGIS Pro and ArcPy are installed. The steps were tested with ArcGIS Pro 3.4.3.
- Map the project folder to drive `X:`. Run this once per session:

  ```powershell
  net use X: \\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\tools\PUPS
  ```

- You need read access to the production geodatabase (`source_data\epups_spatial_dev\epups_spatial_dev.gdb` for now) and write access to the workspace folder (`source_data\epups_workspaces`).

> Command-line tools fail when run from a network path that starts with `\\`. Always work from the `X:` drive.

### One-time setup: the project template

Only needed for workspaces that get a separate project (the command line, or **Where to work** set to a separate project). Each separate project is copied from a template. Pro opens a project at the view the template was saved with, so the template has to be saved zoomed to BC. This only needs doing once, by anyone, and all editors then share the template.

1. In ArcGIS Pro, create a new project from **Map**. Name it `epups_workspace_template`, set the location to `source_data\templates`, and **untick "Create a new folder for this project"**.
2. In the Contents pane, right-click the map and open **Properties** > **Coordinate Systems**. Search for `3005` and choose **NAD 1983 BC Environment Albers**. Click **OK**.
3. Zoom so the whole province fills the view. For example, add `Ref_BC_Boundary` from the production geodatabase, choose **Zoom To Layer**, then remove the layer.
4. Save the project and close Pro.

The file should be `source_data\templates\epups_workspace_template.aprx`. Without it, the create step uses ArcGIS Pro's own blank project, which opens over Australia.

### Where to start: the starter project

Double-click **`source_data\ePUPS_Start.aprx`** in File Explorer. ArcGIS Pro opens with the **ePUPS** toolbox already attached: in the Catalog pane under **Toolboxes**, and in the Geoprocessing pane (**Analysis** tab > **Tools**) under **Toolboxes** > **Project**. Expand **ePUPS** and double-click a tool to open it. The starter is shared and read-only: you start workspaces from it, but don't work in it.

If it's missing, the database owner makes it with `scripts\make_starter_project.py`.

**To use the toolbox in your own projects instead**, add it to your Favorites once: in the **Catalog** pane, right-click **Toolboxes** > **Add Toolbox**, pick `X:\epups-spatial\ePUPS.pyt`, then right-click **ePUPS** > **Add To Favorites**. It then shows under **Favorites** in every project.

The tools are numbered in the order they're used:

| Tool | Who runs it |
|---|---|
| 1. Create Workspace | Editor |
| 2. Start or Resume Permit | Editor |
| 3. Finish or Save Draft | Editor |
| 4. Check Workspace (QA) | Checker |
| 5. Review Permit Version | Reviewer |

A permit version moves through these statuses:

| Status | Meaning | Set by |
|---|---|---|
| `DRAFT` | Being edited. You can leave it and come back | Start or Resume Permit, Save as draft, or a reviewer returning it |
| `SUBMITTED` | Finished by the editor, waiting for QA and review | Finish and submit for review |
| `APPROVED` | Signed off by a reviewer, waiting for promotion to production | Review Permit Version |

> **Saving.** In ArcGIS Pro, your drawing and the changes the tools make are held in Pro until you click **Edit** tab > **Save** (in the Manage Edits group). Until then, they're not in the workspace, and they're lost if Pro closes without saving. **Ctrl+S saves the project, not the edits.** Click Edit > Save after drawing and after each tool; each tool reminds you.

Each tool fills in the open project's workspace. The editor tools also fill in the editor's ID; the checker and reviewer type their own. Each has a command-line script that does the same thing, shown under each step.

If a project shows an empty `epups_workspace_template` toolbox, ignore it. It's the empty toolbox every Pro project has.

## Step 1: Create your workspace (editor)

Open the starter project (`source_data\ePUPS_Start.aprx`), then open **1. Create Workspace**:

| Input | What to enter |
|---|---|
| **Editor ID** | Your user ID |
| **Only copy these authorizations** | Leave blank to copy all of production |
| **Start empty** | Only for new permits, with nothing copied |
| **Workspace name**, **Folder** | Leave the defaults |
| **Where to work** | **Make a separate project and open it** (the default in the starter) |

Click **Run**. The tool copies all of production into a new workspace. It pulls production fresh each time, so the workspace starts from what is in production now. It makes the workspace's own project next to it and opens it in a new ArcGIS Pro window:

- One map named after the workspace, opened on all of BC.
- The workspace is the project's default geodatabase, so the other tools fill it in.
- The ePUPS toolbox is attached.

Close the starter window, and do everything else in the workspace project. To come back to a draft later, double-click the workspace's `.aprx` in `source_data\epups_workspaces`.

**In your own project instead** (with the toolbox in your Favorites), choose **Set it up in this project**. The open project gets a map named after the workspace, opened on BC, and the workspace becomes its default geodatabase. Save the project (Ctrl+S) to come back to drafts later. The starter project can't be set up this way, because it's shared.

**Command line instead.** This makes the workspace and a separate project next to it, then opens it:

```powershell
$propy = "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat"

& $propy scripts\create_workspace.py --editor 7
& $propy scripts\create_workspace.py --editor 7 --copy-auth 6812345   # copy only these authorizations
& $propy scripts\create_workspace.py --editor 7 --empty               # copy nothing (new permits only)
& $propy scripts\create_workspace.py --editor 7 --no-open             # don't open ArcGIS Pro
```

### What you get

The workspace is named `ePUPS_Temp_Workspace.gdb` and saved in `source_data\epups_workspaces`. If that name is already taken, a number is added: `ePUPS_Temp_Workspace_1.gdb`, `_2` and so on. A separate project, if you chose one, sits next to it with the same name, for example `ePUPS_Temp_Workspace.aprx`.

The workspace map, named after the workspace, opens on all of BC:

| Layer | Source | Notes |
|---|---|---|
| `ePup_Spatial` | The workspace | **The layer you draw and edit.** Red outline |
| `Ref_Protected_Lands` | Production | Green, 50% transparent. Polygons must sit inside it. Reference only, no editing template |
| `Ref_BC_Boundary` | Production | Grey, 50% transparent. Reference only, no editing template |
| Topographic basemap | Esri | Same basemap as a new ArcGIS Pro map |
| `ePup_Spatial_Version` (table) | The workspace | The permit versions, with who created, edited and reviewed each one |

The workspace contains:

| Object | What it holds |
|---|---|
| `SpatialData\ePup_Spatial` | The permit polygons |
| `ePup_Spatial_Version` | One row per permit version, with its authorization and status |
| `users` | User records |
| `SpatialData\ePup_Version_Polygons` | The link from each version to its polygons, on `VERSION_ID`. Identify a polygon to see its version and authorization |
| `Workspace_Info` | Where the workspace came from, the editor's ID, the permit being drawn, and the source details for new polygons |

### What to look for

- The messages end with `Workspace ready` (`SUCCESS: Workspace ready` on the command line).
- The version and polygon counts copied match production.
- The new map is open on BC, and `Added toolbox` appears in the messages.

## Step 2: Start or resume a permit (editor)

Open **2. Start or Resume Permit**, enter your **Editor ID**, and choose the **Action**. The inputs below it change with the action:

| Action | What you enter | What happens |
|---|---|---|
| **Start a new permit** | Nothing else is required. A change reason is optional | You don't enter an authorization ID. The tool assigns the next one, one above the highest in production, and shows it under Action before you run. The permit gets version 1 |
| **Edit an existing permit** | The **Permit**, found with **Search authorization ID** (type any part of the number to shorten the list) or **Use the polygon selected on the map**. A **Change reason** is required | The permit gets its next version number, for example 3 if it has versions 1 and 2. If it already has a draft in this workspace, that draft is resumed instead, and no reason is needed |
| **Resume a draft** | The **Permit**, from a list of the drafts in this workspace ("draft in progress") | Carries on where you left off. It keeps its version |

To use a selected polygon: select it on the map first (**Map** tab > **Select**), then open the tool, or tick the box after selecting. If the search or selection matches one permit, it's picked for you.

Every action has the same **New polygon details** (expand): source type (list), source reference (for example a Geomark or file number), source date and source note. Every polygon you draw gets these.

Click **Run**. The version is a `DRAFT`, created by you.

### Drawing

A layer called **"Drawing: authorization 7000002 (version 1)"** appears at the top of the map. It shows only that permit's polygons, outlined in bright blue. In **Create Features** (**Edit** tab > **Create**), pick the template with the same name and draw as usual. Every polygon you draw is added to that permit:

- `SPATIAL_ID` is set to the next free number, above every ID in the workspace and in production.
- `VERSION_ID` is set to the permit's version.
- The source type, reference, date and note from this step are filled in, unless you type your own.
- `AREA_HA` is calculated from the shape.

You can also reshape, move or delete the permit's existing polygons as normal. Don't change their IDs. Save your edits when you're done (**Edit** tab > **Save**).

If you draw a polygon without starting a permit, the save is rejected with "This polygon has no version to belong to". To draw for a different permit, run the tool again and pick it.

> If the Drawing template doesn't appear in Create Features, click **"Click here to see templates not listed"** in that pane, or draw with the `ePup_Spatial` template. The polygons still go to the permit you started.

Command line:

```powershell
& $propy scripts\start_authorization.py "<workspace.gdb>" new --editor 7 --source-type GEOMARK --source-ref GM-1234
& $propy scripts\start_authorization.py "<workspace.gdb>" 6812345 --editor 7 --reason "Trail realigned"   # edit, or resume its draft
```

The attribute rules stop a save that breaks a rule and show the message. The reference layers come from production and are for context; don't edit them.

> Two workspaces made at the same time can hand out the same new authorization ID, `SPATIAL_ID` or `VERSION_ID`, because each one only knows production and itself. QA at promotion has to catch this until the ID assignment decision is made.

## Step 3: Finish, or save as a draft (editor)

Save your edits first. Then open **3. Finish or Save Draft**:

| Input | What to enter |
|---|---|
| **Editor ID** | Your user ID |
| **Permit** | Filled in with the permit you're drawing. The list has every permit with edits or a draft |
| **What next** | **Save as draft (come back to it later)**, or **Finish and submit for review** |
| **Spatial effective date** | Optional. The date the permit's polygons take effect, stored on its version |

Either way, the tool compares the workspace with production and, for every permit with a polygon added, reshaped, changed or deleted:

1. Uses the version you started in Step 2. If there isn't one, for example because you only reshaped a permit's polygons, it makes the next version now.
2. Moves **all** of the permit's polygons in the workspace onto it, not only the ones you edited. The version holds the whole permit as edited.
3. Records you as `LAST_EDITED_BY`, with the date.

Then, for the permit you chose:

- **Save as draft.** It stays `DRAFT`. To carry on later, reopen the project you worked in (save it first, Ctrl+S), run **2. Start or Resume Permit** with Action **Resume a draft**, and pick it.
- **Finish.** It becomes `SUBMITTED`, ready for the checker and the reviewer. A permit with no polygons can't be submitted.

The "Drawing:" layer is removed, and new polygons aren't linked to the permit until you start or resume it again.

Command line:

```powershell
& $propy scripts\finish_edits.py "<workspace.gdb>" --editor 7 --permit 7000002             # save as draft
& $propy scripts\finish_edits.py "<workspace.gdb>" --editor 7 --permit 7000002 --submit --effective-date 2026-11-01   # finish
```

### What to look for

- The tool lists each permit, its version number and the edits it found.
- "No permits with edits or drafts" means nothing was saved. Save in ArcGIS Pro and run it again.

## Step 4: Check the workspace (checker)

Open **4. Check Workspace (QA)**, enter your **Checker ID**, leave **Write results to polygons** ticked, and click **Run**. It reads the whole workspace and lists every problem it finds:

- Errors show as warnings in the tool messages, and the summary says `FAIL: n errors`. The tool itself finishes normally; a FAIL is the result, not a tool failure.
- **The failing polygons are highlighted on the map:** they're selected, and a **"QA: failing polygons (n)"** layer outlines them in thick red. Right-click that layer > **Zoom To Layer** to find them, or open the `ePup_Spatial` attribute table and click **Show selected records**. The next QA run replaces the layer; it's removed when nothing fails.
- The report is saved to `X:\epups-spatial\logs` as `qa_<workspace>_<date>_<time>.txt`.
- Each polygon gets its result in the attribute table:

| Field | Value |
|---|---|
| `GEOMETRY_QA_STATUS` | `PASS` (no problems), `NEEDS_REVIEW` (warnings only) or `FAIL` (errors) |
| `QA_CHECKED_BY`, `QA_CHECKED_DATE` | Your ID and the date |
| `QA_NOTE` | The problems found, if any |
| `OUT_OF_BOUNDARY_FLAG` | `1` if the polygon is outside protected land or BC |

Writing the results doesn't count as an edit, so it doesn't start new versions.

Command line (`--checker` writes the results onto the polygons; without it, the check only reads):

```powershell
& $propy scripts\qa_validate.py "<workspace.gdb>" --checker 9
echo $LASTEXITCODE
```

The exit code is `1` if there are any errors.

### Reading the result

- **PASS, 0 errors.** The workspace is ready for review. Warnings can stay, but the reviewer should look at them.
- **FAIL.** Each error names the record and the problem. The editor resumes the permit, fixes them, saves, finishes it again, and the check is run again.

With the demo data, a new workspace fails with 2 errors on purpose: polygon 3 crosses the protected-land edge, and polygon 4 is outside protected land.

Examples from a planted-error test:

```
ERROR    geometry      OBJECTID 1    null geometry
ERROR    spatial-id    SPATIAL_ID 1  Duplicate SPATIAL_ID appears 2 times
ERROR    version-link  OBJECTID 3    VERSION_ID 999 not found in ePup_Spatial_Version
WARNING  version-link  AUTHORIZATIONID 1  2 current versions; expected at most one
ERROR    reference     OBJECTID 2    Polygon is outside protected land
ERROR    new-version   AUTHORIZATIONID 6812345  Edited (SPATIAL_ID 1 reshaped) but not saved as a new version. Run Finish or Save Draft.
```

### What the check covers

- **Structure and schema.** The tables, fields, domains and schema version match production. A workspace built with an older schema fails this check. Create a new workspace and move your work into it.
- **Geometry.** Every polygon has a shape, uses EPSG:3005, and is valid.
- **Required values and picklists.** Required fields are filled, and coded values are in their domain.
- **Keys and links.** `SPATIAL_ID` and `VERSION_NUMBER` are unique, and every `VERSION_ID` exists.
- **Area.** `AREA_HA` matches the shape. A difference of more than 0.1% (and at least 0.01 ha) is a warning.
- **Protected land and BC boundary.** Every polygon must lie inside protected land and inside the BC boundary. These layers are read from production, so the check needs production to be reachable. If they are missing, the check reports a warning and skips them.
- **New versions.** Every edited permit has its new version, with all its polygons on it. If not, run Finish or Save Draft.

## Step 5: Review the version (reviewer)

Open **5. Review Permit Version**:

| Input | What to enter |
|---|---|
| **Workspace** | Filled in |
| **Reviewer ID** | Your user ID |
| **Version to review** | Pick from the list of submitted versions. Each shows its authorization, version number and who created it. Drafts aren't listed until the editor finishes them |
| **Decision** | **Approve**, or **Return to editor** |
| **Note** | Optional for an approval. Required when returning: say what needs fixing |

- **Approve** runs QA again first. If any of this version's polygons have errors, the approval is refused and the errors are listed. Errors on other permits in the workspace don't block it. Otherwise the version becomes `APPROVED`, with you as `REVIEWED_BY` and today as `REVIEWED_DATE`.
- **Return to editor** sets the version back to `DRAFT`, records you as reviewer, and adds your note to its `CHANGE_REASON`. The editor resumes it with Start or Resume Permit.

If you also created the version, the tool warns you. A second person should normally review it.

An approved version stays not current until it is promoted to production, where the old version is marked `SUPERSEDED`. Promotion is not built yet.

Command line:

```powershell
& $propy scripts\review_version.py "<workspace.gdb>"                                   # list versions
& $propy scripts\review_version.py "<workspace.gdb>" 4 --reviewer 9 --approve
& $propy scripts\review_version.py "<workspace.gdb>" 4 --reviewer 9 --return "Polygon 3 crosses the park edge"
```

## Step 6: Hand over the workspace

1. Keep the QA report with the workspace. The report is in `logs`, and its name includes the workspace name.
2. Tell the upload owner which workspace has an approved version, and its path.
3. The upload owner moves the records into production. This step is not built yet.

> **Open questions for the upload:** who runs it, where approved workspaces are placed for it, and whether the QA check is run again before records are added.

## Common problems

- **`propy.bat` fails with an error about a path.** You are running from a `\\` network path. Map a drive letter and run from `X:`.
- **"No blank project to copy", or the map opens over Australia.** The project template is missing. Do the one-time template setup under "Before you start", then run the create step again.
- **The toolbox has a red X.** Pro couldn't load it. Close ArcGIS Pro completely and reopen the project. If it's still red, run `import arcpy; arcpy.ImportToolbox(r"X:\epups-spatial\ePUPS.pyt")` in the Python window and send the error.
- **The toolbox tools don't show recent changes.** Right-click the toolbox in Catalog and choose **Refresh**, or restart ArcGIS Pro.
- **The toolbox isn't in the project.** The create step printed `Could not add the toolbox`. Add `X:\epups-spatial\ePUPS.pyt` from **Catalog** > **Toolboxes** > **Add Toolbox**.
- **The Workspace box is empty or shows an error.** The open project hasn't been set up with Create Workspace, or the workspace was made before 2026-10-29. Run Create Workspace in it, or browse to the workspace `.gdb`.
- **I can't find the ePUPS toolbox.** Open the starter project, `source_data\ePUPS_Start.aprx`, or a workspace project. In any other project, add it to your Favorites (see "Where to start").
- **"This is the shared starter project".** Create Workspace can't set up the starter itself. Choose **Make a separate project and open it**.
- **"This workspace was made with an older version of the tools".** Create a new workspace. Workspaces are temporary, and older ones lack the fields the toolbox uses.
- **"No permits in this workspace".** The workspace has no versions. It was made with `--empty`, or production has none. Use Start a new permit.
- **"Say why the permit is changing".** You're editing an existing permit, which makes a new version. Enter why in Change reason.
- **"Select a permit polygon on the map first".** "Use the polygon selected on the map" is ticked, but nothing is selected. Select a polygon (**Map** tab > **Select**), then untick and tick the box again.
- **The Permit list is long.** Type part of the authorization number in **Search authorization ID**. The list shows at most 200 permits.
- **"This polygon has no version to belong to".** You haven't started a permit, or you saved the last one as a draft or finished it. Run Start or Resume Permit, then draw again.
- **No "Drawing:" template in Create Features.** Click "Click here to see templates not listed" in the pane, or draw with the `ePup_Spatial` template; the polygons still go to the permit you started.
- **"Violated attribute constraint rule".** A rule rejected your edit. The message after it says which rule. Fix the value and save again.
- **Changes are missing after reopening the project, or a script doesn't see them.** The edits were never saved: Ctrl+S saves only the project. Use **Edit** tab > **Save**. While edits are unsaved, Pro holds `.ed.lock` files in the workspace folder.
- **"Polygons of other permits were edited too".** You changed polygons of another permit, for example moving one to fix QA. That permit now has its own draft. Resume it and finish it if it should be reviewed.
- **QA warns that a table is "not part of the ePUPS schema".** An editing tool left it, for example `Links` from **Transform**. Delete it in the Catalog pane (right-click > **Delete**) before hand-over.
- **Finish or Save Draft lists no permits.** Your edits aren't saved. On the **Edit** tab, click **Save**, then run it again.
- **The Review list is empty.** No version has been submitted. The editor runs Finish or Save Draft and chooses Finish.
- **"Not approved: n errors".** The version's polygons failed QA. Return it to the editor, who resumes it, fixes the polygons and finishes it again; then the checker runs QA before the review is tried again.
- **"Cannot get exclusive schema lock".** Another application is using the geodatabase. Close ArcGIS Pro completely, including any Catalog connection and any map that uses its layers, then run the script again.
- **QA reports `reference` warnings.** Production's reference layers are missing. Ask the database owner to run `scripts\fetch_reference_data.py`.
