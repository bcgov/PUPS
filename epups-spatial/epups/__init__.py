"""
Shared package for the ePUPS spatial tools.

- config: paths for production and workspaces
- schema: field and domain definitions (plain data, no ArcPy)
- builder: creates the schema in any geodatabase
- workspace: creates editor workspaces, optionally copied from production
- project: the ArcGIS Pro project for a workspace
- versioning: new permit versions for edited authorizations
- validation: the QA/QC checks
"""

import sys

# Print each line as it happens, even when output is piped to Tee-Object.
# Without this, long runs show nothing until they finish. Inside ArcGIS Pro
# (the toolbox, the Python window) stdout is Pro's own stream, which has no
# reconfigure, so it is skipped there.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
