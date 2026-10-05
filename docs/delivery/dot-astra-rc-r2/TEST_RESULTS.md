# R2 test results — final engineering source and historical ledger

**Final tested engineering source 98b: all hosted gates PASS. Bounded internal acceptance candidate; real-model/interactive/user acceptance remains separate.** Counts overlap and skips are not passes.

## Environment and execution boundaries

Local tests: isolated Linux, Python **3.12.14**, Node **24.19.0**, pnpm **10.6.5**, synthetic manuscript/media, isolated HOME/XDG/runtime-data roots, explicit File or controlled transport adapters, cloud disabled and no real model credentials. Hosted configuration pins Python **3.12.9**, Node **22.14.0**, PostgreSQL 16 and .NET SDK **8.0.424**. Actual version/result evidence takes priority over workflow configuration.

## Current candidate and intermediate results

| Evidence ID / revision | Result | Qualification and evidence |
|---|---|---|
| INDEPENDENT-E38 / `e38d1eccff6c1aac02a836817c878f423df0479e` | **55 invariant checks pass**; File **2131 passed /  46 skipped**; UI **549 / 108 files**; TypeScript, token lint **42 files**, Vite build pass | INDEPENDENT_REVIEW.md. Original red assertions retained; all earlier original and Discovery findings closed within scoped synthetic/Linux review. 1310 tracked source files byte-identical to fixed archive. |
| E38 packaging/PG structure | **59 passed /  10 skipped** | Same independent review. Skips are real-PG cases; structural review is not real-PG execution. |
| LEAD-E38-FONT / e38 | File **2132 passed /  45 skipped** | Actual pinned-font runtime test enabled by lead. One added pass, not an additive second coverage count. |
| LEAD-BBB-LOCAL / `bbb55d10ac57de123e138a51510efd846ee42aee` | File **2136 passed /  45 skipped**; UI **568 / 109 files**; TypeScript, correct `pnpm lint` **42 files**, Vite build pass | `evidence/bbb55d1-local-receipt.json`, `bbb55d1-full-file.txt`, `bbb55d1-full-ui.txt`. Actual pinned font used. Existing large-chunk warning retained. |
| INDEPENDENT-BBB / bbb | Existing File **2135 / 46**, existing UI **568 / 109** pass; **new StrictMode repro FAILS** | Separate P2: initial history promise is incorrectly invalidated by React.StrictMode effect replay. Existing complete-suite green did not cover this behavior. Historical failed review remains preserved; this P2 is independently closed at d033 below. |
| BBB-HISTORY-FOCUSED | **49 passed /  6 files**, **19 new real-QueryClient/App tests** | `revision-history-work.md`, `evidence/revision-history.txt/.xml`. Server-version history invalidation; actor/session/workspace/project/storyline/branch and A→B→A fencing; no token cache keys; clean/dirty App hydration. |
| BBB-AGENT-TIMERS | **75 focused passes** | `browser-ci-repair.md`, `evidence/agent-timer-cleanup.txt`. Owned timer disposal, no deleted-job recreation and explicit database failure behavior. |
| D033-STRICTMODE-FOCUSED / `d03399ee7d4b183173be47e5336b9bc4e0bd30b0` | **56 passed /  7 files**; TypeScript pass | `revision-history-work.md`, `evidence/revision-history-strictmode.txt/.xml`, `revision-history-strictmode-typecheck.txt`. Includes original 19 history tests, four new StrictMode cases and all three byte-identical independent assertions. Independent closure is recorded below; subsequent93d actual hosted recheck PASS. Latest layout candidate remains separate. |
| INDEPENDENT-D033 / d033 | **3 original assertions + 23 additional StrictMode replay tests pass; committed UI 575 / 110; Agent/timer/dispatch 90; type/tokens/build pass** | `INDEPENDENT_REVIEW_INCREMENTAL.md`. All 1324 tracked files match fixed Git blobs. P2 closed, no new concrete unresolved defect in the bounded increment. Backend unchanged from independent bbb File 2135 / 46; full backend not rerun at d033. |
| B0-BROWSER-NAVIGATION / b0 | Actual hosted reruns **PASS at 93d and final 98b** | `browser-ci-repair.md`. After reload, wait for the existing navigation control instead of immediate count. Actual journey/export assertions unchanged. |
| 871-NATIVE-SMOKE-CONTROLS / 871 | **40 focused passes:29 input +11 verifier cases** | File-backed bounded output capture, original finite deadlines, owned-PID timeout cleanup, progress and diagnostic receipts. Real Windows/native PG subsequently PASS at 93d and final 98b; first-reload history positive browser assertion added without weakening other acceptance. |
| WINDOWS-INPUT-ASSEMBLY / e38 | **4876 actual prepared files;29 current input contract cases** | `docs/R2_WINDOWS_BASE_INPUTS.md`, official input manifest/materializer. Downloaded and materialized on Linux; **no Windows executable run** by this preparation. |

