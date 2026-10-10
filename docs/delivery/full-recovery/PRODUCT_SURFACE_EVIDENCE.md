# Product surface recovery evidence

Date: 2026-10-07 (Asia/Shanghai). Baseline: PR #45, `6658172`.

## Delivered frontend behavior

| Capability | Code evidence | Verification evidence | State |
| --- | --- | --- | --- |
| Start from a premise without an existing chapter; request World, Characters, Outline with the configured real provider/model | `frontend/src/novel/AIPlanningPanel.tsx`; `frontend/src/api.ts` planning API | `AIPlanningPanel.project.test.tsx` covers all three request kinds, empty sources, premise, dynamic provider/model and full structured preview | DONE |
| Human review and explicit adoption into original Story owners | `AIPlanningPanel.tsx`, `CreationWorkbenchPanel.tsx`, `App.tsx` query invalidation; POST `/api/novels/{nid}/planning-runs/{rid}/candidates/{cid}/apply` with exact run `expected_version` | Explicit confirmation, cancellation, duplicate-submit exclusion, returned receipt, CAS failure retaining input, and late results after project/actor/unmount are covered | DONE |
| Avoid adopting simulated output as real project facts | Apply button requires `execution_mode === 'real'`, READY candidate and local project scope; preview displays a warning for `mock_standin` | Additive project-planning tests verify mock adoption disabled and collaboration scope fail-closed | DONE |
| Display newly adopted world summary in original Story database | `App.tsx` reads `world_summary`, falling back to legacy `long_term_summary` only when the new field is absent; manual world edit saves `world_summary` | `AppWorldSummary.test.tsx`: new-field display/save, legacy compatibility, explicitly empty summary | DONE |
| View and edit project world/characters/outline before creating a first chapter | Original `StoryDatabasePanel` receives novel ID independently of optional chapter; original project owners handle all requests; only chapter-specific consistency/foreshadowing consumers require a real chapter | `AppProjectStory.test.tsx`: actual App navigation plus exact world/character/outline owner reads and saves; no synthetic chapter | DONE |
| Reviewer and Verifier are selectable and executable in the existing Agent team | Original GET `/api/agents`; `api.ts` typed `additional_agents`; `creativeAgentCatalogItems` merges the registered catalogs with exact-ID deduplication; `AgentTeamPanel.tsx` role/catalog/history consumers | `AgentTeamPanel.additional.test.tsx`: Reviewer/Verifier model jobs use selected provider/model, additional-only catalog, deduplication, history filtering. Original Agent tests retained | DONE for UI wiring; real Agent execution verdict is independently recorded |
| Explicit development Host identity for real local Agent execution | `LocalHostSessionPanel.tsx`, memory-only `localHostSession.ts`, original `api.ts` request/download transports, original backend `app/api.py` GET `/api/local-session`; protected Agent query keys use an opaque numeric identity epoch | 15 additive frontend tests, 9 backend tests, plus real browser password input → validation → Qwen Reviewer completion; no automatic browser-header injection | DONE |
| Malformed writing-goal metadata does not crash the manuscript editor or manual save | `App.tsx` validates the five numeric fields actually consumed; persistent incomplete-data notice preserves the original editor/save path | `AppWritingGoalRecovery.test.tsx` mounts App and performs a version-aware save for missing/NaN/string metadata, plus valid progress rendering | DONE |
| Save, compare, explicit restore and persistent conflict protection | Original `App.tsx` `RevisionHistory`/`ScopedRevisionHistory`, `RevisionPanel.tsx`, local draft/conflict owners retained | Original AppRevisionHistory, independent history audit, RevisionPanel, ConflictDialog, StoryRecordVersionEditor and StoryCoreRecordVersionEditor suites pass; actual React browser restore preview and persistent 409 pass | DONE for restored frontend contracts |
| Create project, chapter generation/revision/review/export surfaces | Existing EntryExperience, AiWritingPanel, ContinuityCheckPanel, ExportPanel owners retained; project-bootstrap entry lives in original CreationWorkbench | Original component/lifecycle suites pass. Full real-model product acceptance is independently run by the controlling agent | DONE for frontend wiring; real-model verdict belongs to product acceptance report |

The new project-planning UI calls the original planning-run owner and adopts its typed results. It does not synthesize project facts locally, write directly to Canon, select a hard-coded model, create another AppShell, or replace the existing chapter/history/export implementations.

