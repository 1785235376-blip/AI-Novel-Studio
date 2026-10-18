# Research native OCR controls

The existing Research source panel now mounts a shared-primitives OCR panel for imported PNG/JPEG image sources. It reads host-admitted routes, creates an original analysis receipt, previews explicitly, requires a confirmation checkbox, dispatches once per retained idempotency key, refreshes durable status, opens saved receipts and offers explicit human review or cancellation. Model/language/source identity and preview version/digest are pinned. Project/source/version changes remount the scoped controls and discard late responses without continuing execution. Results remain separate derived records; original image/text search and Canon are not changed.

Evidence:
- research-native-ocr-ui-r1: 27 React tests passed across new controls and four unchanged Research suites.
- research-native-ocr-ui-build-r1: four focused tests passed, TypeScript passed, actual Vite production build passed, UI token guard passed. This includes a lost-response retry reusing the same application idempotency key.
- Earlier research-native-ocr-ui-typecheck-r1 passed before the final additional test.
- Canonical novel reference and design-system rules were inspected. No shell, shared primitives, tokens, spacing or baseline screenshots changed.

Browser limitation remains explicit: the unchanged original geometry configuration could not launch its absent bundled Chromium (geometry-r1). A temporary system-Chromium configuration first hit an ESM config-loader error (system-geometry-r1); corrected ESM loading reached installed Chromium but it aborted because socket() is denied in the existing check runner (system-geometry-r2). No sandbox/network guard was relaxed, browser downloaded, baseline rewritten or successful visual/end-to-end claim made. All failure receipts are retained. Four geometry cases were scheduled; the first failed at browser launch and the other three did not run.

Current limits: manual status refresh (no automatic job replay), native orphan recovery still pending, English smoke only, no general OCR quality or Windows acceptance, and no production browser full-chain acceptance. The production bundle is a test artifact, not a V2 release.
