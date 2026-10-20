# U16 independent Studio Image batch — CPU cutout first slice

Requirement: `docs/v2/V2_REQUIREMENTS_LEDGER_20261019_R2.json`, `/entries/343`
(`U16`). Its historical lead is not acceptance. Source base is product
`19d90d51eed4a9683c4290592dd91495125e5fcf`; original batches supported only
PROOF/EXPORT/SYNTHETIC_MEDIA/REGISTERED_MEDIA/VOICE_REDO via old owners.

Add only STUDIO_IMAGE with an explicit saved image pin, saved mask pin, stable
request ID and optional license note. The original Studio preview verifies the
two authorized assets, exact versions/digests, mask pixels/dimensions and current
incarnation. The closed command is `m5.image.cutout`, empty prompt/parameters,
provider/model null, allow_cloud=false. No raw bytes/path, discovery, GPU model,
download, new algorithm or execution queue is introduced.

Original U16 preflight/confirm/stop/CAS/claims/UNKNOWN lifecycle is reused. The
hard limits remain20 total items, concurrency1, known cost0. Preflight and
confirmation create no ImageJob and invoke no cutout. Each explicit dispatch
persists an original stage claim and a create intention before **one** original
ImageJob create and one original execute. Completion leaves a private original
AWAITING_REVIEW candidate. Each candidate requires its own authorized preview
and explicit original ImageJob review, bound to batch snapshot/version, item,
job/version/request digest and output digest.

The atomic original batch transaction reuses a previous exact same-key preflight,
including UNKNOWN, rather than allocating another batch that could resend that
key. A changed body with an owned key refuses; duplicate keys and duplicate
image/mask pairs in one batch refuse. An unknown create/execute result is never
retried or requeued. Reconcile only reads the matching original job; it can
recover a proven terminal receipt without execute/create. QUEUED/unresolved
receipts remain UNKNOWN. Failed image items are not reset by failed-only retry.

The API retains old novel scope authorization **and** the injected original
Studio Host invoker for image commands. It checks the real Host request/principal,
session generation, original actor/scope/permission and project incarnation.
Server-only job bindings fence standalone reads/actions and late execution/review
after stop/revocation. Original production pixel/source guards run under their
existing leases; full batch preflight runs before/after, never nested in asset
or queue phases. Missing/stale sources do not get silently replaced. Unreadable
job receipts never expose cached private candidate details. Old five-kind input
DTOs retain their exact original serialization.

The panel adds explicit image/mask selections and fixed pin inspection using
existing fields/primitives. Same asset pairs cannot be added twice; stale
selections remain visible but disable preflight. Busy/scope fences and original
review actions are reused. No auto-confirm/Save/dispatch/next-item/approval occurs.
The original safeBatchesClient and shared shell/tokens are unchanged.

Evidence is in task-local `../u16-image-batch-evidence-20261020`: raw initial
failures and focused final File/API/frontend results, one type/build pass,
controlled component screenshots and digest-verified original CPU PNG. Mounted
tests use actual File owners and trusted synthetic Host sessions, not a real
user Host session. PostgreSQL, real Host/desktop acceptance, full E2E, actual
model/paid execution and universal U16 acceptance remain NOT_RUN.
