# Try Local Interop V1 with synthetic local data

This is an opt-in development integration, not Tutor Desktop certification.
Use an isolated test checkout/profile with synthetic projects. Nothing installs or
starts a model, calls a paid provider, writes prose, or uploads a case.

1. Install the repository's ordinary Python/frontend dependencies. Keep the shared
   `local_interop_protocol` package with the app (included in its wheel/package).
2. Explicitly launch the synthetic peer from the repository root:
   `python scripts/run_synthetic_tutor.py --port 8052`.
   It binds only `127.0.0.1` and prints `MOCK_ONLY_ENDPOINT`. Stop it normally when done.
3. Start Studio's normal development host with only
   `EXPERIMENTAL_FEATURES=local_tutor_interop_v1` enabled. Use an existing trusted
   scoped workspace session; the bridge never invents an identity in file-only mode.
4. Open “问助手” or AI Tutor Integration in Settings. Enable the user-level switch,
   then connect explicitly to `http://127.0.0.1:8052`. Capability and MOCK_ONLY notices
   must be visible. V1_ACCEPTANCE_MODE overrides both switches to OFF.
5. Preview metadata. Content remains NONE unless you separately choose an exact
   saved selection, current chapter or explicit bounded source set. Confirm the
   preview before sending. Guidance is inert advice; handoffs need their own click.
6. Diagnostics allow removing each optional field and display both outgoing
   envelopes. Close/disable disconnects and cancels pending sharing. Normal writing
   continues if the peer is missing or the bridge is disabled.

Automated isolated path: from frontend run
`INTEROP_PYTHON=python pnpm exec playwright test --config playwright.interop.config.ts`.
For HTTP/client proof without a browser, use
`LOCAL_INTEROP_REAL_HOST_TEST=1 INTEROP_PYTHON=python pnpm exec vitest run tests/localInteropRealHost.test.ts --pool=forks --maxWorkers=1 --minWorkers=1`.
Both create their own synthetic data and explicit reference peer processes.

Windows Named Pipe code in `interop-reference/PoemSeed.LocalInterop.Pipes` is a
standalone current-user transport reference, not automatic app integration.
Actual Tutor Desktop composition and native user acceptance remain LOCAL_REQUIRED.
