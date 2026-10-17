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
- PostgreSQL, actual browser, 3D viewport, transformed scene bounds, frame export, GLTF/OBJ/FBX/USD, Blender/UE interoperability and graph/reference integration remain NOT_RUN or NOT_IMPLEMENTED for this slice. No M10/full-V2 completion claim.
