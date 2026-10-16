# Compatibility and data

The frozen PR37 candidate and its original acceptance package remain unchanged. Later source with flags off is a new compatibility guarantee, not byte-identical PR37.

New metadata reuses R3 ExperimentalStore scope documents, File cross-process locking and PostgreSQL migration019. Existing migrations are not rewritten. No startup conversion of manuscript or automatic model/scanner launch is introduced. Feature metadata is content-free; pending directions are not executable capabilities.

EXPERIMENTAL_FEATURES accepts exact registered names only. Runtime prerequisites are explicit and never auto-enabled. V1_ACCEPTANCE_MODE overrides every runtime flag. Every new write/read/task callback also requires current server authority and source checks; hiding a button is not authorization.

Use a new isolated Experimental data directory/database. Turning flags off does not roll back data. Do not open a newer real database with PR37; use a separately supported export/import into a new target and validate it. No production backup or user data conversion is performed here.
