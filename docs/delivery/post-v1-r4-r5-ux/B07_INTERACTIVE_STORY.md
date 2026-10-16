# B07 · Interactive-story authoring, bounded preview and independent export

Date: 2026-10-05. Branch: `work/post-v1-r4-r5-ux`, Draft PR #39. This is Experimental work, not a change to frozen PR37/PR38 or a V1 acceptance claim.

## Delivery state and reuse

- Classification: **NEW adaptation layer, EXTEND existing planning/world/assets**. Original planning graph and node IDs remain the identities used for narrative nodes. Approved temporal-story-graph records and original character IDs can be referenced. Approved/public asset-library records retain their original authority and origin-feature guards.
- **IMPLEMENTED / INTEGRATED / CONTRACT_VERIFIED** for deterministic authoring, persistence, source-bound review, typed paths, real HTTP playback and independent bundle generation. Real File storage and mounted production API are verified below.
- Browser UI is implemented and React behavior is verified. The hosted-browser journey is authored but **NOT_RUN locally**. Known Chromium launch `EPERM` was not retried. A hosted job must actually return before browser PASS is claimed.
- PostgreSQL cases are explicitly marked for real PG; **NOT_RUN locally**, no configured `TEST_POSTGRES_DATABASE_URL`. No replacement database or mock is counted as PG.
- Ren'Py **8.5.4 documented text/menu subset** is exported and statically tested. **Target runtime NOT_RUN**, no SDK/runtime execution, no external compatibility claim. No real model is used or needed.
- Full visual-novel media rendering is **PARTIAL**: character names, dialogue, variables, conditions, choices and endings work; background/music are approved-library references only. They are explicitly not embedded or played. This limitation appears before export and in the bundle.
- No imported scripts, plugins, paid services, credentials, cloud upload, manuscript rewrite, Canon promotion, asset promotion, release or deployment occurs.

## User workflow

Experimental → **互动故事与导出**:

1. Create a normal planning graph/nodes if none exist. Select an existing graph and the original nodes to adapt. The selection order is retained; first selected node is the initial entry and can be changed.
2. Edit each selected node's title/dialogue, choose its original character ID, and optionally reference approved image/audio assets and reviewed graph records. Enter an ending label or add up to eight outgoing choices. Every choice names another original selected node.
3. Add strictly typed `bool` or bounded `int` variables. Choice conditions support names, bool/int literals, `== != < <= > >=`, `and/or/not`, and parentheses. Choice effects assign literal values of the matching type within bounds. Examples: `trusted and courage >= 2`, `not trusted`, `True`.
4. Save the draft. Unsaved input blocks record-switching/refresh/review/export; save conflicts preserve the input. Restore unsaved input is explicit. A browser-navigation warning exists while dirty. Scope changes intentionally remove the previous scope's private state.
5. Inspect unreachable nodes, cycles, no-exit nodes, undefined targets/variables, type/bounds errors and state-search limits. Ending witnesses include replayable choice IDs.
6. **从开头试玩** starts real server-backed playback. Each click replays the bounded path against current authority and saved version. The two synthetic test routes reach separate endings. Reset starts from initial variables; no autonomous loop or hidden background task runs.
7. Submit → preview exact review → approve. Approval applies only to this independent adaptation. Editing/rebinding reopens DRAFT. Reopen revokes approval. Archive is recoverable and permitted even when sources are stale; restore requires current valid sources.
8. Export preflight reports media references, missing/corrupt bytes and compatibility losses. Explicitly acknowledge those losses, then generate and download the ZIP. No directory is written on the server and no existing project is overwritten.
9. A changed source hides derived story text and disables playback/export. **预览互动来源重绑定** checks the same current authorized original IDs; **确认重绑定并重新审核** retains author text/choices as an unreviewed draft. It does not rewrite dialogue. Missing, archived or revoked references cannot be bypassed by rebinding; restore legitimate references/permission or create a new adaptation.

## Runtime and safety contract

