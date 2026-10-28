"""
Shared package for the ePUPS spatial tools.

- config: paths for production and workspaces
- schema: field and domain definitions (plain data, no ArcPy)
- builder: creates the schema in any geodatabase
- workspace: creates editor workspaces, optionally copied from production
"""

import sys

# Print each line as it happens, even when output is piped to Tee-Object.
# Without this, long runs show nothing until they finish.
sys.stdout.reconfigure(line_buffering=True)
