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
