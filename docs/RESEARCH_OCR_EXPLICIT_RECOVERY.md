# Explicit trusted-host native OCR recovery

The original Research, Job and ModelBroker owners now support an explicit recovery operation for interrupted native OCR receipts. The mounted endpoint requires the existing trusted-host session and domain write authority before parsing the bounded request. The operator must explicitly confirm that the previous executor has stopped and supply a nonblank evidence note. The UI uses an unchecked confirmation, bounded note and explicit action; it never retries inference automatically.

Recovery validates the original actor, scope, project incarnation, cached and persisted job identity, binding and request digest. Known active executions are refused. The original native-only broker seam reconciles only its pinned zero provider-fee ledger, preserves the first evidence and uses a stable recovery identity for retry. This is not a claim that host compute is free. Original project leases remain held through each owner commit. The ledger commits before the Research receipt: an injected second-phase failure demonstrates idempotent retry, not cross-owner atomicity. Cancelled or invalidated source receipts remain cancelled or invalidated; recovery does not expose or restore their source or results.

Final verification:
- File recovery: 9 passed, 9 PostgreSQL cases deselected.
- Real PostgreSQL recovery: 9 passed, 9 File cases deselected, database OID 16384 retained and server stopped.
- Catalog and PUBLIC package checks: 6 passed, including an actual offline wheel.
- Research UI: 20 passed across 3 files. TypeScript, production Vite build and 52-file UI token guard passed.
- Earlier broader File and PostgreSQL runs and all original logs are retained in delivery records.
- API catalog has 2367 mounted method/path entries and application fingerprint de7b3d510115d7ef00cda67c8f3a9abc7b441c5837e145d19c6dfb33aa2df516. This is not a feature-completion count.

Tests include explicit boolean rejection, active-worker refusal, actor/project-incarnation isolation with a legitimate new-project OCR positive case, cached identity mismatch, revoked source, original commit failure/retry, and mounted trusted-host routing. Restart state is injected as an original queued persisted job and reopened through the original manager. This is not an actual process-kill or power-loss acceptance test. Confirmation of the old executor stopping is an operator attestation, not OS process discovery.

The current panel exposes recovery for its selected image's interrupted receipt. Cancelled/revoked-source recovery is covered through the API but a project-wide recovery list UI is still pending. Real production browser acceptance, Chinese/PDF/general vision quality and whole-product acceptance remain incomplete. Existing browser sandbox failure is not bypassed. No paid model/API, main merge or Release was used.
