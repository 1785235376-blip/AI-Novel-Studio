# Original local-image dispatch guard backport candidate

The shared change adds an optional `dispatch_guard` to `AssetGenerationRequest` and invokes it in the original `LocalImageAdapter` after live metadata validation, immediately before the existing provider call. Default behavior and existing caller signatures remain compatible. It neither enables a route nor sends inference by itself.

The callback allows an already-authorized coordinator to recheck its source, cancellation, current route and budget after potentially blocking model metadata checks. The original bridge rechecks enablement after the callback. No new provider, transport, credentials, model download or arbitrary workflow execution is introduced.

Verification: `tests/test_r2_local_image_dispatch_guard.py`, two injected-delegate tests passed. No real runtime/inference call. This is a shared safety/correctness backport candidate, not a release or backport authorization. Independent security review remains platform-blocked and was not retried.
