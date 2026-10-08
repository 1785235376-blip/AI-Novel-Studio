# V2 Narrative Production Development

Development branch: `feature/v2-narrative-platform`. This is development work, not a product release or version metadata change.

V2 extends the frozen V1.X Core with a Creative Expansion Layer. Novel editing, Memory, Context, version/CAS, original screenplay APIs and existing experimental director behavior remain available. New screenplay, director, storyboard and video-planning workflows use separate explicit modes, typed documents, scoped authorization, source references, review and optimistic concurrency.

## Baseline provenance

The branch begins at `edb3e8577c32c2bb8e0ca3825f223aa75149f9a8` and imports the 18 file differences required to reproduce the original 1576-input frozen working-source map. The map and import list are in [v1x-source-baseline.json](../delivery/v2-development/v1x-source-baseline.json). SHA256 map fingerprint: `8235de1659d7069fad2285e590017117bbc969338c943262be8b2ee21313979b`.

RC1 build `hardening-package-20261008T012141Z-47c9f581`, ZIP SHA256 `724ae7c6940e8526f5eb031076c89e12e39d383ce78348260a752e0b67ab4b9c`, remains in the original `D:\小说\AI-Novel-Studio-Latest-Product` checkout. That checkout, its frozen branch, package, reports and uncommitted historical acceptance evidence are preserved. They are not silently replaced by the clean base commit. No model weights, user data, credentials, RC1 ZIP or large historical runtime evidence are copied into Git as V2 code.

## Implementation sequence

1. Typed creative data, scoped storage and document API.
2. Screenplay Studio and Screenplay Agent/Skill; novel adaptation, scene/action/dialogue editing, review and screenplay export.
3. Director Agent and typed Director Notes; camera, emotion, pacing and performance suggestions.
4. Storyboard data and editing; numbered shots, framing, composition, camera movement, visual description and sound cues.
5. Video Production planning interface reserved, with truthful unavailable-generation status.

All stages require backend/API/UI evidence as applicable, regression tests and separate commits pushed to this branch. No main/RC1 merge, tag or release is authorized.

## Isolation

Set independent `PROJECT_ROOT`, `NOVEL_DATA_PATH`, `LOCALAPPDATA`, session/profile/log paths and ports before importing the application in any V2 test or server process. Imports can initialize host identity; changing the novel data directory alone is insufficient. Read-only external tool/model resources may be reused; original RC1 services and profiles must not be modified.

## Changelog

- Baseline import: exact frozen source differences, original tests retained; verified file equality on import. No new feature or new runtime validation claimed.
