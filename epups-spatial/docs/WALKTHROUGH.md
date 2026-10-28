# ePUPS Workspace Walkthrough

How the park use permit database is organised, and how to create a working space in ArcGIS Pro, check it, and get it ready for the upload.

## 1. How the system fits together

The system has one production database and a set of temporary workspaces. Editors never change production directly. They draft changes in a workspace, check the workspace with the QA script, and only QA-passed records move toward production.

| Piece | What it is | Who uses it |
|---|---|---|
| Production geodatabase | The authoritative permit data. Holds the polygons, their versions, users, and reference layers. | Read by everyone; changed only through the upload process |
| Editor workspace | A separate geodatabase with the same structure as production. Empty, or filled with copies of production records for chosen authorizations. | Any editor with access; created for each piece of work |
| QA check | A script that reads a workspace and reports problems. It writes a report, and any error means the workspace is not ready. | Editors before upload; reviewers |
| Reference layers | The BC boundary and the protected lands (parks, ecological reserves, protected areas), copied into production from public sources. | Used by the topology check in production |
| Topology | A rule set in production: each permit must sit inside protected land and inside the BC boundary. Permits may overlap each other. | Checked in production with the Error Inspector |

### What is inside the production geodatabase

- **SpatialData** (feature dataset): `ePup_Spatial` (the permit polygons), `Ref_Protected_Lands`, `Ref_BC_Boundary`, and `ePUPS_Topology`.
- **Tables**: `ePup_Spatial_Version` (one row per permit version, with its authorization and status) and `users`.

Every polygon has a stable `SPATIAL_ID`. It stays the same when a record is copied into a workspace, so QA and promotion can match it back to production. `OBJECTID` is set by ArcGIS and can change when records are copied.

### Where the code lives

- `epups`: the shared code (paths, schema, creating workspaces, the QA checks).
- `scripts`: the commands an editor or administrator runs.
- `tests`: test and demo scripts, which work on test data only.
- `arcade`: the attribute rule logic.
- `logs`: QA reports and the reference data log.

## 2. Before you start

- Use the VDI, where ArcGIS Pro and ArcPy are installed.
- Map the project folder to a drive letter, `X:`, so the scripts can be run from it. The script commands below assume this.
- You need access to the production geodatabase and to the workspace folder.

> Running the scripts from a network path (starting with `\\`) fails for command-line tools. Always work from the mapped drive letter.

## 3. Step A: create your temporary working space

You can do this in ArcGIS Pro's Python window (on the **Analysis** tab, **Python**), without the command line. Paste the lines in one at a time.

```python
import sys
sys.path.insert(0, r"X:\epups-spatial")

from epups import workspace

# Copy only the records for the authorizations you are working on.
gdb = workspace.create_workspace("auth_6812345", authorization_ids=[6812345])
print(gdb)
```

The output is the path to your new workspace, which is named with your label and the date and time. It sits in the workspace folder and holds the full schema, plus the production records you chose to copy.

Give the label a clear name, such as the authorization number or the task. Leave out `authorization_ids` to start with an empty workspace for new polygons only. Use `copy_all=True` only when you need every production record.

### What to look for

- The path prints without an error.
- If you copied records, the version and polygon counts match what you expected for those authorizations.

## 4. Step B: check the workspace before upload

Run the QA check on your finished workspace. It reads the whole workspace and reports every problem it finds.

```python
from epups import validation

ws = r"\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\source_data\epups_workspaces\auth_6812345_20261028_093000.gdb"

issues = validation.run_all(ws)
errors, warnings = validation.count_by_severity(issues)

for issue in issues:
    print(issue.severity, issue.check, issue.record, issue.message)

print("PASS" if errors == 0 else "FAIL", errors, "errors", warnings, "warnings")
```

Replace the path with the one `create_workspace` printed for your workspace. The check also works from the command line, where it writes a report to the project's `logs` folder:

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat" scripts\qa_validate.py "<path to workspace>"
echo $LASTEXITCODE
```

### Reading the result

- **PASS, 0 errors.** The workspace is ready for the upload. Warnings can stay, but a reviewer should look at them.
- **FAIL.** Each error names the record and the problem, such as a missing value, a duplicate `SPATIAL_ID`, a version that doesn't exist, or a geometry error. Fix those in the workspace and run the check again.
- **Schema version message.** The workspace was made with an older schema. Create a new workspace and move your work into it.

### What the check covers now

- **Protected land and boundary.** Every polygon is checked against the protected lands and the BC boundary held in production. A polygon outside either one is an error, so it fails in the workspace, not later in production. The check needs the production database to be reachable.
- **Attribute rules.** Every new workspace gets the attribute rules automatically. Duplicate IDs, a second current version for an authorization, and the area calculation all work in a workspace, as they do in production.

## 5. Getting it into the daily upload

Once a workspace passes the check, it is ready to hand over. The upload itself is not automated yet. The steps below are a placeholder until the upload process is confirmed.

1. Keep the QA report and the workspace together. The report is in the project's `logs` folder, and its name includes the workspace name.
2. Tell the upload owner which workspace passed, and when.
3. The upload owner moves the records into production. This step is not built yet, and we need to agree how it will work, including who runs it and when.

> **Open questions for the upload:** who runs the daily upload, where passed workspaces are placed for it, and whether the upload owner runs the QA check again before adding records.

## 6. What I'd like to do next

The next step is a test run that goes from the digitized permit data all the way to a production-ready check, without changing the live database.

### Goal

Show the full path works end to end, with real data:

1. Bring in the permit polygons already digitized, in the `park_use_permit_digitization` geodatabase (about 843 records).
2. Join them to the CORAL authorization records we want in the revised ePUPS system (`pu_authorization`: authorization ID and number, type, commencement date, and expiry date).
3. Load the joined result into a test workspace, which gets the rules automatically.
4. Run the QA check on that workspace, and fix what it reports.
5. Do a dry run of promotion: count the records that would be added to production and list any that would be rejected. Nothing is written to production.

### Things to find out in the first run

- **Missing authorization IDs.** The digitized table already has records with an empty authorization ID or number. These can't be joined to CORAL, so each one needs a decision: fix it, or hold it back.
- **Date fields.** Commencement and expiry dates from CORAL are the basis for the date rules and the expired status. The join is how they first reach the new system.
- **Protected land and boundary.** How many digitized polygons fall outside protected land or the BC boundary. That tells us how much the QA check will flag before anyone is asked to change anything.
- **Permit IDs.** Each digitized polygon needs a `SPATIAL_ID`. Until the ID decision is made, the test uses a reserved range set aside for the test workspace.

### What this needs from you

- A CORAL extract of `pu_authorization` for the authorizations in the digitized data, or access to read it.
- Confirmation of which digitized records are current, such as the `STATE` field.
- A decision on the ID range for the test, since no production IDs exist yet.

## 7. Common problems

- **"Cannot be updated outside an edit session".** This appears when editing production records that belong to the topology. Those edits must be made inside an edit session.
- **"Cannot get exclusive schema lock".** Another application is using the production geodatabase. Close ArcGIS Pro completely, including any Catalog connection to the geodatabase and any map that uses its layers, then run the script again.
- **The script can't find the project.** Check that `X:` is mapped and that the path to the `epups` folder is correct.
- **A workspace path doesn't open.** Copy the exact path that the script printed, including the date and time in its name.

---

*Written from the project as it stands. Tested on the VDI with test data. The upload process and the production server are still to be decided.*
