# Setting up and checking an ePUPS workspace

Written for: editors and reviewers who create and check workspaces in ArcGIS Pro on the VDI.

A workspace is a temporary copy of the ePUPS spatial database. You draft changes there, check them, and only then do they move toward production. Editors never change production directly.

## Before you start

- Use the VDI, where ArcGIS Pro and ArcPy are installed. The steps were tested with ArcGIS Pro 3.4.3.
- Map the project folder to drive `X:` so the scripts can be run from it. Run this once per session:

  ```powershell
  net use X: \\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\tools\PUPS
  cd X:\epups-spatial
  ```

- You need read access to the production geodatabase (`source_data\epups_spatial_dev\epups_spatial_dev.gdb` for now) and write access to the workspace folder (`source_data\epups_workspaces`).

> Command-line tools fail when run from a network path that starts with `\\`. Always work from the `X:` drive.

## Step 1: Create your workspace

You can create a workspace in two ways. Both give the same result.

### Option A: ArcGIS Pro Python window

On the **Analysis** tab, open **Python**, and paste these lines one at a time:

```python
import sys
sys.path.insert(0, r"X:\epups-spatial")

from epups import workspace

# Copy only the records for the authorizations you are working on.
gdb = workspace.create_workspace("auth_6812345", authorization_ids=[6812345])
print(gdb)
```

### Option B: Command line

Open PowerShell and run one of these from `X:\epups-spatial`. Use the ArcGIS Pro Python path from your install if it differs.

```powershell
$propy = "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat"

& $propy scripts\create_workspace.py my_edits                          # empty workspace
& $propy scripts\create_workspace.py auth_6812345 --copy-auth 6812345  # production records for one authorization
& $propy scripts\create_workspace.py full_copy --copy-all              # every production record
```

### Choosing the copy option

- **Empty.** For new polygons only.
- **`--copy-auth` (or `authorization_ids`).** For revising or adding to existing permits. Copies the version rows for those authorizations first, then the polygons that belong to those versions.
- **`--copy-all`.** Only when you need every production record.

### What you get

The path to the new geodatabase prints at the end. It is named `ws_<label>_<date>_<time>.gdb`, for example `ws_auth_6812345_20261028_093000.gdb`, and it is saved in `source_data\epups_workspaces`. Copy this path exactly. You will need it for the check.

The workspace contains:

| Object | What it holds |
|---|---|
| `SpatialData\ePup_Spatial` | The permit polygons |
| `ePup_Spatial_Version` | One row per permit version, with its authorization and status |
| `users` | User records |
| `SpatialData\ePup_Version_Polygons` | The link from each version to its polygons, on `VERSION_ID`. Identify a polygon to see its version and authorization |
| `Workspace_Info` | One row saying where the workspace came from, who made it, and which records were copied |

The workspace also has the attribute rules, which run when you edit it in ArcGIS Pro. The rule list is in `epups/rules.py`.

### What to look for

- The path prints without an error, and the output ends with `SUCCESS: Workspace ready`.
- The output lists the three domains (`ePup_Version_Status`, `ePup_Source_Type`, `ePup_Geometry_QA_Status`).
- If you copied records, the version and polygon counts match what you expected for those authorizations.

## Step 2: Draft your changes in ArcGIS Pro

Add your work to the workspace the same way you would in production.

1. Add version rows to `ePup_Spatial_Version` before the polygons that belong to them. Each version needs an `AUTHORIZATIONID`, a `VERSION_NUMBER` that is not already used for that authorization, and a `VERSION_STATUS`.
2. Add polygons to `ePup_Spatial`. Each polygon needs a `SPATIAL_ID` that is not used by any other polygon, and a `VERSION_ID` that exists in `ePup_Spatial_Version`.
3. Leave `AREA_HA` empty. The attribute rule fills it from the shape.
4. Only one version per authorization can be marked current (`IS_CURRENT` = 1).

