# V2 creative workbench implementation

The workbench is an explicit entry inside NOVEL and is visible only when the server reports `experimental.narrative_production_v2: true`. The existing global modules, protected AppShell, tokens and V1 default path are unchanged.

## Implemented workflow

- Novel: embeds the existing manuscript editor, save controls and inspector. Switching creative modes keeps the manuscript mounted; original App remains the manuscript write owner.
- Screenplay: source-bound or independent documents, scene/action/dialogue editing, and an explicit saved-chapter-to-scene text scaffold. The scaffold copies text and is labeled as an unadapted starting point.
- Director: independent scene direction fields; prepare local rule-assisted proposals, edit and review them, then explicitly adopt a new source-bound director document.
- Storyboard: editable shot size, angle, motion, lens, lighting, environment, composition, color, sound and duration. Earlier/later ordering keeps shot IDs stable and renumbers in one document save.
- Production: derive an ordered plan from a saved storyboard, add/remove/reorder sequence segments, edit durations and output settings. No rendered audio/video is implied.
- Saved screenplay/director documents derive source-bound storyboard drafts through the server. Saved storyboards derive production plans.
- History is readable and restores require reviewing a selected historical snapshot; restoration creates a new current version using expected-version concurrency.
- Export reads the authorized server snapshot. Unsaved drafts can be explicitly exported as JSON.

The asset browser reads authorized character, location, story-route and audio/video asset records, plus current-document scenes/shots. The inspector includes the real backend-host AI environment report with truthful unscanned/unverified status.

## Optional model path

The director inspector loads available nonsynthetic local text routes. It requires an exact input preview and explicit confirmation before one model dispatch. The server bounds this path to known-zero cost, LOCAL_ONLY execution, no cloud fallback and no automatic replay. Results have a separate explicit review step. Missing model-host authority disables model controls while manual/rule-assisted work remains usable.

## Recovery and authority

Creative drafts remain in this page's memory until saved; the UI says so. Mode changes preserve drafts. Leaving prompts to continue editing or explicitly discard, with draft export available. Version conflicts and uncertain mutation receipts preserve and lock the draft until server results are reviewed. Repeat clicks are coalesced. Identity changes unmount the previous scope; late reads/writes/exports cannot repopulate content after access revocation. Server permissions remain authoritative.

## Verification

- TypeScript project build: passed.
- Vite production build: passed, with the existing large-bundle warning category.
- Shared UI token lint: passed.
- Focused creative Vitest suite: 47 tests passed across five files. JSON and text reports accompany this document.
- Portable Playwright UI/geometry suite: implemented at `frontend/playwright.creative.config.ts`, covering default-off isolation, keyboard mode selection, cancelled navigation, retained drafts and 1366x768 / 1440x900 / 1920x1080 shell geometry.
- Local Chromium launch attempts failed before page creation with `process_singleton_posix.cc:297: socket() failed: Operation not permitted`. This is not a visual test pass; no screenshots or visual baselines were approved from those attempts. The separate live-browser acceptance task and hosted browser CI own further results.

No V1 frozen release, RC1, PoemSeed, protected shell geometry, token values or manuscript write authority was changed by this UI work.

## Reopen recovery correction after hosted head `99e3c63`

Hosted screenshots and both live browser runs showed saved documents in the left list while the central canvas stayed on an unnamed draft after rapid reopen/stage selection. The cause was local draft initialization against the still-loading initial empty array. The workspace now initializes a stage only after its authorized scoped list succeeds. All existing drafts take precedence, including untouched explicit-new drafts. Initial list failures expose the existing retry command instead of creating a false empty draft. Existing identity, revocation, request-epoch and optimistic-version fences remain in place.

Ten additional workspace regressions cover early stage selection during capability/list loading, saved version/content recovery (including the legacy Production alias), an expected-version PUT after recovery, successful empty-list initialization, explicit-new and dirty draft preservation, confirmed discard/reopen, failed-list retry, uncertain-create reconciliation, late prior-scope responses and revocation during bootstrap. Six of those tests failed against the prior implementation before the correction. The focused creative suite passes 60 tests, including a new timeline CSS regression.

The same hosted screenshots exposed reorder buttons painting over the sticky Production header. Timeline-local stacking isolation and the existing `--z-dropdown` token now keep the header opaque and above scrolled controls. Three additive browser tests verify header hit targets, blocked click-through and normal exposed reorder controls at 1366x768, 1440x900 and 1920x1080. Browser collection succeeds with eight total mocked scenarios; execution of the new browser assertions remains pending hosted revalidation. No live browser assertion or gesture was changed.

The final source-hashed full frontend build/lint/unit receipt for this correction is recorded separately from earlier entry-fix evidence as `creative-recovery-99e3c63-20261009.{json,log}`. It passed on the corrected working tree based on `99e3c636bc59f45f5faa4b7af84b80981f1ec2e5`: TypeScript, Vite build, token lint, 235 passing test files and 1,567 passing tests; the existing two skipped files/eight skipped tests were unchanged. The runner records identical before/after source hashes (`sources_changed_during_check: false`). This is local build/unit evidence, not a hosted browser pass for the correction.
