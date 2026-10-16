# A13 production receipt inspection and original-owner recovery

Baseline: `8b7540bb5107940a8de60abd56e26ccf1dfc662f`. The containing local commit identifies delivery; no push or hosted CI. A13 remains **PARTIAL**.

## Audited gap and existing owners

`ProductionLineageService` already captures immutable task/source/version/digest/parameter/environment/output evidence, explicitly preflights current dependencies and budget, and creates a new pointer to an original MediaService task. Explicit execute/cancel and replay idempotency remain original-owner operations. Its existing File fixtures cover synthetic PNG repeatability, retained pending review, restart, cancellation and unavailable outputs; that is protocol evidence, not native/provider quality.

`ChangeImpactService` already owns selection recipes, dependency/lock/current-source checks, selective task preparation and explicit execution. Graph reusable-node cache is a different existing execution owner; it must not be inferred from a production manifest digest or duplicated here. Manifest projections do not provide a complete per-stage cache ledger, historical approval snapshot, settled actual cost or a direct source-selection handoff to ChangeImpactPanel.

The concrete gap was a raw source/outputs list and generic media navigation that discarded the exact task ID. The original MediaPanel already accepts `requestedTaskId`; this slice reuses it. TaskCenter's separate exact task/candidate inspector was already implemented and is unchanged.

## Bounded implementation

- Clear manifest ID/version plus captured original task ID/version, paginated twenty-row source pins and at most twenty original candidate ID/digest entries. Original environment/parameter evidence remains visible.
- Strict bounded pin/output interpretation rejects malformed/oversized collections, withholds unavailable identities and incomplete version/digest navigation, and blocks duplicate source identities and duplicate candidate IDs/indices. Unknown collections show unknown counts, never zero. Source and candidate content is not fetched by this inspector.
- Explicit task and replay links carry the original MediaService authority and exact task ID into the existing App/MediaPanel path. Original current task/status and review remain owned there; no task is created, retried, reconciled or approved by navigation.
- Chapter links pass the recorded ID/version but explicitly say they open the **current chapter body**. Existing App anchor/version behavior is retained. This is not historical source replay or exact saved text retrieval; the manifest pin is never upgraded. Asset pins remain metadata-only because there is no verified historical-asset navigation contract here.
- Every new cross-panel link requires explicit leave confirmation warning about unsaved source declarations and transient preflight loss. Cancel retains the original form. Consent and retained handlers are invalidated by manifest/replay fingerprint, source digest, target, busy, callback and lifetime changes.
- Existing preflight blocker codes are grouped into source/authorization, environment/model, original output and cost/current authorization with actionable original-owner guidance. Unknown future codes stay blocked with no invented retry. This grouping is an explanation of the existing preflight, not new independent stage execution or cache evidence.
- Direct selective rebuild remains explicitly not ready from this manifest. The user must return to the original change-impact owner to choose the current source and concrete outcomes and preflight again; no guessed source/recipe/task or execution fallback is manufactured.

## Verification

Evidence index: `production-receipt-recovery-20261016.json`. Referenced original receipts preserve full commands, environment, exit codes, timestamps, source hashes and logs. All indexed checks passed against identical final source hashes.

- 97 selected mocked UI/pure tests across eight files, including real App navigation with actual A13 and MediaPanel components: cancelled leave preserves dirty source declaration; explicit task navigation selects the original task; explicit source navigation shows the current chapter rather than claiming historical text; all navigation traffic is GET-only. Original replay creation/idempotency, cancellation during execute and late-response cases remain covered.
- Actual retained-handler tests cover target/busy/unmount, callback/receipt change and same chapter ID/version with changed digest. Malformed/null/oversized/withheld evidence, duplicate pins/outputs, unknown blocker fallback, source pagination and missing identity/version cases are covered.
- Four original nonsecurity File owner cases: synthetic replay/new original task/pending review/restart, historical environment evidence absence, corrupt persisted output never claiming equality, and running cancellation dropping late output without restart retry. Plus 30 PUBLIC profile checks. No skips.
- Forced TypeScript build, Vite build, test discovery, global and scoped token guards, `git diff --check`, and 487-file PUBLIC source closure. Existing Vite large-chunk and Starlette/httpx deprecation warnings remain.
- Independent reviewer reran 97 tests against unchanged source and reported no remaining blocker in the new receipt/navigation scope. Final commit verification follows publication of the local SHA.

The first UI run retained two failed assertions because this Vitest version lacks `toHaveBeenCalledExactlyOnceWith`; assertions were corrected without changing production behavior. Superseded passing receipts remain retained. No failed receipt is replaced by a false success claim.

## Remaining boundaries

Existing MediaPanel locates tasks by ID using its original list/find behavior; this slice does not add duplicate-record validation to that owner. It does not add direct exact candidate selection or transplant TaskCenter's candidate inspector. Candidate snapshots here lack historical approval versions, so current approval is never inferred from a digest or successful task. Full cost/review/stage-cache snapshots and direct selective-rebuild integration remain open.

Browser/visual/native IME/HTTP integration, PG/P0/security lifecycle, Windows/GPU/provider/real model quality/user-machine/full RC are **NOT_RUN**. No source/controller/permission/schema/production backend, protected UI or model execution changes; no new store/queue/reconciliation mutation. P0 remains BLOCKED; R3-GATE HOLD; production Prompt Adoption writes disabled. No user computer, saved environment, paid service, hosted CI, push, merge, release or tag. All prior evidence and denial/cost boundaries remain intact. Parent review of final SHA precedes further tracked feature edits.
