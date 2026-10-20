# Reviewed c40 PUBLIC build source closure

Base: `c40aec6d7ccf5162bef7a2a054ff45b6baf2b13b`, tree `d1e9a1da44cc6beca2fa8daf6fb0e0a719c5b704`.
Branch: `work/hermia-public-build-c40-20261020`.

## Problem and change

The fixed c40 product contains twenty existing standard runtime modules omitted from the exact PUBLIC source list: seventeen inherited from b837 and three added by the reviewed c40 U16/Audio integration. The real source-closure CLI fails before staging. Add these twenty individual paths; do not allow whole directories. Runtime inputs increase from 571 to 591.

The first focused regression also exposed one existing Docker auxiliary omission: `contracts/storyboard-video-timeline-v1.md`, introduced by `a6678a4144b40277dce3c94f42cfed66a140fae5`. The reviewed public document describes the same original-owner video-only Timeline contract. Add only this exact auxiliary input; Docker inputs increase from 42 to 43, yielding 634 staged files including the runtime inputs.

Only `packaging/public-build.json`, `tests/test_public_build_c40_closure.py` and this report change. No application code, feature gate, permission, model/provider selection, system setting, shared owner or DSH interactive implementation changes.

## Individual source review

All twenty files remain byte-identical to c40. Local review evidence retains their full introducing/last baseline commits, SHA-256 values and import edges.

| Exact module | Reviewed public purpose |
| --- | --- |
| `app/creative/graph_conditions_catalog.py` | Read-only discovery for the original gated schema7 owner. |
| `app/creative/graph_failed_retry.py` | Explicit retry admission over the original WorkflowRun owner; no alternate executor. |
| `app/creative/graph_local_conditions.py` | Existing bounded bool/int conditions and gated original workflow projection. |
| `app/creative/graph_local_subgraph.py` | Current-pin pure-local subgraph calls under original scope and caller guards. |
| `app/creative/impact_reads.py` | Request-local reads through existing Graph/Storyboard authority. |
| `app/creative/storyboard_video_timeline.py` | Reviewed video-only Timeline draft creation through original owners. |
| `app/experimental/audio_manifest.py` | Manual reviewed Audio result manifests; no replay or new audio execution. |
| `app/experimental/audio_manifest_api.py` | Original injected Studio Host router with current read/write authority. |
| `app/experimental/comic_timeline_handoff.py` | Explicit original Comic-to-Asset-to-Timeline handoff, without rendering dispatch. |
| `app/experimental/portable_cache_policy.py` | Advisory bounded cache policy; no automatic eviction or filesystem scan. |
| `app/experimental/safe_batch_studio_image.py` | U16 bridge to original Host/ImageJob owners for bounded CPU cutout only. |
| `app/experimental/storyboard_impact_adapter.py` | Intent-only guarded projections; no router or executor registration. |
| `app/services/asset_bounded_file_windows.py` | Existing opt-in native bounded reader; copying source does not enable or validate it. |
| `app/services/comic_page_origin.py` | Passive provenance for original Comic render copies. |
| `app/services/comic_page_source_reads.py` | Phase-local original-owner reads of approved direct Comic sources. |
| `app/services/studio_audio_denoise.py` | Existing bounded local denoise profile under the original audio worker. |
| `app/services/studio_audio_loudness.py` | Existing bounded measurement proof under the original audio worker. |
| `app/services/studio_image_composite.py` | Reviewed two-layer bounded CPU composition under original ImageJob/Asset owners. |
| `app/services/studio_image_cutout_webp.py` | Opt-in lossless WebP encoding over the existing bounded CPU mask result. |
| `app/services/studio_timeline_links.py` | Metadata-only paired video/audio clip links under the original Timeline owner. |

## Import closure and private isolation

- The twenty modules reach 539 local Python modules, including implicit package initializers. Every local import resolves inside the explicit PUBLIC manifest; no undeclared transitive file or unresolved dynamic import remains in this scoped closure. Standard-library and already-declared external dependencies remain unchanged. This is static closure validation, not execution of these feature owners.
- New tests inspect the actual staged Python payload for private namespace imports and private NSFW route/executor/capability names or executable strings. Negative controls detect all four forms. Docstrings and shared compatibility policy vocabulary remain legal.
- `app/creative/content_policy.py` stays byte-identical, `STATUS=RESERVED`, default `STANDARD`; `MATURE` remains compatibility vocabulary and its notice remains unrendered/nonblocking. No private NSFW mode, dedicated router, executor or capability is added.
- `schema`, `profile=PUBLIC`, `excluded_namespace=studio_private_extensions`, roots and dependency review fields are unchanged. `scripts/public_build.py`, `pyproject.toml`, `Dockerfile` and the shared policy file remain byte-identical. Existing guards still reject undeclared files, private references in source/frontend, private nested archives, stage tampering and unexpected auxiliary inputs.

