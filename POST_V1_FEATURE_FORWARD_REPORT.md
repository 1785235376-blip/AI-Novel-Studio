# AI-Novel-Studio — Post-V1 Feature Forward R3

## 1. Delivery and frozen scope

- Starting SHA: `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0`.
- Frozen V1 acceptance: Draft PR #37 / `work/dot-astra-v1-rc-r2`; its source, acceptance package and recorded evidence are unchanged.
- R3 branch: `work/post-v1-feature-forward-r3`.
- New stacked Draft PR: [#38](https://github.com/1785235376-blip/AI-Novel-Studio/pull/38), base `work/dot-astra-v1-rc-r2`.
- Integrated implementation checkpoint: `20cd2679ee104702529962202ce4b9d894bffc89`, source tree `bc0fd5eb415a2d0b2076e061f6982d8e85fecacb`.
- This report records the final tested implementation SHA above. The following documentation/evidence-only delivery commit is identified by its exact SHA and rerun in the PR #38 delivery readback; a file cannot embed its own commit hash. No partial earlier checkpoint is used as final implementation proof.
- Product version remains 0.7.0; “V1 acceptance” identifies the user's frozen acceptance scope, not a formal release.

No merge, release, production deployment, signing, paid API, private credential use or executable third-party plugin enablement was performed. Plugin execution remains DENY_ALL. V1 acceptance does not require these Experimental features.

## 2. Implemented engineering

### Advanced authoring and planning

Real scope-bound Project → Volume → Chapter → Scene graphs provide goal, conflict, turning point, climax, ending intent, character objectives and custom beats. Three-act, conflict-escalation and multiple-ending templates are optional and extensible. References resolve to project characters, locations, chapter revisions, story routes and reviewed world rules.

Proposals can be created or explicitly generated with the Mock structured adapter, compared, approved, rejected, archived and restored from history. Sources, target node and ancestors are version/digest fenced. Approval atomically updates the experimental planning node and its history; it never overwrites manuscript or V1 Canon. The UI preserves unsaved drafts and requires an explicit comparison/rebase when the selected node changes version.

### Long-book semantic import

Import jobs persist bounded chunks and per-attempt claims. Pause, resume, cancel, retry and interrupted-claim recovery retain completed work. Evidence retains chapter identity/version/hash, exact Unicode offsets, paragraph position and quote. Cross-chunk duplicates aggregate evidence; alias/identity and conflicting-attribute suggestions remain reviewable.

Seven candidate categories are represented. Characters, locations, timeline and foreshadowing can be explicitly committed through the existing per-target ImportApplyService journal. Each write revalidates source evidence and live authority. A partial or ambiguous write does not blindly repeat a successful mutation. Extended organization/world-rule/relationship candidates remain proposals until a corresponding promotion adapter is available. The bundled extractor is a local heuristic, not a verified semantic model. Unknown or remote injected adapters fail closed.

### World and character engines

Typed history/temporal relations, geography/ownership, civilization/faction, ability rules and usage, psychology snapshots, relationship evolution and character events have persisted review/history/version contracts. Only explicit approval creates separate experimental Canon. Archive/retirement of approved Canon requires review authority.

Chapter-state queries use narrative order and one canonical snapshot. Deterministic findings cover unexplained post-death appearance, conflicting ownership, ability limits/costs and temporal reversal, with stale dependent records excluded. These are deterministic rules, not claims of unrestricted semantic understanding.

### Unified review inbox

The Inbox projects the new planning/world/import/team/media/audio queues plus eight legacy groups: import, planning, Canon, world rules, agent results, workflows, media and export/release gates. Every item carries its domain/source/scope, version/hash, actor, status/staleness, risk/privacy state, preview and target.

Actions dispatch to the domain's own review service or existing authenticated route. There is no direct Inbox Canon/manuscript mutation path. Detail-dependent or unversioned legacy queues are read-only; original-domain permission failures produce a sanitized unavailable marker without leaking denied rows or hiding unrelated authorized items. Missing privacy metadata is UNKNOWN, not assumed safe/local. Explicit allowlisted batch rejection records each success/failure and never pretends to be a cross-domain transaction.

### Domain agent teams

Eight role templates and four recipes provide outline→draft→editor→human review, continuity→fix proposal→human review, screenplay→shots→human review, and storyboard→image proposal→human review. The executor has versioned scope, pause/resume/cancel/retry, persisted claims and artifacts, host-restart recovery and late-result fences.

Current execution is contract-only; artifacts and human review are real, while literary output quality and real agent-model execution remain NOT_RUN. No unapproved artifact overwrites manuscript or Canon.

### Media workflows, cover/storyboard, embeddings and audiobook

The registry defines all 17 requested IMAGE/VIDEO/AUDIO input contracts and separates model discovery from actual workflow implementations. Qwen-Image, FLUX/FLUX.2, Z-Image, MiniMax H3, Wan, LTX, SeedVR2 and RIFE family definitions remain ADAPTER_REQUIRED. Model files do not make an adapter runnable.

Cover briefs include title/subtitle/genre/characters/palette/composition/safe areas. Shot-derived storyboard briefs preserve original scene/chapter provenance. Explicit Mock tasks create real decoded fixture PNGs, multiple proposals, comparison and reviewed assets with stable lineage. Cross-store approval uses durable promotion intent and asset checkpoints; it can resume idempotently. If sources change after partial promotion, it exposes the existing asset and reconciliation-required state instead of silently rejecting or deleting it.

The image/media validators require real ffmpeg and ffprobe executables. Both backend and experimental browser CI install and verify these tools; validation is never skipped to make a Mock workflow appear successful.

Embeddings have provider capability contracts, typed vector records, asset/character/scene lineage, model/index identity, rebuild/invalidate/remove/query and stale guards. Runtime status defaults to NOT_CONFIGURED. Deterministic vectors are explicit Mock fixtures; lexical metadata is never a fake embedding fallback.

Audiobook V2 provides conservative dialogue attribution, NEEDS_REVIEW uncertainty, character/voice mapping, emotion/style, ordered segments, measured duration manifests, music/ambience/SFX slots and subtitle interfaces. An injectable local PCM16 WAV mixer is implemented and tested. Runtime TTS/mixer configuration defaults to NOT_CONFIGURED. Unmeasured timings stay unknown; there is no invented phoneme alignment or precise lip sync.

Optional Provider Profiles are credential-free schemas and selection/disable/revoke/OS-vault-reference contracts only. No plaintext key input, browser vault identifier or runtime credential-write UI/API is exposed. New optional bulk asset-governance tools were not delivered.

## 3. Compatibility, migration and API/UI changes

- `EXPERIMENTAL_FEATURES` is an explicit server allowlist; unset/empty means all OFF. `V1_ACCEPTANCE_MODE=true` forces all nine OFF even when the allowlist names every feature. See V1_SCOPE_FREEZE.md.
- Existing `app/api.py` and migrations 001–018 were not modified.
- New migration: `019_experimental_scope_documents.sql`. It adds a separate JSONB scope-document table/index with transactional locking. No legacy record conversion, destructive migration or old checksum rewrite is required.
- File storage atomically replaces one locked scope document. PostgreSQL atomically commits its row. Disabling flags preserves data. Downgrade keeps new metadata untouched; export it before any separately authorized removal.
- The packaged migration runner includes migration 019 only on explicit Experimental opt-in; its default V1 migration list is unchanged.
- There are 85 additive method/path pairs, each with the existing `/api/v1` alias. See [API_CATALOG.md](docs/delivery/post-v1-r3/API_CATALOG.md).
- Functional UI is an optional Experimental FeatureLauncher group and nine panels inside the existing NOVEL workspace. Existing AppShell/tokens/primitives and R2 tests/goldens are preserved; no final visual redesign was performed. See OPUS_UI_HANDOFF.md.
- Collaboration metadata is isolated by project/workspace/storyline/branch. Where the inherited repository lacks a true branch-bound manuscript reader, captured manuscript snapshots fail closed. Branchless characters, locations, story routes and legacy Canon may be referenced as shared project-level entities with digest fencing; they are not claimed as branch-specific source snapshots. Full branch-source parity remains PARTIAL.

## 4. Verification

Local working-tree evidence:

| Gate | Actual result | Boundary |
|---|---|---|
| Full inherited + new File backend | 2,289 passed; 168 skipped | 123 skips are new real-PG parameters; they must execute in hosted PG |
| Forced V1 acceptance, all flags overridden OFF | 2,147 passed; 45 skipped | Entire inherited suite; R3 opt-in-only tests intentionally not selected in this separate compatibility run |
| Frontend full unit/component suite | 602 passed; 6 optional HTTP skipped | Includes explicit checkpoint recovery, initial hydration and accessible-field regressions |
| Separate real-HTTP React/jsdom integration | 6 passed | Actual File HTTP service; not a real-browser claim |
| Independent Astra backend review selection | 142 passed; 123 PG deselected | Seven reproduced backend findings corrected and revalidated |
| TypeScript / production build / token guard | PASS | No inherited assertions or golden images weakened |
| Local Chromium | NOT_RUN | Process-singleton socket denied, including the permitted escalated attempt |

A separate real File long-book measurement processed 20 synthetic chapters / 320,475 persisted characters / 80 chunks, paused after 16, resumed in a fresh process and finished in NEEDS_REVIEW. It verified 81 candidates and 1,080 exact evidence spans, unchanged manuscript/legacy Canon, zero network calls, 67.02 seconds total, a 2,231,651-byte scope document and 71.16 MiB peak worker RSS. See [LONG_BOOK_MEASUREMENT.json](docs/delivery/post-v1-r3/LONG_BOOK_MEASUREMENT.json). This is bounded local-heuristic evidence, not maximum-scale or literary-quality validation.

[LOCAL_TEST_RECEIPT.json](docs/delivery/post-v1-r3/LOCAL_TEST_RECEIPT.json) records the File/JUnit counts. [REVIEW_RESOLUTIONS.md](docs/delivery/post-v1-r3/REVIEW_RESOLUTIONS.md) records the independent review boundary and corrections.

Exact hosted verification for the integrated implementation:
- [Push CI](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37321369458): SUCCESS, all five lanes.
- [PR CI](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37321380176): SUCCESS, all five lanes.
- Actual File: 2,289 passed / 168 skipped. Actual PostgreSQL: 2,322 passed / 135 profile-specific skips; downloaded JUnit proves all 123 new PG parameters passed with zero skips/errors.
- Frontend: 605 passed / 6 optional HTTP skipped; type/build/token checks passed. Hosted Chromium: all seven new journeys, nine inherited geometry checks, two R2 business journeys and one export journey passed (19 total, zero skipped).
- Windows Host: 59 tests passed. Fresh unsigned package and embedded Python/PostgreSQL native smoke passed; interactive application acceptance remains NOT_RUN.
- Push checked out `20cd2679ee104702529962202ce4b9d894bffc89`. PR checked out synthetic merge `c185dd00827cc022fd847d75671e744e4fcaf610`; both trees are exactly `bc0fd5eb415a2d0b2076e061f6982d8e85fecacb`.
- See [CI_RESULTS.json](docs/delivery/post-v1-r3/CI_RESULTS.json), [all 123 PG cases](docs/delivery/post-v1-r3/POSTGRES_CASES.json), and [eight inspected screenshot manifests](docs/delivery/post-v1-r3/screenshots/manifest.json).

A PR run may check out a synthetic merge commit. Push SHA, PR merge SHA and tree are recorded separately; they are not conflated. R3 Windows artifacts are engineering regression artifacts and do not replace the PR #37 frozen acceptance package.

## 5. Known inherited defect and remaining PARTIAL / NOT_RUN boundaries

**OPEN: File project deletion versus lazy document reads.** An unchanged inherited FileRepository can race a live reader that lazily migrates/creates chapter-document files. Actual hosted teardown observed `Directory not empty`; a separate deterministic synthetic-project reproduction paused a read before lazy migration, completed deletion, then resumed the read and observed the deleted directory/project reappear. R3 does not fix this production defect. Disposable browser fixtures now quiesce client-observed requests and close their page before exact-owned-ID cleanup, retaining all deletion-status assertions. This improves test lifecycle ordering but does not prove every server handler has stopped or prevent deletion races in the application. The next authorized engineering branch owns a separate shared-fix/backport-candidate change; it must not alter PR #37 without separate authorization. See [KNOWN_INHERITED_DEFECTS.md](docs/delivery/post-v1-r3/KNOWN_INHERITED_DEFECTS.md).


- Real planning/extraction/agent/embedding/image/video/TTS provider quality, local GPU/runtime workflows, literary/image/voice quality: NOT_RUN.
- Family adapters: ADAPTER_REQUIRED; definitions and Mock execution are not real model integrations.
- Full branch-source adapters: PARTIAL; unsupported branch manuscript snapshots fail closed, while branchless project entities/legacy Canon remain shared project references, not branch-specific source evidence.
- Extended import category promotion: PARTIAL; evidence-backed review is available, legacy target adapters are not configured.
- Interrupted media promotion after source changes: explicit checkpoint/reconciliation state exists; automatic reconciliation/removal is not implemented.
- Maximum-scale long-book throughput at declared bounds: NOT_RUN. Whole-scope serialization and repeated candidate/source-map processing need scale measurement.
- Named Provider Profiles: contract-only; live OS-vault registrar/UI NOT_RUN.
- New optional bulk asset tags/archive/restore/replace/reimport/repair UI: MISSING.
- Interactive Windows, GPU/model hardware, IME, real OS vault, installer/upgrade/uninstall, signing and user V1 acceptance: NOT_RUN here.

The detailed per-capability status is in POST_V1_FEATURE_MATRIX.md. R3 adds no V1 acceptance requirements. The inherited defect remains disclosed for the user’s acceptance decision and cannot be backported into frozen PR #37 without authorization. Mock or contract passes do not conceal these limits.
