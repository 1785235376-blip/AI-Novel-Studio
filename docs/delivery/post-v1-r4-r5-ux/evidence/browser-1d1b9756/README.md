# Actual browser evidence at 1d1b9756

Source and artifact checksums are in [manifest.json](manifest.json). These are unmodified synthetic-test outputs from hosted Linux Chromium. The run passed 34/35 R4 journeys but did not pass its frontend lane. They are not screenshots of the later corrected chrome.

- [U10 before chrome fix, 1366×768](u10-before-chrome-fix-1366.png): retained failure evidence. Prose is clipped because the resume banner took the flexible editor row. **Not visual acceptance.**
- [U08 exact local variants and original diff](u08-variant-diff.png): real functional journey, with the same subsequently corrected editor-chrome issue. PRIVATE_TAIL_CANARY is a synthetic fixture; original local diff may display it while the inspected model request excludes it.
- [B09 original three-way review](b09-merge-review-1366.png): actual original versioned comparison and manual choice.
- [B10 manual sync review](b10-sync-review-1366.png): actual selected exchange/conflict UI; no cloud identity or transport claim.
- [B06 actual rendered PNG segment](b06-rendered-test-segment-001.png): readable CJK, synthetic input, actual exported raster. This is an output artifact, not a screenshot or a model-art quality claim. [OFL license](OFL.txt).

Six raw U13 input/search JSON receipts retain 3 warmups and 30 samples at 100k/500k/1m Han. Input p95 = 22.2/35.3/41.0 ms; warm browser-to-File-API search p95 = 52.3/160.9/299.2 ms. They are source-specific rendering/network proxies, not physical latency or native Windows IME acceptance. The [real PostgreSQL receipt](postgres-receipt.json) has its own job and artifact identity.
