# Bounded Timeline slip and explicit ripple-delete handoff

Source base: `b40809baef392d3f818c37d2a5d768fb61432f4a`.
Status: implementation, primary verification and scoped independent verification complete. This is bounded wiring acceptance, not full product or release acceptance.

## Existing owners and exact behavior

The existing inspector/mapper already emits `clip.slip {op, clip_id, offset_ms}` and `clip.remove {op, clip_id, ripple:true}`. The mounted editor previously rejected both through its position-only guard. The new exact-descriptor branches precede that guard and dispatch to the original local controller. They reject extra descriptor fields, mismatched operation names, wrong selected targets and missing explicit ripple consent.

Both operations follow checked detached clone → mutation → complete `checkedTimelineDraft` validation → the existing `change()` owner. Rejection publishes nothing and adds no undo entry. Success is exactly one local undo/redo step. Only the original explicit Save persists via `timelineSave` and expected-version CAS. Original GET and explicit adoption reopen the saved result. There is no new backend route, schema, store, rendering engine, automatic Save/render, source replacement path or asset creation. Existing ordinary delete, manual source edits, source replacement and speed controls remain unchanged.

- Slip adds a signed safe-integer source-time offset to both in/out points. Placement, rendered duration, rational speed, source pins, fades, transitions and neighbors remain unchanged. Image slip is refused. Zero offset is a local no-op without dirty/history changes, although the backend accepts an equal detached result. Invalid source bounds fail atomically.
- Ripple-delete requires explicit `ripple:true`, removes the selected clip, then shifts only same-track clips starting at or after the removed clip's OLD rendered end. The shift is negative `(out_ms - in_ms) * speed_den / speed_num`, following the original integer/rational duration contract.
- Earlier starts, other tracks, captions and total timeline duration remain unchanged. The last clip in a track cannot be deleted. No transition repair or overlap correction is attempted: dangling predecessor transitions and invalid final geometry fail complete-draft validation atomically.

Parity fixture: target starts at 1000 ms, source 600..3600 ms, speed 3/2, rendered duration 2000 ms. Slip +500 yields 1100..4100; -600 yields 0..3000. Ripple deletion keeps a 2999 ms start unchanged and moves starts 3000→1000, 3001→1001 and 4500→2500. Canonical clip sorting remains the original validator's responsibility.

## Consent, lifecycle and honest boundaries

The controller binds callbacks to current client and semantic generation, including edit/undo changes. Mounted routing checks the current selection and generation. Existing busy, pending-operation, authority, track-lock, conflict and UNKNOWN-result protections remain active; uncertain Save is not replayed.

Inspector authored-input generation increments synchronously on form edits and reset. A retained generate callback cannot reuse old ripple consent after uncheck or an uncheck→recheck ABA sequence. A new current callback works normally. Semantic target changes reset source trim/slip input and ripple consent; unrelated rerenders preserve authored values.

Timeline ruler marks are timeline coordinates, not measured source-media bounds. The inspector no longer passes them as slip `sourceRange`. The mapper's optional verified `sourceRange` remains available to genuinely informed callers.

Save validates structure and source identity/content; it does not measure the actual source duration. The renderer still reads media and checks measured bounds. A File test saves a structurally valid slip beyond the synthetic WAV duration to establish this boundary, without claiming successful rendering.

Typed but unapplied inspector fields are local form state, not timeline draft history, and are not protected by existing navigation-dirty handling. The UI now explicitly states that boundary. No ad hoc second dirty/recovery system was introduced. Crash recovery, real-media preview and full desktop usability acceptance are not claimed.

## Verification and preserved failure history

- Primary File: 39 passed (22 new slip/delete cases plus 16 original trim and 1 original asset case), 1 PostgreSQL-only case deselected. Original runner, verified clean interpreter/origins. PostgreSQL was not executed.
- Primary UI final r3: 200 passed across 10 suites, including 33 new cases (29 controller/mounted and 4 inspector). Mounted original components exercise slip/delete, one-step undo/redo, explicit CAS Save and reopen. Original mapper, panels, trim, source editing, asset handoff, shell and primitives suites remain passing.
- Final forced TypeScript, production Vite build and token guard: exit 0. Build retains the existing large-chunk warning.
- Final r3 UI/type/build/token use unchanged `scripts/run_v2_checks.py`. Each receipt contains 2,544 before/after source hashes, unchanged within and identical across all four checks, actual command/exit, isolated profile and verified log digest.
- Earlier r1/r2 UI/type/build/token were direct-tool checks, not executions through `run_v2_checks.py`; their scope was only five owned frontend hashes. Preserve them as bounded direct evidence. r1 forced TypeScript failed on three unsupported `exact:true` query options in the new test. Only those new-test options were removed; string role-name matching remains exact. r2 direct checks passed. r3 is the final whole-source wrapper evidence.
- Primary File r1 predates that test-only correction. Backend/runtime/File-test sources are unchanged; final independent verification must reconcile the complete source map rather than claiming the earlier complete map is identical.

