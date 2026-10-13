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
5. Independent media execution on the original image/audio/video owners: explicit T2I/I2I/T2V/I2V/V2V/TTS/music/SFX and local audio trim, with source/job CAS, private candidates and human review.
6. Versioned multitrack clip/track/caption edits, atomic source-bound saves and history restore, plus explicit local FFmpeg review/H.264/VP9 export on the original VideoAssemblyService. [Schema 3 text archive and timeline export](text-archive-timeline-export.md) describes the actual source behavior and retained resource/acceptance gates.
7. Concrete OTIO/SRT/WebVTT transfer on the original timeline, source-pixel crop and track locks, exact private publication/review recovery, and the original caption task's guarded burn-in implementation. The original Registry AUDIO node and local Whisper dispatch/review source retain an explicit trusted-model admission requirement. [Source completion boundaries](source-completion-boundaries.md) records configuration, remaining gaps and deferred execution evidence.

All stages require source-bound backend/API/UI evidence and the original acceptance gates. Current tests, collection, typecheck, build, CI and Windows/GPU/model execution are NOT_RUN — USER_DEFERRED. M4 remains PARTIAL; M5–M9 acceptance remains LOCAL_REQUIRED in the original M4 → M9 order. Publication of engineering source does not satisfy those gates. No main/RC1 merge, tag or release is authorized.

## Isolation

Set independent `PROJECT_ROOT`, `NOVEL_DATA_PATH`, `LOCALAPPDATA`, session/profile/log paths and ports before importing the application in any V2 test or server process. Imports can initialize host identity; changing the novel data directory alone is insufficient. Read-only external tool/model resources may be reused; original RC1 services and profiles must not be modified.

## Production framework and UI handoff

The read-only [production operation contracts](production-operation-contracts.md)
describe M4–M9 through original owners and remaining reserved interfaces, with
no execution grant. The actual [production execution](production-execution.md)
uses separate explicit commands and the original trusted Host, permissions,
global cloud/source policies, owner stores and human review.
The [workspace operation seam](studio-workspace-operations.md) separates reading
and navigation from rendering. [Opus UI/UX handoff](opus-ui-ux-handoff.md) lists
the actual entry points, protected behavior and deferred verification.

Framework preparation does not advance milestone acceptance. Windows/GPU and
real model acceptance continue in the original M4 → M9 order.

Explicit schema 3 now wires [Graph media execution and atomic asset inputs](graph-media-execution.md)
through the original WorkflowRun and modality job owners. Queueing, sending,
candidate review and recovery remain separate actions. Original schemas 1/2,
TEXT routing and ordered acceptance gates are preserved. Schema-3 text archival
uses the original text archive owner, and explicit timeline_export now composes
original edits, queue admission, native export and human review. Source publication
is not release readiness. Historical source phases below deferred execution;
the current isolated media-security checks are recorded in the 2026-10-13
changelog entry. Installed application and real-model acceptance remain open.

The eight catalog/coverage/receipt files in separate repair commit `776286f`
describe the earlier `5ed1cbee` snapshot and do not inventory these new
API/source changes. Synchronize
current metadata with the original tools after verification resumes; preserve
the frozen V1 manifest, original failures and source-bound historical receipts.
QingJian work is paused.

The 2026-10-13 media-security increment now regenerates the four API artifacts
and separate V2 inventory with the original tools. Their exact source mapping,
counts and remaining Windows metadata-test prerequisite are recorded below;
the older `776286f` receipt remains historical evidence.

## Changelog

- 2026-10-13: [verified non-WAV handoff and Windows lifecycle fixes](../delivery/v2-development/nonwav-windows-integration-20261013.md); final related CPU/File checks 750 passed and real PostgreSQL checks 762 passed, each with 14 original skips. API inventory is 2219 operations; 13364 collected nodes retain the frozen 9151. Original Windows metadata checks are 45 passed / 2 symlink-permission setup failures; the two original assertions passed separately on Ubuntu. Counts overlap; CI, installed Windows, GPU and real-model acceptance remain separate gates. Existing Opus UI/UX controller boundaries are unchanged.

- 2026-10-11: actual independent media commands, private result/review flow and bounded multitrack review rendering added in source; media/timeline headless UI seams and original public JSON receipts are prepared. All execution validation remains NOT_RUN — USER_DEFERRED.

- 2026-10-11: additive M4–M9 read-only operation framework and UI/controller seams; execution verification is deferred by user instruction.

- Baseline import: exact frozen source differences, original tests retained; verified file equality on import. No new feature or new runtime validation claimed.
