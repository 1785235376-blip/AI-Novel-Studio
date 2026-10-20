# B07 / DIF-10 / E2E-07 export target contract freeze (2026-10-20)

Baseline: product commit `b8371a48816b852176d45151eb9a0e3618a32c07`, tree `d1abbaaf64d7fd95535ad75ea2470fa288a35579`,
restored and verified from archive artifact `artifacts/2026-10-20-studio-v2-cloud-authoring-reviewed-b8371a48/`
(SHA256SUMS, bundle verify, prerequisite ancestry chain and `verify_package.py` all PASS).

This document freezes the shared surface every target line codes against. The
machine-readable authority is `app/experimental/interactive_export_contract.py`.

## Shared authority

- The original story spec is the only story authority. Targets only consume the
  authorized, approved snapshot the service builds in `InteractiveStoryService._snapshot()`
  (story id, revision, status, spec, spec digest, source digest, review receipt,
  characters, authoritative witness, media manifest, bounded analysis).
- Target adapters are restricted pure converters: no disk reads outside their own
  module assets, no external writes, no engine install/launch, no story execution,
  no network. Unsupported features must be reported, never silently dropped.
- The service adds `manifest.json` and `source-receipt.json`; adapters must not emit those names.
- All output paths go through `safe_bundle_path`: relative POSIX, ASCII segments, no
  `..`/absolute/drive/backslash/reserved device names, case-insensitive collision free.
  Limits: 256 files, 8 MiB per file, 32 MiB total, 180 char paths.
- The deterministic ZIP is produced only by `package_export_zip`.

## New target IDs (old IDs stay untouched)

| line | new target id | format | module (owner) |
|---|---|---|---|
| B | `RENPY_8_5_4_PROJECT_V1` | complete Ren'Py 8.5.4 project | `app/experimental/interactive_renpy_export.py` |
| C | `GODOT_4_RUNTIME_PROJECT_V1` | complete Godot 4 project | `app/experimental/interactive_godot_export.py` |
| D | `INK_2_3_2_CURRENT_ARTIFACT_V1` | current-artifact Ink delivery | `app/experimental/ink_export.py` |

Legacy IDs preserved byte-for-byte in existing bundles:
`RENPY_8_5_4_TEXT_MENU_SUBSET`, `GODOT_4_DATA_ADAPTER`, `INKJS_2_3_2_TYPED_TEXT_SUBSET`.

## Adapter module surface (frozen)

```python
DESCRIPTOR = {                    # plain dict, validated by TargetDescriptor
    'target_id': 'GODOT_4_RUNTIME_PROJECT_V1',       # must equal registry id
    'display_name': 'Godot 4 runtime project',
    'kind': 'RUNNABLE_PROJECT',                      # RUNNABLE_PROJECT | DATA_ONLY_ADAPTER | LEGACY_FRAGMENT
    'format_version': 'godot-runtime-project-1',
    'adapter_revision': 1,
    'engine': {                                      # absent/None when no external engine is needed
        'name': 'Godot', 'minimum_version': '4.0',
        'executables': ['godot', 'godot.exe', 'Godot_v4.7-stable_win64_console.exe'],
        'version_args': ['--version'], 'env_override': 'POEMSEED_GODOT_BIN',
        'search_hints': ['D:/GameDev/Godot/Godot-4.7-stable/Godot_v4.7-stable_win64_console.exe'],
        'gui': False, 'note': '',
    },
    'capabilities': {key: {'supported': bool, 'lossy': bool, 'note': str} for key in CONTRACT CAPABILITY KEYS},
    'losses': ['...'], 'runtime_requirements': ['...'],
    'launch_instructions': '...', 'integration_notes': ['...'],
    'evidence': {'SOURCE_IMPLEMENTED': 'PASS', 'FIXTURE_TESTED': 'PASS'},   # only what this line really ran
}

def compatibility(snapshot) -> dict:
    return {'can_export': bool, 'capabilities': {...same shape...}, 'losses': [...],
            'issues': [{'code': str, 'node_id': str|None, 'choice_id': str|None, 'detail': str}],
            'notes': [...]}

def build(snapshot, options) -> dict:
    return {'files': {relative_path: bytes, ...}, 'manifest_extra': {...}}   # optional
```

Capability keys (all 13 required): `conditions, bool_variables, int_variables, assignment, dialogue, choices, endings, loops, step_cap, save, restore, unicode, media`.

Evidence levels (independent, never auto-upgraded): `SOURCE_IMPLEMENTED, SCHEMA_VALIDATED, FIXTURE_TESTED, GENERATED_ARTIFACT_VALIDATED, TARGET_RUNTIME_EXECUTED, SAVE_RESTORE_VERIFIED, WINDOWS_USABILITY_VERIFIED`
with statuses `PASS | FAIL | PARTIAL | BLOCKED_ENVIRONMENT | BLOCKED_AUTHORITY | NOT_RUN`.
Generating a project is **not** running it. Fixture tests are **not** current-artifact runtime acceptance.

## Service-facing endpoints (already wired in this contract commit)

- `POST /{sid}/export-targets` `{expected_version}` → descriptors + per-target compatibility,
  engine probe, independent evidence, witness, media manifest, `can_export_any`.
- `POST /{sid}/export-preview` `{expected_version, target_id?}` → legacy preview plus `targets` list and
  `selected_target`; the reproducible `preview_digest` excludes host engine detection.
- `POST /{sid}/export` `{expected_version, preview_digest, target_id?}` → legacy multi-file ZIP when
  `target_id` is omitted; otherwise the deterministic single-target project ZIP + manifest + receipt.

## Line ownership

- A (UI): `InteractiveStoryPanel.tsx`, `InteractiveStoryPreview.tsx`, `InteractiveStoryHistory.tsx`,
  `interactiveStory.css`, new local helpers/components and their frontend tests. Never edit
  `interactiveStoryClient.ts` (frozen above) or Hermia-owned shell/routes.
- B: `app/experimental/interactive_renpy_export.py`, `app/experimental/interactive_targets/renpy/**`, tests.
- C: `app/experimental/interactive_godot_export.py`, `app/experimental/interactive_targets/godot/**`, tests.
- D: `app/experimental/ink_export.py` (add the new-target surface only; keep `InkExportAdapter` unchanged),
  `app/experimental/interactive_targets/ink/**`, tests.
- Lead: contract module, `interactive_story.py`, `interactive_story_api.py`, client, integration, delivery.

## Local environment facts (verified 2026-10-20)

- Godot 4.7 stable (Win64, console + GUI exe) at `D:/GameDev/Godot/Godot-4.7-stable/` → target runtime available.
- Ren'Py 8.5.4 is **not installed** on this host → B runtime evidence must be `BLOCKED_ENVIRONMENT` unless a real
  engine appears; static/schema/fixture evidence still required.
- inkjs 2.3.2 is pinned; npm registry reachable; verification must consume the *current exported* Ink artifact.
- Python 3.11.9 + pydantic 2.13.4 + pytest 9.1.1 available; frontend deps via pnpm 12.4.2 / Node 22.14.0.

## Definition of done per line

1. Real source under the owned paths, committed on the line branch (stable slices).
2. Directed tests actually executed and logged (commands + exit code + result).
3. Engine/runtime evidence only at the level actually achieved; missing engine is a recorded
   `BLOCKED_ENVIRONMENT`, never a silent pass.
4. Files, target id, format version, selector semantics and receipt documented in the line report.
5. No edits outside owned paths; shared interface needs go to the Lead as an interface request.
