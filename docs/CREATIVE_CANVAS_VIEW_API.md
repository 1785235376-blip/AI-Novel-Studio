# Display canvas API slice — 2026-10-18

The independent media display records are now mounted through the original Graph router and Studio authority resolver. This is not the completed large-canvas UI.

## Closed surface

GET/POST `/projects/{nid}/studio/canvas-views` and GET/PUT `/projects/{nid}/studio/canvas-views/{vid}` are available at the existing `/api` and `/api/v1` prefixes. Unknown actions and methods do not gain collaboration admission. There are no execution, model, job, review or provider endpoints here.

The original narrative feature flag, domain permissions, actor-private ownership, captured scope, project incarnation, current-authority guards, CAS, original Asset metadata and capacity limits remain authoritative. These schema-1 display views do not require or grant model-host authority. The display API uses a 768,000-byte actual-stream request bound, independent of Content-Length, with sanitized validation failures and no-store/nosniff headers. The persisted definition remains independently bounded at 512,000 bytes.

## Verification

- Original mounted application, both API prefixes; genuine File and PostgreSQL owners.
- Create/idempotency, list, explicit movement/save, GET reopen, exact Asset reference, tombstone masking, and unchanged empty execution-graph collection.
- Original authenticated collaboration sessions: anonymous rejection, branch requirement, actor-private reads, viewer write refusal, role revocation and late session revocation suppressing both result and private error.
- Sanitized CAS conflict, unknown execution/method refusal, extra-field rejection, oversized body despite false Content-Length, default-off behavior.
- File final: 10 passed; PostgreSQL final: 10 passed, database OID 16384, server stopped. Earlier File plus catalog: 9 passed, PostgreSQL: 6 passed.
- Public manifest and real PUBLIC wheel/metadata: 3 passed. New route module explicitly included in the standard manifest. No private Mature backend introduced.
- API catalog: 2375 operations (4 operations at 2 existing prefixes); source fingerprint 66553d09b196546ca80e7c80a211878bc41f173f9ef2b594a3cbd3ecaaae255e.

## Remaining

The frontend client/editor, viewport culling and measured browser performance are not implemented by this slice. Fresh-owner persistence and 1000-card acceptance are covered in the preceding foundation slice, not inferred from this mounted API's one-card scenario. No real model inference, browser FPS, Windows installation, full V2 acceptance, Prompt production-gate enablement, PR merge or Release is claimed.

Evidence: `docs/delivery/v2-development/canvas-view-api-*` receipts and raw logs.
