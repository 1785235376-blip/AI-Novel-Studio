# R2 release readiness — bounded internal acceptance candidate

**Decision: ready to offer the verified engineering candidate for bounded internal desktop acceptance. Not a formal release and not all-feature completion.**

Final tested source **`98b7d53c3193765e792e5a756fff02a87b5948b8`**, tree `f6c4a84c5ff0d1b2639b537af1ea287611935fd4`, is source-tree-equivalent to independently reviewed local 1c19d83d. [Push 37284138175](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284138175) and [PR 37284145310](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37284145310) completed **all five lanes SUCCESS**; actual PR merge checkout `1c10ecc09ce07d445750a3a994931a1bc7f6f0be` is recorded separately.

## Gates and remaining boundaries

| Gate | Engineering result | Remaining boundary |
|---|---|---|
| G01 Safety/privacy | **PASS** in scoped independent review and final regression | Original/Discovery findings closed; no real-provider quality claim |
| G02 Data/recovery | **PASS**: real PG 2155 / 37; ten specialized controls without skips; native dump/newDB restore/owned stop | Interactive upgrades, power-loss/ACL and actual user-data acceptance NOT_RUN |
| G03 Core authoring/history | **PASS**: full business 2 including first history, Draft/Diff/Accept, restore/conflict | Ambiguous interrupted Accept remains review-required; native IME/crash and real model quality NOT_RUN |
| G04 Exports | **PASS**: export 1/business 2 plus parser/font/frozen-resource contracts | Target Word/Final Draft/EPUB/NLE typography/interoperability NOT_RUN |
| G05 Advanced features | **PARTIAL** | Semantic/hierarchical planning, advanced media, dedicated workflows and unified approvals remain itemized gaps |
| G06 Frontend | **PASS**: UI 579 / 111, type/token/build; geometry 9/business 2/export 1; final three-viewport goal layout; six reviewed screenshots | Broader design polish, native accessibility/IME/user acceptance remain separate |
| G07 Providers | **MOCK_ONLY / bounded protocol contracts** | Real model/GPU/quality NOT_RUN; missing adapters/capabilities stay blocked |
| G08 Windows | **PASS**: SDK 8.0.424/Host 59, complete unsigned package and 11 real native commands | Interactive WebView2/vault/IME, clean install/upgrade/uninstall, signing and user acceptance NOT_RUN |
| G09 Plugins | **Safe disabled executable runtime** | Declarative lifecycle works; executable sandbox/broker remains DENY_ALL/incomplete |
| G10 Source/artifacts | **PASS** for final engineering source and exact artifact evidence | Later documentation-only delivery SHA/readback/CI reported separately by lead |

No unresolved concrete defect remains in the stated independent review scope. Reviews preserve earlier failures and do not certify unseen requirements, real model output or every historical feature. All 143 original IDs,19 packages and 28 supplement sections remain in the matrix, with PARTIAL/MISSING/MOCK_ONLY/NOT_RUN where appropriate.

## Windows acceptance boundary

The complete unsigned internal acceptance ZIP and actual Windows native base passed at the final source. Isolated Python 3.12.9 / 27 wheels, binary psycopg, PostgreSQL 16.15, pgcrypto, UTF-8/custom dump into a new restored database, packaged app import and owned shutdown are verified. All 11 native commands exit0. The 40 focused source controls are 29 input +11 verifier cases.

The package includes self-contained.NET 8 and retained provenance/licenses, with external prerequisites **WebView2 Evergreen Runtime and VC++ x64 Redistributable**. Observed System32 CRT hashes do not claim CRT bundling or clean-prerequisite installation. Use the complete `windows-acceptance-*` artifact, not the compile-only Host artifact. Download hashes and 2026-10-19 retention dates are in [TEST_RESULTS.md](TEST_RESULTS.md).

**NOT_RUN:** interactive Windows/WebView2/OS vault/Chinese IME; clean install/upgrade/uninstall data retention; signing; real GPU/local/paid model inference; target desktop document interoperability; user acceptance. These remain independent acceptance gates even though hosted package/native checks passed.

## Next authorized boundary

1. Lead publishes the documentation/evidence-only commit, verifies its actual delivery SHA and follows its separate CI; final Draft PR body/delivery message records it. No final code result is unknown or awaiting repair review.
2. The user can perform the documented bounded internal desktop checks with backups/synthetic data and the prerequisites above. Tests against real user data, real credentials/paid models or additional permissions require their own authorization.
3. Any later product work should start from the matrix’s explicit missing/partial capabilities, preserving fail-closed privacy, current authority, source/version fencing and original repros.

Do not merge main, create a formal Release or deploy production automatically. Consult [FINAL_REPORT.md](FINAL_REPORT.md), [FEATURE_READINESS_MATRIX.md](FEATURE_READINESS_MATRIX.md), USER_ACCEPTANCE_GUIDE.md and LOCAL_AI_WINDOWS_ACCEPTANCE.md.