Project adoption invalidates the original novel detail, outline, Story database, world rules and AI context preview queries so subsequent generation can read the newly adopted context. New proposal kinds are currently limited to local novel projects; the existing collaboration branch path does not own those project-wide domains. This scope boundary is explicit in the UI and backend rather than silently writing across branch authority.

## Verification results

| Check | Result | Durable evidence |
| --- | --- | --- |
| Initial original lifecycle/history/creation/consistency/export subset | 14 files, 172 tests PASS | Original test files were run unchanged |
| Final full frontend Vitest, including all 43 additive tests | 226 files PASS, 2 files SKIP; 1498 tests PASS, 8 tests SKIP; 117.81s | `LOCAL_HOST_FRONTEND_FULL.log`; pre-binding full run (1483 PASS) retained in `FRONTEND_FULL_VITEST_FINAL.log` |
| Final production build | PASS; 3.04s Vite build | `LOCAL_HOST_BUILD_FINAL.log`; pre-binding build retained in `FRONTEND_BUILD_FINAL.log` |
| Final design-token lint | PASS, 42 files | `LOCAL_HOST_LINT.log` |
| Final Playwright visual/geometry/discovery suite after local Host completion | 15 PASS, 11.6s | `LOCAL_HOST_VISUAL.log`; pre-binding 15/15 run retained in `FRONTEND_VISUAL_FROZEN_FINAL.log`; earlier RED run retained in `FRONTEND_VISUAL_FINAL.log` |
| New mounted backend local Host boundary tests | 9 PASS, 3.43s | `LOCAL_HOST_BACKEND.log`; initial frozen-settings fixture error retained in `LOCAL_HOST_BACKEND_INITIAL_RED.log` |
| Reviewed history and production-shell screenshot baseline migrations | Both individual migrations PASS; original business assertions and 1.5% screenshot tolerance retained | `VISUAL_HISTORY_BASELINE_MIGRATION.log`, `PRODUCTION_SHELL_BASELINE_MIGRATION.log`, retained old gold and prior RED evidence |

The initial full Vitest attempt hit Windows `python3` ENOENT in the original FountainParser tests. Running with `PYTHON` resolved to this checkout's `.venv/Scripts/python.exe` fixes the environment; all 21 FountainParser tests and the entire final suite pass. No failing tests were removed or marked skipped. The eight pre-existing skipped tests remain unchanged.

Final commands (from `frontend/`):

```powershell
$env:PYTHON = (Resolve-Path ../.venv/Scripts/python.exe).Path
pnpm exec vitest run --maxWorkers=2 --minWorkers=1
pnpm build
pnpm lint
pnpm exec playwright test --config playwright.visual.config.ts
```

The build retains the existing warning for JavaScript chunks larger than 500 kB (App about 721 kB and ExperimentalWorkbench about 647 kB). No warning threshold was increased.

Component tests use controlled API responses to verify UI lifecycle and exact calls. Visual tests run the actual React product with deterministic HTTP fixtures. Neither is presented as a real-model acceptance run; the independent local-model/browser acceptance is recorded in the top-level product acceptance deliverable.

## Preserved tests and reviewed exceptions

Eight additive frontend test files provide 43 new tests:

- `frontend/src/novel/AIPlanningPanel.project.test.tsx` (11).
- `frontend/src/planningProjectApi.test.ts` (1): encoded owner URL, exact CAS body and captured authorization context.
- `frontend/src/AppWritingGoalRecovery.test.tsx` (4).
- `frontend/src/AppWorldSummary.test.tsx` (3).
- `frontend/src/AppProjectStory.test.tsx` (4).
- `frontend/src/novel/AgentTeamPanel.additional.test.tsx` (5).
- `frontend/src/localHostSession.test.ts` (6): memory-only credential, no anonymous/cleared transport authorization, team/scope/packaged exclusion, original-token capture, validation header with no token in URL/body.
- `frontend/src/novel/LocalHostSessionPanel.test.tsx` (9): explicit password/click and duplicate exclusion, invalid credential and mode, unchanged selected local manuscript, delayed validation after team navigation/unmount, original mutation-error visibility and instruction preservation, no stale follow-up start after unlink, immediate actor A→B/unlinked protected cache isolation.

