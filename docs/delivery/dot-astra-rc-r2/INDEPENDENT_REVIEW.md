# Independent review of fixed R2 candidate e38d1ecc

Reviewed commit: `e38d1eccff6c1aac02a836817c878f423df0479e`
Git tree: `197a04c858434b58ad1ab38fbd478030bcbca7b8`
Original inherited baseline: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`
Date: 2026-10-05 UTC

## Verdict

**All previously reproduced audit defects are fixed in this snapshot within the reviewed scope.** Original failing tests were retained and independently rerun. No additional concrete unresolved defect was found in the final focused review.

This is a scoped source/contract review, **not** formal release approval or proof of Windows, real-provider, PostgreSQL or user acceptance. Final exact-revision hosted CI and its native/PostgreSQL receipts must still succeed; no local result substitutes for those gates. Keep the delivery Draft and unmerged.

## Independent execution

- Original core privacy/cancellation/acceptance invariants, Discovery adversarial controls, the five final remaining invariants, and request-serialization/ASGI author-job integration: **55 passed**. `adversarial.log`, `adversarial.xml`.
- Complete frontend unit suite: **549 passed across 108 files**, including the original WorkflowPanel stale-project repro. `frontend-full.log`, `frontend-full.xml`.
- TypeScript, design-token lint (**42 files**) and production Vite build: passed. The existing large-chunk warning is retained. `typecheck.log`, `token-lint.log`, `frontend-build.log`.
- New Windows input/extraction/prerequisite contracts, remaining Discovery tests and backend fixture-isolation checks: **59 passed, 10 skipped**. The skipped cases are the explicit real-PostgreSQL acceptance/dispatch tests, not passed substitutes. `packaging-pg-structure.log`, `packaging-pg-structure.xml`.
- Complete File backend suite: **2,131 passed, 46 skipped**, one deprecation warning; 123.39 seconds. `full-file.log`, `full-file.xml`.
- Source integrity: **all 1,310 tracked files** in the archive remain byte-identical to the fixed commit. `source-verification.json`.

Execution environment: Linux, Python **3.12.14**, Node **24.19.0**, pytest 8.4.2; exact installed Python packages are in `environment.json`. These available tool versions differ from the pinned hosted build environment (Python 3.12.9 / Node 22.14.0), another reason the hosted gates remain mandatory.

Counts overlap and must not be added as unique coverage. Tests were run in independent git-archive checkouts with synthetic manuscripts/media, controlled transport doubles, scrubbed environments and no real credentials. Installed frontend dependencies were copied into the isolated archive; no fresh dependency-lock installation was claimed. No main-tree source edits, commits, pushes, merges, releases, production deployment or real-model calls were performed by the auditor.

## Repair closure

The following original reproduced groups now pass:

1. Raw adaptation manuscript is constrained by version/hash-bound source privacy and project restrictions.
2. Agent context policy/authority is revalidated through the actual dispatch boundaries.
3. Audio/image pre-dispatch cancellation and audio source revocation block the request; late-result fencing remains intact.
4. Local Draft Accept cannot rebase old model output onto newer saved text.
5. Concurrent/restarted acceptance uses a durable claim and does not duplicate chapter/proposal effects; uncertain operations fail closed for review.
6. Explicit project/outline restrictions cannot be overridden by chapter approval.
7. Workflow responses from an old project/scope cannot update the new view.
8. Ollama tags/show `remote_host`/`remote_model` cannot obtain local-source routing; both new Discovery and legacy Ollama leaf paths require positive current local-model evidence.
9. Discovered text routes work through the real author normalized node using explicitly buffered output, without pretending live token streaming.
10. Identity/capability changes on rescan/dispatch invalidate approvals for Ollama, A1111, ComfyUI and GGUF.
11. Late Enable cannot overwrite newer Disable/remove/configuration, and last authority callbacks cannot send after disable.
12. External llama dispatch uses the validated alias, and Comfy capability checks bind the selected model to its actual workflow loader.
13. Both new and legacy validation/diagnostics are passive; no executable `--version` probe occurs on those paths.
14. Incomplete buffered Ollama responses are rejected, while missing/malformed token counts retain unknown usage.

Earlier red evidence and REQUEST_CHANGES reports remain under the sibling eb165609, 547167e8 and 19e240d9 evidence directories. Those were correct findings against their own frozen commits, not claims about the repaired commit.

## PostgreSQL coverage review

The File-only fixture changes are explicit rather than ambient backend fallback. The memory fixture directly writes JSON to a temporary File tree; acceptance process fixtures pass File directories/fixed IDs. The new PostgreSQL-specific coverage now includes:

- actual PostgresChapterRepository/PostgresGenerationRepository assertions;
- separate connection pools observing the committed ACCEPTING claim and persisted output;
- **two spawned OS processes**, with different-PID/backend/environment assertions, racing the same PG job and producing one accepted result and one blocked result;
- a fresh spawned PG process proving interrupted ACCEPTING cannot replay;
- independent PG connections committing character policy changes at route preparation and normalized provider resolution, with captured prompts remaining empty;
- the preserved real-PG privacy migration, fresh-process reopen and pg_dump/new-database restore/inventory tests.

There is no File fallback in these explicit PG tests. The CI plugin still fails a PostgreSQL lane if marked PG contracts skip. This auditor has inspected their structure but has **not run a PostgreSQL server**. A green final PG lane is still required; the File process tests and source inspection cannot be relabeled PG execution evidence.

## Windows packaging/input review

Reviewed the new input lock, materializer, native verifier, Host prerequisite handling and pipeline/build scripts. The materializer uses reviewed HTTPS hosts, exact length/SHA256 checks, wheel dependency/license metadata checks, fresh destinations, no-link/reparse safeguards, Windows path/case/reserved-name validation and bounded archive expansion. It retains original license notices and requires independently established redistribution eligibility for optional CRT copying.

The native verifier requires Windows, checks the pinned base inventory, isolates environment/profile/data, uses a new synthetic loopback PG cluster, performs Python import/ABI and pgcrypto/UTF-8/custom-dump restoration checks, and stops only its owned cluster. Its success cannot prove interactive WebView2, IME, install/uninstall, signed installer or user acceptance. The hosted job and package provenance remain the source of actual native evidence.

No Windows binary was executed by this auditor, and no vendor inputs were downloaded again. Input materialization on Linux is not counted as native validation. The documented WebView2 Evergreen and VC++ x64 external prerequisites remain genuine limitations of the internal payload.

## Remaining acceptance boundaries

NOT_RUN here: real PostgreSQL/CI; Windows Host/WebView2/AppContainer/OS vault and clean install/upgrade/uninstall; interactive browser and Chinese IME; real local GPU/Ollama/ComfyUI/A1111 generation; paid/cloud providers; target Word/Fountain/EPUB desktop application compatibility; user acceptance. Optional pinned-font runtime verification was not independently prepared here.

The feature matrix covers D00-D18 and the original 143 feature IDs while disclosing PARTIAL/MOCK_ONLY/NOT_RUN. No claim is made that every historical feature, semantic planning quality, advanced video workflow, plugin sandbox or visual design requirement is complete. This review does not waive the original release gates or authorize merge, formal Release, deployment or real API spending.
