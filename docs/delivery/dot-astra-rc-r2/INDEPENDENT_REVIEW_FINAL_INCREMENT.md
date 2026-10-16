# Independent incremental review: 1c19d83d

Fixed commit: `1c19d83d870f325cb6af1d182573b1e8b2a47a29`; tree `f6c4a84c5ff0d1b2639b537af1ea287611935fd4`.
Compared against previously reviewed `d03399ee7d4b183173be47e5336b9bc4e0bd30b0`. The intermediary native/browser source is published as `93daeb977d9fd238ffda7be3d9c566fd3768dc27` (tree `09d9ebb78e4a987344546535cbd02ca1acfa35dc`).

## Verdict

**No new concrete defect found in this bounded increment.** The verifier's finite file-backed capture, owned-process timeout cleanup, browser synchronization repair, and scoped writing-goal CSS are consistent with the stated contracts. The CSS's new three-viewport real-browser assertions remain pending execution on the newer exact remote head; the earlier 93d green run cannot prove the later CSS result.

## Independent local execution

- Windows native-verifier and pinned-base-input contracts: **40 passed** (`native-contracts.log` / `.xml`). These include real synthetic local subprocess timeout/output tests and mocked Windows ownership/failure paths; they are not mislabeled as local Windows execution.
- Scoped UI/history/StrictMode/layout contracts: **35 passed** (`ui-focused.log` / `.xml`), including the four new CSS source tests, five shared UI contracts, 23 history controls and the original three independent controls.
- TypeScript, token lint (42 files), and production build pass. Existing large-bundle advisory remains.
- All **1331** tracked files remain byte-identical to the fixed commit after tests (`source-verification.json`). Only isolated archives/evidence were used; no production edits, commits, GitHub mutations, real manuscripts or provider calls.
- This narrow increment did not rerun the 2000+ backend suite or locally execute Playwright. Available local Python/Node versions and reused dependencies remain as disclosed in the preceding review.

## Source review

### Native Windows verification

The new runner sends output to exclusive-created regular files, waits only for its immediate child under the original finite timeout, and reads bounded tails. This avoids waiting for inherited pipe EOF from a still-running PostgreSQL descendant. Progress records contain stage/basename/counters rather than environment values.

Timeout handling remains failure: `TIMEOUT` is retained in command evidence, propagated to the enclosing FAILED receipt, and cannot promote the smoke to success. Windows cleanup uses absolute System32 taskkill, a currently live Popen-owned PID, `/T /F`, a ten-second timeout, and a direct-handle/five-second fallback. It does not select processes by executable name. A previously exited process is not subjected to PID termination. Tree cleanup reports its actual assurance level instead of claiming independent descendant enumeration.

The existing `finally` still stops only the freshly created synthetic data directory, including when startup leaves a postmaster PID file but has not returned success. Shutdown errors also force FAILED and retain receipt evidence. Fresh-root, separate-tree, link/inventory validation and scrubbed runtime environment protections remain intact. The added always-run lightweight artifact step collects the bounded evidence without altering native assertions or timeout limits.

### Browser helper and layout

The reload helper replaces immediate `count()` with waiting for the existing accessible navigation button before clicking. Existing business checks are retained. The new first-history assertion runs immediately after reload, before later saved versions could hide a StrictMode observer failure.

The writing-goal change is limited to five lines of scoped CSS using existing spacing tokens: shrinking single-column grids, stacked labels, zero outer margins and full-width border-box inputs. App logic and protected shell/theme primitives are unchanged. Source contracts pass. New browser geometry assertions check all three field labels, positive rectangles, panel bounds, input width, vertical separation and button placement at 1366×768, 1440×900 and 1920×1080. I viewed the hash-verified pre-fix 93d 1366 screenshot and confirmed the inline label-wrap defect. No post-fix visual result is inferred from source tests.

## Independently verified hosted evidence

Through the read-only GitHub connector, observed 93d push run [37282974046](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37282974046): all five jobs completed successfully, including actual disposable PostgreSQL, business/geometry/export browser checks, Host compilation, and full-package native smoke. The 93d PR run [37282980028](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37282980028) is also completed/success. Original connector results are saved in `ci-93d-observed.json`.

I independently hashed the existing downloaded ZIPs and matched GitHub's artifact metadata, then compared every extracted file to its ZIP member. All match (`artifact-integrity.json`):

- Native 93d artifact 11333231658: SHA256 `ef1273f71c5429d5e22744c2aaec8d47507c666806ebc61a7661ca67d7428c75`; 34 files.
- Frontend 93d artifact 11333003685: SHA256 `3cb1fd7c9975b6ca58a54a8ecc30fd0ec810d853f433e27446c62be587fd8bbe`; 22 files.
- PostgreSQL 55a artifact 11332517596: SHA256 `178c927c13961b457d1e14b3d7dc1403d1c634635c1dfe0a599edd26c1ecd445`; eight files.

The 93d native receipt records **11 PASS commands, all exit 0**, including isolated embedded Python 3.12.9/binary psycopg, PostgreSQL 16.15, pgcrypto, UTF-8 custom dump/new-database restore, packaged app import and owned-cluster shutdown. Interactive desktop and user acceptance remain explicitly NOT_RUN. The VC runtime receipt identifies existing System32 DLLs; this does not prove clean machines have no prerequisites.

The package provenance points to 93d, and fresh/staged Host DLL hashes match. Independently compared all **232 backend source hashes and three Host source hashes** with fixed Git blobs: all match after the explicit Windows LF→CRLF checkout transformation; none match raw LF byte hashes. This is provenance-inventory consistency, not an assertion that I separately unpacked or executed the 161 MB full package binary ZIP. See `native-source-provenance.json`.

The 93d frontend artifact has **575 unit, nine geometry/discovery, two business and one export-recovery tests**, all passing with no skipped cases. The 55a PostgreSQL XML has all **ten** acceptance/dispatch specialized cases actually passing, no skips, including two spawned-process tests and two independently connected policy-row revocation tests (`pg-55a-specialized.json`). This closes the earlier absence of actual PG evidence for those source-equivalent paths; it is not a local PG execution claim.

## Corrected historical attribution and remaining limits

The actual 55a browser failure occurred after the later reload/navigation helper race. The independently reproduced StrictMode initial-history defect was real, but the old browser journey could hide it through later version changes. My earlier immediate message predicting it would itself block that exact old journey was too strong. The new early-history assertion and 93d actual pass now provide direct browser evidence for its repaired path.

Final later-head CSS/browser CI is still required. None of these receipts proves interactive Windows/WebView2/IME, clean install/upgrade/uninstall, code signing, paid-model quality, or user acceptance. No such promotion is made here.
