# Trying the ePUPS toolbox

The ePUPS toolbox lets an editor draft park use permit polygons in a temporary copy of the database, save them as a new permit version, check them, and have them reviewed, all inside ArcGIS Pro. This page walks you through one complete run with the demo data (about 10 minutes) and lists what to look at and what is still open.

Everything here runs against the **development** database, which holds test data only.

## Before you start

- You need access to `\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits`.
- People are identified by a **user ID** (a number), not a name. For this run, use **7** as the editor and **9** as the checker and reviewer. Any number works while the `users` table is empty.

> **Saving matters.** In ArcGIS Pro, your drawing and the tools' changes stay in Pro until you click **Edit** tab > **Save** (in the Manage Edits group). **Ctrl+S saves the project, not the edits.** Each tool ends with a yellow reminder. Click Edit > Save after drawing and after each tool.

## The walkthrough

### 1. Open the starter project

In File Explorer, double-click:

```
\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\source_data\ePUPS_Start.aprx
```

ArcGIS Pro opens on a map of BC showing protected lands. The project is read-only and shared; you only start from it. Open the toolbox from the **Catalog** pane (**View** tab > **Catalog Pane**) > **Toolboxes** > **ePUPS**. Double-click a tool to open it.

### 2. Create a workspace: tool 1

Run **1. Create Workspace** with an **Editor ID**, for example 7. Leave everything else as it is.

It copies the database into a new workspace named `ePUPS_Temp_Workspace` (numbered if taken) and opens it in a **new** ArcGIS Pro window. Close the starter window and work in the new one.

The demo data holds two permits:

| Authorization | Versions | Polygons |
|---|---|---|
| 6812345 | 1 (current), 2 (draft) | 1 and 2 inside a park; 3 crosses the park edge |
| 7000001 | 1 (current) | 4, outside protected land |

Polygons 3 and 4 are wrong on purpose, so QA has something to find.

### 3. Start a new permit: tool 2

Run **2. Start or Resume Permit**:

- **Action:** Start a new permit. The tool shows the authorization ID it will assign (7000002), so you don't type one.
- **New polygon details** (expand): pick a source type and type a source reference, for example `GM-TEST`.

When it finishes, a **"Drawing: authorization 7000002 (version 1)"** layer appears at the top of the map.

### 4. Draw: normal ArcGIS Pro editing

On the **Edit** tab, click **Create**. In the Create Features pane, pick the **Drawing:** template and draw two or three polygons **inside the green protected land**. Then click **Edit** > **Save**.

Open the `ePup_Spatial` attribute table. Your polygons should have a `SPATIAL_ID` (5 and up), `VERSION_ID`, source type and reference, and `AREA_HA`, all filled in automatically.

### 5. Save it as a draft, then come back: tools 3 and 2

1. Run **3. Finish or Save Draft**, choose **Save as draft**, then click **Edit** > **Save**. The Drawing layer goes away.
2. Run **2. Start or Resume Permit** with Action **Resume a draft**, pick 7000002, and draw one more polygon. Click **Edit** > **Save**.
3. Run **3. Finish or Save Draft** again and choose **Finish and submit for review**. Click **Edit** > **Save**.

### 6. Check it: tool 4

Run **4. Check Workspace (QA)** with **Checker ID** 9. Click **Edit** > **Save**.

Expect **FAIL with 2 errors**. Polygons 3 and 4 are outside protected land. They're selected and outlined in red in a **"QA: failing polygons"** layer. In the attribute table, every polygon now shows `GEOMETRY_QA_STATUS` (PASS or FAIL), `QA_CHECKED_BY` 9 and the date. Your new polygons pass.

### 7. Review it: tool 5

Run **5. Review Permit Version** with **Reviewer ID** 9. Pick the 7000002 version and choose **Approve**. Click **Edit** > **Save**.

It's approved, because QA runs again and the permit's own polygons pass. The demo polygons belong to other permits, so they don't block it. In `ePup_Spatial_Version`, version 7000002 shows `APPROVED`, `REVIEWED_BY` 9, and `CREATED_BY` and `LAST_EDITED_BY` 7.

### 8. Optional: fix a failing permit

Run **2. Start or Resume Permit** with Action **Edit an existing permit**:

- Find 6812345 with the search box, or select polygon 3 on the map and tick **Use the polygon selected on the map**.
- A **change reason** is required. The tool makes version 3 of that permit.

Move polygon 3 fully inside the park, **Edit** > **Save**, then finish it and run QA again. Polygon 3 now passes, and 6812345 has a new `SUBMITTED` version holding all three of its polygons.

## What isn't built yet

- **Promotion.** Approved versions don't go into the production database yet. Nothing in the workspace changes production.
- **Retiring old versions.** An approved version doesn't become current, and the old one isn't marked retired. Both wait on promotion.
- **User IDs** aren't checked against a list, because the `users` table is empty.

## If something goes wrong

- **Changes are missing, or a tool doesn't see your polygons.** The edits weren't saved. Click **Edit** tab > **Save**; Ctrl+S only saves the project.
- **"This polygon has no version to belong to".** No permit is started. Run **2. Start or Resume Permit**, then draw again.
- **No "Drawing:" template in Create Features.** Click "Click here to see templates not listed" in the pane, or draw with the `ePup_Spatial` template. The polygons still go to the permit you started.
- **The toolbox has a red X or doesn't show recent changes.** Right-click it in Catalog > **Refresh**, or restart ArcGIS Pro.
- **QA warns about a table "not part of the ePUPS schema".** An editing tool left it, for example `Links` from **Transform**. Delete it in the Catalog pane.
- **"Not approved: n errors".** The version's polygons fail QA. Choose **Return to editor**, fix them, finish again, and rerun QA.

See the [README](../../README.md) for how the pieces fit, setup, and the command-line tools.

