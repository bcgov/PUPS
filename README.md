# PUPS: ePUPS Spatial Database

Tools for the ePUPS spatial database: park use permit polygons, the version history behind them, and the checks that keep bad data out of production.

Editors never change production directly. An editor creates a temporary workspace, draws or edits polygons in ArcGIS Pro, and saves the changes as a new permit version. A checker runs QA, and a reviewer approves the version. Only an approved version moves toward production.

## How it works

- **Production database.** One file geodatabase holds the permit polygons (`ePup_Spatial`), their versions (`ePup_Spatial_Version`) and users. The schema follows the co-worker DBML design. For now it is a development copy on the share, until the production server is chosen.
- **Workspaces.** Editors open a shared starter project, which has the toolbox, and one tool makes a workspace: a copy of production (schema, rules and every record, pulled fresh each time) with its own ArcGIS Pro project, ready to digitize. The map shows the workspace polygons over semi-transparent protected lands and the BC boundary, on the Topographic basemap, and opens on all of BC.
- **The toolbox.** Five tools take a workspace through the whole workflow: start or resume a permit, finish it or save it as a draft, check it, and review it. People are identified by user ID (`users.UserID`), not by name.
- **New permits.** The authorization ID is assigned automatically, one above the highest in production. Editing an existing permit needs a change reason; a new permit doesn't.
- **Drawing.** Once a permit is started, a **"Drawing: authorization …"** layer appears at the top of the map with its own template in Create Features. You draw with the normal Create tools, and you can always see which permit you're adding to.
- **Automatic values.** A polygon you draw gets the next free `SPATIAL_ID`, the permit you started, and the source details you entered (type, reference, date, note). You don't type IDs into the attribute table.
- **Versions.** Editing a permit makes a new version: `VERSION_NUMBER` one higher, not current yet. All of the permit's polygons move onto it. A version is `DRAFT` while you work on it (you can leave it and come back), `SUBMITTED` when you finish it, and `APPROVED` once a reviewer signs it off.
- **Who did what.** The version records who created it (`CREATED_BY`), last edited it (`LAST_EDITED_BY`) and reviewed it (`REVIEWED_BY`), with dates. Each polygon records its QA result, who checked it, when, and what was wrong.
- **Attribute rules.** Rules run inside ArcGIS Pro on every save. They keep keys unique, stop polygons with no permit, allow one current version per permit, fill the automatic values, and calculate the area in hectares.
- **QA/QC.** Checks run on the whole workspace: structure, geometry, required values, keys and links, area, unfinished versions, and whether each polygon sits inside protected land and inside BC. Errors block approval; warnings need a reviewer's decision.

## Getting set up

