# Work handoff — public-base edition

Base is public efd083c, not local bd85784c. Apply only the new test plus this delivery directory. App must remain byte-identical to efd. Do not import old unpublished TaskCenter helpers or carry forward the lost old package's 170 result.

Replay evidence/run_groups.sh with paths adapted to an isolated fixture root and the existing Python environment. Explicitly set PROJECT_ROOT, XDG_DATA_HOME, LOCALAPPDATA, NOVEL_DATA, STORAGE_BACKEND=file and PYTHONPATH. No dependency installation is needed. Negative-only.patch is an intentionally broken separate-checkout sensitivity probe; NEVER apply it to a deliverable app.

Publication is authorized only for tests/docs/synthetic evidence on work/hermia-export-artifact-recovery-20261028. Root coordinator must verify remote SHA/tree after upload. No main write, force-push, Release, private project data or credentials. This edition does not require publishing the unapproved coexistence parent.
