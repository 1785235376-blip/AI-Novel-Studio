# Explicit storyboard Director model analysis

Live model quality: **NOT_RUN**. Verification uses the original mock transport only.

The original Director coordinator, author adapter, broker, jobs and human review own this path. No automatic dispatch, retry, fallback or new workflow engine exists. Existing screenplay schemas and request text are unchanged; legacy preview/dispatch reject storyboard sources before preparation, broker admission or receipt shortcuts.

Authenticated GET `director-proposals/model-capabilities` advertises the additive contract. POST `{rid}/storyboard-preview` requires `expected_version`, `route_id`, and literal `source_contract: STORYBOARD_SHOT_CONTEXT_V1`. POST `{rid}/storyboard-dispatch` requires `expected_version`, the displayed `reviewed_preview_digest`, and the same literal contract. Missing, null, unknown or source-incompatible contracts fail closed. Refresh and review use only the exact persisted admitted preview and live original job authority.

The input contains exact saved source document ID/version/digest, title, scenes, complete authored shots ordered by number, and immutable `{source_shot_id,note_id,scene_id,source_number}` associations. Optional authored visual_target is explicit. All source content is untrusted data. No chapter prose, style, plan or automatic context is implicitly included. A real source chapter anchor is required; independent boards without one are not supported. At most 20 explicit chapter IDs and 20,000 instruction characters including schema/context are accepted, without truncation. Existing rule-entry field limits remain unchanged.

The response envelope echoes contract and source document ID/version/digest. Exactly one note per frozen shot association is required, in authored order; the note carries source_shot_id and exact id/scene_id/number. Missing, extra, duplicate, crossed or reordered mappings fail before any sorting. Each note requires typed planning, rationale and uncertainty. Only validated transport source_shot_id is removed before the original Director validator. Existing scene-field evidence validation applies; shot-field citations are not supported and semantic/spatial correctness remains unverified.

The preview digest binds contract, source mode/strategy, identity/input digest, mapping and exact adapter request. Dispatch retains all original route, price, budget and Host checks and one admission receipt. Output is bounded to 128,000 UTF-8 bytes and 180 seconds. `context_tokens=0` and `max_output_tokens=None` are not token-fit guarantees. No guessed truncation or live-quality acceptance is claimed.

Refresh preserves source_mode, full immutable source_shots and exact mapping alongside original provider/model/job/request/raw-output provenance. The human may edit proposed camera, duration and other candidate values, but not associations. Adoption creates a separate Director DRAFT. Original storyboard, shots, assets and bindings remain untouched. Restart without live job authority fails closed and cannot replay or import stored model output.

## Verified offline evidence

`storyboard-model-core-r1`: 159 passed, 146 PostgreSQL cases deselected; original runner receipt confirms `sources_changed_during_check: false`. This includes mock execution once through the original broker/job owner, exact source/image-binding/approval and asset-byte preservation, human DRAFT adoption and File reopen, cancellation/restart fail-closed behavior, exact 20,000/20,001-character and 20/21-chapter bounds, protected legacy rejection and frozen screenplay request/schema comparison. No live provider/model quality evaluation occurred.

`storyboard-model-core-r2`: 173 passed, 160 PostgreSQL cases deselected after recovery in the same checkout. The additional cases reject legacy preview/dispatch even after storyboard job admission without creating another job or transport call, and reject completed-candidate tampering of execution contract, missing preview contract, preview mapping/order/digest, and frozen source camera/note association before acceptance. Backend implementation and golden fixtures remain identical to r1. Original runner before/after full source snapshots are equal; protected tests and guards are unchanged.

## Actual PUBLIC artifacts

`storyboard-model-public-artifacts-r1`: all three original real-wheel payload, wheel metadata, and real-sdist payload/metadata tests passed using current-root staging, the clean test interpreter, and the existing installed packaging interpreter. Original runner before/after source snapshots are equal. Both builders report `APPLICATION_IMPORTS=NONE NETWORK=NONE`; no installation or application execution occurred.

- Wheel SHA256: `5ec3611969ae9715a24e540fe88a5ab14c1214acd790e795d3babdd7506a0b2c`
- Sdist SHA256: `817e2e11e9e409dc5f1276281dafcfe9a3f3c7410e3bba560b250253734ea189`
- New module `app/creative/storyboard_model.py` in both verified artifacts and both pristine stages matches current source SHA256 `4bc019b4e4b78d1697f5543213fb2db682c4f4829c3303d44d392fa2612238a2`.

Full artifact and pristine-stage hash receipts and raw build logs are retained beside this document as `storyboard-model-public-{wheel,sdist}-r1.json`, `storyboard-model-public-{wheel,sdist}-stage-r1.json`, and `storyboard-model-public-{wheel,sdist}-build-r1.log`. Actual archives and stages remain in `.runtime/storyboard-model-public-artifacts-r1-tmp/public-{wheel,sdist}0/`. Declared dependencies remain external and metadata verified. Sdist is future-format verification; these results do not establish platform, packaged-runtime, live-provider, or release acceptance.

## Independent final verification

The independent review passed 90 backend cases with 88 PostgreSQL cases deselected and 61 UI cases (49 new, 12 original). These repeated subsets overlap the primary 173 backend / 126 UI totals and are not added. Current source snapshots remained stable, with 1,275 protected entries and 36 guard/companion entries unchanged. Actual wheel and sdist bytes and pristine-stage module hashes were independently verified. See `storyboard-model-independent-review.json`, `storyboard-model-independent-r1.{json,log}`, and `storyboard-model-independent-ui/`.

Original clean-interpreter startup and current-root origin proof were copied byte-exact to `storyboard-model-origin/`; original intermediate static and receipt review reports are retained as `dot-storyboard-model-*-review-*-20261017.json`. Their pending statuses and intermediate hashes remain historical; the final independent review binds the final source. Source checkpoint remains `abff2ee7acc842e87abd53e0858110669922f9bc` until a separate parent commit. This independent evidence does not close any live-model, browser, PostgreSQL, target-platform or full-release acceptance gate.

## Raw-byte whitespace evidence

The full staged whitespace check reports seven EOF blank lines in preserved raw Vitest/build logs and two EOF blank lines in the frozen screenplay golden source fixtures. These bytes are intentionally unchanged. The scoped runtime/test/documentation check excludes only those raw `.log` files and the two named golden fixtures and passes; the full staged check is not claimed as passing.