ArcGIS Pro and ArcPy only run on the VDI. Steps 1 to 4 are done once, by the database owner, for everyone. Editors then just open the starter project (see [Editing permits](#editing-permits-the-workflow)).

### 1. Map the project folder to `X:`

Command-line tools fail from a `\\` network path, so work from a drive letter. In PowerShell:

```powershell
net use X: \\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\tools\PUPS
```

The mapping lasts for the VDI session.

### 2. Check the production database exists

The production database is at `source_data\epups_spatial_dev\epups_spatial_dev.gdb`. If it's missing, the database owner builds it. See [Building production](#building-production-database-owner).

### 3. Make the project template (once, for everyone)

Each workspace's ArcGIS Pro project is copied from a template, and Pro opens a project wherever the template was last looking. So the template is saved zoomed to BC:

1. In ArcGIS Pro, create a new project from **Map**. Name it `epups_workspace_template`, save it in `source_data\templates`, and **untick "Create a new folder for this project"**.
2. In the Contents pane, right-click the map > **Properties** > **Coordinate Systems**. Search `3005`, choose **NAD 1983 BC Environment Albers**, and click **OK**.
3. Zoom to the whole province. For example, add `Ref_BC_Boundary` from production, use **Zoom To Layer**, then remove it.
4. Save the project and close Pro.

Without it, workspace projects open over Australia.

### 4. Make the starter project

```powershell
cd X:\epups-spatial
& "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat" scripts\make_starter_project.py
```

This makes `source_data\ePUPS_Start.aprx`: a read-only ArcGIS Pro project with the ePUPS toolbox already attached, showing protected lands and the BC boundary. Editors open it to start. Rerun it if the template or the toolbox location changes (close the starter in Pro first).

## Editing permits (the workflow)

**1. Create the workspace.** Double-click `source_data\ePUPS_Start.aprx` in File Explorer. ArcGIS Pro opens with the **ePUPS** toolbox in the Catalog pane (**Toolboxes**) and the Geoprocessing pane (**Toolboxes** > **Project**). Run **1. Create Workspace** with your user ID, and leave **Where to work** as **Make a separate project and open it**.

It copies production into a new workspace, `ePUPS_Temp_Workspace` (numbered `_1`, `_2` if taken), and makes its own project next to it, which opens in a new ArcGIS Pro window: a map of the workspace, opened on BC, with the toolbox attached and the workspace as the default geodatabase. Close the starter window; do everything else in the workspace project. To come back to a draft, double-click that workspace's `.aprx` in `source_data\epups_workspaces`.

Each tool fills in the workspace; the editor tools also fill in the editor's ID.

> **Save with Edit > Save.** In Pro, drawing and the tools' changes stay in Pro until you click **Edit** tab > **Save**. Ctrl+S saves only the project. Each tool reminds you.

| Step | Who | Tool | What you enter | What it does |
|---|---|---|---|---|
| 2 | Editor | **2. Start or Resume Permit** | Your ID; an **Action**: *Start a new permit*, *Edit an existing permit* (search by authorization ID, or use a polygon selected on the map; change reason required), or *Resume a draft* (from a list of drafts); optionally the source type, reference, date and note | A new permit gets the next authorization ID. Makes or resumes the permit's `DRAFT` version, created by you, and adds the "Drawing:" layer and template for it |
| 3 | Editor | *Draw and edit* | Draw with the "Drawing:" template in Create Features, reshape or delete polygons, then **Edit** > **Save** | New polygons get their `SPATIAL_ID`, the permit and the source details automatically |
| 4 | Editor | **3. Finish or Save Draft** | Your ID; the permit; **Save as draft** or **Finish and submit for review**; optionally the spatial effective date | Gives every edited permit its version and moves all its polygons onto it. Draft: stays `DRAFT`, to resume later with step 2. Finish: `SUBMITTED`. Records you as last editor and removes the "Drawing:" layer |
| 5 | Checker | **4. Check Workspace (QA)** | Your ID | Runs the QA checks, writes a report to `X:\epups-spatial\logs`, and writes each polygon's result (`PASS`, `NEEDS_REVIEW` or `FAIL`), with your ID, the date and the problems. Failing polygons are selected and shown in red in a "QA: failing polygons" layer |
| 6 | Reviewer | **5. Review Permit Version** | Your ID; a submitted version, from a list; Approve or Return to editor; a note | Approve: re-runs QA, refuses if the version's polygons have errors, otherwise `APPROVED`. Return: back to `DRAFT` with your note. Records you as reviewer |

To edit existing polygons of a permit, choose *Edit an existing permit* in step 2 (it makes the next version), or just edit and save: step 3 finds the edits and makes the version. **Working in your own project instead.** Add the toolbox to your Favorites once (**Catalog** pane > right-click **Toolboxes** > **Add Toolbox** > `X:\epups-spatial\ePUPS.pyt`, then right-click **ePUPS** > **Add To Favorites**). Then in any project you own, run Create Workspace with **Where to work** set to **Set it up in this project**: the open project gets the workspace map. The command line also works: `scripts\create_workspace.py --editor 7` makes the workspace and its own project, and opens it. Step-by-step instructions, with what to expect, are in [WORKSPACE_SETUP.md](epups-spatial/docs/WORKSPACE_SETUP.md).

### Example with the demo data

Authorization `6812345` has version 1 (current, polygons 1 and 2) and version 2 (draft, polygon 3). Authorization `7000001` has version 3 with polygon 4.

1. Open `ePUPS_Start.aprx` and run **Create Workspace**, editor 7: all four polygons are copied, and the `ePUPS_Temp_Workspace_N` project opens.
2. **Start or Resume Permit**: editor 7, Action **Start a new permit**, source type `GEOMARK`, reference `GM-1234`. The tool says it will be authorization `7000002`. It makes version 1 (`VERSION_ID` 4), and the map gets "Drawing: authorization 7000002 (version 1)".
3. Draw two polygons inside the park with that template and save. They get `SPATIAL_ID` 5 and 6, `VERSION_ID` 4, `GEOMARK` and `GM-1234`.
4. **Finish or Save Draft**, permit `7000002`, **Save as draft**. Later, **Start or Resume Permit**, Action **Resume a draft**, shows "7000002 - 2 polygons, version 1 draft in progress". Pick it, draw a third polygon, save, then **Finish and submit for review**.
5. **Check Workspace** with checker 9: FAIL with 2 errors. Polygons 3 and 4 (the demo data) sit outside protected land on purpose; they're selected and outlined in red. The new polygons show `PASS`, checked by 9.
6. **Review Permit Version**, reviewer 9, approve `7000002` version 1: approved, because its own polygons pass. Approving a version of `6812345` would be refused until polygon 3 is fixed.

### From the command line instead

Every tool has a script that does the same thing:

```powershell
cd X:\epups-spatial
$propy = "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat"

& $propy scripts\create_workspace.py --editor 7
& $propy scripts\start_authorization.py "<workspace.gdb>" new --editor 7 --source-type GEOMARK --source-ref GM-1234
& $propy scripts\start_authorization.py "<workspace.gdb>" 6812345 --editor 7 --reason "Trail realigned"   # edit existing
& $propy scripts\finish_edits.py "<workspace.gdb>" --editor 7 --permit 7000002             # save as draft
& $propy scripts\finish_edits.py "<workspace.gdb>" --editor 7 --permit 7000002 --submit --effective-date 2026-11-01   # finish
& $propy scripts\qa_validate.py "<workspace.gdb>" --checker 9
& $propy scripts\review_version.py "<workspace.gdb>"                       # list versions
& $propy scripts\review_version.py "<workspace.gdb>" 4 --reviewer 9 --approve
```

`create_workspace.py` prints the workspace path to use in the later commands.

## Commands

| Script | What it does | Notes |
|---|---|---|
| `scripts\create_workspace.py` | Copies production into a new workspace, builds its project with the toolbox, and opens it | `--editor <ID>`. `--copy-auth <ID> ...` copies only those authorizations; `--empty` copies nothing. `--name`, `--folder`, `--no-open`, `--no-project` |
| `scripts\start_authorization.py <gdb> <ID or new>` | Starts or resumes a permit for new polygons. `new` assigns the next authorization ID | `--editor` (required), `--reason` (required when editing an existing permit), `--source-type`, `--source-ref`, `--source-date`, `--source-note` |
| `scripts\finish_edits.py <gdb>` | Saves edits as new versions; with `--permit`, saves that permit as a draft or, with `--submit`, finishes it | `--editor` (required), `--permit`, `--submit`, `--effective-date`, `--reason` |
| `scripts\qa_validate.py <gdb> ...` | Runs the QA checks and writes a report to `logs` | `--checker <ID>` also writes the results onto each polygon. Exits with code 1 on any error |
| `scripts\review_version.py <gdb> [VERSION_ID]` | Lists versions to review, or approves or returns one | `--reviewer`, and `--approve` or `--return "note"` |
| `scripts\create_project.py <gdb>` | Makes the ArcGIS Pro project for an existing workspace | `--open` opens it. The toolbox runs it in a separate process, so the new project doesn't open read-only. Also remakes a deleted `.aprx` |
| `scripts\test_arcpy_environment.py` | Checks ArcPy and share access | Run first on a new VDI session |
| `scripts\apply_attribute_rules.py <gdb>` | Adds or updates the attribute rules | Brings an existing workspace or production up to the current rules |
| `scripts\promote_to_prod.py` | Placeholder | Not built yet |

### Building production (database owner)

Run these in order. Each is safe to rerun.

| Script | What it does |
|---|---|
| `scripts\build_production.py` | Creates or completes the production database, including domains, indexes, the version-to-polygon relationship and the attribute rules |
| `scripts\fetch_reference_data.py` | Copies the protected lands and BC boundary layers into production, and logs the source |
| `scripts\build_topology.py` | Creates `ePUPS_Topology` (polygons covered by protected land and by BC), validates it, and exports the errors |
| `scripts\make_starter_project.py` | Makes the read-only starter project `source_data\ePUPS_Start.aprx`, with the toolbox attached. Run after `fetch_reference_data.py` and the project template |

### Tests and demo data (test data only)

Do not run these against a database that holds real records.

| Script | What it does |
|---|---|
| `tests\seed_production.py` | Adds the demo records to dev production: two authorizations, three versions and four polygons placed around a real protected area (two inside, one crossing the edge, one outside). Refuses if versions exist |
| `tests\test_attribute_rules.py <fresh workspace>` | Tries bad inserts (each should be rejected), automatic IDs and the area calculation. 12 checks. Make the workspace with `create_workspace.py --name rules_demo --empty --no-project` |
| `tests\test_versioning.py` | Runs the whole workflow on a copy of authorization 6812345: edit, finish, a new permit with an assigned ID and source details, draft, resume, submit, QA write-back, approval and refusal. 19 checks. Needs the seeded demo data |
| `tests\make_bad_workspace.py` | Creates a workspace with planted errors. QA should fail on it |
| `tests\list_topology_errors.py` | Lists the topology errors exported by `build_topology.py` |
| `tests\diagnose_geometry.py <gdb>` | Lists polygons and their geometry checks, for troubleshooting |
| `tests\reset_dev_data.py` | Deletes dev production and every workspace and project in the workspace folder. Lists only, unless run with `--yes`. Refuses unless production is the dev copy |

## Where things are

| Path | Purpose |
|---|---|
| `epups-spatial/ePUPS.pyt` | The ArcGIS Pro toolbox |
| `epups-spatial/epups/` | Shared package: paths (`config`), schema, builder, workspace, project, versioning, drawing, validation, review, rules |
| `epups-spatial/arcade/` | Attribute rule logic, in Arcade |
| `epups-spatial/scripts/` | Command-line tools |
| `epups-spatial/tests/` | Test and demo scripts |
| `epups-spatial/logs/` | QA reports and the reference data log (git ignored) |
| `epups-spatial/docs/WORKSPACE_SETUP.md` | Step-by-step guide for editors, checkers and reviewers |
| `epups-spatial/docs/DECISIONS.md` | Confirmed decisions and open questions |
| `source_data\epups_spatial_dev\` | Dev production database (on the share, not in git) |
| `source_data\epups_workspaces\` | Editor workspaces and their projects |
| `source_data\templates\` | The project template |
| `source_data\ePUPS_Start.aprx` | The starter project editors open (read-only) |

## Status

| Area | Status |
|---|---|
| Production schema, workspaces and projects | Built and tested on the VDI |
| ArcGIS Pro toolbox | Full workflow run on the VDI from the starter project, and the data checked (2026-10-30): new permit, draft, resume, finish, QA fail and fix, review. Save reminders, the other-permits warning and the extra-table QA warning were added after that run |
| Automatic IDs | Built and tested in ArcGIS Pro (2026-10-29). Automatic authorization IDs for new permits added the same day, not yet tested |
| New versions on edit | Built and tested on the VDI (2026-10-29). Rerun `tests\test_versioning.py` (now 19 checks) for the new flow |
| Source details on new polygons, QA write-back, review | Built 2026-10-29. Not yet tested on the VDI |
| Attribute rules | 15 rules. Tested on the VDI (`tests\test_attribute_rules.py`, 12 of 12, 2026-10-29) before the four source-detail rules were added |
| QA/QC checks | Built and tested, including planted errors |
| Topology (protected lands and BC boundary) | Built and runs on the VDI |
| Picklists (domains) | Built from the DBML. Values still to confirm |
| Promotion into production, archiving and backups | Not started. Waits on the production server decision |
| Permit dates and CORRAL sync | Not started. Waits on the source of permit dates |

Workspaces made before 2026-10-29 (schema 0.3) don't have the editor and default fields. Create a new workspace for the toolbox.

## Next steps and open decisions

- **Authorization IDs.** New permits get the next number after production's highest. Real authorization IDs come from CORRAL, so once the CORRAL link is set up, the ID should probably be taken from there instead.
- **Version statuses.** `SUBMITTED` was added for the review step; it isn't in the DBML. Confirm with the design owner.
- **Drafts across workspaces.** A draft lives in its workspace until it's promoted, so you come back to it by reopening that workspace's project. Keeping drafts in production, so any new workspace can pick them up, waits on promotion.
- **User IDs.** Where the user IDs come from, and filling the `users` table. Until it has rows, any ID is accepted; after that, the tools warn about an ID that isn't in it.
- **Promotion.** Moving an approved version into production, making it current, and marking the old version `SUPERSEDED`.
- **Hand-over.** Where a passed workspace geodatabase is placed, and how the upload owner is told.
- **Finalize the schema.** Confirm the fields, picklist values and units with the design owner. Polygons don't have their own created-by field in the DBML; who drew them is recorded on their version.
- **Link existing polygons.** Load the polygons made so far into production, with their authorizations and versions.
- **Archiving.** Turn on geodatabase archiving in production, so every version's polygons stay retrievable after edits. This depends on the production platform.
- **Production platform.** Which server, and how it affects locking, owner-qualified names and promotion.
- **ID assignment across workspaces.** Each workspace pulls current production when it's made, so its new IDs start above production's. Two workspaces open at the same time can still hand out the same new `SPATIAL_ID` or `VERSION_ID`. Final IDs may instead be assigned at promotion.
- **Workspace size.** A workspace copies all of production. If production grows large, copying only the authorizations being edited (`--copy-auth`) may become the better default.
- **Permit dates.** How issue and expiry dates reach this database. A scheduled CORRAL extract is the chosen approach; the owner and frequency aren't agreed.

## Working conventions

- `main` holds only work that has passed a VDI run. Work happens on a feature branch and is merged after testing.
- Commits and pushes are run by the person working on the repo, not by the tools.
- Local planning notes live in `PLANNING.local.md`, which git ignores.
