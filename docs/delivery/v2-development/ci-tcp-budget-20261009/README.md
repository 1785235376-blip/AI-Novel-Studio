# Original TCP job-budget repair, 2026-10-09

## Preserved failure

- Branch head: `99e3c636bc59f45f5faa4b7af84b80981f1ec2e5`.
- PR run: [37902141902](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37902141902), attempt 1.
- Actual PR checkout/event SHA: `42d8355c00eb545d40ab503c4429315bb7eef74e`.
- Actual tree: `b0595aaccb9c42437f3d61aaf209a61de94d584d`.
- File job: [113726946131](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37902141902/job/113726946131), cancelled.
- The full original-order File process reported **6,190 passed / 3,259 exact skips** in **1,080.84s**, with 9,449 nodes. The workflow step lasted 1,089s.
- The following original TCP step ran for 32s and was cancelled by the existing 20-minute job limit. It has no final successful TCP XML and is not a passing job or aggregate.
- Artifact [11603852261](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37902141902/artifacts/11603852261), named `backend-file-shard-0-42d8355c00eb545d40ab503c4429315bb7eef74e-attempt-1`: GitHub metadata reports 858,762 bytes and SHA256 `076869f23aa629211dea4cfee260c116e67ae1ab0a19c22f6a061245a8da0c19`. The ZIP was not downloaded as part of this repair verification; this is provider metadata, not a local ZIP verification claim.

`original-cancelled-file-job.json` and `original-cancelled-file-job-timings.json` are byte-identical copies of the existing monitoring evidence. They are retained unchanged, including the cancelled conclusion. No historical receipt is rewritten or joined to a later run.

## Narrow repair

The only execution change is moving the exact original two real TCP tests into a separate **10-minute** `backend-tcp` job. File remains one original-order process capped at **20 minutes**; both PostgreSQL shards remain capped at **55 minutes**. Both original Backend aggregate checks require the whole full-suite matrix and the TCP job to have succeeded.

The additive runner checks source/manifest/dependency/checkout/event/run/attempt/repository identity and records actual raw TCP output. The joiner validates the originals, creates a fresh byte-identical aggregation layout, and invokes the untouched original reconciler. The workflow independently invokes the original reconciler CLI again. Raw input artifacts are never rewritten. Full details: [TCP evidence design](../../../../.github/ci/TCP_EVIDENCE.md).

Unchanged gate/prepare/test/frozen-manifest hashes and the final new source hashes are in `source-identities.json`. Existing frontend, independent V2 browser, Windows and Interop work is outside this repair. No existing test or assertion, historical skip/external-gate map, frozen gate, API catalog or V1 manifest was changed by this repair.

## Verification receipts

- Initial infrastructure invocation outside the nested owned profile: **276 passed** (original 174 plus additive 102), 5.11s. Temporary `.runtime` receipts preserve that invocation.
- First owned-profile invocation: **275 passed / 1 failed**, 5.94s. The explicitly synthetic pytest fixture inherited the enclosing repository root and emitted prefixed synthetic JUnit classnames. The unchanged JUnit validator rejected them. This real failure is retained in `../ci-tcp-budget-infrastructure.{json,log,xml}`.
- Corrective change: the temporary synthetic fixture now creates its own minimal `pytest.ini`, establishing the intended synthetic root. Production runner, workflow, product tests and all old assertions were unchanged by that fixture correction.
- Corrected owned-profile invocation: **276 passed**, 5.82s, comprising all original 174 infrastructure tests plus 102 new checks. Receipts: `../ci-tcp-budget-infrastructure-fixed.{json,log,xml}`. The before/after source snapshots are identical.

The new checks include wrong/missing identities, manifest/dependency/source drift, missing/duplicate/altered evidence, failed/cancelled/skipped/pending enclosing jobs, incomplete receipts, raw TCP skip/failure/error/truncated/foreign/duplicate nodes, full-shard corruption, overwrite/symlink refusal, and unchanged gate/job/full-suite bytes. Genuine synthetic pytest subprocesses exercise the producer's pass/failure/skip/source-change/abort behavior. These synthetic fixtures are not claimed as product TCP or PostgreSQL execution.

After the final V2 source manifest refresh, the unchanged original real TCP tests passed **2/2 in 28.04s**, with zero skips/errors/failures. Receipts: `../ci-tcp-budget-real-loopback.{json,log,xml}`. All 1,661 manifest sources match and the before/after snapshots are identical. The unchanged original reconciler independently accepts the exact raw two-node JUnit; `real-loopback-validation.json` records its hashes and the V2 manifest SHA256 `df72d854d942b0759b9d02229c33523bb1dd11470dd95c5c12a405a73c9a66ab`. This is local owned-profile execution against the frozen working sources, not a fabricated hosted run. Actual hosted producer provenance and the complete same-run aggregation must still be established by the next exact-source GitHub Actions execution. Publication remains owned by the parent task; no commit, push, cancellation or rerun was performed by this repair worker.

## Dependency identity compatibility

A read-only audit of genuine hosted receipts found byte-identical 709-byte,
38-row package inventories (SHA256
`74cf563c7bc414940db61b6c9e84d500b0507b0b559590452b040b57a5738b12`)
in current 99e3c63 push File artifact 11603118144, current PR V2 browser artifact
11602858790, and historical fe4d250 PostgreSQL artifacts 11602087694 and
11601719569. `hosted-dependency-parity.json` preserves the audit and original
archive identities. This demonstrates compatibility of the unchanged dependency
install steps; it is not a current PostgreSQL success or a same-run join, and
no historical result is substituted into new coverage evidence. The local owned
profile package bytes also match, while its Python version is separately
recorded as 3.12.14 in `local-runtime.json`, not the hosted pin of 3.12.9.
