# Selected Timeline duplicate collection inventory

Source checkpoint: `881231d07bd300893bbc494e7913a4029c558d23`.
Predecessor checkpoint: `feade20ce2f6671e5d5a16c0781896f3c5696927`.

Collection inventory only, not passing coverage or product/release acceptance. No test bodies, PostgreSQL services, native/browser checks, providers, installation or network operations are run by this packet. Bounded implementation evidence remains separately described in `docs/TIMELINE_SELECTED_DUPLICATE_HANDOFF.md`, unchanged.

The byte-exact predecessor V2 manifest contains 2,640 sources and 16,892 rows, SHA-256 `835210459b56ac40948631ba6ac228bb98732ab2d723d49cb3266222917126a4`. The committed source delta adds the selected-duplicate helper, three UI test modules and one File test module, and changes exactly three original frontend runtime files. The derived inventory contains 2,645 sources and 16,924 Python collection rows. All 32 new rows originate in `tests/test_v2_timeline_duplicate_handoff.py` and are classified File-only. Frontend test source bytes are included; UI cases are not Python collection rows.

All 16,892 predecessor full row dictionaries, order and classifications remain exact. All 1,318 protected predecessor source entries and 11 omitted frontend script/E2E companions are unchanged. Full source maps bind to committed Git blobs and stable before/after SHA-256 maps. All 8,348 existing tracked documentation files, including prior ledgers, implementation handoff and evidence, match committed bytes and remain preserved.

PUBLIC packaging is outside the generator source map and is separately unchanged, SHA-256 `57f657057a391fa9ebdd8586fba62262ea6f3bb5fb1e2fe71f0c5ff27ad573be`. Its predecessor bytes are archived separately. The original Graph/SCREENPLAY fixture remains SHA-256 `640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac`; frozen audio omission fixture remains `1aa9100e0d3622b6d5a99019b5a7f33aa60e94173a9c962dce0a500c3a63c2d5`. Frozen V1, original V2 generator, original runner and immutable gates are unchanged.

Each stage uses fresh natural interpreter startup with outer PYTHONPATH unset and a sanitized environment, plus actual unchanged-runner child provenance. The owned stdlib-only probe checks the sole approved clean interpreter, dependency allowlist and exact current product origins without importing product or pytest. Exact raw logs, exit status, reports, raw collection, Git bindings and source brackets are retained. The original generator's isolated collection profile and basetemp are unchanged.

Three gates: initial original no-write collection and independent review; original generator write to owned `.runtime/timeline-duplicate-inventory/candidate-manifest-v2.json.gz` only, independent exact-candidate review and explicit parent byte-promotion approval; separate third original no-write confirmation after promotion. The collector never writes canonical bytes.

Offline read-only verification from repository root (no Python imports, test execution, Git metadata or network):

    node docs/delivery/v2-development/timeline-duplicate-inventory-20261017/check.mjs review
    node docs/delivery/v2-development/timeline-duplicate-inventory-20261017/check.mjs candidate .runtime/timeline-duplicate-inventory/candidate-manifest-v2.json.gz
    node docs/delivery/v2-development/timeline-duplicate-inventory-20261017/check.mjs final

The predecessor raw collection remains in the waveform inventory packet. Exact original-runner receipts/logs are copied into this packet under unique paths. Final evidence indexing binds every packet file and explicit external evidence dependency.

## Canonical promotion

Independent gate 2 approved exact candidate SHA-256 `f85eff91861041c2867f6a184286b0ab484f6d8765bcb96ca08639181daa09c4`. Explicit parent authorization permitted byte-exact promotion after rechecking the predecessor digest. The candidate bytes were copied without recompression and verified equal to canonical. The approval text and promotion receipt are retained in this packet.

The independent read-only Git audit initially exceeded Node's default output buffer. It succeeded with a 40 MiB buffer; `independent-git-buffer-note.json` retains the explanation. No collection or test failed, and no source edits resulted.

The separate third original no-write confirmation completed successfully. All three raw collections are byte-identical, SHA-256 `b8b55ea25ed271890add0b077cdce56fefe08f546edf9604f5c752fdc230d4a2`. Fresh natural-startup and actual runner-child provenance, complete Git/source closures and canonical/source preservation passed in all stages. Independent final review and evidence indexing close collection inventory only.
