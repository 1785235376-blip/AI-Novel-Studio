# R2 legacy outbound-path closure

## Memory extraction after Accept

Automatic extraction always applies `LOCAL_ONLY`, even when the originating author job used `QUALITY` or another profile. It uses the normalized text node and registered, enabled `LocalTextAdapter` routes whose live registration passes the loopback-only discovery guard. Provider labels alone do not establish local confinement. The historical raw Ollama/legacy router path is deliberately not used: its redirect/proxy transport is not the guarded local-discovery adapter.

With no verified local route, the independent memory job records `NOT_CONFIGURED` and `TEXT_PROVIDER_NOT_CONFIGURED`; the already accepted chapter stays accepted. There is no cloud retry or fallback. An explicitly enabled development MockProvider can be used outside packaged mode, with `mock_standin` provenance. Merely having the mock provider in a registry does not enable it. The packaged application never treats mock extraction as a production result.

The final normalized-node dispatch guard rechecks the current provider registration after route preparation. Successful extraction creates pending proposals with evidence only, preserving the existing separate approval step.

## Retired NovelWorkflow helper

Repository reference inspection found `NovelWorkflow` used only by its synthetic test. Calls without an explicit `draft_override` now fail before reading a project, invoking a router, or writing a chapter. Real author generation must use the guarded Draft/Accept job flow. `draft_override` remains a file-format fixture harness and is not exposed by an API or production caller.

## Motion tasks

Configured provider dispatch requires a current authorization callback. After frame preparation and before calling the provider, the service rechecks screenplay/project/branch/owner, task state, attempt, execution token, submission key, provider registration, exact outbound request and current permission. Frame resolution is repeated, including asset hash/version/privacy checks. Results from cancelled or replaced attempts are discarded.

Cloud approval is bound to the prompt, both frame references, constraints, provider/model, endpoint, and screenplay ownership scope using `request_sha256`, in addition to the historical prompt hash. The review response includes frames and constraints. Prompt-only historical approval cannot authorize a request; the user must review it again. A changed provider endpoint or task branch likewise requires a new review. Current project source policy and independent screenplay/frame restrictions remain mandatory, even after prompt approval. No screenplay-stage approval grants cloud permission.

API callers provide `reauthorize=...`; `update_motion_privacy` accepts the additional positional `request_sha256=None` parameter. Requests granting `CLOUD_ALLOWED` must supply the current request digest. Local generation does not require cloud review but still requires current authorization.

## Legacy asset tasks

Legacy asset descriptions can contain manuscript-derived text and have no complete exact-prompt cloud review path. Remote execution therefore fails closed with `IMAGE_CLOUD_PROMPT_REVIEW_REQUIRED`. Individual authorized local execution remains supported. Bulk workers cannot execute without a per-task authorization callback; they do not silently acquire authority from a saved worker configuration.

Local dispatch checks the current owner/scope, permission, source description, provider/endpoint, RUNNING state, attempt and unique execution token. Duplicate active execution is rejected. Cancellation, retry, or restart recovery invalidates the old attempt; late success/failure cannot overwrite its replacement. No external exception text is copied into persistent task errors except controlled validation codes.

## Verification

`tests/test_r2_legacy_egress_guards.py` uses in-process provider spies and synthetic content. It covers zero-call assertions for source/policy/review/permission/owner/cancellation/attempt/registration drift, remote asset rejection, duplicate execution, and late-result discard. Existing memory, workflow, motion and asset regressions are also run. These checks prove application contracts, not live-provider quality or paid-provider verification. Real PostgreSQL checks remain separately environment-gated.