No protected owners, old tests, runner scripts or design tokens were changed. No Windows, PostgreSQL, browser visual/geometry or full release acceptance is inferred from these tests.

## Independent review

Independent review passed 33 UI cases and 22 File cases, overlapping the primary totals rather than increasing unique coverage. Final review checked seven retained receipts: current final 2,544-source manifests and corresponding log hashes, with 1,289 protected entries unchanged. No remaining scoped implementation blocker was identified.

The initial independent File r1 invocation produced 22 setup errors because its command omitted the required owned `--basetemp`; its failure receipt and raw log remain preserved. The invocation was corrected to use an owned basetemp and independent File r2 passed, without source changes. This was an execution-profile correction, not a product/test-source repair. See the independent review JSON and both File attempts below.

## Byte-exact evidence index

The following SHA-256 values identify retained files; no logs were rewritten.

| Retained evidence | SHA-256 |
| --- | --- |
| [timeline-slip-delete-build-r1.exit](delivery/v2-development/timeline-slip-delete-build-r1.exit) | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| [timeline-slip-delete-build-r1.log](delivery/v2-development/timeline-slip-delete-build-r1.log) | `d6d4ea027dde4847e5fa616fc343f829c5976ce93ae63fdd8510bf5d75f063d3` |
| [timeline-slip-delete-build-r2.exit](delivery/v2-development/timeline-slip-delete-build-r2.exit) | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| [timeline-slip-delete-build-r2.log](delivery/v2-development/timeline-slip-delete-build-r2.log) | `4454ee4a2884ea7718f9f6dd3ad17a3a8796613ac64929b6b0c97ed8897d6e19` |
| [timeline-slip-delete-build-r3.json](delivery/v2-development/timeline-slip-delete-build-r3.json) | `28db5f7350d530e06f71b59c4a3e81eb0866f2f7ede15ea05748f2c7d4b8f588` |
| [timeline-slip-delete-build-r3.log](delivery/v2-development/timeline-slip-delete-build-r3.log) | `b893c5b3e931f473148272d72bad09175ca9a7d88c6511b7f43e68565b8bc101` |
| [timeline-slip-delete-file-r1.json](delivery/v2-development/timeline-slip-delete-file-r1.json) | `0730ba56500e619170ed72dea76ba7a74bd34667458a65eab416a345979e7463` |
| [timeline-slip-delete-file-r1.log](delivery/v2-development/timeline-slip-delete-file-r1.log) | `fe339d73bd1bb6fa23b235cd3e104f2adc6ef312496eafdd8a1e1b0cf84e27ed` |
| [timeline-slip-delete-independent-file-r1.json](delivery/v2-development/timeline-slip-delete-independent-file-r1.json) | `4289a2b9e4eb5e8535f871c57b1e9279acfb0e48ad59a2cfa37544194d17cf79` |
| [timeline-slip-delete-independent-file-r1.log](delivery/v2-development/timeline-slip-delete-independent-file-r1.log) | `d069aae50d595029d6c1658bd3009c3c1bc75bece3732ffbd7dd565b461970e2` |
| [timeline-slip-delete-independent-file-r2.json](delivery/v2-development/timeline-slip-delete-independent-file-r2.json) | `b394772635ff5d68c16991d7cc16a20831d7c8ad6d7c72451f341fdd542e39fd` |
| [timeline-slip-delete-independent-file-r2.log](delivery/v2-development/timeline-slip-delete-independent-file-r2.log) | `971ef00c75250fbf7c2ee313eb810a6465f7c70eea289b6dde3ce689054a42f9` |
| [timeline-slip-delete-independent-review.json](delivery/v2-development/timeline-slip-delete-independent-review.json) | `c58dbf08002c4aac4e5c323dc6b4fb12b00c0f4ddf04968b7d70c70484281244` |
| [timeline-slip-delete-independent-ui-r1.json](delivery/v2-development/timeline-slip-delete-independent-ui-r1.json) | `62efcaa8c343b23e6065d53aa7cf1d4184ec46bcbefa9bca76d720ad9b9ccc81` |
| [timeline-slip-delete-independent-ui-r1.log](delivery/v2-development/timeline-slip-delete-independent-ui-r1.log) | `52f2aa2e71c0f8db7272dd4dde4ed44180efbf08e3e0ff5e281d17ac817dbc65` |
| [file-launcher.log](delivery/v2-development/timeline-slip-delete-origin/file-launcher.log) | `5a15fc676bff3f899c1aa2e3c3c5be34f9ddd70d86c25138cd049feedd3b0898` |
| [launcher.log](delivery/v2-development/timeline-slip-delete-origin/launcher.log) | `bf0ee9b9c5e41630006c72ca6cb1655162d305700dae5ffd6220484763e677ba` |
| [normal-startup.json](delivery/v2-development/timeline-slip-delete-origin/normal-startup.json) | `f9d7d1873057ebbcab3aa6015ac5af5b897d55fedf71ba85e9969c72f8d611f7` |
| [normal-startup.stderr.log](delivery/v2-development/timeline-slip-delete-origin/normal-startup.stderr.log) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [origin-probe.py](delivery/v2-development/timeline-slip-delete-origin/origin-probe.py) | `e5c68040186dc860252f7b195ecae829a16aa8b0c1844d598c92d07fce765381` |
| [run-proof.sh](delivery/v2-development/timeline-slip-delete-origin/run-proof.sh) | `97b64b181475e7070375b89e0581a6ce494568c3b8c13744a78be8ed5504030b` |
| [timeline-slip-delete-origin-r1.json](delivery/v2-development/timeline-slip-delete-origin-r1.json) | `fa875a1d1c418e86c602a27b29d913fbbf5484866917165b4ff6a8b6dce1ebfe` |
| [timeline-slip-delete-origin-r1.log](delivery/v2-development/timeline-slip-delete-origin-r1.log) | `1acaaefb3557a494cd143e0c603b1265b028d52c229fea00db4126c7e25dd9d2` |
| [timeline-slip-delete-token-r1.exit](delivery/v2-development/timeline-slip-delete-token-r1.exit) | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| [timeline-slip-delete-token-r1.log](delivery/v2-development/timeline-slip-delete-token-r1.log) | `720c976bb800c2f989255bfef0431c263b72c50e0b2c052599e3b39e1cb1de50` |
| [timeline-slip-delete-token-r2.exit](delivery/v2-development/timeline-slip-delete-token-r2.exit) | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| [timeline-slip-delete-token-r2.log](delivery/v2-development/timeline-slip-delete-token-r2.log) | `720c976bb800c2f989255bfef0431c263b72c50e0b2c052599e3b39e1cb1de50` |
| [timeline-slip-delete-token-r3.json](delivery/v2-development/timeline-slip-delete-token-r3.json) | `2b204735ced122529919f86277407242879d2321ae0a952fd22b4e38e1c4c8c8` |
| [timeline-slip-delete-token-r3.log](delivery/v2-development/timeline-slip-delete-token-r3.log) | `720c976bb800c2f989255bfef0431c263b72c50e0b2c052599e3b39e1cb1de50` |
| [timeline-slip-delete-type-r1.exit](delivery/v2-development/timeline-slip-delete-type-r1.exit) | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| [timeline-slip-delete-type-r1.log](delivery/v2-development/timeline-slip-delete-type-r1.log) | `fe67e0ca9d8e70169fb69b5fb0ca4755dd3223585f8dec641df093388cdb3f73` |
| [timeline-slip-delete-type-r2.exit](delivery/v2-development/timeline-slip-delete-type-r2.exit) | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| [timeline-slip-delete-type-r2.log](delivery/v2-development/timeline-slip-delete-type-r2.log) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [timeline-slip-delete-type-r3.json](delivery/v2-development/timeline-slip-delete-type-r3.json) | `5aec2f0cc31eb1fe358ee5cd0ccbbb1834530a233d8e41e9c52a5624c3551aae` |
| [timeline-slip-delete-type-r3.log](delivery/v2-development/timeline-slip-delete-type-r3.log) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [timeline-slip-delete-ui-origin-r3.json](delivery/v2-development/timeline-slip-delete-ui-origin-r3.json) | `8718593c4dfe3480a635ef61fff04d69d24e1f6111c9733b6f8d7fe1d7798e12` |
| [timeline-slip-delete-ui-r1.before.sha256](delivery/v2-development/timeline-slip-delete-ui-r1.before.sha256) | `aee191a1d797f69ede300090887355b495a80bffb03b11b39079f648bd14f0ae` |
| [timeline-slip-delete-ui-r1.exit](delivery/v2-development/timeline-slip-delete-ui-r1.exit) | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| [timeline-slip-delete-ui-r1.log](delivery/v2-development/timeline-slip-delete-ui-r1.log) | `3bae972ec0fa8844b833c54a2225fc3f44f0eb2449cd56449c9859d8a0438471` |
| [timeline-slip-delete-ui-r2.before.sha256](delivery/v2-development/timeline-slip-delete-ui-r2.before.sha256) | `2ea4ea576e82b1b469cef5f0be1c635bc73c2c23d0e3de68357c8f0c7b3507a2` |
| [timeline-slip-delete-ui-r2.exit](delivery/v2-development/timeline-slip-delete-ui-r2.exit) | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| [timeline-slip-delete-ui-r2.log](delivery/v2-development/timeline-slip-delete-ui-r2.log) | `78c8a85e03a4f3309896c6b2adb3f5e7305e5f4418098bd544ca2246fb4d5e5e` |
| [timeline-slip-delete-ui-r3.json](delivery/v2-development/timeline-slip-delete-ui-r3.json) | `92d17fdafeadfc7507fd8e1f4726cb6ccee76b62301029d5dffa26e062587f79` |
| [timeline-slip-delete-ui-r3.log](delivery/v2-development/timeline-slip-delete-ui-r3.log) | `ba0a40d213a3046012a93799790a4ac8204b239428e9b03680f6f343eaabf2b4` |