A first local `pnpm lint:tokens` attempt failed because that script does not exist; it did not execute token lint. A later correct `pnpm lint` passed. Do not describe the initial chained invocation as successful. Current command names are in frontend/package.json.

The lead-local and independent File count difference is the optional actual-font test. Their counts must not be combined. Raw independent bundles identify the execution source; committed summaries distinguish retained historical raw bundles from final permanent receipts; a test filename alone is not passing evidence.

## Historical terminal hosted run: 4e7ca3d3

[Actions 37277922570](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37277922570) tested `4e7ca3d3bfcf9908fee7d3a6e80a3d1243b9238a`, source-tree-equivalent to local `19e240d999b41c28fe64f076759a567dd87ca2e6`. **Terminal FAILED.**

| Lane | Result |
|---|---|
| File backend | 2069 passed /  45 skipped |
| Real PostgreSQL | 2073 passed /  41 skipped; actual server **16.15** |
| Frontend unit | 548 passed |
| TypeScript / production build / token lint | PASS |
| Browser geometry + Local AI | 9 passed |
| Browser export recovery | 1 passed |
| Browser business journey | **1 passed /  1 failed** |
| Historical Windows compile/native checkpoint | 59 native contracts passed; does not prove complete package/native base acceptance |

The failed business journey accepted AI output to chapter v3 but retained a mounted history list fetched at v2, preventing selection of historical v2. bbb repaired that product cache defect; independent review then found the new StrictMode edge case corrected at d033. Historical failure logs are retained in `browser-ci-repair.md` and the run's receipts. The old run is never relabeled green.

Missing Linux ffmpeg/ffprobe caused environment-dependent media skips in earlier hosted lanes. The current workflow now installs/records these real tools; final lane receipts must establish which cases actually ran. This setup change does not itself prove they passed and does not bundle Windows codecs.

## Interim hosted run: published 55a9082d

Source `55a9082dbd3655c39a9b23bd4da19fedb3373072` has the bbb tree. [Push 37281198873](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37281198873) and [PR 37281203870](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37281203870) started as **IN_PROGRESS** and are now superseded; incomplete native work was **CANCELLED** on 93daeb97 publication. PR checkout: `a48d6915927fe9b7b135d4373c65c7b7cd09fdab`; reported base prefix `fed2404`. Branch SHA and synthetic PR merge checkout must not be conflated.

- Windows Host job **111669455963: PASS**. SDK **8.0.424** assertion, Host build and **59 native contracts** pass.
- Actual PostgreSQL job **111669455843: PASS**, **2144 passed /  37 skipped**. All ten new acceptance/dispatch cases ran without skips. Artifact **11332517596**, SHA256 `178c927c13961b457d1e14b3d7dc1403d1c634635c1dfe0a599edd26c1ecd445`.
- Browser business: reached second export after reload, then **FAILED** at a navigation helper that raced React mount. Prior restore/style/comments/conflict/first-export steps completed; b0 changes the helper wait without weakening assertions.
- Windows full-package job **111669455960: outcome not accepted**. Pinned base/font prepared; acceptance ZIP built but native smoke hung. This55a run remained incomplete/cancelled. The subsequent871 correction ran successfully in actual 93d native smoke; see the complete successful checkpoint below.
- This run precedes the independently closed d033 StrictMode repair and b0 browser-helper increment. Even passing 55a lanes cannot certify newer source.

## Final engineering-source gates: all PASS

Final branch source **`98b7d53c3193765e792e5a756fff02a87b5948b8`**, tree `f6c4a84c5ff0d1b2639b537af1ea287611935fd4`, equivalent local source `1c19d83d870f325cb6af1d182573b1e8b2a47a29`.

