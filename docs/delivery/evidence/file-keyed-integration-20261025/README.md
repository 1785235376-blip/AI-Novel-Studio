# M5 + keyed File generation integration (local only)

Historical merged-source evidence for d76acaa before the required default-off
experimental gate. These counts do not certify the subsequent opt-in change.
See [opt-in verification](../file-keyed-optin-20261025/README.md) for fresh results.

Base: canonical M5 `18c8744b4c2f208cbfe5607ad1d672b7dcb8e58c`, tree
`67a2f5f02758129403524c8fd390c4e84685224f`.
Applied reviewed standalone M6 `942099b6b0599cf1449901fedb9671aec0d08359`
without changing that frozen branch/worktree. No public writes or uploads.

## Actual merged-source verification

- Combined regression: **682 passed, 3 live-PostgreSQL skips**, zero failures,
  147.25 seconds. No deselection. Includes all five M5 receipt-fence tests and
  all original activation, manual/memory, passive PG protocol, restart,
  idempotency, variants, adapter and specialized compatibility selections.
- Independent review: **30 passed**, 54.28 seconds: previous 25 M6 probes
  rerun on this merge plus all five M5 receipt cases. Includes genuine keyed
  HTTP → original Mock stream → durable candidate → HTTP adoption → actual
  Canon and bound memory effects and writer/manual/memory late-owner fences.
- Separate original-composition three-way concurrent same-key HTTP proof:
  **1 passed**, 9.72 seconds.
- Production and full selected input/source hashes unchanged across runs.
  Production manifest SHA256:
  `dfe76568ee2ce066923c46667d58e21197e93f3005208be0212dd196597a6cef`.
  Final generation repository SHA256:
  `6c0dcff5192f58b41708ca901ffba8270b50877a77e78dd278fae976e35dec72`.

## Exact conflict resolution

Only `app/repositories/generation_repository.py` conflicted. The merged save
keeps the original M5 helper unchanged, pins the leaf to the captured Job path
for opted-in receipts (also writer receipts), serializes the payload, checks
M5 root/physical-owner/memory expectations, then checks M6 writer owner/source
expectations immediately before atomic write. The former duplicate standalone
memory final check is supplied by the unchanged M5 helper. Both v1 passive
manual/memory and v2 writer/manual receipts retain their original protections.
No API mode expansion, binding upgrade, fallback or redispatch was introduced.
Original M5/M6 file snapshots and the resolved diff are in `implementation/`.

## Evidence and limits

`implementation/run_regression.sh` records exact combined selection and raw
stdout/XML plus before/after hashes. The genuine Mock preimport runner remains
at `../file-keyed-activation-20261025/run_tests.py`; network calls are blocked.
`independent/MERGED_REVIEW.md` and `independent/merged-freeze/` contain the
separate review, probes, commands, stdout/XML and frozen sources.

Earlier standalone 677/25 counts remain historical, not evidence for this merge.
Live PostgreSQL, real local/external model inference, Windows and frontend are
NOT_RUN. Local adapter metadata proof is not real-model execution. Specialized
Graph Mock seams/passive contracts are not full live director/OCR certification.
Raw historical failures remain preserved without whitespace normalization.
The new generation entry is not part of the approved public M5 upload and
requires separate authorization before publication.
