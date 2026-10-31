# Pending legacy image candidate: read-only contract proposal

Status: **PROPOSAL ONLY; no endpoint or proxy implemented.** Source baseline: `8738ecb2ecd667dd9d401c4c16c2136f812e2a17`. This follows the [image flow ledger](CLOUD_IMAGE_FLOW_LEDGER_20261023.md) and concerns the original legacy image-job owner only. It does not replace the separate `studio-image-execution/1` or production-job contracts. This review did not execute a provider, accept a job, retrieve media, run restricted media security checks, or change runtime code.

## Decision and actual source capability

The smallest useful addition is an explicit description and bounded read of **inline content already held by the original job owner**. It cannot make pending network candidates previewable: those records contain an address, not an owner-held binary candidate. A network result must remain unavailable under this proposal.

| Current source fact | Consequence for the proposal |
| --- | --- |
| [ImageJobService](../../app/services/image_job_service.py#L23) persists the legacy queue in its existing JSON owner. `for_actor`, `_path`, and `list` select actor/novel/branch records; `list` excludes `studio-image-execution/1`. | Read through that owner. Do not scan other actor roots, invent a second candidate store, use the browser node association as authority, or reinterpret a Studio job as legacy. |
| [Completion](../../app/services/image_job_service.py#L162) saves `SUCCEEDED`, `asset_uri`, and update time. The result guard limits the URI to 36 MiB **characters**. It does not publish a legacy candidate asset, output digest, or formal job version. | Inline data may already be present in the row. A network, file, relative, or blob URI is not proof that this owner holds readable content. Do not dereference any such URI. |
| [Accept](../../app/services/image_job_service.py#L181) separately decodes or acquires media, inspects it, creates a formal asset, then records `APPROVED` and `asset_id`. | A read must never call accept, `fetch_media_bytes`, the provider registry, generation, edit, ingestion, inspection, or an asset mutation. Accepted assets use their existing asset route. |
| [Legacy routes](../../app/api.py#L2425) distinguish `domain.read` from create/execute/cancel/retry/accept `domain.write`. | Being able to read a candidate does not grant any write, execute, review, or adoption capability. |

No arbitrary file or URL input is part of the proposed API. No additional credential or secret is required. Existing rows and the existing `{items}` list response remain unchanged.

## Proposed additive API

The following paths and fields are proposed, not available at this baseline:

1. `GET /api/novels/{nid}/image-jobs/{job_id}/candidate`: a small, authorized descriptor, without `asset_uri`, provider URL, inline payload, credentials, execution token, or storage path.
2. `GET /api/novels/{nid}/image-jobs/{job_id}/candidate/content`: only a bounded pending-inline response, conditional on the descriptor's original-owner observation. It performs no mutation and emits no redirect.

The descriptor should have a new, explicitly named response **schema** contract, exact job/novel identity, the observed `status`, `approval_status`, `attempt`, `updated_at`, and `request_sha256`, plus one of these content states:

| Proposed state | Meaning and returned content information |
| --- | --- |
| `INLINE_AVAILABLE` | The exact legacy row is `SUCCEEDED`, `PENDING`, has no `asset_id`, and holds a nonempty supported raster data URI within the proposed limits. Return only a bounded declared MIME, decoded byte count, and an opaque owner observation validator. Availability is an observation, not a durable permission grant. |
| `APPROVED_ASSET` | The row is `SUCCEEDED`, `APPROVED`, with a valid `asset_id`. Return the reference, not pending content or a URL. The caller must use the existing scoped asset download and its current access checks. |
| `UNAVAILABLE` | Return a fixed reason such as `NOT_READY`, `CONTENT_NOT_HELD`, `INLINE_UNSUPPORTED`, `INLINE_INVALID`, or `INLINE_TOO_LARGE`. Do not echo the rejected value, a parser exception, a URL, or storage location. |

An authorized existing network-only row is `UNAVAILABLE / CONTENT_NOT_HELD`; it must not trigger a probe to establish reachability. A record with a different contract is not a legacy candidate. Missing, ambiguous, corrupt, or differently owned records do not produce an availability descriptor for another owner.

This descriptor is useful even when content is unavailable. A supported inline read is not evidence of image quality, valid decoded pixels, provider execution in this cloud environment, or human approval.

## Authority, ordering, and deployment admission

Reuse the original [media authorization](../../app/api.py#L566), `_image_jobs(session_token)`, and `_image_branch` selection. In collaboration mode this means the live trusted session, current membership/project `domain.read`, a required valid branch in that project, and the resolved actor's original queue. Verify the selected row's job, novel, branch, actor, and legacy contract explicitly; do not rely only on a caller-supplied ID or directory location.

The ordinary non-packaged, non-collaboration local runtime has the existing [loopback gate](../../app/main.py#L137); the legacy helper does not add per-actor authorization there. Local branch headers are ignored by the original owner. Packaged and collaboration modes retain their own session gates. A browser-local actor or node binding does not turn local queue content into private actor storage. Use “original access boundary,” not an unconditional claim of authentication or actor privacy.

The current [collaboration allowlist](../../app/main.py#L228) covers the original list and execute/cancel/retry/accept paths. A new candidate path would currently return 501. Future implementation needs exact **GET-only** admission for the two new paths, including the existing `/api/v1` normalization. Do not admit an arbitrary image-jobs suffix or new write methods.

Preserve the original middleware/session/project/branch rejection ordering. Perform descriptor/content-specific parameter and observation validation only after the applicable original access check. A malformed candidate observation must not turn a no-session, no-grant, revoked-membership, missing-branch, or foreign-project request into a candidate-specific response. Recheck live authority before publishing descriptor or content; failures disclose neither candidate existence nor content mode. Do not refactor the shared permission framework for this addition.

## Observation and concurrent changes

The owner has no formal legacy revision or output digest. `request_sha256` hashes input parameters; `attempt` counts execution claims; `updated_at` also changes during transitions and acceptance. None is an output SHA or an immutable result version. Do not create an apparent `version`, `output_sha256`, `X-Asset-Version`, or `X-Asset-SHA256` from these fields.

Propose a new, non-authorizing **opaque observation validator**, returned only after an authorized descriptor read and supplied to content through `If-Match`. Its implementation must be defined and reviewed before an endpoint is claimed complete. It must be derived by the original owner from the exact canonical observed record, including original owner identity, contract, job/novel/branch/actor, status, approval, asset reference, execution attempt/token, input identity, update time, and the exact held inline value. It must not expose those private values, require a new secret, confer access, or masquerade as a persisted job version or output checksum. A bare timestamp or tuple of attempt/input digest is insufficient.

For content, authorize again, select exactly one original row, and compare the supplied observation under the owner's lock. Decode only the copied, bounded inline payload from that observation. Recheck the same original row and live authority before returning bytes, using the established lock/guard ordering. Retry, cancellation, re-execution, approval, owner/branch changes, a changed URI or input, and a changed observation all invalidate the read. Require a fresh descriptor; do not silently substitute the latest candidate or the approved asset.

Do not keep a process lock during network I/O: this contract performs none. These checks still do not create a transaction across the descriptor/content/browser or continuous authorization after delivery. Identical observed state is not proof that no intervening state ever existed. If the original owner cannot provide the described validator and checks, keep the new content capability unavailable rather than inventing a version.

## Bounds, MIME, and response behavior

A proposed first implementation supports only `data:image/{png,jpeg,jpg,webp,gif};base64,...` with strict, full-string base64 validation. Normalize the `jpg` declaration to `image/jpeg`. Exclude SVG, HTML, arbitrary MIME parameters, whitespace, empty data, and all non-data URI schemes. This is a protocol allowlist; it does not inspect, transcode, or verify image pixels.

Use an explicit initial preview limit of **8 MiB decoded bytes**; this is a proposed new read limit, not an existing owner capability. Reject excessive encoded length before decoding and enforce nonempty actual decoded size afterward. The original 36 MiB character guard and formal asset library's 25 MiB byte limit are different constraints. Do not reuse them as interchangeable measures. The existing owner loads a whole queue JSON file; a bounded candidate response does not prove bounded parsing of arbitrarily large historical queues or bounded decoded-pixel memory. No new file store, copy, decode cache, or durable mutation is proposed.

For supported content, return exact `Content-Length`, normalized raster `Content-Type`, fixed safe disposition, `Cache-Control: no-store, private`, and `X-Content-Type-Options: nosniff`. Apply no-store to descriptors and safe errors as well. Do not return redirects, provider locations, raw inline content in error JSON, or synthetic asset-integrity headers. Do not claim a MIME declaration or base64 check is media validation or a safety review.

After the original authorization checks, proposed content-specific errors are fixed and contain no record details:

| Condition | Proposed response |
| --- | --- |
| Job missing, ambiguous, outside the selected owner, or wrong contract | 404; no candidate details |
| Missing required observation | 428, fixed `CANDIDATE_OBSERVATION_REQUIRED` |
| Malformed observation | 400, fixed `CANDIDATE_OBSERVATION_INVALID` |
| Observed state changed | 412, fixed `CANDIDATE_OBSERVATION_CHANGED` |
| Current row has no supported pending-inline content | 409, fixed `CANDIDATE_CONTENT_UNAVAILABLE` |

Existing session, domain, branch, and runtime-admission errors retain their original semantics and priority. On a failing read, do not call execute, retry, accept, an alternate owner, a file reader for the URI, or a remote downloader. There is no browser/provider credential forwarding, DNS lookup, redirect following, SSRF surface from a caller URL, or network fallback in this proposed path.

The future consumer must use captured original context, reject redirects, omit browser cookies for the explicit header-authenticated download, bound both success and error-body handling, and keep abort/stale-scope checks. Only an explicit action may create an in-memory Blob URL, retired and revoked on hide, identity/attempt/source change, failure, or unmount. Already delivered pixels cannot be revoked from the user's memory or treated as continuously authorized.

## Capability exposure and explicit execution remain separate

There is an existing capability-display gap: [asset-provider discovery](../../app/api.py#L1112) exposes configuration, registry, and reachability state, while the legacy job list exposes statuses and `recoverable`; neither is an authoritative per-job `execute_allowed` or candidate-content capability. The [queue](../../frontend/src/novel/ImageQueuePanel.tsx#L37) exposes a separate explicit execute action for `QUEUED` jobs, and the server rechecks `domain.write`, current attempt, and existing egress authority at execution. This proposal does not execute or modify that action.

Do not infer execution authority from a readable candidate, a configured/reachable provider, a selected model, an actor string in local browser storage, `recoverable`, or a successful GET. Do not interpret a local provider as a waiver of original permissions. If a future UI needs action affordances, obtain them from the existing authority for that action, represent unknown/unavailable explicitly, and still reauthorize each write. Candidate descriptor state describes content support only; it must not manufacture a broad permission or provider-execution capability.

## Implementation acceptance boundary

Before implementation, settle the observation-validator definition, exact route admission, lock/guard ordering, safe errors, and the proposed byte limit with the original owner. An additive implementation would need isolated protocol fixtures demonstrating exact original-owner selection, inline-only support, missing/changed observations, state changes around a read, and authorization rejection before candidate validation. It must preserve the existing list/create/execute/accept contracts and show that candidate reads invoke no provider, fetch, inspect, accept, asset mutation, or source rewrite.

Synthetic states and synthetic content may verify protocol behavior; they must remain labeled as such and cannot prove real generation, acceptance, media validity, or provider quality. PostgreSQL support, media ingestion/security paths, platform-restricted safety checks, network-candidate persistence, frontend adoption, and server canvas history are not implemented or verified by this proposal. Do not rerun restricted media checks or build a proxy to work around those limits. For existing remote-only candidates, the remaining blocker is owner-held content under a separately authorized persistence design; this document deliberately leaves that capability unavailable.
