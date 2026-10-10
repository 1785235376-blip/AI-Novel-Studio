# M4-C receipt admission follow-up

Bounded correctness continuation of published `ef79251fdc1a9b17f5733a28ee97afc525b73d7f`.
The prior 109-file M4-C checkpoint and all real-model/failed diagnostic evidence remain intact.

## Defect and owner fix

A prompt within the unchanged 32,000 UTF-8-byte input limit can exceed the existing
64,000-byte receipt or containing initial asset metadata limit after JSON escaping.
The original path discovered this only after successful model execution. Durable Job
output was retained, but the asset remained INCOMPLETE and retry could not reduce it.

Two independently measured red inputs on the exact published source demonstrate
both failures without inference: 31,784-byte prompt / 66,089-byte receipt /
67,046-byte initial metadata, and 30,584 / 63,689 / 64,646 respectively. These are
synthetic route-fixture measurements, not real-model performance results. A sentinel
proved that both invalid-to-archive requests reached original Job preparation.

The narrow fix validates the actual JSON bytes through the original asset validator
after the existing permission/route policy and before Job preparation. Shared passive
builders keep the receipt, source and containing metadata shape identical to actual
archival. Only not-yet-created UUID, SHA-256 and UTC timestamp fields use owner-proven
maximum encoding forms; they are never persisted as evidence or authority.

Both 64,000-byte caps, the input cap, original HTTP 422/error codes, legacy opt-out,
permissions, CAS, original 180-second deadline, human review and private asset boundaries
are unchanged. Oversized admission creates no Job, reservation, generation or asset,
mutates no run, and performs no model call. No prompt truncation, limit increase,
migration, deletion, replay, new queue/registry or manuscript apply was introduced.

## Verification

- Source: 1,743 runner inputs; map SHA256 `8d7ede7975bf4680ae5f6dd2cf702430b21d404b3d6bd61de50d551e4537ed8f`.
- Focused File: 102 passed / 101 opposite-profile deselected / 0 skipped; four files.
- Fourteen new shared File/PostgreSQL cases cover receipt and outer metadata each at
  63,999/64,000/64,001 bytes, double escaping, Unicode/control preservation,
  original input/permission precedence, no side effects and legacy opt-out.
- Existing tests were not changed. The first new legacy test omitted the original
  explicit refresh; its failure is retained and the fixture now exercises that step.
- Real CPU recheck: official already-verified llama.cpp/Qwen bytes, unchanged owned
  host configuration, one original Job and one TextAsset v1→v2; dispatch-to-draft
  3.179 seconds, entire check 15.244 seconds, normal runtime exit 0, unchanged source.
  Real execution passed; quality and real-browser acceptance remain NOT_RUN.
- Extended same-source 8-file File regression: **233 passed / 189 opposite-profile skips**, 172.97 seconds.
- Same 8-file fresh PostgreSQL: **233 passed / 189 opposite-profile skips**, 666.59 seconds; empty new database, 20 unchanged migrations, original real identity and normal shutdown retained.
- Original catalog/coverage/reconciliation/TCP infrastructure: **279 passed** after the generated inventory settled. The earlier 279-pass run overlapped inventory writing and is not used as final-manifest evidence.
- Two independent complete collections agree on **11,321** ordered nodes and backend classifications, +28 from the prior checkpoint. Frozen V1 bytes and old skips remain unchanged. Collection is not execution.
- API catalog regeneration reports **2,123 operations**, no added/removed endpoint. The first complete collection overlapped that regeneration and correctly rejected full-source drift; that failure remains, followed by the two stable collections.
- [Final source-bound verification](docs/delivery/v2-development/stage-m4c-size-publish-verification.json) checks original raw evidence bytes and all before/after maps.
- Prior checkpoint `ef79251f`: all five original runs are terminal, **29 jobs: 23 success / 4 failure / 2 cancelled**. Four PostgreSQL shards passed; each event's two-shard profile records **7,505 passed / 3,788 profile skips** across all 11,293 collected nodes. Both File executions were cancelled with incomplete receipts and no final backend JUnit. Four strict joins correctly failed their execution prerequisites; receipt download/reconciliation was NOT_REACHED. Cancellation timing is consistent with the unchanged 20-minute File budget; logs explicitly say only “The operation was canceled.” This is **PARTIAL_HOSTED_CI_CAPACITY**, not complete-source PASS. [Original terminal evidence](docs/delivery/v2-development/stage-m4c-ef79251-hosted-terminal.json).
- On that prior published source, both hosted frontends passed 2,401 tests / 8 original skips and all browser/build stages; original TCP, two Interop runs and R123 succeeded. Hosted Windows evidence remains limited native/build/package contracts. Those results are not promoted to follow-up-source acceptance.
- Follow-up exact-SHA CI: NOT_YET_PUBLISHED.

## Historical evidence and limits

All red receipts and native logs are retained in the [evidence index](docs/delivery/v2-development/m4c-size-admission/manifest.json).
The [real CPU recheck](docs/delivery/v2-development/m4c-size-admission/real-attempt-1/acceptance.json)
binds its own stable source before/after and original owner receipts. No successful
results from different source maps are combined into a final-tree PASS. The earlier
full frontend/build applies to ef79251f; this follow-up changes no frontend source.
Hosted checks use Mock and only limited Windows contracts. Historical M4-B File
capacity cancellations and failed strict joins remain separate; old independent
review BLOCKED remains. Broader models/quality, Windows/GPU, browser-real-model,
reserved API execution and large Image/Video modules are not completed by this slice.

Raw diagnostic and native logs retain their original whitespace. Source and
document whitespace checks pass; whole staged checking may report raw-log
trailing spaces/EOF lines, which are not reformatted as evidence.
