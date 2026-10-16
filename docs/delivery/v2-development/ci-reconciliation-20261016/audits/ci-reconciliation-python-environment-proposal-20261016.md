# Dependency-only Python environment proposal

PROPOSAL ONLY: no environment created, no old venv executed, no product import or pytest collection performed.

Verified base: `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12`; SHA256 `fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7`.
Destination: `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1`.

## Setup after release

```sh
env -u PYTHONHOME -u PYTHONPATH -u PYTHONSTARTUP -u PYTHONUSERBASE /opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -I -S -m venv --without-pip /workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1
```

Copy regular RECORD-owned dependency files only, never whole site-packages or path hooks. The JSON provides the exact37-distribution metadata allowlist and read-only hash preflight. The installed project distribution and editable finder are excluded.

- Require target does not exist; do not use --clear or overwrite an existing environment.
- Require allowed name/version exact; no unreviewed dependency additions.
- Validate every available RECORD hash and size; also compute independent SHA256 for every copied byte.
- Reject symlinks in every path component, escapes, missing files and conflicting ownership. No fallback to an old source path.
- Copy complete dependency resources/native libraries tracked in RECORD, not only Python modules.
- Keep source/destination path, distribution, size and SHA256 ledger; prove source unchanged during copy and destination byte-equal.
- No .pth/sitecustomize/usercustomize/editable finder anywhere in new site-packages.
- pyvenv.cfg must have include-system-site-packages=false; base identity must match verified base.

## Command-local environment

{
  "unset": [
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTEST_ADDOPTS",
    "PYTEST_PLUGINS",
    "PACKAGED_RUNTIME_INSTANCE_ID",
    "PACKAGED_BOOTSTRAP_SECRET",
    "PACKAGED_CONTROL_PIPE"
  ],
  "set": {
    "PYTHONNOUSERSITE": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PACKAGED_WINDOWS_MODE": "false"
  },
  "root_binding": "For actual runner commands use current reconciliation cwd; run_v2_checks sets PROJECT_ROOT and PYTHONPATH to that root before its child. For startup-only proofs set PYTHONPATH explicitly to current root after clearing inherited values."
}

## Required startup and child-origin proof

- Run newly created python with a stdlib-only probe, not the old venv executable. Record sys.executable/sys.prefix/sys.base_prefix and full sys.path/meta_path identities. Require no old-tree path/finder/hook, including namespace placeholders.
- Use importlib.machinery.PathFinder.find_spec with explicit root path for app/local_interop_desktop/local_interop_protocol and explicit parent search paths for app.application/app.autosave and app.application.persistence. Do not call importlib.util.find_spec on dotted product names and do not import any product package.
- Check package specs resolve only into current reconciliation code and namespace locations; fail on absent/different origins.
- Read dependency distributions using importlib.metadata only, assert allowed versions and no ai-novel-studio editable metadata. Import pytest alone only after metadata/startup proof release, never repository modules during the origin probe.
- Spawn a child using the actual new sys.executable and same sanitized environment/current cwd; repeat the entire stdlib-only prefix/path/origin proof. This matches generator subprocess inheritance.
- Archive both probe outputs and exact exit codes before authorizing any narrow backend test. The proof has not been run yet.

## Static dependency preflight

36 approved installed distributions; 2088 eligible RECORD-owned file entries; 85424772 bytes; 0 validation errors.

Not installed among constraints/declared set: ['fonttools']. Constraints constrain versions; absence of optional fonttools does not authorize installation or claims that font-dependent suites pass. Required missing files fail.

Pypdf6.19.0 is a documented direct-project pin outside the unchanged constraints file. AnyIO is the only existing pytest entry point; disabling autoload has no identified dependency in the72e test sources, but future exact old-row comparison still decides inventory compatibility.

## Permission boundary

Parent approval required to create/copy the environment and run startup-only probes. This plan grants no permission for blocked candidate code/tests, collection or manifest writes.
