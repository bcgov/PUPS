# PUPS: ePUPS Spatial Database

Tools for the ePUPS spatial database: park use permit polygons, the version history behind them, and the checks that keep bad data out of production.

Editors never change production directly. An editor creates a temporary workspace, draws or edits polygons in ArcGIS Pro, and saves the changes as a new permit version. A checker runs QA, and a reviewer approves the version. Only an approved version moves toward production.

**To try it,** follow [Trying the ePUPS toolbox](epups-spatial/docs/TRY_THE_TOOLBOX.md): one complete run with the demo data, in about 10 minutes.

## How it works

- **Production database.** A file geodatabase holds the permit polygons (`ePup_Spatial`), their versions (`ePup_Spatial_Version`) and users. It follows the ePUPS database design (DBML diagram). For now it is a development copy on the share.
- **Workspaces.** A workspace is a fresh copy of production with its own ArcGIS Pro project and the toolbox attached. All editing happens there.
- **The toolbox** (`ePUPS.pyt`) has five tools, used in order: Create Workspace, Start or Resume Permit, Finish or Save Draft, Check Workspace (QA), and Review Permit Version. People are identified by user ID, not by name.
- **New permits.** The authorization ID is assigned automatically. For now it is one above the highest in production; this will change to handle several people working on permits at the same time.
- **Versions.** Editing a permit makes one new version, however many polygons change or how often you save: `VERSION_NUMBER` one higher, holding all of the permit's polygons. It is `DRAFT` while being worked on, `SUBMITTED` when finished, and `APPROVED` once reviewed. It becomes current only when promoted to production.
- **Automatic values.** New polygons get their `SPATIAL_ID`, version, source details and area automatically, through attribute rules that also block invalid saves.
- **QA.** Checks structure, geometry, required values, keys and links, area, unfinished versions, and whether each polygon sits inside protected land and inside BC. Results are written onto each polygon, and failing polygons are highlighted on the map. Errors block approval.

## Setup (database owner, once)

ArcGIS Pro and ArcPy run on the VDI. Command-line tools fail from a `\\` path, so map the project folder to `X:` first:

```powershell
net use X: \\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\tools\PUPS
cd X:\epups-spatial
$propy = "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat"
```

1. **Production.** Run `& $propy scripts\build_production.py`, `fetch_reference_data.py`, then `build_topology.py`. Each is safe to rerun.
2. **Project template.** In ArcGIS Pro, create a Map project named `epups_workspace_template` in `source_data\templates` (untick "Create a new folder"), set the map to NAD 1983 BC Environment Albers (3005), zoom to all of BC, and save. Without it, workspace projects open over Australia.
3. **Starter project.** Run `& $propy scripts\make_starter_project.py`. It makes the read-only `source_data\ePUPS_Start.aprx`, with the toolbox attached, which editors open to begin.

Demo data for testing: `& $propy tests\seed_production.py` (dev production only).

## Command-line tools

Each toolbox tool has a script that does the same thing, in `epups-spatial\scripts`:

| Script | Toolbox tool |
|---|---|
| `create_workspace.py --editor <ID>` | 1. Create Workspace |
| `start_authorization.py <gdb> <ID or new> --editor <ID>` | 2. Start or Resume Permit |
| `finish_edits.py <gdb> --editor <ID> --permit <ID> [--submit]` | 3. Finish or Save Draft |
| `qa_validate.py <gdb> --checker <ID>` | 4. Check Workspace (QA) |
| `review_version.py <gdb> <VERSION_ID> --reviewer <ID> --approve` | 5. Review Permit Version |

Run any script with `--help` for its options. Tests are in `epups-spatial\tests` (`test_versioning.py`, `test_attribute_rules.py`); run them against the dev database only.

## Where things are

| Path | Purpose |
|---|---|
| `epups-spatial/ePUPS.pyt` | The ArcGIS Pro toolbox |
| `epups-spatial/epups/` | Shared package: schema, workspace, versioning, rules, QA, review |
| `epups-spatial/arcade/` | Attribute rule logic |
| `epups-spatial/scripts/`, `tests/` | Command-line tools and tests |
| `source_data\ePUPS_Start.aprx` | The starter project (on the share) |
| `source_data\epups_spatial_dev\` | Dev production database (on the share) |
| `source_data\epups_workspaces\` | Workspaces and their projects (on the share) |

## Status

Built and tested on the VDI: the production schema, workspaces, the toolbox workflow (new permit, draft, resume, finish, QA, review), attribute rules and QA.

Not built yet:

- **Promotion.** Moving an approved version into production, making it current, and marking the old one `SUPERSEDED`.
- **Archiving and backups** in production.
- **CORRAL sync** for authorization IDs and permit dates.

## Open decisions

- **Production platform.** Which server, and how it affects promotion.
- **Authorization IDs.** Real IDs come from CORRAL. Until then, how to keep two people starting new permits at the same time from getting the same ID.
- **IDs across workspaces.** Two workspaces open at once can hand out the same new IDs or version numbers. Final IDs may be assigned at promotion.
- **`SUBMITTED` status.** Added for the review step; not in the original design.
- **User IDs.** Where they come from, and filling the `users` table.
- **Schema.** Confirm the fields, picklist values and units.