`tests/test_local_host_session_recovery.py` adds nine backend checks against the mounted original app/v1 alias: original trusted actor resolution, no credential echo/no-store, absent/invalid/revoked tokens, wrong Origin, remote loopback denial, and original collaboration/packaged 501 boundary. No Agent permissions or role checks were changed.

Original unit test bodies/assertions are unchanged. `frontend/tests/visual/design-system.spec.ts` has narrowly reviewed exceptions:

1. Its production HTTP fixture now returns the endpoint's real writing-goal shape instead of generic `{items: []}`; text-model responses use `{items: []}` and archived chapters use `[]`; experimental flags use their actual shape. The malformed-data runtime crash is separately fixed and tested in App, so correcting the fixture does not hide that defect.
2. The revision test opens the existing folded FeatureLauncher before selecting “版本历史”. No duplicate sidebar was introduced; business preview/confirmation/conflict assertions remain.
3. The standalone production-shell fixture now supplies actual owner names with the same original IDs, and deterministic real-shaped bootstrap, empty chapter/model lists, writing-goal and media-task responses. It waits for the chapter empty state and font readiness. All original “当前工作区” and raw-ID exclusion assertions remain; the original four missing-metadata fallback unit tests remain unchanged.
4. Explicit 1440×900 viewport, shell bands, navigation widths, 804px main width, 802px history-panel width, main-workspace bounds and horizontal-overflow assertions were added. The history panel is scrolled into view before checking its bounds, matching locator screenshot behavior inside the existing scrollable workspace.
5. Exactly two reviewed retired screenshots were migrated, as detailed below. No screenshot threshold changed; the four other golden images are unchanged.

This is preservation with documented fixture/navigation and reviewed baseline exceptions, not a claim that all existing test files are byte-identical.

## History golden-image migration evidence

The inherited history screenshot failed in both this worktree and a separate `git archive HEAD frontend` extraction of original PR45 in the same environment. The extracted frontend reused dependencies but retained original runtime code. Its legal corrected fixture/navigation produced the exact same current screenshot bytes as this worktree.

| Artifact | Geometry / SHA-256 |
| --- | --- |
| Original tracked gold from source import | 802×742; `CC16BBBB8B69924394809D97B3CD6999C41E17F9654BB664D311ABFFDEB8F86B` |
| Original PR45 actual with legal fixture/navigation | 802×383; `51D34B0B3603F1FF9BF601CCBE8BA1BF2F54FDE307B2397E5A0D9392B273B36B` |
| Recovery actual and reviewed migrated gold | 802×383; `51D34B0B3603F1FF9BF601CCBE8BA1BF2F54FDE307B2397E5A0D9392B273B36B` |

The original image belongs to the early white/blue “修订历史” consumer. Original PR45 already labels the shared Panel “版本记录”; `5698aca` already adopted the deep navy/aqua tokens. The actual current render uses those inherited tokens and shared Panel/Button/Badge primitives; the history/now comparison, human restore confirmation and persistent red conflict are complete. The Design System freezes shell bands and navigation widths, not a 742px history Panel minimum. Its canonical reference is a design hierarchy reference, not a pixel input.

The controlling agent independently reviewed the current PNG against the Design System and canonical reference and authorized this maintenance. Runtime CSS/layout/tokens were not modified to imitate the retired theme. The original gold is retained at:

`visual-history-geometry/retired-original/production-revision-restore-conflict-chromium-win32.png`

Prior evidence remains:

- `PR45_ORIGINAL_VISUAL_RED.log`, `pr45-original-visual-red/`: original fixture exposes the original App writing-goal crash.
- `PR45_ORIGINAL_VISUAL_LEGAL_FIXTURE.log`, `pr45-original-visual-legal-fixture/`: corrected fixture/navigation on original PR45 still fails original gold.
- `VISUAL_HISTORY_GEOMETRY.log`, `visual-history-geometry/`: recovery fails the same old gold; shell geometry and conflict comparison pass.
- `VISUAL_HISTORY_BASELINE_MIGRATION.log`: reviewed one-image migration and new geometry checks pass.

The old golden-image comparison did not pass; it was explicitly retired after proving it diverged before this recovery. Its threshold and original business assertions remain.

## Production-shell fixture and golden-image reconciliation

The first full 15-case visual run had one failure in `production NOVEL route uses the frozen AppShell`, before its screenshot. Its old localStorage fixture contains IDs with no display metadata but expects “当前工作区” and no `workspace-real`. PR45's `selectedScopeLabels.ts` and its four original unit tests explicitly require actual selected IDs when metadata is absent: they prohibit inventing mainline/default owner names, preserve distinct opaque identities, and use actual provided names when available. Those original unit tests pass.

