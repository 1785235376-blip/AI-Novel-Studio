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

`origin` may only be the original host's `CanvasImageTaskOrigin` capture. It is
shown as a session capture after matching its exact input pin. It is not durable
Job provenance and never infers a canvas/card from an asset shared by several
positions. The existing Job contract has no durable canvas/card origin or durable
adoption receipt, so cross-session position recovery remains unavailable.

`task-detail.integration.patch` is a minimal, **unapplied** insertion into the
existing `StudioCanvasImageTaskPanel` detail. The owner should review/apply it in
the integration line. That example has no asset getter in its current props, so
it shows Job approval as recorded and leaves current formal-asset verification
explicitly unavailable. A host with the original StudioClient can supply
`assets={studioClient}` to enable the original asset GET verification. No history
or result-return component is changed.
