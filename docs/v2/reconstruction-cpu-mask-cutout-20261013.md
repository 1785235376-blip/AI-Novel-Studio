# Standalone CPU mask cutout reconstruction

## Scope

Adds `m5.image.cutout` to the existing standalone Studio production commands. It uses the original `ProductionExecutionService`, `ImageJobService`, private `AssetLibrary` candidate, and explicit review/promotion flow. No queue, asset store, provider, model, credential route, process, or image dependency was added. Graph retains its original closed media operation subset and existing validation errors. Its catalog does not advertise Graph cutout actions.

The command requires exactly two distinct image Asset snapshots, ordered source then authored mask. Both carry exact ID/version/digest. Provider and model are null, prompt and parameters are empty, and cloud permission is false. Mask identity is validated against the original immutable manual-mask marker, canonical bytes, source pin, provenance, scope and project incarnation. A current authorized actor can use another author's formal mask; the author's identity remains provenance. A later mask annotation is usable at its current version, without rewriting its original source pin.

## Pixel contract

The renderer reuses the existing strict bounded PNG reader and canonical manual-mask verifier. Source PNGs are 8-bit, noninterlaced grayscale, RGB, grayscale-alpha or RGBA, containing only IHDR, contiguous IDAT and IEND. Dimensions are 64–1024 and multiples of eight. Inputs are at most 8 MiB. CRC errors, ancillary chunks, animation, palettes, extra streams and decompression overflow remain rejected.

All five PNG scanline filters are reversed using the source channel stride. White mask pixels retain source RGBA exactly, including hidden RGB when source alpha is zero. Black mask pixels produce zero RGBA. Output is a deterministic filter-zero RGBA PNG with stored-DEFLATE encoding and an exact 4,195,716-byte maximum. The existing grayscale mask encoder and its byte contract are unchanged.

A persisted processing proof binds source and mask digests, dimensions, kept/removed pixel counts, output digest and exact output byte count. The original job receipt includes this proof. Recovery additionally compares its mask fields with the immutable authored-mask evidence.

## Authority, cancellation and recovery

Preview, atomic queue admission, execution, publication, review and candidate recovery recheck relevant original authority and exact inputs. CPU execution needs the Studio and asset-lineage features, but does not require the AI-execution feature. Queue admission retains the original queue → source → asset → project lock order; the source phase spans the original atomic queue write. Publication and promotion keep source → asset → project order without taking a queue mutex inside their asset callback.

Only cutout permits RUNNING image cancellation. Bounded checkpoints observe authority and exact execution state. Cancellation stays terminal and cannot be overwritten by completion or error handling. Any already-published result remains private. A cancelled job with a publication-ready proof and a lost candidate receipt can explicitly reconcile its exact original private candidate for inspection while remaining CANCELLED; it cannot be approved or replayed. Other image-provider cancellation behavior is unchanged.

The original publication-ready/UNKNOWN receipts, idempotency checks, review reservation compensation and explicit approval remain in place. Approved results are classified as `DERIVED_PROCESSING`, retaining both input snapshots.

## Verification

New additive suites cover real PNG filter/color/alpha pixels, deterministic maximum output, invalid framing/decompression, checkpoints, source/mask identity and versions, private inputs, queue races, Host revoke/rebind/ABA, feature loss, cancellation, lost publication/review receipts, proof corruption and Graph exclusion. Mounted tests exercise both original API prefixes and can emit actual response fixtures for the strict frontend decoder. Registry/vault/transport controls and generic process/image decoding are denied during the CPU flow.

- Focused File suite: 262 passed, 160 opposite-backend skips.
- Focused fresh PostgreSQL suite: 262 passed, 160 opposite-backend skips.
- Both use the pinned CI interpreter and original isolated verification harness.
- PostgreSQL began with a verified empty new database, applied all 20 unchanged migrations, and shut down cleanly.
- Unchanged original media/provider, workspace and Graph regression selection: File and fresh PostgreSQL each produced 529 passed, 182 backend skips and two existing Graph target-budget failures. An untouched detached checkout at base `3cd94a4424bdba0c03c5da1ae6c9efb91ac4c589` reproduces both failures in `test_target_selection_has_a_finite_id_budget` (GraphPreflight and GraphRunCreate). Their assertions and original node limits were not modified. This selection is not an all-green acceptance result.
- Independent read-only review reproduced the queue and lost-candidate races, then confirmed their repairs. Its separate focused File run passed 128 cases, with 59 opposite-backend skips.

These are bounded backend reconstruction checks, not a complete repository acceptance run. Browser-native decoding, frontend interaction/visual checks, Windows packaging and product acceptance are separate stages. No real model, GPU, external provider, paid API, user-machine operation, push, upload, release or inventory-generator edit was performed. Raw runtime receipts, database files, logs and mounted fixture instances are not part of the source commit.
