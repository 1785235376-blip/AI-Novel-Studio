# ROUND3W_DECISIONS — R3-W design decisions

Decisions taken while completing R3-W, with the evidence that settled each one.

## D-1. Reuse the asset owner; do not build a Prompt store

A Prompt is an existing asset with `kind="prompt"` (bytes = the prompt text) and its payload under
`parameters.prompt`. Version = the asset's own `version`/CAS. Review = `promote_owned`. The chain is
`previous_asset_id` inside the payload, grouped into families by `family_id`.

**Why:** the directive forbids a second asset/version/review/task system or database. Verified from
source that the owner already provides immutable bytes, CAS metadata, native idempotency, a
lineage/`history` mechanism and a review marker — so a new store would duplicate solved problems.

**Consequence:** `ManualAssetImport.kind` is **not** widened (still `image|video|audio`); prompts get
their own dedicated entry instead.

## D-2. The shared conflict redaction stays; prompts answer from their own whitelist

`production_lineage_api.api_call` reduces `CapabilityVersionConflict.current` to `{version, status}`
so a conflict cannot leak internal snapshots or denied parent ids. **That property was not weakened.**

**Chosen:** a prompt conflict travels as `PromptAuthoringConflict` and is rendered by the prompt
routes from a strict whitelist. **Rejected:** exposing full `exc.current` for all APIs (directive
§2.6 forbids it), and hacking the service to encode state where a redaction layer would strip it.

## D-3. D2 was a test-contract error, and the assertion was corrected rather than dropped

The retry returned `201`; the failure was `library["entries"][0]["asset_id"]`. The Library entry
exposes **`head_asset_id`**; `asset_id` is the write receipt's field. The assertion now reads
`head_asset_id` and **still proves the same invariant** — the retry resolves to the revision the
interrupted attempt had produced. No idempotency, version, failure-injection or consistency
assertion was removed.

## D-4. A request identity is bound to its bytes, not just to its metadata

An interrupted create reused the existing asset's bytes while writing the retry's metadata — the
forbidden "old body ↔ new metadata" binding. The byte SHA-256 alone does not prove the first
request's *whole intent*, so the check combines the owner's recorded `idempotency_key`, the payload
projection digest (`CONTENT_KEYS`), and the stored body digest.

**Rule:** resume only when the stored bytes equal the request's bytes; otherwise refuse with
`PROMPT_REQUEST_ID_REUSED` and a recoverable state. **Nothing is claimed as success that cannot be
proven.**

## D-5. Revision allocation is conflict-detecting, not lock-serialized — re-verified

Checked directly rather than assumed: `workspace_mutation("asset-library")` is acquired **inside**
each owner method, and `project_scope` is a scope adapter. `PromptAuthoringService._write` is
therefore **not** one cross-process critical section. A structural test asserts the lock is present
in `create`/`update_metadata` and absent from `_write`.

**Chosen:** a deterministic loser rule (the higher asset id yields) plus the read-side
`DUPLICATE_REVISION` anomaly as backstop. **Rejected:** adding a new lock (the directive says reuse
the existing one) and claiming serialization that the code does not provide.

**Guarantee:** two racers cannot both be confirmed as the family's sole next revision, and a losing
racer's content is preserved and reported — never silently deleted.

## D-6. One minimal, prompt-scoped owner extension

`approved_at` is in the owner's general metadata allow-list, so an ordinary metadata write could
self-approve a prompt revision. A `kind == "prompt"` guard now refuses changes to
approval/provenance identity. The review path uses `promote_owned`, which does not go through that
method, so review still works; **other asset kinds keep their existing behaviour** (asserted).

This is the only change to `AssetLibraryService` in R3-W.

## D-7. `previous_asset_id` is a reference, not a lineage claim

It is a string reference in the prompt payload. The projection names it as such and exposes **no**
`lineage` record. Calling it "Asset Lineage" without a real `annotate_lineage` edge would overstate
the implementation; promoting it to a true graph edge is Round 4 work.

## D-8. Privacy default unchanged; masking is still not confidentiality

New drafts are private to the resolved author; all reads and writes use the server-resolved actor,
scope and project identity. R3-R-08 remains **PARTIAL**: presentation masking is not encryption, and
the generic asset download contract was left alone.
