# Static GLB reference import: bounded first slice

This adds real binary parsing and original-Asset persistence for a deliberately narrow 3D reference subset. It is not a complete 3D workspace, glTF conformance certificate, viewport, model generator or graph execution adapter.

## Original owners and endpoints

- POST /api/projects/{nid}/studio/assets/model-reference: original domain.write authority, project-incarnation Asset lease, storage admission, quota, idempotency and binary version owner.
- GET /api/projects/{nid}/studio/assets/{aid}/model-reference: original domain.read authority, bounded exact-pinned binary read, local geometry inspection, and fresh source/version/authority recheck before returning.
- Existing asset download, lineage declaration, soft deletion/restoration and project isolation remain original operations.
- The old image/video/audio import contract is unchanged. The new import requires contract studio-static-glb-import/1, filename ending in .glb, content_base64 and idempotency_key. Its internal kind is model; it does not advertise compatibility with existing production media ports.
- The new POST reads at most 12 MiB of request body and returns private validation codes without reflecting the uploaded content. The decoded GLB limit is 8 MiB.

## Implemented subset

GLB version 2 with one JSON chunk and one embedded BIN chunk, glTF asset.version 2.0, one embedded buffer, bounded views/accessors, uncompressed triangle primitives, float32 VEC3 POSITION, and optional unsigned scalar indices. Actual position/index bytes are decoded, not JSON-declared min/max. Strided vertex input is supported. Container lengths, component ranges, index bounds, finite positions, duplicate JSON keys and bounded geometry/JSON are checked. URI-bearing data, sparse accessors, animation/skins, morph targets and declared extensions are rejected. No external resource is opened.

Returned counts are per primitive, not instantiated scene totals. Bounds combine mesh-local position values and explicitly do not apply node transforms. Materials/textures are not rendered/decoded. Unsupported or malformed data returns no partial success. The bounded subset checks are not a full glTF validator.

The container and accessor interpretation follows the [Khronos glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html), consulted 2026-10-17. No dependency, executable, external model or paid API was added. License declaration remains explicit through the existing lineage owner; file metadata is not treated as a license grant.

## Evidence and remaining work

- static-glb-parser-r2: 19 focused tests using generated real GLB bytes, including malformed payloads and an assertion that resource opening is not performed.
- static-glb-owner-r2: 6 new original File/router cases plus 2 original workspace cases PASS. Covers exact binary reopen, no inspection persistence, import idempotency, invalid-content rejection, cross-project/deleted/recreated-owner isolation, positive fresh-owner import, revocation, private validation and request-body cap.
- Earlier parser/owner receipts are retained; their totals overlap the final cases and must not be summed as new capability counts.
- Router tests mount the real router with a constrained test authorization callback. They are not full application/desktop session acceptance.
- UI import/inspection now mounts in the original Asset workspace: explicit file save, byte/hash-bound receipt, original idempotent retry, separate source declaration and exact source inspection. static-glb-ui-r3:7 mounted/unit checks and TypeScript PASS; transport is mocked.
- PostgreSQL, actual browser, material/animation viewport, production frame export, GLTF/OBJ/FBX/USD, Blender/UE interoperability and graph/reference integration remain NOT_RUN or NOT_IMPLEMENTED for this slice. No M10/full-V2 completion claim.

## Explicit mesh-local diagnostic increment (20:49 UTC)

GET /api/projects/{nid}/studio/assets/{aid}/model-reference/mesh-preview reuses the exact-pinned read and final authority/source recheck. It returns the closed studio-static-glb-mesh-preview/1 contract with actual numeric positions and triangle indices. At most 4096 positions and 2048 triangles are accepted for this view. Larger metadata-supported files receive a private preview-limit error without invalidating the stored asset; there is no silent decimation. Known private parser codes survive as bounded 422 errors, while stale-source handling remains unchanged.

The original Asset panel explicitly requests this geometry, validates source/digest/counts/bounds/topology, and displays a local orthographic wireframe or gray diagnostic with yaw/pitch controls. Node transforms, scene instancing, materials, textures and animation are not applied. Painter-sort occlusion is approximate. Read state is retired across source/scope changes. Nothing is automatically fetched or generated.

An explicit SVG diagnostic download requires the original manual_export capability. It contains only numeric projected geometry and fixed text; it does not create a formal Image asset, PNG, video frame or production render. Original metadata v1 preview_available/frame_export_available flags remain false for full-scene/production capabilities; the narrow mesh diagnostic has its own explicit contract.

Evidence: static-glb-mesh-owner-r1 has 28 focused Python checks; static-glb-mesh-final-r1 has 7 File/router and 4 UI checks plus TypeScript; static-glb-mesh-workspace-r1 has 2 mounted original-workspace checks; static-glb-mesh-export-gate-r1 has 7 focused/mounted checks plus TypeScript. These overlap, are not additive acceptance counts, and do not replace PostgreSQL/browser/full product acceptance. No full suite or production build was repeated.

## Explicit static scene transform diagnostic (2026-10-18)

GET /api/projects/{nid}/studio/assets/{aid}/model-reference/scene-preview uses the same exact binary pin and final original-authority recheck. The new studio-static-glb-scene-preview/1 receipt is separate from unchanged mesh-local metadata. It selects a declared default scene, or the sole scene; multiple scenes without a declared default fail with an explicit selection-required code. No scene is silently chosen from an ambiguous list.

The bounded implementation checks a forest of strict node trees, valid roots and node references, mutually exclusive matrix/TRS, finite bounded values and unit quaternions (within 1e-5, normalized for evaluation). It applies column-major matrices, local T*R*S and parent-world composition. Repeated mesh instances get separately transformed positions and recomputed world bounds. Cycles, multiple parents, invalid affine transforms, unsupported node extensions, overflows and empty scenes fail without partial geometry. It is still not a complete glTF validator; cameras/materials/textures/animation are not evaluated.

These conventions follow the [Khronos node tutorial](https://github.com/KhronosGroup/glTF-Tutorials/blob/main/gltfTutorial/gltfTutorial_004_ScenesNodes.md) and [glTF 2.0 scene hierarchy specification](https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc), consulted through their indexed primary-source excerpts on2026-10-18; the registry HTML request timed out. No external runtime/dependency was added.

Expanded scene limits are4096 positions,2048 triangles and128 primitives. The prior mesh decode limits also apply before scene expansion, including unused meshes; this conservative limitation is deliberate, not silent decimation. UI offers an explicit coordinate-space selection/read, reuses the original diagnostic renderer/export gate, and discards late responses on space/source replacement. Scene SVG labels that transforms were applied while materials/animation were not. Painter-sort occlusion remains approximate; no production frame/asset is created.

Evidence:static-glb-scene-r1 has44 focused parser/owner checks; static-glb-scene-ui-r2 has2 File/router checks plus11 UI checks and TypeScript; final static-glb-scene-mount-r2 has11 UI checks and TypeScript including the actual workspace scene path. These overlap. First router fixture omitted required constructor callbacks; first scene mount fixture incorrectly paired zero-node metadata with a node instance. Both fixtures were corrected with valid setup/actual scene-bearing GLB bytes, not weakened decoders; failed receipts retained. No real browser, PostgreSQL, Blender/UE interchange or live renderer acceptance.
