# Creative Director execution lifecycle collection inventory

Source checkpoint: `e5ebd59644b394048460da5c40b399a6dc3cc06d`.
Predecessor checkpoint: `3087f53276e42c57bf4baed2a76fbf75380d947e`.

This is collection inventory only. No test bodies are executed here; it does not establish PostgreSQL, browser, provider, desktop, or release acceptance.

The byte-exact predecessor manifest has 2,611 source entries and 16,312 collection rows. Five existing runtime sources change and three sources are added: two test modules and their fixture helper. The new source map has 2,614 entries and collection has 16,495 rows. All 183 added rows are file-only: 163 execution-lifecycle rows and 20 invocation rows. These are collection classifications, not passing-test claims. Every predecessor full row dictionary, order, classification and all 1,296 protected predecessor sources remain exact. All 11 frontend script/E2E companions are separately bound.

`packaging/public-build.json` remains unchanged at SHA256 `3261cc7549d58e5d8e84c69572a9475d9c416bfd487588ecfbec472e8695d37c`. It is outside the generator source map and separately guarded. The legacy request fixture remains frozen at SHA256 `640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac`; frozen V1, original generator, runner and existing immutable gates remain unchanged.

Each phase retains a fresh sanitized normal-startup origin proof and an actual original-runner child origin proof, raw launcher output and exit code, complete source brackets, complete raw collection, generator report and validation. Current source bytes are checked against actual committed Git blobs. The archived predecessor raw rows are retained in the predecessor evidence packet.

Three gates apply: no-write review and independent approval; an owned candidate generated using the unchanged original generator with `--write --output .runtime/creative-lifecycle-inventory/candidate-manifest-v2.json.gz` and independent exact-candidate approval; then explicit parent byte-promotion release followed by a third no-write confirmation and independent final review. Review and confirmation omit `--write`; none of these invocation scripts writes the canonical manifest.

Offline, read-only verifier commands from repository root:

    node docs/delivery/v2-development/creative-lifecycle-inventory-20261017/check.mjs review
    node docs/delivery/v2-development/creative-lifecycle-inventory-20261017/check.mjs candidate .runtime/creative-lifecycle-inventory/candidate-manifest-v2.json.gz
    node docs/delivery/v2-development/creative-lifecycle-inventory-20261017/check.mjs final

The verifier requires retained source/evidence bytes, but no Python interpreter, Git metadata, test execution, provider, network, or browser. The evidence index excludes itself and is produced only after independent final review. Original-runner origin receipt/log pairs also live directly under `docs/delivery/v2-development/creative-lifecycle-inventory-{phase}-origin.*`; exact copies are included in this packet. The independent source/Git binding is copied here from the sibling `creative-lifecycle-review-source-git-binding.json`.
