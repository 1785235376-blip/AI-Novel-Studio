# Current standard-feature PUBLIC distribution closure

The current-source PUBLIC check initially failed because six newly implemented standard modules were absent from the explicit distribution allowlist: Bailian text preset, static GLB parser, scene transforms, material metadata, depth/clay diagnostic renderer, and independent screenplay model data contract. This was a real packaging omission; runtime source and frontend build results did not prove PUBLIC distribution closure.

The fix adds exactly those six reviewed paths. The private namespace exclusion, dependency checks, closed source inventory, runtime archive guards and original tests are unchanged. These modules reuse original text transport and passive geometry/screenplay data; no private extension namespace, new credential, purchase or model call is admitted.

## Evidence

- continued-features-public-wheel-r1: FAIL, 2 failed / 28 passed / 26 setup errors, all rooted in the missing source allowlist entries. Receipt and raw log retained.
- continued-features-public-wheel-r2: 57 PASS (one additive current-module check plus 56 unchanged public-profile/real-wheel checks). A genuine offline pure-Python wheel was built and inspected for exact stage closure, RECORD integrity, dependency metadata, excluded private namespace, unsafe paths, extra code/native payloads and altered archives.
- The existing packaging interpreter was selected explicitly because the clean test Python has no setuptools. The original artifact builder forbids importing the application, network activity and nested processes. No packages were installed.

Manifest SHA-256: 7e907370b421d84201043e3447003ca722c49be8ce655f6caf1d2e101c7e9553
Wheel: ai_novel_studio-0.7.0-py3-none-any.whl
Wheel bytes: 1901988
Wheel SHA-256: 385ccfd6bc65df3243a0d160142f01c0836a289f1b17beb16e51e9e66e293a58

This is a test PUBLIC Python distribution, not a V2 release, Windows installer, live application startup or end-to-end acceptance. No main merge, tag or Release was created. The fixed package has not been represented as installed or user-ready.

The test temporarily filled available disk through disposable altered-wheel fixtures. Completed, owned earlier fixture trees were recoverably compressed after every archive member hash/size was verified, preserving their archives and inventories; actual free space recovered to 112 MiB. Four local bundle duplicates were removed only after exact equality with already-fetched, remote-verified GitHub archive blobs; their restoration commit/path/hash inventory is retained. No source, unique evidence, database or raw report was deleted.
