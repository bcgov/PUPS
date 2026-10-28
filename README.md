# PUPS: ePUPS Spatial Database

Tools for the ePUPS spatial database: park use permit polygons, the version history behind them, and the checks that keep bad data out of production.

## What it does

- **Production database.** One file geodatabase holds the permit polygons (`ePup_Spatial`), their versions (`ePup_Spatial_Version`), and users. The schema follows the co-worker DBML design.
- **Editor workspaces.** Anyone with access can create a temporary copy of the schema, optionally filled with production records for chosen authorizations, and draft changes there.
- **QA/QC.** A checker reviews a workspace before its records go to production. Errors block promotion; warnings need a reviewer decision.
- **Attribute rules.** Rules that run inside ArcGIS Pro when someone edits: unique primary keys, one current version per authorization, and the hectare area calculated from the shape.
- **Topology.** Every permit polygon must sit inside protected land (BC Parks, Ecological Reserves, and Protected Areas) and inside the BC boundary. Permits may overlap each other.
- **Promotion and backups.** Not built yet. Both wait on the production server decision.

## Where things are

| Path | Purpose |
|---|---|
| `epups-spatial/epups/` | Shared package: paths, schema, builder, workspace, validation, rules |
| `epups-spatial/scripts/` | Commands you run |
| `epups-spatial/tests/` | Test and demo scripts (test data only) |
| `epups-spatial/arcade/` | Attribute rule logic, in Arcade |
| `epups-spatial/logs/` | QA reports and the reference data log (git ignored) |
| `epups-spatial/docs/WORKSPACE_SETUP.md` | How to create and check a workspace in ArcGIS Pro (for editors) |
| `epups-spatial/docs/DECISIONS.md` | Confirmed decisions and open questions |

## Running the tools

ArcGIS Pro and ArcPy only run on the VDI. Use ArcGIS Pro's Python and run from the `epups-spatial` folder on a drive letter. `propy.bat` is a `cmd` script and fails from a UNC path:

```powershell
net use X: \\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\tools\PUPS
cd X:\epups-spatial
& "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat" scripts\<script>.py
```

Paths in the examples below use the `\\spatialfiles.bcgov\...` form, which works as an argument. The scripts print the paths they create.

### Commands

| Script | What it does | Notes |
|---|---|---|
| `scripts\test_arcpy_environment.py` | Checks ArcPy and share access | Run first on a new VDI session |
| `scripts\build_production.py` | Creates or completes the production database | Safe to rerun; adds missing fields and indexes |
| `scripts\create_workspace.py <label>` | Creates an empty editor workspace | Add `--copy-all` or `--copy-auth <AUTHORIZATIONID> ...` to copy production records |
| `scripts\qa_validate.py <workspace.gdb>` | Runs the QA checks and writes a report to `logs` | Exits with code 1 on any error |
| `scripts\apply_attribute_rules.py <gdb>` | Adds GlobalIDs and the attribute rules | Needed for each geodatabase that should enforce the rules |
| `scripts\fetch_reference_data.py` | Copies the protected lands and BC boundary layers into production | Overwrites the copies; logs the source of each run |
| `scripts\build_topology.py` | Creates `ePUPS_Topology` with the two covered-by rules and validates it | Run after `fetch_reference_data.py` |
| `scripts\promote_to_prod.py` | Placeholder | Not built yet |

### Tests and demo (test data only)

| Script | What it does |
|---|---|
| `tests\make_bad_workspace.py` | Creates a workspace with planted errors. Run `qa_validate.py` on it; it should fail. |
| `tests\seed_production.py` | Adds three versions and four test polygons to the dev production database, placed around a real protected area: two inside, one crossing the edge, one outside protected land. Run after `fetch_reference_data.py` and before `build_topology.py`. Refuses to run if versions exist. |
| `tests\test_attribute_rules.py <fresh workspace>` | Tries bad inserts (each should be rejected) and checks the area calculation. Use a fresh workspace. |
| `tests\list_topology_errors.py` | Lists the topology errors exported by `build_topology.py`, with the polygon each one refers to. |
| `tests\reset_dev_data.py` | Deletes the dev production database and the `ws_*` test workspaces, so the demo data can be rebuilt. Lists only, unless run with `--yes`. Refuses to run unless production is the dev stand-in. |
| `tests\diagnose_geometry.py <workspace.gdb>` | Lists polygons and their geometry checks, for troubleshooting. |

Do not run the test or seed scripts against a database that holds real records.

## Status

| Area | Status |
|---|---|
| Production schema and workspace tool | Built and tested on the VDI |
| QA/QC checks | Built and tested, including planted errors |
| Picklists (domains) | Built from the DBML. Values to confirm with the design owner. |
| Attribute rules | Built and tested on the VDI (8 of 8 checks, 2026-10-28). Not yet applied to production. |
| Topology (protected lands and BC boundary) | Built and runs on the VDI. Error count and valid-polygon check still to be confirmed in ArcGIS Pro. |
| Promotion into production | Not started. Waits on the production server decision. |
| Backups | Not started. Waits on the production server decision. |
| Permit date rules and CORRAL sync | Not started. Waits on the source of permit dates. |
| Automatic IDs | Not started. Waits on the decision on how IDs are assigned. |

## Open decisions

- **Production platform:** which server or system, and how that affects locking, owner-qualified names, and promotion.
- **Permit dates:** how issue and expiry dates reach this database (a scheduled CORRAL extract is the chosen approach; the owner and frequency are not yet agreed).
- **Automatic IDs:** reserve a number range per workspace, or assign production IDs at promotion.
- **Picklist values:** confirm the values for the three domains.
- **Area units:** hectares, with a warning when the stored value differs from the geometry by more than 0.1%.

## Working conventions

- `main` holds only work that has passed a VDI run. Work happens on a feature branch and is merged after testing.
- Commits and pushes are run by the person working on the repo, not by the tools.
- Local planning notes live in `PLANNING.local.md`, which git ignores.
