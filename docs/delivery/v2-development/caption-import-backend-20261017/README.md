# B04 backend evidence index

Original runner outputs, retained unchanged in the parent directory:
- `caption-import-backend-r1.log` / `.json`: 99 passed, 4 failed, 90 deselected.
- `caption-import-backend-r2.log` / `.json`: 103 passed, 2 failed, 92 deselected.
- `caption-import-backend-r3.log` / `.json`: 109 passed, 96 deselected; PASS.

Every receipt includes the actual command, interpreter, owned profile, source hashes before/after, timestamps, return code and raw-log SHA256. All report unchanged sources during execution. The final receipt remains authoritative for tested source bytes. This index does not rewrite a receipt or relabel a failure.

The normal-startup and startup-command/probe files here are exact copies of the independent reviewer's stdlib-only origin proof. The probe uses the clean reconciliation interpreter and checks current-worktree origins in the normal process and an actual child without product/pytest imports. It is provenance evidence, not an added product runner. `origin-probe.py` is the exact probe source.

The backend note `docs/v2/caption-import-preview-backend-20261017.md` records fixes, scope and limitations. Real File and original upload/save/export APIs ran via in-process TestClient at both prefixes. Scoped authorization uses a real branch File asset seeded via the existing AssetLibraryService because the legacy upload endpoint is project-only. No allow-all authorization stub was used. PostgreSQL cases were deliberately deselected.