Feature: `interactive_story_v2`, default OFF. Explicit dependencies: `advanced_planning_v2` and `temporal_story_graph_v2`; the latter still requires its existing world dependency. `V1_ACCEPTANCE_MODE` defeats every route, including malformed-body requests. No wildcard enablement.

API root under both mounted API versions:

`/novels/{nid}/experimental/interactive-stories`

- GET `/catalog`, list, and `/{id}`
- POST create, PUT `/{id}` save
- POST `/{id}/preview` with expected version and bounded selected-choice path
- POST `/{id}/review-preview`, `/review`
- POST `/{id}/refresh-preview`, `/refresh`
- POST `/{id}/export-preview`, `/export`

Current trusted actor/workspace/project/storyline/branch and `domain.write`/`domain.review` are checked through the original authorizer. Records are author-private. Read responses are `Cache-Control: no-store`. Current flag and authority checks occur again inside the write transaction and before response/export. Stale-CAS errors contain only ID/version/status, never draft text or history. Playback also rechecks the latest adaptation version before returning a delayed result.

Provenance captures include:

- Original planning graph/node versions; full ancestor digests and current linked-entity digests
- Chapter versions, document/content digests, metadata, exact branch and current source-privacy decisions
- Approved graph record versions/digests and their original evidence authority
- Character digests/names and approved asset versions/digests/metadata/origin gates

Storage uses the existing isolated `ExperimentalStore` collection `interactive_story_adaptations`. Scope-atomic File/PG storage, version checks and history are reused. No new SQL migration, schema replacement, startup conversion, manuscript or planning write occurs. New databases remain Experimental; disabling the flag is not a downgrade/data rollback.

Limits: 100 selected nodes, 8 choices/node, 16 variables, integer values and bounds within -10000…10000, 100000 total dialogue characters, 20 current chapter sources, 50 graph-evidence references, 100 adaptations/scope, 2 MiB HTTP body, 128 maximum runtime choices. Integrity checking of all referenced assets is limited to 32 MiB total. These are explicit rejected limits, not silently trimmed story content.

Conditions are parsed with Python's parser but interpreted only through our own allowlisted typed tree. There is **no eval/exec**, no function call, attribute/subscript access, import, string expression, arithmetic, comprehension or script execution. Both preview and target compilation use the validated tree. The engine-neutral file also includes the tree.

Path analysis combines bounded structural traversal, reverse ending reachability, and breadth-first typed-state exploration (4096-state maximum). It reports cycles and runtime step caps, actual ending witnesses, conditional dead states and incomplete analysis. Incomplete or erroneous analysis cannot be approved/exported. This is not an unbounded termination proof. Repeating a state is deduplicated during analysis; interactive playback still stops at the explicit step cap.

## Independent ZIP and practical target subset

A new generated UUID-based folder contains:

- `story.json`: `ai-novel-interactive-story/1`, adaptation/version, original graph/node IDs and versions, explicit narrative endings, typed variables, restricted condition trees, character display names and source-version references
- `game/story.rpy`: generated Ren'Py narration/explicit speaker strings, conditional menus, mapped labels/jumps, typed assignments, endings/return and runtime step cap
- `media-manifest.json`: original asset ID/version/hash/kind, missing/corrupt indication, `packaged: false`, explicit reference-only reason
- `compatibility.json`: preflight, runtime `NOT_RUN`, media/animation/plugin/whitespace/font losses, bounded analysis
- `checksums.json`: SHA-256 for the other files
- `README.txt`: extract into a new empty directory; inspect in a new target project without overwriting existing work

The ZIP is generated in memory and returned for a browser Blob download. Member paths and target identifiers are server-generated; user titles, labels, dialogue and resource filenames never become archive paths or script labels. Quotes, backslashes, line breaks, interpolation brackets, text-tag braces, ruby/furigana opening brackets and percent characters are escaped. No original filesystem paths, resource URLs or executable imported code are included. Manifest-only resources do not cause remote fetches or execution. Missing bytes change the exact export receipt, so an earlier acknowledged receipt cannot export a later result silently.

