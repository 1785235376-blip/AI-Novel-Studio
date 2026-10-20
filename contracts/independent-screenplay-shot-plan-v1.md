# Opt-in independent screenplay shot planning

The existing `model-v2` preview accepts `planning_mode: "MULTI_SHOT_V1"` only for independent SCREENPLAY sources. Omitting it retains the original one-note-per-scene prompt/schema and V2 receipt. Existing chapter-backed model planning already supports multiple shots; this contract does not replace it.

## Bounded model selection

- Exactly 1–2 authored source scenes; larger sources fail with `CREATIVE_MODEL_SHOT_PLAN_REQUIRES_ONE_OR_TWO_SCENES`, without splitting or truncating.
- Preview freezes three identity slots per scene in `allowed_source_mapping` (`note_id`, `scene_id`, `source_sequence`, `slot`). This is an allowlist, not a deterministic dramatic breakdown.
- The model chooses an ordered subset with 1–3 shots per scene, at most six overall. Slots can be skipped. Every scene must be covered. Selected global `number` values are contiguous from one and are distinct from slot numbers.
- Output contract `INDEPENDENT_SCREENPLAY_SHOT_PLAN_V1` requires rationale, sequence/duration reasoning, uncertainty, 1–600 seconds per note, and exact own-scene evidence or explicit speculative assumptions. Scene order, identity membership, uniqueness and coverage fail closed.
- The global output-token ceiling remains 2048. Six shots are not guaranteed to fit. Invalid/incomplete JSON fails with `CREATIVE_MODEL_SHOT_PLAN_INVALID_OR_INCOMPLETE_JSON`; no silent repair, shortening or automatic retry.

## Original ownership and review

V3 preview/pending receipts use the existing model-v2 endpoints. Pending provenance separates selected `source_mapping` from frozen `allowed_source_mapping`. Original Host, actor/scope/incarnation, exact source/version/digest, route fingerprint, LOCAL_ONLY known-zero policy, Broker reservation, Job, terminal evidence, explicit publication and adoption owners remain authoritative.

Human review must retain selected candidate IDs, scene associations and order. It keeps the original content-field editing semantics, including optional planning and authored geometry. Original sealed model output and candidate digest remain separate from the reviewed output digest. Human edits are not re-certified as grounded model analysis; any duration default introduced by the original human-review owner is not a model estimate. Timing and summed duration are unmeasured planning estimates, not quality or geometry verification.

Adoption creates one Director DRAFT. Existing `derive(STORYBOARD, shot_policy=DIRECTOR_NOTES)` creates one Shot per adopted note. Ancestry is direct edges Storyboard → Director → Screenplay, with exact version/digest at each edge; source documents remain unchanged.

## Verification scope

Tests use the original File owners, LocalTextAdapter and an injected synthetic response. They do not run a real model or establish output quality, provider fit, browser behavior or PostgreSQL lifecycle support. Early test runs exposed omitted sparse dependencies and missing owned pytest basetemp; these were corrected without product changes. Two lifecycle assertions were corrected to match existing owners: preview cannot be reread after dispatch, and ancestry is direct-parent rather than flattened. Final checks must be reported separately from those failed attempts.
