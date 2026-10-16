# U08 / U09 implementation boundary

This is Experimental work on top of R3, not V1 acceptance or real-model validation.
Flags are server allowlisted; `V1_ACCEPTANCE_MODE=true` disables both entry points.

## U09: passive workflow inspection

Flag: `local_ai_workflow_inspector_v2`.
UI: Experimental workbench → Local AI workflow inspector.
API: `/api/novels/{nid}/experimental/local-ai/workflow-inspections` with the existing `/api/v1` alias.

- GET reads an existing ComfyUI discovery snapshot, never runs Detect or Validate.
- POST `/inspect` accepts a bounded API node graph or a `prompt` envelope. It does not accept the canvas/UI graph format as a runnable graph.
- The frontend supports a local JSON file or pasted text and explicitly sends it to the app server. Imported raw JSON is not persisted. Users should remove keys and private input before inspecting.
- Structural checks reject malformed JSON, duplicate keys, non-finite values, oversized bytes/node/input/edge/value/depth counts, missing link sources, bad slot numbers and cycles. Depth is checked before JSON parsing. Node identifiers become report-local references.
- Model/node presence comes only from the selected runtime's existing discovery metadata. Full input/output schema was not saved by R3 discovery, so type compatibility and required-input validation remain unverified. Missing entries in a bounded snapshot are not proof of missing files on disk.
- Custom-node implementation is unknown even when its name appears in metadata. Code, network, credentials and file-access indicators are warnings, not a security certificate.
- Existing R3 media definitions and the existing Local AI SD adapter are compared as separate contracts. Matching required node names does not bind the imported graph to that adapter. `DENY_ALL` is unconditional; no launch/register/enable endpoint is provided.
- POST `/reports` explicitly recomputes and saves an immutable version-1 aggregate summary in the existing isolated experimental store. GET `/reports` lists only the current project/scope. At most 100 reports are retained per scope. Summaries omit arbitrary names, graph values, prompt text, paths, endpoints, credentials and hardware inventory. Download is a local JSON Blob from the same allowlisted schema. Inspect alone does not persist a report.
- Both host-session authorization (same as Local AI Model Center) and project/branch authorization apply. Save additionally requires domain write. Late frontend responses cannot restore cleared input or a different scope.
- No network, executable, shell, pip, CUDA, model loading/download or registry mutation is performed. Runtime availability, licensing, hardware memory and actual generation remain separate, unverified dimensions.

Verified documentation source: [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes), retrieved 2026-10-05. The official route description distinguishes GET metadata from POST `/prompt` execution; this inspector never invokes either route.

## U08: actual single-author-request preflight

Flag: `author_context_inspector_v2`.
UI: AI writing inspector, after choosing an explicit text Provider/model and saving the current chapter.
API: `/api/novels/{nid}/experimental/author-context/preview` and `/generate`, with the existing `/api/v1` alias.

The former `AiContextPreviewPanel` was a role-context/auxiliary-data browser, not the author generation payload. It now says so explicitly, labels auxiliary queries and fences cached results by chapter version/session/scope. It is not promoted to exact request evidence.

The new path uses `app/author_request.py` and `JobManager.prepare_author_request` for both preview and final author dispatch. It shows the actual adapter-facing prompt, context, parameters, Provider/model and saved chapter version. Prompt length is measured in characters; unknown tokens remain null, not a made-up token estimate. Provider-specific protocol encoding still belongs to that adapter.

- The digest binds the exact payload, persisted chapter content/document hash and version, project, scope, actor/session, route locality, profile and approved style/plan source records. Transient job IDs are excluded.
- Selected text must match saved source. TipTap multiline/hard-break/Unicode selections use the same editor projection as workspace navigation, and a document must still project to persisted Markdown before it can authorize an alternative selection representation. Unsaved text cannot use an old chapter approval.
- With no selection, the existing last-2000-saved-character strategy is shown and used by both preview and generation.
- Generation requires the digest, rechecks current source/permissions/approved style-plan inputs, persists the binding, and performs the same recheck after route preparation and at the model-node dispatch boundary. Flag-off blocks before route preparation. Privacy/cancellation/authorization changes cannot use an earlier receipt.
- A transient request-authorization callback captures request authority without serializing the token. Restart cannot restore that callback; reviewed jobs require fresh preflight rather than dropping the digest on retry.
- The frontend supplies a stable attempt ID from the successful preview. The server reuses the existing idempotency lock/store and rejects reusing a key with changed payload.
- Privacy omission metadata is reduced to a generic reason in the real request builder. Excluded IDs, names and counts are not exposed through that field. Private derived summaries remain filtered by the existing source-privacy pipeline.
- Changes in input, style, chapter/version, Provider/model, profile, session or branch invalidate the UI receipt. Dirty/conflict state disables preflight and generation.

### Remaining U08 scope

This verified path handles one explicit Provider/model and one draft. Multi-variant prompts differ, so the preview-enabled UI blocks multi-variant generation until per-variant preflight exists. Source-removal/pinned-reference controls, comprehensive source-version manifests, cost estimates, and full route/fallback preflight remain open. U08 as a whole is PARTIAL; actual single-request correspondence is CONTRACT_VERIFIED. No real provider or model quality is claimed.

## Validation

Synthetic-only automated coverage is in `tests/test_r4_local_ai_inspection.py`, `tests/test_r4_author_context.py`, and matching React tests. It includes malformed/cyclic/oversized/key/path/code-node inputs; no-probe/no-process enforcement; host/scope/flag checks; report redaction; stale responses; exact captured request equality; late revocation/context/version changes; saved multiline/hard-break/emoji selections; private derived-summary exclusion; stable retry idempotency; legacy generation regressions. Refer to the final acceptance receipt for counts at the integrated commit.

Real Windows GPU inference, named model-family workflow compatibility, licensing approval and commercial-model quality remain NOT_RUN. No model, private manuscript or user credential was needed for these tests.