`PR45_ORIGINAL_PRODUCTION_SHELL_RED.log` reproduces the original PR45 failure. The controlling agent authorized completing the fixture with real owner metadata rather than changing runtime fallback semantics. The test workspace is actually named “当前工作区”; the project, storyline and branch have explicit test names, and all original IDs remain. The old three business assertions pass unchanged. Deterministic endpoint responses replace the earlier unmocked loading race; new geometry assertions pass against the actual App.

This exposed an independently stale production-shell gold from initial source import `ddf7997`: its early consumer omits the already inherited 主控 tab, current chapter identity, chapter navigation and project-target inspector, and predates the inherited navy/aqua tokens. Both current and independently extracted original PR45 produce exactly the same 1440×900 PNG with the same legal completed fixture. Evidence:

| Artifact | SHA-256 |
| --- | --- |
| Retired production-shell gold | `5A45821AB3B15E7013429C074464CB95FC8CA34646F145CCB351CD8CDFC9FA60` |
| Original PR45 and recovery actual with completed fixture | `ACDBB3990730505D9F1C2C27A45651C5461DA7D368CB0D4748DD10C7AF872DDB` |
| Regenerated production-shell gold from reviewed real React fixture | `07DD56B9AD07BB55D1367CF1442DE40DB81ADA4788DC910FE8988371E7A45EFD` |

The original gold remains at `visual-history-geometry/retired-original/production-novel-shell-chromium-win32.png`; `PRODUCTION_SHELL_LEGAL_FIXTURE_RED.log` and `PR45_ORIGINAL_PRODUCTION_SHELL_LEGAL_FIXTURE.log` preserve original-gold failures with matching actual images and diffs. The controlling agent authorized the second image migration after the same baseline-proof method. `PRODUCTION_SHELL_BASELINE_MIGRATION.log` records that one migration; the complete final suite then passes 15/15 with the unchanged 1.5% tolerance. No other golden image, assertion or scope-label runtime implementation changed. Neither old golden comparison is claimed to have passed.

## Handoff

Real runtime checks were then performed against `127.0.0.1:8051` / frontend `127.0.0.1:5209`, with no route interception or mock responses:

- `REAL_PRE_CHAPTER_BROWSER.json` verifies original project `91ccf654` has no chapters, the visible world summary exactly matches the live project owner, real character 林渊 is visible, and the OUTLINE entry can select the discovered available Qwen route and enable generation. Original WORLD/CHARACTERS receipts are `execution_mode: real` and APPLIED; the original failed OUTLINE is reported as FAILED. This is a pre-chapter read/control check, not a claim that the failed outline succeeded.
- `REAL_PRODUCT_BROWSER.json` verifies `df4544f1` original World/three characters/adopted outline, live editor text against the actual TipTap document, manual-save control, AI rewrite tab, consistency control, history versions 3/2/1 with comparison and explicit restore confirmation (cancelled without writing), and original successful export download. `real-product-browser-df4544f1.md` is the real downloaded 3794-byte Markdown artifact, SHA-256 `a13f504ce59e8b4d654d5bda400931c58baa8d1ef3a774564eaf1e11c1e8d44c`. There were no browser JavaScript errors or horizontal overflow. These are UI reachability/read/download checks; the controlling agent separately performs the ten mutating product steps.
- The initial latter check exposed two 401 responses for `/api/agent-jobs` in the ordinary local browser. Reviewer/Verifier controls were visible, but original job history/start required trusted actor authorization. Putting the credential in `studio.session` instead switches to the team identity and intentionally prevents local manuscript loading; that original guard is preserved. This original gap and its subsequent explicit development Host completion are both recorded; the failed initial unauthenticated attempt is not relabelled as a successful Agent execution.
- `REAL_AGENT_FAILURE_DIAGNOSTICS.json` records the five original persisted failed model Agent jobs on `df4544f1`: each safe error is PROVIDER_UNAVAILABLE, while the original llama.cpp log proves input admission rejected 8493–9116 tokens against an 8192-token server context. They did not reach generation/output-schema validation. The controlling agent subsequently restarted the independent model runtime with a larger context and reruns acceptance; this report does not relabel those failed jobs as successful.