- [Push 37284138175](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175): **completed SUCCESS**, all five lanes; actual checkout `98b7d53c3193765e792e5a756fff02a87b5948b8`.
- [PR 37284145310](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284145310): **completed SUCCESS**, all five lanes; actual merge checkout `1c10ecc09ce07d445750a3a994931a1bc7f6f0be`.
- Exact summary: [evidence/ci-98b.json](evidence/ci-98b.json). Branch and PR merge checkout are never conflated.

| Final gate | Result |
|---|---|
| Full File backend | **2147 passed /  45 skipped** |
| Actual PostgreSQL 16.15 full backend | **2155 passed /  37 skipped** |
| Specialized real-PG acceptance/dispatch controls | **10 passed /  0 skipped**, including two spawned-process and two independently connected revocation cases |
| Frontend unit | **579 passed /  111 files** |
| Typecheck / token lint / production build | **PASS**; existing large-bundle advisory retained |
| Actual geometry/Local AI browser | **9 passed** |
| Actual full business browser | **2 passed**, including first-reload history and final writing-goal geometry at 1366×768, 1440×900, 1920×1080 |
| Actual export browser | **1 passed** |
| Windows Host | **SDK 8.0.424; build and 59 native contracts pass** |
| Complete unsigned internal Windows package | **PASS** |
| Real Windows native base | **PASS; all 11 commands exit 0** |

[Native receipt](evidence/ci-98b-native-smoke.json) proves isolated Python 3.12.9 and 27 locked wheels, binary psycopg, PostgreSQL 16.15, pgcrypto, UTF-8 Chinese data, custom-format dump/new-database restore, packaged app import and owned cluster shutdown. It preserves interactive desktop and user acceptance NOT_RUN. The System32 CRT observation is an external prerequisite, not a bundling claim.

[PG controls](evidence/ci-98b-pg-controls.json) preserve the exact final checkout and all ten non-skipped specialized cases. [Application provenance](evidence/ci-98b-application-provenance.json) and [Host provenance](evidence/ci-98b-host-provenance.json) retain latest source/staging facts. The prior93d 232-backend/three-Host comparison was after explicit Windows LF→CRLF normalization; it is not literal Git-blob byte equality and is separately historical.

### Final artifacts and retention

| Artifact | ID | Bytes | SHA256 / download |
|---|---|---|---|
| windows-host | 11334100802 | 532000 | `57a65b9f6aa3170e3c356d73bf79774a6d534303a0a074bdc02a670d9bca982c` · [download](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175/artifacts/11334100802) |
| backend-postgres | 11334096982 | 48051 | `f0b30a6c84df25e11abd4190fae63242b038f09f95d3f0a7a4a7101d2bdceee9` · [download](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175/artifacts/11334096982) |
| windows-native-receipts | 11333762608 | 541621 | `b4d4d9e46558c4d5b7d1fe070b77597b090164501421d3715e0e4e074f139832` · [download](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175/artifacts/11333762608) |
| windows-acceptance | 11333273928 | 161705892 | `e248ce586e0dc8ceec313dc947b5cb991bdd48dd9ba73743e75b42b77bfa0d28` · [download](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175/artifacts/11333273928) |
| backend-file | 11333198775 | 48335 | `fd686e5b037a8223cf1f0bbc7b2a262f3b15a6fa706c3f712b43006a21abd7b7` · [download](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175/artifacts/11333198775) |
| frontend | 11333054745 | 1529950 | `f6b246d173e0decbf59f4c3c7ed1a18a5f0bda8d1e22a7c9e30140930477a739` · [download](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175/artifacts/11333054745) |

All listed SHA256s identify outer downloaded CI artifact archives. They are not inner acceptance-ZIP digests. These CI artifacts expire **2026-10-19** at the precise timestamps retained in `ci-98b.json`; permanent safe Git receipts and screenshots remain available independently of Actions retention.

### Final screenshots and independent review

Six PNGs under [evidence/screenshots](evidence/screenshots/manifest.json) are keyed to exact final source/run/artifact and SHA256/size. Every digest and size matches. The integration lead opened and reviewed all six. Export-recovery screenshots: real File backend, synthetic text, explicit mock model; Local AI screenshots: actual browser with synthetic API/hardware/runtime fixtures, not real GPU/Windows discovery. Post-fix stacking/containment/width/overlap assertions pass at all three viewports.