## Actual validation and retained failures

Use the existing Python 3.11.9 / pytest 8.4.2 environment. No dependencies were installed or copied. The offline packaging fixtures run with `--noconftest` and plugin autoload disabled, avoiding unrelated application/global runtime initialization.

```text
python -B scripts/public_build.py --source .
python -B -m pytest --noconftest tests/test_public_build_profile.py tests/test_public_continued_features_additive.py tests/test_public_build_c40_closure.py -q -p no:cacheprovider -k "not test_symlinks_fail_before_copy"
```

| Run | Actual result |
| --- | --- |
| Unmodified c40 source-closure CLI | exit 1; exact twenty added paths, no missing paths |
| New closure/isolation regression before manifest edit | 4 passed, 2 fixture setup errors caused by the real source-closure failure |
| First focused run after twenty runtime additions | 35 passed, 2 failed: native symlink fixture WinError 1314; Docker auxiliary document omission |
| Final focused run after exact auxiliary addition | exit 0; 36 passed, 1 explicitly deselected; 8.57 seconds |
| Actual PUBLIC test stage, independently reverified | 591 files with original per-file hash receipt |
| Actual Docker test stage, independently reverified | 634 files with original per-file hash receipt |

The symlink case was executed and failed while constructing its fixture, before exercising the guard: the current Windows account lacks the required privilege (WinError 1314). Its original test and failure output are retained. No permission change, test weakening or symlink bypass was attempted. Native symlink behavior is BLOCKED_ENVIRONMENT, not PASS.

Raw command/exit records, logs, JUnit, exact source/import review, final scope proof and both stage receipts are retained in the companion local `public-build-c40-evidence-20261020` directory. Only reproducible task-generated temporary fixture/stage copies may be removed after receipt capture; original failure evidence and unique inputs remain.

## DSH eighteen-path review: not imported

Reviewed read-only at DSH tip `6232f9d7c2c8fbc6dde6e26c1d9dfb631efbc1fe`. These eighteen candidate additions have no private execution marker findings in the scoped source/template audit. None exists in the fixed c40 source tree or this PUBLIC manifest. Their original DSH product and delivery remain untouched.

```text
app/experimental/interactive_export_contract.py
app/experimental/interactive_godot_export.py
app/experimental/interactive_renpy_export.py
app/experimental/interactive_targets/__init__.py
app/experimental/interactive_targets/godot/main.gd
app/experimental/interactive_targets/godot/main.tscn
app/experimental/interactive_targets/godot/project.godot.tmpl
app/experimental/interactive_targets/godot/runtime/acceptance_runner.gd
app/experimental/interactive_targets/godot/runtime/save_store.gd
app/experimental/interactive_targets/godot/runtime/story_loader.gd
app/experimental/interactive_targets/godot/runtime/story_runtime.gd
app/experimental/interactive_targets/ink/__init__.py
app/experimental/interactive_targets/ink/current_artifact.py
app/experimental/interactive_targets/ink/descriptor.py
app/experimental/interactive_targets/ink/runtime.py
app/experimental/interactive_targets/renpy/__init__.py
app/experimental/interactive_targets/renpy/project.py
app/experimental/interactive_targets/renpy/witness.py
```

Future integration must retain the twenty c40 runtime entries and this auxiliary document. Accept the DSH additions only after its artifact-bound runtime evidence, ZIP boundary guards and exact Ink artifact/revision save binding are corrected and checked against the final corrected source head. Keep original evidence and bundle history. If exactly these eighteen paths later pass review and no other inputs change, the runtime list would be 609 files. This arithmetic is an integration requirement, not approval or an automatic manifest update.

## Acceptance limits

This change repairs offline PUBLIC packaging closure and validates bounded staged-source isolation. It does not accept a Windows installer/container/wheel/sdist release, native security behavior, real Host, PostgreSQL, GUI, engines/media or full product E2E. No full build, main merge, push, tag or Release is part of this slice. The DSH run/evidence defects remain its separate owner task.
