# Versioned Director observation adapter candidate

Status: candidate, default disabled, no application activation.

This follows the private lifecycle owner candidate in source commit `64248ba847e3db306bb7429fba6e16387ba62f42` and evidence commit `480e3b6`. It adds only observation and exact read-only reconciliation. It does not add model preview, dispatch, pending publication, human adoption, cancellation or automatic retries.

The existing Creative router has a strict boolean construction-time option, `director_observation=False`. The production application call remains unchanged and does not enable it. The isolated HTTP tests explicitly enable it and use the actual Creative invoker, original File owners, trusted Host discovery resolver and current feature flags. A query or request body cannot enable these routes.

The candidate routes, relative to the original Creative router, are:

- GET `/director-proposals/{rid}/model-v1/status`
- GET `/director-proposals/{rid}/model-v1/adopted-draft`
- POST `/director-proposals/{rid}/model-v1/reconcile-review` (read-only exact submitted-review lookup)

Every success uses the `DIRECTOR_OBSERVATION_V1` envelope with the current project, scope, kind and strict passive receipt. Every owner read uses `domain.read`, the current Host session and fresh authority guards. The original owner validates author, incarnation, source, route, generation evidence and exact draft data. `existing_owner_only` covers the entire invocation, preventing a read from creating a missing incarnation marker.

Bodies are bounded to 1 MiB and 15 seconds. Validation failures use a fixed error code rather than echoing submitted private text. Responses and controlled errors are no-store and nosniff. Unknown receipt fields are rejected. Owner exceptions do not expose raw prompts, Jobs or request data. Current authority is rechecked before returning a success or an owner denial.

Tests cover exact post-restart receipt reconciliation, no extra writes or provider calls, trusted Host/token/origin/forwarded-header/scope checks, late revocation, missing identity without provisioning, strict receipt decoding, malformed/oversized bodies, all original feature flags and default-disabled application construction. Provider wire replies are fixtures, not real model-quality evidence.

Verification results are recorded under `docs/delivery/v2-development/director-observation-*`; only completed PASS receipts count. Earlier isolated-adapter runs are retained separately from runs using the actual original Creative invoker.

Independent review remains unavailable. Real PostgreSQL, browser, Windows, GPU and provider checks have not been run. Canonical inventory and accepted integration have not been updated. Completing this adapter does not complete the intelligent director workbench or activate a user-facing feature.

Completed primary checks: 148 passed, 97 PostgreSQL-only deselected in the combined new adapter/lifecycle and original foundation/workflow/project-lifecycle suites. PUBLIC packaging: 87 passed; two actual wheels and two actual sdists inspected against current source payloads. Forced TypeScript, production build, token guard and clean origin checks passed. These are primary checks, not independent review or live-provider acceptance.
