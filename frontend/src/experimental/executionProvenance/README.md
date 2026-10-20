# Original Job execution provenance detail

`ExecutionProvenancePanel` is an additive detail slot over the original standalone
`StudioProductionClient.get(owner, id, signal)` and, when supplied,
`StudioClient.asset(id, signal)`. It creates no execution endpoint, queue, template,
asset store or browser persistence. The initial read and every subsequent read are
explicit. It exposes no execute, refresh POST, retry, reconcile, review or adopt
capability. The original owner has no safe FAILED retry interface; UNKNOWN cannot
replay. The existing video `refresh` operation is a mutation and is deliberately
not part of this component's client type.

The host supplies `selection` from a decoded original Job, current project/branch,
an identity/session fence, the original `read` authorization wrapper, and
`active`/`denied`/`isCurrent`. A source or permission change retires pending reads
and visible data. Auth denial remains latched for that identity/client scope.
Newer versions of the **same request** may be explicitly read; they grant no
execution or adoption permission. Version rollback, same-version receipt changes
and immutable request changes between reads are rejected. Do not pass a partial
Graph media projection as a `ProductionJob`: standalone GET rejects graph-bound
jobs, and the graph projection does not provide this provenance contract.

The projection uses allowlisted numeric/enumerated parameters. It does not render
prompts, license notes, arbitrary recipe/workflow nodes, URLs, credentials or raw
error bodies. Provider/model identities come only from the authorized Job receipt;
credential-shaped identities are withheld. Missing data remains missing. A local
recipe declaration or a synthetic fixture does not prove real model execution.
Cloud receipts are described as interface calls with unavailable internal nodes.

Candidate version and formally approved asset version are separate. When an asset
reader is available, the formal asset must match scope, candidate id/digest/kind,
approved asset version and non-deleted state. An unreadable or changed asset is
not substituted. Job approval does not prove adoption into a canvas.

`origin` is the original host's `CanvasImageTaskOrigin` capture. For legacy Jobs
without a recorded binding it is shown only as a session capture after matching
its exact input pin. It never infers a canvas/card from an asset shared by several
positions. A binding records an intended return position, not a durable adoption
receipt.

`task-detail.integration.patch` is the author's retained, unapplied example from
the pre-binding baseline. The current `StudioCanvasImageTaskPanel` has integrated
the panel semantically, supplies the original production GET and StudioClient
asset reader, and retains the original task/scope guards. Do not apply that older
example over the integrated entry. No history or result-return owner is changed.

When the original Job command contains a checked `studio-canvas-return/1` binding,
the panel displays that recorded canvas/card/source pin. It does not infer an
adoption receipt or certify current CAS, permission, source or incarnation freshness;
the original recovery/adoption owner rechecks these before any write. Legacy Jobs
without the field retain the session-only/missing-origin boundary.