The attribute rules stop a save that breaks these rules and show the message. Until the ID assignment decision is made, agree on a `SPATIAL_ID` range with the group for your workspace.

## Step 3: Check the workspace

Run the QA check on the workspace before you hand it over. It reads the whole workspace and lists every problem it finds. It does not change the workspace.

### Option A: ArcGIS Pro Python window

```python
from epups import validation

ws = r"\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\source_data\epups_workspaces\ws_auth_6812345_20261028_093000.gdb"

issues = validation.run_all(ws)
errors, warnings = validation.count_by_severity(issues)

for issue in issues:
    print(issue.severity, issue.check, issue.record, issue.message)

print("PASS" if errors == 0 else "FAIL", errors, "errors", warnings, "warnings")
```

Replace the path with the one that Step 1 printed.

### Option B: Command line

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat" scripts\qa_validate.py "<path to workspace>"
echo $LASTEXITCODE
```

This also writes a report to `X:\epups-spatial\logs`. The report name includes the workspace name. The exit code is `1` if there are any errors.

### Reading the result

- **PASS, 0 errors.** The workspace is ready to hand over. Warnings can stay, but a reviewer should look at them.
- **FAIL.** Each error names the record and the problem. Fix them in the workspace and run the check again.

Examples from a planted-error test (`logs\qa_ws_qa_negative_20261028_085119.txt`):

```
ERROR    geometry      OBJECTID 1    null geometry
ERROR    spatial-id    SPATIAL_ID 1  Duplicate SPATIAL_ID appears 2 times
ERROR    version-link  OBJECTID 3    VERSION_ID 999 not found in ePup_Spatial_Version
WARNING  version-link  AUTHORIZATIONID 1  2 current versions; expected at most one
ERROR    reference     OBJECTID 2    Polygon is outside protected land
ERROR    reference     OBJECTID 2    Polygon is outside the BC boundary
```

### What the check covers

- **Structure and schema.** The tables, fields, domains and schema version match production. A workspace built with an older schema fails this check. Create a new workspace and move your work into it.
- **Geometry.** Every polygon has a shape, uses EPSG:3005, and is valid.
- **Required values and picklists.** Required fields are filled, and coded values are in their domain.
- **Keys and links.** `SPATIAL_ID` and `VERSION_NUMBER` are unique, and every `VERSION_ID` exists.
- **Area.** `AREA_HA` matches the shape. A difference of more than 0.1% (and at least 0.01 ha) is a warning.
- **Protected land and BC boundary.** Every polygon must lie inside protected land and inside the BC boundary. These layers are read from production, so the check needs production to be reachable. If they are missing, the check reports a warning and skips them.

## Step 4: Hand over the workspace

1. Keep the QA report with the workspace. The report is in `logs`, and its name includes the workspace name.
2. Tell the upload owner which workspace passed, and when.
3. The upload owner moves the records into production. This step is not built yet.

> **Open questions for the upload:** who runs it, where passed workspaces are placed for it, and whether the QA check is run again before records are added.

## Common problems

- **`propy.bat` fails with an error about a path.** You are running from a `\\` network path. Map a drive letter and run from `X:`.
- **The script can't find the project.** Check that `X:` is mapped and that you are in `X:\epups-spatial`.
- **A workspace path doesn't open, or every insert fails with "cannot open".** Copy the exact path that the create step printed, including the date and time in its name. The attribute rule test stops with a message in this case.
- **"Cannot be updated outside an edit session".** The edit was made to a topology-managed record without an edit session. Start an edit session in ArcGIS Pro and make the edit inside it.
- **"Cannot get exclusive schema lock".** Another application is using the geodatabase. Close ArcGIS Pro completely, including any Catalog connection and any map that uses its layers, then run the script again.
- **"Violated attribute constraint rule".** A rule rejected your edit. The message after it says which rule. Fix the value and save again.
- **QA reports `reference` warnings.** Production's reference layers are missing. Ask the database owner to run `scripts\fetch_reference_data.py`.
