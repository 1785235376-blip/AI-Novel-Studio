# Isolated sampled video reference verification

Implementation commit: 8c3226d6. An isolated detached worktree excluded the unfinished Model Center transfer lane from verification and package inputs.

Final isolated results: File 187 passed (111 PostgreSQL deselected), UI 71 passed across five suites, TypeScript and Vite production build passed, token guard passed. PUBLIC wheel/catalog: 6 passed. All three final receipts show unchanged sources during their runs. Earlier real PostgreSQL owner/API parity passed 45 on identical backend sources and stopped/cleaned up the reused database.

The first isolated UI run passed all 71 tests but TypeScript failed on optional test request narrowing and Uint8Array<ArrayBufferLike> Blob typing. That failure is retained. A precise Uint8Array<ArrayBuffer> return type matches the existing allocation; test request guards were made explicit. No runtime byte validation, backend or URL lifecycle was changed. The final UI/type/build run passed after those two changes.

The real PUBLIC wheel was built before those frontend-only type/test fixes; its backend content is unchanged. Catalog: 2401 operations, fingerprint 82b5ec4f5f29bc8fbccd638ef74668dffa23939b691026c3cec81646a1a8abb1.

This slice supports low-resolution sampled reference frames, not full-resolution extraction, semantic keyframes, motion/pose/depth conditions or V2V interval cropping. The original I2V execution requires separate preview/approval and is never launched by frame save. Actual browser/Windows/model-quality acceptance remains open. Retained synthetic MP4/PNG/timing evidence is in video-reference-cpu-evidence-20261018; root inspected the sampled PNG.
