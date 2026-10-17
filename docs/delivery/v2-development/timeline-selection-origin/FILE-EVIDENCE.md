# Timeline selection File verification

Verified worktree: `/workspace/scratch/20a0022d2b33/studio-timeline-selection`.
Base HEAD: `3eb1dfeeba1c94a259aab62ca5d0d05e4f803d16`.

## Authoritative execution

- `run-proof-file-r2.sh`: normal interpreter startup and original-runner child proof, no product/pytest import in probe, no path repair or `-S`/`-I`.
- `run-file-r2.sh`: unchanged `scripts/run_v2_checks.py`, sole approved clean Python, owned File profile/basetemp, PostgreSQL deselected by marker.
- `normal-startup-file-r2.json` and `../timeline-selection-origin-file-r2.log` both report probe SHA-256 `71d879f23e35669fb125030543cd38fcc1288ecd6052cd655eb88f7ab56c9396`.
- `../timeline-selection-origin-file-r2.json` and `../timeline-selection-file-r2.json` both retain complete original-runner source brackets and report `sources_changed_during_check: false`.
- File result: **72 passed, 1 deselected, 1 warning**, 16.53 seconds. The warning is the existing FastAPI/Starlette TestClient httpx deprecation.
- New additive module: 21 cases. Unchanged regression modules: trim, slip/delete, asset handoff, caption transfer preflight.
- Test source SHA-256: `109c926731e01486f40acfab145e9876c00ef8ed6964eeb7f4f965eab96fab32`.
- Runner SHA-256: `64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5`, equal to base HEAD.

## Retained r1 caveat

The r1 File run passed identically (72 passed, 1 deselected, 1 warning), with unchanged product-source brackets. During its preceding origin-proof stages, another worker replaced `origin-probe.py`: natural startup used SHA `71d879...`, while the runner child used SHA `936926...`. Both prove the current worktree and clean dependency locations, but the latter older probe lacks direct timeline-owner specs. Do not describe r1 as a single unchanged-probe proof. Its files remain intact. The separately named `origin-probe-file-r2.py` and r2 launchers/results provide the clean repeat; no source/test changes were needed.

## Contract boundaries

Selection movement changes only selected `start_ms` fields, with same original tracks. Tests compare complete saved-normalized DTOs, preserving pins, trim, rational speed, fades, captions and duration. Real File Save/reopen proves one version, stale CAS rejection, and unchanged history/pins after rejected edits.

Original semantics retained: 40 operations per batch, 30 clips per timeline, repeated same-clip move operations legal, audio overlap legal. Duplicate-selection rejection belongs to UI selection guards. No backend runtime or existing test changes. No PostgreSQL, browser/native, provider, GPU, render or decoded-source-duration acceptance is claimed.
