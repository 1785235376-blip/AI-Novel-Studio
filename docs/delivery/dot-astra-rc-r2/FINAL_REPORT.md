# R2 engineering delivery report

**Decision: candidate for bounded internal desktop acceptance. All final engineering-source hosted gates pass. Not a formal release or a claim that every feature is complete.** Updated 2026-10-05T08:45:14.220087 + 00:00.

## Tested source and delivery identity

- Repository: https://github.com/1785235376-blip/AI-Novel-Studio; branch `work/dot-astra-v1-rc-r2`; [Draft PR #37](https://github.com/1785235376-blip/AI-Novel-Studio/pull/37), unmerged.
- Baseline: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`.
- **Final tested engineering source: `98b7d53c3193765e792e5a756fff02a87b5948b8`**, tree `f6c4a84c5ff0d1b2639b537af1ea287611935fd4`. It is source-tree-equivalent to independently reviewed local `1c19d83d870f325cb6af1d182573b1e8b2a47a29`.
- [Push 37284138175](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175) and [PR 37284145310](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284145310): **all five lanes completed SUCCESS**. Actual PR merge checkout: `1c10ecc09ce07d445750a3a994931a1bc7f6f0be`. Branch and merge checkout are distinct identities.
- Subsequent documentation/evidence-only commit: its actual delivery SHA, readback and separate CI will be reported in the final Draft PR body/delivery message. It cannot embed its own future commit ID. This does not make the completed engineering-source gates unknown.
- Product remains **0.7.0/Beta**; development/audit model reported by the team is `gpt-6-astra`. No merge, formal Release or production deployment is claimed.

## Final execution results

| Layer | Verified result at final source |
|---|---|
| File backend | **2147 passed /  45 skipped** |
| Actual PostgreSQL 16.15 | **2155 passed /  37 skipped**; all **10** specialized acceptance/dispatch controls pass without skips |
| Frontend unit | **579 passed /  111 files** |
| TypeScript / design tokens / production build | **PASS**, with the existing large-chunk advisory retained |
| Actual browser | **9** geometry/Local AI, **2** full business and **1** export-recovery tests pass |
| Final writing-goal layout | Actual containment/stacking/no-overlap assertions pass at **1366×768, 1440×900, 1920×1080** |
| Windows Host | **SDK 8.0.424**, compilation and **59** native contracts pass |
| Complete unsigned internal Windows package | **PASS** |
| Real Windows native base | **11 commands, all exit 0**, including owned-cluster stop |

The native receipt verifies isolated **Python 3.12.9 / 27 locked wheels / binary psycopg**, **PostgreSQL 16.15**, pgcrypto, UTF-8 Chinese text round-trip, custom dump restored into a new database, packaged app import and owned shutdown. This is actual hosted Windows execution, distinct from Linux input preparation or mocked subprocess tests.

Permanent exact-source evidence is in `evidence/ci-98b.json`, `ci-98b-native-smoke.json`, `ci-98b-pg-controls.json`, `ci-98b-application-provenance.json` and `ci-98b-host-provenance.json`. Counts overlap across suites; skipped tests do not pass. Full historical provenance is in [TEST_RESULTS.md](TEST_RESULTS.md).

## Package and screenshot handoff

[Download the complete internal Windows acceptance artifact](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175/artifacts/11333273928) from the successful final-source run. It is **161705892 bytes**, outer CI archive SHA256:

`e248ce586e0dc8ceec313dc947b5cb991bdd48dd9ba73743e75b42b77bfa0d28`

This is the complete package artifact; the separate windows-host artifact is compile-only. CI artifacts expire **2026-10-19**; safe receipts and screenshots remain in Git. The hash above identifies the downloaded CI archive, not an invented inner ZIP hash.

Six actual final-source screenshots are committed under [evidence/screenshots](evidence/screenshots/manifest.json), with source/run/artifact and per-file SHA256/size metadata. Every file digest/size was checked; the integration lead opened and reviewed all six. The export-recovery set uses an actual File-backend business journey with synthetic text and explicitly mocked model output. The Local AI set is real browser rendering against synthetic API/hardware/runtime fixtures, including deliberate PARTIAL/unavailable states. Neither set is evidence of real GPU inference or interactive Windows hardware discovery.

The earlier 93d package inventory matched **232 backend and three Host source files after the documented Windows LF→CRLF checkout transformation**, with no unexpected differences. This is not literal Git-blob byte equality, and its historical inventory check is not silently relabeled as a later execution. Exact latest application/Host provenance is retained separately.

## Delivered bounded capabilities

1. **Privacy and recovery:** migration 018, conservative persisted policies, strict File→PostgreSQL policy preservation, hash/version-bound source review, final-send authority checks, selected sidecar/asset backup and verified restoration to new targets.
2. **Authoring and acceptance:** reviewed STYLE/PLOT/world/psychology records, anchored comments, bounded exact-evidence structured suggestions, Draft/Diff/Accept, captured generation bases, durable acceptance claims and fail-closed ambiguous interruption. History refresh, context/ABA fencing, dirty-buffer preservation and StrictMode replay are exercised through actual browser flows.
3. **Execution:** guarded compatible/Claude/Gemini protocols, explicit usage or UNKNOWN, cancellation and no hidden paid replay; automatic memory stays guarded-local-only. Agent timer ownership prevents late callbacks from recreating deleted jobs. Legacy remote asset generation without exact prompt consent remains unavailable.
4. **Exports and media:** scoped immutable export snapshots/history/recovery, Fountain/parser fixes, resource ZIPs, screenplay CAS/history and pinned licensed CJK fonts; verified image/audio/video bytes, lineage, recoverable asset trash, lexical references, bounded silent review cuts and ordered PCM WAV export.
5. **Workflows and plugins:** bounded persisted DAG, actual Agent job dispatch/review/cancel/retry and three reviewed-artifact local recipes. Declarative plugin lifecycle is checked; executable plugins remain **DENY_ALL**.
6. **UI and Local AI:** existing NOVEL/IMAGE/VIDEO shell/tokens retained. Settings → Model Center → Local AI and both API aliases are mounted; latest scoped goal-field layout passes actual three-viewport assertions without changing App behavior or global design tokens.

The matrix retains **all 143 original feature IDs, 19 packages and 28 supplement sections**, each with specific implementation, integration, verification, evidence and remaining acceptance boundaries. There is no completion percentage.

## Independent review and preserved history

- e38 independently closes the original and Discovery defects with **55** preserved/expanded invariants, complete File/UI regression and type/token/build checks.
- d033 closes the newly discovered StrictMode P2 with the **three unchanged independent assertions**, **23 additional replay checks**, full committed UI **575 / 110**, Agent/timer/dispatch **90**, and type/token/build passes.
- Final source-equivalent 1c19 increment: **35 UI/history/StrictMode/layout** and **40 input/native-verifier** checks pass, plus type/token/build; **1331 tracked files** match fixed blobs. No new concrete defect was found in this bounded review. Its pre-CI note that CSS execution was pending is now resolved by the later actual final-source hosted results, without rewriting that historical report.

See [INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md), [INDEPENDENT_REVIEW_INCREMENTAL.md](INDEPENDENT_REVIEW_INCREMENTAL.md), and [INDEPENDENT_REVIEW_FINAL_INCREMENT.md](INDEPENDENT_REVIEW_FINAL_INCREMENT.md). Earlier red assertions, failed browser runs and incomplete/cancelled native smoke remain recorded; they are not retroactively relabeled green.

## Deliberate partial and NOT_RUN boundaries

The package is an **unsigned internal acceptance ZIP with PowerShell installation tooling**, including self-contained .NET 8, but requires external **WebView2 Evergreen Runtime and VC++ x64 Redistributable**. Observed System32 CRT hashes prove the runner's prerequisite, not CRT bundling or clean-machine readiness. Official pinned inputs were assembled as 4876 files; the corrected focused breakdown is **29 base-input + 11 verifier cases = 40**.

**NOT_RUN:** interactive Windows/WebView2/OS vault/Chinese IME; clean install/upgrade/uninstall retention; signing; real provider/GPU/model inference; target Word/Final Draft/EPUB/NLE compatibility; user acceptance. Native package smoke does not waive these layers.

Local AI Ollama routes require positive current local-model/digest/completion evidence and reject remote or unknown locality; Writer output is explicitly buffered. External llama aliases and managed task-only lifecycle remain bounded. A1111 and standard SD Comfy adapters are connected; unimplemented family workflows, generic model-list/health adapters and unsupported credential bindings remain blocked or PARTIAL. Model names and metadata never certify inference. Old MiniMax audio history is preserved under its disabled identity; the new video identity is separate.

Multi-key profiles/full v2 broker, full hierarchical/semantic planning, long-book identity resolution, embeddings, dedicated cover/storyboard generation, final-master video, automatic speaker/emotion/alignment, unified approvals and executable plugin sandbox remain incomplete as itemized in the matrix.

Use USER_ACCEPTANCE_GUIDE.md and LOCAL_AI_WINDOWS_ACCEPTANCE.md on backed-up/synthetic data for the next bounded desktop checks. No real credentials/paid calls, irreversible user-data changes, main merge, formal Release or production deployment are implied by this engineering handoff.
