# Creative Director binding foundation collection inventory

Source checkpoint: `c7b01d0c503ac944cf078b55b845f76df7d428fa`.

This evidence is collection inventory only. It does not execute test bodies or establish PostgreSQL, browser, provider, desktop, or release acceptance.

The predecessor canonical manifest is archived byte-for-byte. Its 2,606 source entries and 16,139 complete collection-row dictionaries are preserved except for the three explicitly reviewed runtime-source changes. Five source files are added: the inert binding module, its frozen legacy-request fixture, and three test files. The resulting source map has 2,611 entries. The new collection contains 16,312 rows: 173 additional rows (62 file-only, 57 PostgreSQL-only, and 54 both). Collection classifications are not execution results. All 1,292 predecessor sources selected by the current protection predicate are unchanged. The existing 11 frontend script/E2E companion files are independently bound.

`packaging/public-build.json` is outside the generator source snapshot. It is explicitly included in the guard map and independently verified as the exact single-module addition `app/creative/director_binding.py`; it is not silently omitted. The legacy fixture is frozen at SHA256 `640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac`.

The original `scripts/extend_v2_coverage_manifest.py` remains unchanged. Review and confirmation invocations omit `--write`. Candidate generation writes only `.runtime/creative-binding-inventory/candidate-manifest-v2.json.gz`. Canonical promotion requires independent exact-candidate approval and the parent's explicit release; it copies already-reviewed bytes rather than regenerating the canonical file.

Each invocation records sanitized interpreter settings, a fresh successful import-origin probe, complete before/after source hashes, raw collection bytes, launcher output/exit code, original-generator report, and validation. Source checkpoint verification checks actual committed Git blobs. The frozen V1 manifest, immutable gates, prior full rows/order/classifications, companion files, and separate PUBLIC packaging guard are checked before and after collection.

Run the offline, read-only portable verifier from the repository root:

    node docs/delivery/v2-development/creative-binding-inventory-20261017/check.mjs review
    node docs/delivery/v2-development/creative-binding-inventory-20261017/check.mjs candidate .runtime/creative-binding-inventory/candidate-manifest-v2.json.gz
    node docs/delivery/v2-development/creative-binding-inventory-20261017/check.mjs final

The final verifier needs retained repository source/evidence files, including the linked predecessor raw inventory, but requires no Python interpreter, Git metadata, provider/network access, browser, or test execution. The evidence index excludes itself and is created after independent final review.
