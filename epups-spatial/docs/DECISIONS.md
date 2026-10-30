# Design Decisions and Open Questions

Record confirmed decisions here, including the date and rationale.

## Confirmed

- **2026-10-29: Editing a permit makes a new version.** When an authorization's polygons are added, changed or deleted in a workspace, it gets a new version: `VERSION_NUMBER` one higher, status `DRAFT`, not current. All the authorization's polygons move onto it. One workspace makes one new version per authorization. *Why:* each version holds the whole permit as it stands, and `SPATIAL_ID` stays unique, because polygons are moved rather than copied. Keeping older versions' shapes is left to archiving in production.
- **2026-10-29: IDs are assigned automatically.** New polygons get the next `SPATIAL_ID` above the workspace and production. They link to the permit started with Start or Resume Permit, or else the newest version made in the workspace. If none was made, they link to the current version, but only when the workspace holds exactly one; otherwise the save is rejected rather than guessing the permit. *Why:* editors shouldn't type IDs.
- **2026-10-29: People are recorded by user ID, not name.** The toolbox asks for `users.UserID` at each step. It records it as the version's `CREATED_BY`, `LAST_EDITED_BY` and `REVIEWED_BY`, and as each polygon's `QA_CHECKED_BY`. Approval is refused while the version's polygons have QA errors.
- **2026-10-29: New permits get the next authorization ID.** The ID is one above the highest in production and the workspace, not typed in. A change reason is required when editing an existing permit (it makes a new version), not for a new permit. The spatial effective date is entered when the permit is finished or saved as a draft. *To revisit:* real IDs come from CORRAL.
- **2026-10-29: Drafts and submission.** An editor saves a permit as `DRAFT` to come back to, or finishes it as `SUBMITTED`. Only submitted versions are reviewed; returning one sets it back to `DRAFT`. `SUBMITTED` is a new status, not in the DBML, to confirm with the design owner. While drawing, a "Drawing: authorization …" layer and template show which permit the polygons are added to.
- **2026-10-30: Editors start from a shared starter project.** `source_data\ePUPS_Start.aprx` is read-only and has the toolbox attached, so nobody adds it by hand. Create Workspace run from it makes each workspace its own project (with the toolbox) and opens it. The whole workflow then runs there, with no command line. People who prefer their own project add the toolbox to Favorites, and Create Workspace can set up the open project instead.
- **2026-10-29: A workspace copies all of production by default.** Each new workspace pulls production fresh, so it knows what already exists. The workspace project includes the ePUPS toolbox. `--copy-auth` and `--empty` remain as options. This is an interim approach until the ID decision below is made.

## Open items

- Confirm the production database platform.
- Resolve whether source/provenance fields are included.
- Resolve which geometry QA fields are required.
- Confirm the source and refresh process for CORRAL authorization data.
- Confirm boundary validation requirements.
- Confirm the source of user IDs and editor identity.
- Confirm version ID generation and promotion mapping.
- Confirm how current versions are enforced.
