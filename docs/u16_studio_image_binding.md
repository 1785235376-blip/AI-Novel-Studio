# U16 Studio Image server binding

Product base: `19d90d51eed4a9683c4290592dd91495125e5fcf`.

The composition root passes the existing SafeBatchesService to the independent
workspace router. Its existing `create_production_invoker` (trusted Host request,
principal, session generation, original Studio permission and incarnation guards)
is injected with the existing ProductionExecutionService. No new resolver or
permission rule is introduced. No credential or Request is persisted.

`batch_binding` is an optional **server-only** production method argument. It is
not a MediaCommand/MediaCreate field. The exact closed contract is
`studio-image-safe-batch/1`: batch ID, item index0–19, actor, scope key, project
incarnation, frozen batch snapshot digest and original command request ID. Only
`m5.image.cutout` may carry it, without Graph/benchmark binding or a model route.

The original ImageJob context/idempotency digest includes this binding. Production
create/read/list/candidate/execute/cancel/reconcile/review verify exact binding;
standalone callers supply none and cannot see or act on a bound job. Matching
batch calls recheck original batch ownership, scope, frozen snapshot, item/request
and recorded job identity. Create/execute require a confirmed RUNNING stage with
the original in-process claim. Candidate/review require that exact COMPLETED
stage and a noncancelled/nonUNKNOWN batch. Repeated create after binding is denied.

Metadata-only batch checks may run under original queue/asset locks and must not
recursively read a job or rerun preflight. The adapter's outer guard verifies the
full batch snapshot; original production source guards verify current pins/bytes.
Late execution/publication and review guards also fence stop/revocation. An orphan
or UNKNOWN is an observation/reconciliation case, never permission to resend.

Unbound standalone, Graph and video benchmark calls retain their default arguments
and original admission. No queue, algorithm, scheduler or automatic dispatch is added.

The exact validated binding is retained in candidate publication and original
ImageJob candidate-origin checks as well as the job context. A bound command
uses its original bound preview digest; an unbound preview cannot authorize it.
Full batch preflight remains outside original queue/asset leases.