Final independent [1c19 increment](INDEPENDENT_REVIEW_FINAL_INCREMENT.md): **35** scoped UI/history/StrictMode/layout and **40** native/input checks pass; type/token (42 files)/build pass; **1331** tracked files match fixed blobs. The corrected 40-case breakdown is **29 input + 11 verifier cases** (10 verifier functions plus parametrization). It did not rerun full backend or local Chromium. Its then-pending final CSS execution note is now resolved by the separately recorded later final hosted pass.

Earlier93d already passed File 2147 / 45, PG 2155 / 37, UI 575 / 110, browser9 + 2 + 1, Host 59 and actual full package/native 11. It remains a separate successful checkpoint in [evidence/ci-93d.json](evidence/ci-93d.json), not a substitute for the later579 / 111 final source.

## Subsequent documentation-only delivery gate

**Engineering-source gates above are complete and PASS.** After this evidence refresh, the lead will publish a documentation/evidence-only commit, read back its actual SHA and run that head's CI separately. Its self-referential future commit ID is intentionally not invented here; the final Draft PR body/delivery message supplies it. This pending publication receipt does not reopen or obscure final 98b runtime, geometry or native results.

## Preserved earlier checkpoints

Earlier original audit at eb165609: **9 failed / 1 passed** Python assertions plus one failing UI scope assertion, grouped into seven findings (`evidence/independent-before/`). Their unchanged rechecks are included in the later independent closed set, not removed.

Earlier worktree File **2032 passed /  35 skipped /  1 failed** was an outdated missing-policy-authority fixture expectation; focused **143 passed** did not by itself close the full gate. Later complete e38/bbb runs now supersede it as the latest full result without erasing the historical failure. The earlier prepublish PG Session fake failure is separately recorded in `evidence/integration-prepublish.txt`.

Other historical bounded receipts remain useful at their own checkpoints: acceptance integrity **35**; dispatch repair **136 / 1 skipped**; provider/hardware/discovery **263 / 1 skipped**; discovery backend **204**; Local AI UI **36**; structured planning **40**; initial/expanded inventory **18 / 47**; export backend/frontend **133 / 72**. They overlap and are not independent proof of every current feature.

The measured synthetic scale fixture is **200 chapters, 1,002,092 characters, 800 heuristic candidates, 53.848 seconds**, Python tracemalloc peak **19,250,094 bytes** (`evidence/synthetic-scale.json`). It is not a hardware/model/discovery benchmark. Font/parser/resource evidence is bounded structural/runtime testing, not target Word/Final Draft/EPUB/NLE acceptance.

## Reproduction entry points

Use a clean exact checkout and fresh synthetic runtime-data/HOME/XDG paths. `.github/ci/prepare.sh`, `postgres_gate.py`, `receipt.py` and `.github/workflows/cloud-ci.yml` specify isolated execution and receipts. Never run against existing user data.

- Backend: `python -m pytest -q -ra --junitxml=<new-evidence-dir>/backend.xml` using the explicit requested backend. Real-PG cases must have a disposable PostgreSQL database and matching client tools; the CI plugin rejects skipped required PG contracts.
- Frontend: `pnpm install --frozen-lockfile`, `pnpm test`, `pnpm exec tsc --noEmit`, `pnpm lint`, `pnpm build` in frontend.
- Browser: use the checked-in r2/export/visual Playwright configurations; geometry uses `--update-snapshots=none`.
- Windows full package/native smoke: follow `docs/R2_WINDOWS_BASE_INPUTS.md`, exact SDK **8.0.424**, fresh pinned input destination, current source/provenance and owned disposable cluster. The native verifier rejects non-Windows execution.

## NOT_RUN / BLOCKED acceptance layers

Local Chromium is **BLOCKED before assertions by socket EPERM**; no local browser pass or new screenshot golden is claimed. Historical hosted browser results above remain separate.

**NOT_RUN:** real GPU/Ollama/llama/Comfy/A1111/paid-provider inference; interactive Windows/WebView2/OS vault/Chinese IME; clean install/upgrade/uninstall retention; package signing; target document applications; user acceptance. Hosted Host compilation/native contracts and even a future package smoke cannot replace these checks. The internal payload has external WebView2 Evergreen and VC++ x64 prerequisites.
