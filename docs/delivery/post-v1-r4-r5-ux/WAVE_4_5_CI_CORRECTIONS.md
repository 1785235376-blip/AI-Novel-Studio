# Wave 4/5 hosted CI corrections

Observed source: `e12db8d0cf1651afe99dfbfb01a248f198954c7c`, tree `e88df94be1499a4aea5440d5c7ec85aaf22ec0ec`. Both push `37356388925` and PR `37356395289` passed File and the two Windows lanes, and failed PostgreSQL/frontend. The PR browser result was 22 passed / 3 failed. The broker cancellation journey passed with the published production race repair.

This correction changes test fixtures/contracts only; it does not relax production acceptance or authorization.

- Portable restore: real shared disposable PostgreSQL had unrelated synthetic fixture projects. Replace singleton-database assertions with exact preflight inventory equality, exactly one new restore ID, and unchanged source/neighbor project metadata, chapter snapshots and history. An extra owned sentinel exercises nonempty databases on File too. Cleanup touches only IDs created by this fixture.
- Portable browser: the localhost host token belongs in explicit request headers, not collaboration session storage. The repaired journey asserts empty collaboration session/scope state.
- Declarative Workflow: the original File editor GET normalizes the initial Markdown into its rich-document representation. Capture that authoritative baseline before executing the reviewed Workflow; compare exact unchanged content instead of the raw creation echo.
- Multilingual edition: original chapter creation includes a title heading, producing four segments. The old fixture mistranslated the shifted paragraph, correctly triggering `TERM_REQUIRED`. A real mounted regression preserves that rejection. The success journey now saves exactly three structured paragraphs through original versioned save, verifies the exact source mapping, records preview responses, and asserts original content/document/version/history remain unchanged through review/export.
- Reader legacy contracts: Markdown lazy-materialization tests are explicitly File-only rather than parameterizing impossible PostgreSQL filesystem cases and skipping them at runtime. All 18 applicable PostgreSQL reader parameters remain collected. The no-skipped-marked-PG gate is unchanged.

Isolated correction checks: 78 File reader/portable/mounted cases passed, 65 PostgreSQL parameters excluded locally; 20 multilingual mounted File cases passed, 20 PostgreSQL parameters excluded. Feature workers also ran focused panel checks and type/spec collection checks. Actual corrected PostgreSQL/browser execution remains pending hosted CI. Local Chromium was not retried. Independent follow-up review remains BLOCKED.
