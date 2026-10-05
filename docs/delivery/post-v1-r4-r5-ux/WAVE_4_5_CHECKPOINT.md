# Production, reading and language checkpoint

Runtime integration source: `6fb3c44b9d7c4e17c4f820bbe762be0ea9af39ee`, tree `5fda91a6b952dcdd3755bfdcef3db7dfe0b1b46f`. Browser-spec/event-contract correction: `1e3aea0262ee3df8283ba8d414379c842c08ca28` (no Python runtime change). This document is added after those immutable checks.

## Added real workflows

- U11/U15: read-only reader/proof/publish preflight, private session goals, exact historical recap, deduplicated in-panel notices.
- A08/A12: reviewed source-bound shot direction and original history, pinned native OTIO JSON exchange with rational time and explicit loss reports.
- B03/B04: manual voice/text direction, original actor-private local-only audio executor and explicit asset review, measured PCM waveform and versioned SRT/VTT captions.
- U14/U16: bounded selected manuscript/media portable copies, new-target ID maps, digest relink/cache cleanup, explicit selected-source proof/export/synthetic-media serial batches with partial/unknown journal states.
- B01/B02/B05: local versioned declarative templates, original deterministic Workflow execution/SDK with human review, independent manually reviewed language editions/terminology/RTL exports.
- U13: optional tools defer loading until opened; a local error boundary preserves the editor and retries only the interface.

Each has a mounted API, functional frontend controls, persisted/versioned records and real deterministic tests. Boundaries are package-specific PARTIAL, not forty-package completion or model-quality approval. B06–B10 continue separately.

## Immutable local verification

- Full File-compatible backend at `6fb3c44`: **3,054 passed, 9 skipped, 744 real-PG-only deselected**, 247.93 seconds. The native OTIO 0.18.1 dependency was present; those parser tests executed.
- Full frontend at corrected `1e3aea0`: **865 passed, 6 optional HTTP skipped**, 151 passing files.
- TypeScript, production build and design-token guard: PASS. App 610.54 kB plus deferred workbench 385.14 kB minified; the App >500 kB warning remains.
- Targeted deferred-loading/recovery/fixture lifecycle: 23 passed. Request drain remains strict; unresolved teardown requests are only retired after successful browser page closure and remain explicitly server-completion-unknown. Failed closure blocks deletion. Exact-owned-ID and empty-profile checks remain.
- New hosted PostgreSQL and browser journeys at this larger source remain pending publication/CI. Authoring a journey or collecting it is not a browser pass.

Earlier head `11157b4` retained a broker locator ambiguity and an abandoned-browser-request teardown failure, with isolation cascades. Its real File/PostgreSQL/Windows results and separate U13 receipts remain scoped historical evidence. Correction `4364613` is being checked independently before this larger feature increment. No failures are rewritten as successful runs.

The second-slice independent review remains BLOCKED by the platform. Known reported defects have implementation fixes and retained regression tests; that is not independent audit closure. Real TTS/model/GPU, native Windows IME, external subtitle/NLE applications, remote custom Agent execution, branch-isolated original manuscript writing and user acceptance retain explicit NOT_RUN or unavailable boundaries.
