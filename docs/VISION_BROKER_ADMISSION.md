# Vision broker availability follows the actual Research admission boundary

2026-10-18. Fixed a reproduced availability mismatch, not OCR activation.

Before this fix, ModelBrokerService.candidates advertised a local Research provider
with verification=CONTRACT_VERIFIED as available whenever it had analyze(). The
actual original Research ReviewAdapterJobs rejects that same real adapter with
ADAPTER_MODEL_ADMISSION_NOT_CONFIGURED. A contract declaration was therefore being
presented without the actual executor admission dependency.

The broker now adds VISION_MODEL_ADMISSION_NOT_CONFIGURED for non-MOCK_ONLY vision
providers until the original real Research job integration exists. Such a route is
unavailable, excluded from selection and cannot obtain a reservation. The existing
exact synthetic fixture stays available only under explicit synthetic selection;
unverified synthetic subclasses and cloud adapters retain their existing exclusions.
A Chinese reason explains this implementation gap without suggesting more quota,
payment, credentials or silent fallback. The new typed OCR node alone does not
remove the missing integration boundary.

Evidence:
- vision-broker-admission-file-red1: actual new assertion failed because available
  was True. Failure log/receipt retained. No existing test was modified.
- vision-broker-admission-file-green1: 73 passed, 71 PostgreSQL-marked deselected;
  original broker, narrative task routing and Research File/TestClient checks included.
  New tests verify candidate observation does not write or dispatch, no legal preview
  is selected and reservation refusal leaves no ledger entry.
- vision-broker-admission-ui-green1: 17 passed, TypeScript and Vite build passed.
  Existing large-chunk warning remains. These UI checks use jsdom/mocked transport.

No provider was executed, real OCR enabled, source record rewritten, permission
changed, or new job/engine introduced. Current PostgreSQL/browser/model-quality/full
release acceptance is not established by this fix. The prior actual test wheel
belongs to e9d11cd; it is historical packaging evidence, not a wheel rebuilt from
this fix's source. Original public/private isolation and Prompt adoption gate remain.