Official documentation checked 2026-10-05 (pages identified themselves as 8.5.4):

- [Dialogue and narration](https://www.renpy.org/doc/html/dialogue.html)
- [In-game menus](https://www.renpy.org/doc/html/menus.html)
- [Labels and control flow](https://www.renpy.org/doc/html/label.html)
- [Python/default statements](https://www.renpy.org/doc/html/python.html)
- [Text escape characters](https://www.renpy.org/doc/html/text.html#escape-characters)

No copied SDK/runtime is shipped. Static label resolution, generated scalar assignments and expressions, literal escaping, ZIP parsing and checksums are verified; those checks are **not Ren'Py runtime validation**. Fonts, target appearance, custom screens, media playback, transitions, voice/lip sync, save compatibility, target plugins and licensing/commercial suitability remain outside this subset.

## Tests and evidence

Focused runs use the existing disposable isolated harness, Python 3.12.14 and Pydantic 2.13.5. No real manuscripts, models or credentials are used.

- `pytest -q tests/test_r5_interactive_story.py tests/test_r5_interactive_story_mounted.py -m 'not postgres_backend_only'`: **60 passed, 41 deselected**. Deselected cases are real PG contracts, not PASS or mock substitutes. Covers typed expression/code-injection rejection, bounds, two endings, undefined/unreachable/no-exit/cycle detection, 4096-state limit, current graph/asset/source/privacy/actor/branch authority, exact review and rebind, current-version delayed playback fence, concurrent CAS, final-gate rollback, archive/restore, malformed/oversize requests, OFF/dependency/V1 routes, both production API prefixes, ZIP/hash/escaping/subset syntax and no legacy promotion.
- `vitest run src/experimental/InteractiveStoryPanel.test.tsx`: **11 passed**. Transport mocks are explicit frontend contract fixtures, not real browser or backend evidence. Covers Unicode composition state, condition/assignment editing, selected original IDs/order, server-result playback/reset, draft conflict preservation, review receipt invalidation, exact rebind, duplicate-click suppression, scope/StrictMode/late callback cleanup, stale withholding, explicit loss acknowledgment and URL cleanup.
- `tsc -b`: PASS after latest frontend changes.
- Production `pnpm build`: PASS on the final B07 frontend tree; normal existing >500 kB chunk warning remains. Published-checkpoint aggregate regression is owned by the integration lead.
- `pnpm lint`: UI token guard PASS. UI uses the existing AppShell/Workbench, Panel/Button/Badge/StatusMessage/Field and tokens. No protected shell/token/primitive redesign.
- `frontend/tests/e2e/r4-interactive-story.spec.ts`: one authored real File/React journey, no response mocks. Covers original planning setup, form-based authoring, two playable endings, approval, downloaded ZIP inflation/schema inspection, original chapter unchanged, 1366×768 / 1440×900 / 1920×1080 no-horizontal-overflow assertions/screenshots, and source-stale withholding. **NOT_RUN locally**; hosted result must be recorded separately.
- Native Windows IME, assistive technologies, target software runtime and user aesthetic acceptance: **NOT_RUN**.

Intermediate failures are retained as history: initial React run exposed duplicate sibling keys and leaked listener cleanup; implementation keys were made distinct and the final focused suite passes. Test typecheck rejected Testing Library's unsupported `exact` option, fixed to an anchored name. One new graph fixture used `AT` instead of the original authority's `LOCATED_AT`, corrected without relaxing production validation. Some expanded backend attempts were blocked at app import by an in-flight unrelated Writer Room syntax error, resolved by its owner; the final focused run imports real production composition successfully. No failed safety assertion was removed.

Independent second-slice review remains platform-blocked as tracked by the integration lead; this implementation and self-check are not an independent audit. Commit identity, hosted CI and aggregate regression receipts are recorded by the lead for the published checkpoint, without inheriting previous runtime claims.
