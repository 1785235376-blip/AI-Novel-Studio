# U10 isolated first-use sample

## Implemented

- The existing entry experience hosts a skippable/reopenable task guide when `workspace_tools_v2` is enabled. It explains manual writing, long-book import, screenplay/storyboard preparation, audiobook availability, and local-model setup without enabling flags or dispatching models.
- Explicit “创建独立练习（不需要 Key）” creates one new, bounded, original synthetic project and one chapter. Local/no-session authors use the original novel/chapter APIs. Scoped authors use current workspace administration, original project/path creation, and the original membership-aware audited chapter writer. No roles or permissions are granted.
- The sample never uses the currently open project as a target. IDs originate only from an original create receipt or a server-allocated local reservation, not a request body or a title search.
- Explicit opening re-reads the receipt and current target authorization. The editor guide uses existing writing/save/export flows. Its saved-version label requires actual original chapter/version evidence. It does not claim reopening or downloading happened merely because navigation was requested.
- The guide is content within the existing shell and uses DS-v1.0 primitives/tokens. It never reloads, saves, or replaces a dirty editor buffer.

## Recovery and bounds

One small receipt is stored per local-author or trusted actor/workspace in the existing File/PostgreSQL metadata store. It records sample identity and staged original write receipts; it is not a manuscript store or a second permission authority.

An intent is durably committed before each original create. Repeated/concurrent start requests return the same receipt. A known project ID is retained before navigation, and a known chapter ID before chapter hydration. Partial confirmed stages resume only through the explicit recovery action, with current flags and permissions rechecked.

The original scoped create interfaces do not supply operation-idempotency receipts. Therefore an interrupted project/chapter create is not blindly retried or adopted by matching a title. The UI explains the uncertainty, retains known project IDs, and permits opening confirmed partial projects for manual recovery. A browser-response loss after the handler completed resolves through the read endpoint. A backend crash before its original create receipt was journaled remains explicitly uncertain.

Interrupted sample saves reconcile only the exact original chapter version and synthetic document. Any intervening author edit stops seeding. Deleted samples are not silently recreated. No automatic rollback deletes a partial project.

The sample stays one-per-owner/workspace; a later separate practice book can be created through the existing manual new-project flow. Skipping/closing is a UI action and does not cancel an already-dispatched request.

## Verification

- `tests/test_r4_first_use_mounted.py`: real mounted `/api` and `/api/v1`; local and scoped originals; create/save/reopen/TXT export; original-source preservation; concurrency; create/save uncertainty; partial receipts; flag and permission revocation; actor separation; default-off/V1 gates; no recreation after deletion.
- `frontend/src/novel/FirstUsePanel.test.tsx`: actual React states, five scenarios, skip/reopen, single-flight create, explicit open, uncertainty, partial continuation, stale navigation, dirty-buffer/export gating.
- `frontend/src/novel/firstUseClient.test.ts`: captured session/workspace, no credentials in URLs, no uncertain-create retry, safe errors.
- Local focused mounted run: **28 passed, 28 PostgreSQL cases skipped**. Including original workspace and packaged-entry regressions: **48 passed, 40 skipped**. Frontend panel/client/EntryExperience: **20 passed**. TypeScript, production Vite build, and token guard passed (existing bundle-size warning only).
- `frontend/tests/e2e/r4-first-use.spec.ts` is authored for hosted Chromium: real UI and original API, no-model sample, write/save/page reopen, actual TXT download, skip/reopen, and 1366/1440/1920-width shell geometry/screenshots. No response mocking or baseline regeneration.
- Local Chromium was not launched because its previously established EPERM restriction remains in effect. PostgreSQL contracts are authored for the existing real hosted PostgreSQL profile; local PostgreSQL cases are skipped, not passed. Hosted results must be read separately before marking those gates passed.

## Composition

The lead owns router registration, exact collaboration-middleware admission, mounted fixture store rebinding, and App integration. `EntryExperience.onOpenLocalSample` uses the existing `setNovel`. `SampleJourneyGuide` belongs inside the existing inspector content, avoiding extra children in the fixed workspace row layout; its navigation callback uses the existing workspace navigation authority.
