# Independent default-off compatibility review

Base: d76acaa68d0a273f492702a496fd51f8bf061ac8, worktree file-keyed-integration. Reviewer made no production or repository-test changes; probes/runner/evidence are isolated runtime files.

## Scoped result

**41 passed, 3 existing warnings, 60.90 seconds, exit 0.** This is the prior 30-case M5/M6 independent set, 3 new independent switch probes, and all 8 added default-off/switch-off controls. Production and test/probe hashes verified unchanged before/after.

Production manifest SHA256: 7a6bcd2663e4ce353c52e12052e986d1f0dbe09cd47a10c72445a81a07920c57.
Settings file SHA256: fea26ebcccdf421b0b9e5b53c0150682b839556988d766ee0276025b6a669b32.
Admission file SHA256: 1576e9b718db05d50e530c2110c42bdf4d97b36bd1b72d00748ffff8db548777.

## Inspection and proof

Production delta is six added lines: a default-false experimental setting plus an early return from NEW admission when off. The flag is not consulted by existing bound read/review/execution capabilities or retained-receipt handling. No existing binding is downgraded or reconstructed by this switch.

Fresh-import tests prove absent environment means false and explicit environment true opts in. An independent HTTP probe proves payload fields cannot opt in against server off. Actual original default-off LOCAL_ONLY continue/rewrite use the unbound Mock path, retain keyed replay, permit cancellation and cancelled/failed retry, and do not gain a private execution capability.

Switching off after real bound QUEUED preserves the issued live grant and exact binding through completion and replay. Bound cancel/retry remain refused, cold restore has no execution capability, and original HTTP manual adoption remains available under its existing owner/source fences. A new key after switching off follows legacy unbound admission. Cold queued bound restore remains FAILED without restart. All original positive and owner-window adversarial M5/M6 probes continue to pass with explicit fixture opt-in.

All four prior legacy fixture files independently compare byte-for-byte equal to canonical18c8744: generation_idempotency_contracts, generation_worker_authority, generation_admission_receipts and generation_variants_phase3. The prior HYBRID-only scope edits are removed rather than relied on for default compatibility.

## Evidence and limits

optin-freeze/ contains the exact command, stdout/XML, source and input manifests, before/after checks, frozen changed source, copied probes/runner, six-line production patch and legacy-fixture comparison results. Runner clears the experimental environment variable before imports, explicitly uses Mock/nonpackaged mode, removes API/database secrets and blocks sockets. Fresh subprocess configuration probes import configuration only.

Scoped PASS with no remaining concrete compatibility defect found in these tested boundaries. This is not an independent full-aggregate, live PostgreSQL or real-model verdict. No public write, push, deployment or other publication was authorized or performed.
