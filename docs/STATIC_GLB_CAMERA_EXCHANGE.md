# Static source-camera inspection and canonical exchange

This additive slice reads cameras authored in the exact formal GLB Model Asset.
It is separate from Director/Storyboard authored camera grammar and from the
existing normalized orthographic clay/depth diagnostic view.

## Original owner and journey

Within the existing Independent Studio Assets view, select a saved GLB, explicitly
read its cameras, select one instance, and explicitly download its camera-only
glTF. No camera is selected automatically. The existing GLB import owner,
geometry/material/scene inspection and clay/depth contracts remain unchanged.

- `GET /api/projects/{nid}/studio/assets/{aid}/model-reference/cameras`
- `POST /api/projects/{nid}/studio/assets/{aid}/model-reference/camera-export`

Both routes use the original `domain.read` authority and original Asset scope.
Reads are bounded and exact version/SHA256 pinned. Original project incarnation,
branch, feature and visibility rules apply. Authority and source are rechecked
after processing and serialization. Computed results are discarded after a
source change, permission revocation, deletion or project recreation. There is
no new Asset, Job, persisted camera store or execution owner.
Camera observation also never provisions a missing File project identity.

The export request is a closed 4 KiB maximum source selection: contract,
source_version, source_sha256, scene_index, node_index, camera_index and the fixed
`GLTF_2_CAMERA_ONLY` profile. Caller-supplied matrices/projections are not admitted.
Duplicate JSON keys, malformed input and validation failures receive fixed
private errors. Camera responses/errors carry no-store and nosniff headers.

The source reader still requires the existing safe bounded no-follow/nonblocking
filesystem path. Unsupported hosts fail closed with the original bounded-read
error; this feature does not add a Windows fallback or establish Windows support.

## Supported source subset

The existing GLB limits remain: 8 MiB total, 1 MiB JSON, embedded JSON+BIN chunks,
bounded uncompressed triangle geometry, no external URIs, animation, skins or
extensions. Camera reads do not expand mesh geometry and do not impose the
smaller diagnostic mesh-preview vertex/triangle limits.

Camera-specific bounds: 64 definitions and 64 reachable instances, 256 nodes,
64 scenes, labels of at most 240 characters without control/DEL characters,
finite bounded numeric values. Perspective yfov is strictly between 0 and pi;
aspect and near are positive, and an authored far must exceed near. Orthographic
magnifications are positive, near may be zero, and far exceeds near. The subset
is intentionally narrower than full glTF conformance.

Only the declared default scene or a sole scene is selected. An ambiguous scene
list fails explicitly. Each node.camera is an instance; two nodes referencing
the same definition remain two distinct choices. Unreachable definitions do
not acquire invented positions. No authored cameras produces an empty state.

Every ancestor and selected camera local transform must be rigid, with proper
rotation. Nonunit TRS scale is rejected even if a descendant cancels it. Affine
matrix columns must be orthonormal and have determinant +1 within 1e-5; the
bottom row must be exactly [0,0,0,1]. Shear, reflection, singularity and nonrigid
world transforms are rejected. No scale removal or decomposition is guessed.

## Canonical coordinates and absence semantics

The existing scene helper composes column-major local T*R*S and parent*local.
glTF specifies right-handed Y-up coordinates, meters and radians. Camera-local
+X is right, +Y is up and the viewing direction is -Z. The camera view ignores
scale, which is why this first slice accepts rigid ancestry only. Perspective
yfov is vertical. Missing aspect remains viewport-dependent; missing far remains
infinite. These properties are preserved, not replaced by diagnostic-view or
target-application defaults. See the [Khronos glTF 2.0 camera specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#cameras).

The receipt uses explicit nulls for absent optional perspective properties.
The exported glTF omits them, matching their original meaning. No sensor,
focal length, lens shift, focus distance, look-at point or viewport is invented.

## Export and provenance

The deterministic UTF-8 `.gltf` is at most 64 KiB and contains only an asset
declaration, one scene, one camera node with its rigid world matrix, one camera
definition and whitelisted Studio source provenance. There are no buffers,
meshes, materials, images, external resources or copied source extras.

`extras.studio_camera_source` carries its versioned contract, exact source Asset
ID/version/SHA256, original scene index/selection and node/camera indices. The
outer receipt carries byte count/SHA256, the same selected camera data and
explicit false model/animation/Asset-creation flags. The frontend validates
source, selection, receipt, canonical decoded document and actual bytes before
download. Source/identity/scope changes and loss of permission discard pending
work. This camera-only `.gltf` is not accepted by the existing geometry-required
GLB import endpoint; that admission was not broadened.

## DCC and acceptance boundaries

This is a canonical data exchange, not a native Blender or UE integration.
No DCC process is launched or project modified. Native UE import/Sequencer,
animation/timebase exchange and rendering are not implemented by this slice.
Both target import acceptance fields are `NOT_RUN`.

Blender's [official glTF camera importer source](https://raw.githubusercontent.com/KhronosGroup/glTF-Blender-IO/main/addons/io_scene_gltf2/blender/imp/camera.py)
contains target-specific aspect, orthographic-scale and infinite-far behavior;
identical target framing is not claimed. Epic's [camera-component export documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-the-gltf-exporter-handles-unreal-engine-content#cameracomponent)
documents export properties, not acceptance of this artifact by a native UE
importer. No target-specific approximation is applied to canonical data.

Real synthetic GLB tests cover extraction, rigid transform composition,
instancing, omission preservation, deterministic export, bounds and rejection.
Original source-owner and frontend lifecycle tests provide separate bounded
evidence. These do not substitute for browser, Windows, Blender/UE import or
whole-V2 acceptance. Run receipts identify their exact tested source snapshots.
