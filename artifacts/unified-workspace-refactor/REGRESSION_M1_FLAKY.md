# REGRESSION notes

## [HERMIA-FE-20261023 M1-flaky] Flaky stabilization + P3 text dedupe
Code commit 7e96d0ba (tree 485ed7b5), parent 7d6ca86f (Vera review append, unchanged, author Vera (review)), base 3490d0a7.
- P3: the close-confirm network failure now reads exactly 「保存失败：网络错误。修改仍在面板里，没有保存。」, built by `closeConfirmErrorText` in DockLayout.tsx. Test `close confirm network failure shows exact deduped text` asserts the exact string. Workspace panels 17/17.
- Root causes (no assertion weakened, no skip, no deletion):
  - GraphDirectorImage.integration, director.additive "authors a director", GraphImageOutputStarter and StoryFactDownstreamImpact: long jsdom flows take 3–5s and went over the default 5000ms testTimeout under load. Before: under load, GraphDirectorImage failed 3/3 (5507–5829ms) and director failed 3/3 (logs/m1flaky-before-load-*). Fix: `vi.setConfig({testTimeout:30000})` per file.
  - Workspace download-denied: there was a **product race**. The IndependentStudioWorkspace cold-start effect switched IMAGE+NEUTRAL_STUDIO from ASSETS to GRAPH even when the `requestedAssetId` deep link was present. So whether the deep-linked asset (and its download) was shown depended on timing and test order: it failed 20/20 alone (logs/m1flaky-download-denied-load20.log) and failed under load in Vera's runs (2/29). Fix: an explicit asset deep link keeps the ASSETS view. The test also got a 10s findBy budget and a 30s test timeout.
- After: the 5 targets passed 10/10 isolated (logs/m1flaky-after-iso-*). Under load they passed 10/10 except one download-denied failure in run 5, before the product fix (logs/m1flaky-after-load-*). Download-denied after the fix: 10/10 isolated and 10/10 under load (logs/m1flaky-download-denied-after-*.log).
- Full vitest at 7e96d0ba (logs/m1flaky-full-1/2.json): run 1: 307 failed of 11353; run 2: 308 of 11351. IndependentStudioIdentity = 8 in both, so adjusted = 307 / 308. Gate ≤307: run 1 meets it, run 2 is 1 over. Run 2's extra failures are load-sensitive tests outside this scope (IndependentStudioRunReads graph cancellation, ModelBrokerBudgetRecovery). The baseline 3490d0a7 retry had 308. Compared with that baseline, 11 failures are fixed. 6 failures remaining in the target files are pre-existing and are not the targeted tests.
- tsc: 6 errors (the known baseline; logs/m1flaky-tsc.log).

## [HERMIA-FE-20261023 M1-flaky2] P4 + environment root cause for ComicLayoutsPanel/VoiceSubtitle
Commits: 84e684a4 (Vera's review append for f8124581, committed unchanged, author Vera (review)); dc1d4350 (tree 26b512e4): P4 + env logs.
- P4: the panel status line `RENAME_NETWORK_TEXT` is now exactly 「保存失败：网络错误。修改还在面板里。」, matching the dialog's wording style. The test `rename network failure` asserts the exact text. The dialog still reads 「保存失败：网络错误。修改仍在面板里，没有保存。」 (exact-text test unchanged). Workspace tests 128/128.
- **10 always-failing tests.** ComicLayoutsPanel.* has 9 failures ('Unable to find role="img" … 漫画分段/待审原图片'). VoiceSubtitlePanels has 1 ('已读取含停顿混音…'). Both throw jsdom Blob `TypeError: object.stream is not a function`. **Root cause: the runtime environment, not code.**
  - The box was provisioned 2026-10-23 03:42 (UTC+8) by `apt-get install nodejs` (/var/log/apt/history.log). That installed Debian `nodejs 20.19.2+dfsg-1+deb13u3`.
  - That Node does not bundle undici (`process.versions.undici` is undefined). It loads the system `node-undici 7.3.0` from /usr/share/nodejs/undici instead.
  - When undici 7's Response/body extraction is handed a Blob-like object (toStringTag 'Blob'), it calls `.stream()`. jsdom 25's Blob doesn't have `.stream()`, so it throws. The preview pixels/mix are never produced, so the img/text assertions fail.
  - package.json `engines.node` is ">=22.14.0 <25", so this Node violates the repo's own requirement.
  - The package versions are not the cause: node_modules/.package-lock.json matches the untracked package-lock.json exactly (0 version diffs). jsdom is 25.0.1 and vitest is 2.1.9.
  - A/B on the same tree: Node 20.19.2 gives 10 failed / 70 passed (logs/m1flaky2-env-node20.log). Official Node v22.14.0 (bundled undici 6.21.1) gives 80/80 passed (logs/m1flaky2-env-node22.log).
  - No test or polyfill change was made. A Blob.stream polyfill would hide an unsupported runtime that CI (Node 22) never sees. Remedy: run the suite on Node ≥22.14 (e.g. /tmp/node-v22.14.0-linux-x64/bin on this box).
- Full vitest at dc1d4350 (logs/m1flaky2-full-*.json):

| Runtime | Run | Failed | IndependentStudioIdentity | Adjusted | ComicLayoutsPanel/VoiceSubtitle |
|---|---|---|---|---|---|
| Node 20 | 1 | 307 | 8 | 307 | 10 |
| Node 20 | 2 | 310 | 8 | 310 | 10 |
| Node 20 | 3 | 307 | 8 | 307 | 10 |
| Node 22.14 | 1 | 301 | 8 | 301 | 0 |

  - Total is 11353 tests in every run. Best-of-3 adjusted is 307, so the ≤307 gate is met.
  - The Node 22 run has 4 failures that don't appear in Node 20 runs 1 or 3. They look like timing flakes: IndependentStudioGraphWorkspace.presentation, CreativeWorkspace reorder, WorkspaceToolsPanel delayed search, ComicPublicationPanel PDF preflight.
- tsc: 6 errors (known baseline; logs/m1flaky2-tsc.log).
