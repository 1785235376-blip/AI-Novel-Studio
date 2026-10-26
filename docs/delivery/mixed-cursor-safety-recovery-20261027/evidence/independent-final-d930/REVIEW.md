# Reconstructed final independent acceptance

PASS: newly executed 99 tests, pytest exit 0, on d93034821efa4f064ac680b8bfdedef86faa3b0d / tree b9c22586cad50ac7bfd76c9ab4fd727bac770544 / app 775a084c75dd5cfd7ccf0189060b056bf8f1c309. All 601 app files stayed unchanged; all 478 loaded app modules belong to the independent checkout.

This supersedes the intermediate14650cef acceptance for source/tests consistency, without overwriting it. It does not restore or reuse lost bf0bbdb2 records. The group comprises 26 reconstructed request/observer/pipeline cases, 53 donor-independent mixed-source/reader-receipt cases and 20 real process boundary cases. Counts overlap parent groups and must not be added.

The added POSIX test spy repair was independently checked: e5 original file freshly reproduces 12 failures and 8 passes, every failed child reporting lock() unexpected initialize keyword. d930 changes only the test callback signature and forwards initialize unchanged into the original lock function. No failure is hidden and no production lock code changes. Both initialize=True and initialize=False retain their original meaning. Production app remains byte-identical to14650cef.

The new e5 context baseline likewise records 22 failures and4 passes for the26 reconstruction tests. Final99 passes on the exact same three new test files. The production request isolation clears inherited budget and strict markers only at independent ASGI boundaries, restores callers on exception/cancel, and preserves nested same-request reuse and true request-owned background work. The observer correction keeps genuine GET-owned background effects visible. Eight real h11 socket pipeline cases verify transport-context behavior, with a scope-reporting endpoint, not an asserted business-owner end-to-end chain. Parent handles full application TCP acceptance separately.

Static protected-source review: Store/identity/scope/Export owner/canvas adoption blobs are unchanged from e5. The donor's five-file mixed implementation and the authorized three-file request isolation make up the production delta. No budget values, lock algorithm, source authorization or rollback/CAS policy are relaxed.

Linux/File synthetic scope only. No Windows, PG, browser, real model/GPU or CI acceptance; no historical F37/root-cause or Windows cursor repair claim, no cross-owner atomic snapshot/full ABA/hard resource bound claim. No upload or main modification.