Real browser evidence contains status/path summaries and screenshots, without session credentials or traces. Independent loopback API reads use the ignored runtime credential file; ordinary local UI keeps the original local identity. A diagnostic failure originally exposed an APIRequestContext request-header value inside the internal tool transcript; the local development credential was rotated and the prior value invalidated, the file logs redacted, and diagnostic errors now redact credentials before writing. No credential is in the report, browser JSON, download or Git changes.

### Development Host binding completion and final live UI

The initial ordinary-browser Agent 401 gap was subsequently completed through the product's explicit `本机可信会话` Panel inside the original Agent owner. The user supplies a password-type credential and clicks `验证并绑定本机会话`; GET `/api/local-session` resolves it through the original server-owned registry and returns only `LOCAL_HOST` and actor ID. This endpoint neither mints sessions nor grants capabilities. It is disabled behind the original collaboration/packaged boundary; packaged applications retain their existing host-injected bootstrap route.

The credential lives only in page memory. Original `studio.session`, `shouldLoadLocalNovels`, collaboration metadata/scope guards and project selection are unchanged. Core API transports add this credential only with no team token, no scope/actor metadata, no collaboration/packaged route and no packaged host. Team connection and explicit unlink clear it. Agent create/start/retry sequences capture the initiating credential and refuse a follow-up start after the identity changes. Protected history/audit/detail queries use the identity epoch rather than a token, and successful binding/unlink synchronously removes their caches. API mutation failures are persistent and preserve task input.

`REAL_AUTHORIZED_PRODUCT_BROWSER.json` / `.log` records final project `f4b8c9ee` on the actual backend8051/frontend5209. The browser has no route interception or automatic request-header injection; it reads/writes through the original UI. Independent authenticated API reads only compare live owner data and persisted receipts. The live check verified World, three Characters, adopted Outline, exact current editor document, save/rewrite/consistency controls, versions 3/2/1 with comparison and explicit restore confirmation (cancelled), export download, Reviewer/Verifier choices, explicit local binding, real Reviewer execution and explicit unlink.

The anonymous Agent start returned 401, then actual UI validation returned 200 `LOCAL_HOST`. The UI-created Reviewer job `4953fb9c-6fdc-4cee-bf1a-e43d9c7be26b` completed with `execution_mode: model`, `model_called: true`, nonempty structured output and context hash `fcd3eb46b474d3fb5cd65395fd476c60f860a264102607af47b4a86b55db348f`. It selected the dynamically discovered actual Qwen route, retaining approved world/character context. There were zero network failures after binding, zero browser JavaScript errors and no horizontal overflow. The three pre-binding 401 responses (two history reads and one explicit negative start) demonstrate the original anonymous boundary remains enforced, rather than an incomplete acceptance step. The successful screenshot is `real-authorized-product-agent.png`; it contains no password input value.

The final original export downloaded as `real-product-browser-f4b8c9ee.md`, 3695 bytes, SHA-256 `31c28ce219e9c1656d8dd573378864a2b8b122976c942198c8d2a4891aaad2ef`. The reproducible browser driver is `scripts/full_recovery_product_surface.cjs`: `node scripts/full_recovery_product_surface.cjs f4b8c9ee --full --trusted-agent`. It obtains its development credential from the ignored runtime configuration and redacts diagnostic errors. Its read/control/export checks and real UI Agent execution are distinct from the controlling agent's ten mutating API acceptance steps, Memory extraction/explicit approval and all five real Agent executions.

- DONE: original frontend owners recovered; premise-based structured creation, explicit reviewed adoption, world-summary binding, pre-chapter project Story viewing/editing, additional Agent selection, malformed-goal editor recovery, explicit development Host binding and protected cache isolation delivered. Actual UI starts and completes a real Qwen Reviewer while preserving the anonymous 401 boundary. Frontend verification retains the two explicitly reviewed golden-image migrations.
- PARTIAL: large frontend bundle warning remains. New project-wide structured adoption is local-project scoped. Local development Host credentials are deliberately memory-only and must be reverified after refresh; packaged authentication follows its separate original bootstrap owner.
- BLOCKED: no new frontend implementation block. The real-model product verdict is controlled by the independent end-to-end acceptance run, not inferred from fixture tests.

No commits or pushes were made by the product-surface agent. Frontend runtime and test changes are ready for the controlling agent's final integration review.
