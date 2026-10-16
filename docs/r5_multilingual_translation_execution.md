# B05 selected-segment local model execution

This is an original-runtime feature implementation, not language-quality acceptance.
The independent edition/manual alignment/terminology/review/export workflow remains usable without a model.

## Author workflow

1. Save the source and select a paragraph in an independent language edition.
2. Open **本段模型翻译**, select a registered, available local text route, and explicitly opt into a synthetic route if testing.
3. Preview the exact original author request and broker receipt. Only this saved segment, approved edition terminology/aliases/strategies and the edition's style/language instructions enter the request. Other segments, automatic context and style/plan references are excluded.
4. Confirm the source, language, route and known zero-cost reservation, then explicitly dispatch. No cloud or paid-route fallback is supplied. Unknown/nonzero estimates and zero estimates without known-zero actual pricing are blocked.
5. Reopen the panel and select the original run to recover its identity; refresh obtains the original JobManager and broker accounting result. Closing the panel does not create, retry or cancel a job.
6. Inspect the bounded untrusted candidate. Explicit adoption replaces only the selected edition segment with a DRAFT under the original edition CAS. Submit, terminology preview and human segment acceptance are still separate original review actions.

## Authority and persistence

`MultilingualTranslationCoordinator` composes `AuthorPreparer.prepare_preview/prepare_author`, `ModelBrokerService.preview/reserve/guard_dispatch/finalize` and `JobManager.start_prepared`. It supplies no alternative prompt builder, scheduler, provider or acceptance authority. Translation directives are ordinary user instructions supplied to the original author builder. The captured production adapter-facing request must equal the displayed preview.

Translation previews and admissions are stored in the existing experimental scoped store, separately from the edition. They bind the original source version/paragraph, edition version, terminology/style snapshot digest, exact author request, selected route identity, price/budget receipt, original job and reservation IDs. Durable admission precedes reservation and start. Repeated dispatch with the same receipt returns the original admission; uncertain start, orphaned job and restart-lost live authority never replay. An unresolved admission prevents another same-segment dispatch. Broker holds remain conservative when upstream status is unknown.

The original executor enforces a 20,000-byte UTF-8 output bound and a 300-second deadline. Receipt refresh requires completed original execution and settled accounting, current live authorization, original route identity and unchanged source/edition. Revoked, cancelled, late, stale, oversized, unknown or restarted-without-live-authority results cannot be adopted. Source changes never schedule retranslation. Candidate text is withheld when current source/edition/route authority fails.

Adoption and marking the run ADOPTED occur in one existing-store transaction; edition CAS, original source and authority fences are checked inside that transaction. The manuscript and its history are never written. The original generic generation acceptance path rejects the `multilingual_translation` origin, including persisted jobs.

All model endpoints require `multilingual_editions_v2`, `model_broker_v2`, `author_context_inspector_v2`, current scope/actor write authority and the existing trusted host session. Default-OFF and V1 force-OFF remain unchanged. Missing host/model/feature configuration shows a blocked state while manual edition tools remain available.

## Verification and limits

- `tests/test_r5_multilingual_translation.py`: mounted production routers at `/api` and `/api/v1`; actual File persistence and marked actual-PostgreSQL parametrizations. Captured labeled synthetic transport, exact request equality, explicit adoption/review, CAS and privacy fences, bounded output, cancel, identity recovery, conservative unknown accounting, branch/actor isolation, feature/route revocation and no cloud/nonzero/unknown-cost dispatch.
- `frontend/src/experimental/LanguageTranslationPanel.test.tsx`: exact preview/consent, original receipt recovery, close/late response, unsaved-input fencing, separate adoption consent, cancellation and visible saved-draft synchronization.
- `frontend/tests/e2e/r4-multilingual-translation.spec.ts`: real React/API/File journey using the existing hosted R4 synthetic broker fixture. Three desktop widths, close/reopen, original receipt recovery, exact preview, draft adoption, separate segment review, reload and source-change withholding. No mocked HTTP routes.
- Local PostgreSQL: NOT_RUN when `TEST_POSTGRES_DATABASE_URL` is absent. Use the marked actual-PG hosted lane; do not substitute File for PG.
- Local Chromium: NOT_RUN due to previously established EPERM; no launch retry. Hosted browser result must be observed before claiming browser verification.
- Real model inference, translation quality, all-language/font coverage, paid/cloud execution: NOT_RUN. Synthetic protocol output proves wiring only.

## Local implementation check receipt (2026-10-05)

The new UI and unchanged manual multilingual regression suites pass 15 tests.
TypeScript `tsc --noEmit` and the UI design-token guard pass. Playwright collection
finds the authored real-API translation journey; this is collection only, not a
browser pass. The File/actual-PG mounted fixture retains its separate markers.
The final combined multilingual and original declarative-model/bounds File run
passes 120 tests; 104 marked actual-PG cases are deselected because no local PG
endpoint is configured. This includes active-stream and accounting-SETTLING
recovery without identity loss, and uncertain terminal accounting without replay.
