# Issue #14 Batch 2B-2 — Visual continuity TIME_JUMP_CUT

This is not a V1.0 claim, not a DesktopHost DH-01–DH-08 PASS, and not a Release decision.

Batch 2B-2 repairs one remaining product defect. It does not close Issue #14. User-preference `harness_enabled` and world-rule `forbidden_terms` are unchanged. Issue #20 is unchanged.

This document records **named snapshots**. It does not permanently define “current-main” as a single SHA.

| Snapshot | SHA | Meaning |
| --- | --- | --- |
| Batch 2B-2 task base / post-PR-22 main | `9f210b7117c14d418a7f57d8976568cd5506125a` | Live `origin/main` when this batch was authorized. Snapshot only. |
| Batch 2B-2 task base tree | `a0e81c055f32a8493e3419471ff65dd8ece1f12d` | Tree of `9f210b7` |
| Production/test implementation HEAD | `47a080fae2c8e45d595c8ffe6a742492c77c5acd` | Helper + service view + contract tests. Documentation commits may follow. |

| Field | Value |
| --- | --- |
| Work branch | `fix/p1-visual-continuity-time-jump-cut` |
| Related issue | #14 (remains OPEN) |
| Frontend toolchain issue | #20 (UNCHANGED) |
| Target | `tests/test_p1_regression.py::test_visual_continuity_reports_scene_jumps` |
| Verdict | `FIXED_BATCH_2B_2` |
| Production change required | YES |

## Root cause

`validate_visual_continuity(shots)` reported `TIME_JUMP_CUT` only when `str(current.get("transition","")).upper() == "CUT"`.

The target test does not set `transition`. Product default when a transition is missing, blank, or `"None"` is a direct cut: `plan_transitions()` writes `type="CUT"`, `TransitionIn.type` defaults to `"CUT"`, and an unplanned cut is still a cut.

On task base `9f210b7`:

| Field | Value |
| --- | --- |
| TARGET TEST RESULT | FAIL |
| actual codes | `{LOCATION_JUMP, EMOTION_DISCONTINUITY}` |
| expected codes | `{LOCATION_JUMP, TIME_JUMP_CUT, EMOTION_DISCONTINUITY}` |

`ScreenplayService.validate_visual_continuity()` passed raw `shots`. `plan_shots()` does not copy scene `time` / `location` / `emotion`. Planned transitions live in `screenplay["transitions"]`, not on shot objects. The API therefore could not see scene-level time jumps or planned CUT/FADE.

## Helper contract

Missing / `None` / blank / `"None"` (any case, surrounding whitespace) → effective type `CUT`.

Explicit `CUT` (any case, surrounding whitespace) still reports `TIME_JUMP_CUT`.

Explicit `FADE` / `DISSOLVE` / `MATCH` / `WIPE` suppress `TIME_JUMP_CUT`.

Same time, or time missing on either side: no `TIME_JUMP_CUT`.

Unknown non-empty types are not redesigned in this batch; they are not treated as CUT.

Finding shape is unchanged:

- `code = TIME_JUMP_CUT`
- `severity = INFO`
- `from_shot_id` / `to_shot_id` = previous / current ids
- `message = 时间发生变化，当前使用直接剪切。`

`LOCATION_JUMP` and `EMOTION_DISCONTINUITY` rules are unchanged. The helper does not mutate the input list or dicts.

## Service / API enrichment contract

`ScreenplayService.validate_visual_continuity()` builds a check view and does not save:

- resolve `shot.scene_id` → scene
- shot `time` / `location` / `emotion` win when present and non-blank
- otherwise copy those fields from the scene onto the view
- look up `from_shot_id → to_shot_id` in `screenplay["transitions"]`
- planned type is attached on the view only
- no planned pair → helper default CUT
- screenplay, shots, scenes, transitions, and revisions are not written

End-to-end (`GET /visual-continuity`):

1. Two scenes with different times; shots inherit via the view.
2. Unplanned transition → `TIME_JUMP_CUT`.
3. Default planned CUT → still `TIME_JUMP_CUT`.
4. Update that transition to FADE → no `TIME_JUMP_CUT`.
5. `LOCATION_JUMP` / `EMOTION_DISCONTINUITY` remain when their helper conditions still hold.
6. Finding order and from/to shot ids are stable.
7. Repeating the GET does not change persisted screenplay equality.

## Files changed

Production:

- `app/services/screenplay_service.py`

Tests:

- `tests/test_visual_continuity_contracts.py` (added)
- `tests/test_p1_regression.py` assertions unchanged (not weakened, not skipped, not xfailed)

Docs (this documentation commit):

- `docs/issue14_batch2b2_visual_continuity_report.md`
- `docs/baseline_failure_registry.md`
- `docs/test_report.md`

Frontend / schema / migration / plugin runtime / `app/api.py` = 0.

## Results (bound to `9f210b7` + `47a080f`)

| Check | Result |
| --- | --- |
| Target before | FAIL; missing `TIME_JUMP_CUT` |
| Target after | PASS |
| Helper matrix | missing/None/blank/None-string = CUT; explicit CUT including case/padding; FADE/DISSOLVE/MATCH/WIPE suppress; same time and missing time do not report; adjacent pairs ordered; inputs not mutated |
| Service/API | unplanned CUT finding; planned CUT finding; FADE suppresses; GET is read-only |
| `tests/test_p1_regression.py` | PASS (includes the original target) |
| `tests/test_phase8_screenplay.py` | PASS |
| `tests/test_phase8_transitions.py` | PASS |
| Related screenplay/transition/asset tests | 21 passed |
| Targeted 50-run | 50/50; 12 passed per run; 0 failed |
| Backend full run 1 | 1024 passed, 2 failed, 28 skipped, 0 xfail; 26.17s |
| Backend full run 2 | 1024 passed, 2 failed, 28 skipped, 0 xfail; 25.38s |
| Collection | 1054 = 1024 + 2 + 28 |
| Arithmetic vs post-PR-22 main `1012/3/28` | +1 previously failing target now passing + 11 new contract tests = 1024 passing |

Remaining FAILED node IDs:

- `tests/test_user_preference_service.py::test_preferences_are_explicit_and_separate`
- `tests/test_world_rule_payload.py::test_world_rule_payload_normalizes_terms`

`tests/test_p1_regression.py::test_visual_continuity_reports_scene_jumps` is not in the FAILED set.

NEW FAILURES / SKIPS / XFAILS = 0 / 0 / 0 versus those two remaining product defects.

## PDF fallback

`tests/test_import_parsers.py::test_pdf_fallback_extracts_simple_literal_text` did **not** fail on this Linux Python 3.11 isolation tree for task base `9f210b7` or the implementation HEAD. Earlier independent review classified it `ENVIRONMENT-SENSITIVE BASELINE / INVESTIGATION REQUIRED`. It is not repaired here and is not a fourth product defect.

## Security boundaries

| Boundary | Result |
| --- | --- |
| `STORAGE_BACKEND` | `file` |
| Real PostgreSQL | 0 |
| Real Provider requests | 0 |
| Real credential access | 0 |
| User `.env` | 0 |
| User `novel_data` | 0 (run-scoped `NOVEL_DATA_PATH` + isolated `--basetemp`) |
| Schema / migration | 0 |
| Frontend delta | 0 |

V1.0 / DH-01–DH-08 / Windows / PostgreSQL / Provider / Release = not claimed.
