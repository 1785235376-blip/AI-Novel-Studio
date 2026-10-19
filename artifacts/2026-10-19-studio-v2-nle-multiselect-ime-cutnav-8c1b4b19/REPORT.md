# Studio V2 NLE limited incremental archive

Base `333f384a125068a4e7714b347f687f5dc2034123` → combined `8c1b4b197e57ce7ae070f0e4f7d4e36c805a360f`. Archive parent `14a7779e126565e74ca73679e8d71ecee9393281`.

This increment contains arbitrary cross-track clip multiselect, its reviewed DOM composition lifecycle repair, and local previous/next real clip-boundary navigation. It reuses the original Timeline validator, rational duration calculation, playhead, batch/history, CAS save, storage and permissions. The accepted Host333 fix remains unchanged in the base.

Three fixed changes were cherry-picked without conflicts: `cb93855f` → `935832d2`, `10f3770` → `43a204a0`, `64bbe5c2` → `8c1b4b19`. Stable patch IDs match; all 18 final changed file blobs match their original last writer, and all 12 Host333 changed files remain intact.

Evidence retained: original IME three-red→three-green probes and 275 regressions; navigation four-red→green probes, 297 regressions, and independent four-probe review. The navigation real browser recorded 36 GETs, zero writes, 44 boundary/state checks and four viewport sizes; five persistence hashes stayed unchanged. These suites were not repeated during combination or upload.

The combined version ran two focused mounted smoke cases, one original `tsc -b && vite build`, and one real original-app browser smoke (8.7 s). Its 61 completed API responses include exactly one acknowledged CAS PUT, expected version1→2; the same saved ID reopened after refresh. All matched the original server log; four additional server-only GET entries are documented. File history and both source assets match. Source stability and generated dist hashes are recorded separately.

Public contents are the incremental bundle, required source/tests in that bundle, sanitized check logs, independent review results, browser/persistence summaries, and the temporary opt-in combined test source. Raw Host/session/network traces, private session files, runtime profiles, credentials, environment dumps, browser traces and paid/model/GPU data are excluded. Exact original hashes remain for excluded local evidence.

This is limited NLE/DOM/browser evidence. Native Windows IME, macOS hardware, external NLE software, GPU/paid model execution, PostgreSQL and full Studio V2 acceptance are not claimed. No main/source branch, PR, Tag or Release changes belong to this upload.

See [RESTORE.md](RESTORE.md), [MANIFEST.json](MANIFEST.json) and [SHA256SUMS](SHA256SUMS).
