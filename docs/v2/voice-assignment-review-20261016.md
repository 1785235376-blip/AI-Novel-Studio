# B03 saved voice assignment review

Baseline: local `85fdf375423446d13c8badea7694657cae840aac`. Audit before implementation.

## Existing owner and exact gap

`app/experimental/audiobook.py`, `voice_direction.py`, `voice_direction_api.py` and original `VoiceDirectionPanel.tsx` already implement saved plans, source offsets/digests, character snapshot digests, Profile versions, explicit direction edits with CAS, human text/voice consent, original approval/queue, audio binding, measured timing and mix review. Original `AudiobookPanel` owns Profile creation and character mappings. No missing TTS engine was inferred. Catalog advertises runtime checking only on explicit execution and quality NOT_RUN; declarative `supports_emotion` is not measured support.

The concrete missing authoring workflow was a saved-plan consistency review leading to the exact original segment editor. Existing track preview shows kind/speaker/time only; missing selected reference IDs looked blank in HTML selects. Legacy `segment.emotion` was also silently initialized to neutral when `direction` was absent. This slice closes those gaps without changing backend or introducing another store.

## Implemented workflow

- Explicit “核对已保存声音分配” opens a read-only, twenty-segment-per-page review from the current catalog plan. It identifies unassigned/missing/ambiguous speakers and Profiles, mismatched/unrecorded Profile versions, missing human confirmations, unsupported emotion declarations and different Profile/version assignments for the same speaker. Different voices can be intentional; no automatic normalization occurs.
- Review shows saved plan ID/version, original chapter source map, original segment offsets/text digest, character snapshot digest, Profile configuration and exact audio pin/timing metadata. It does not reread historical prose, prove current character hashes or infer word/phoneme alignment.
- Exact unique segment navigation focuses the original editor article. It never overwrites inputs, auto-saves, changes assignments, approves, queues or generates audio. Composition, refresh/error and expired render/lifetime callbacks cannot use stale location. Duplicate IDs cannot be located. Existing version-conflict input retention and manual replacement/save remain authoritative.
- Missing select references remain explicit. Editor keys now include plan identity so a reused segment ID in a different plan cannot retain the previous plan's editor. Legacy saved emotions initialize the existing original editor accurately.
- UI uses existing primitives, classes and spacing; no AppShell/token/protected-surface changes.

## Boundaries

This review inspects saved records only; below it may be unsaved edits. Same-speaker differences are advisory, not an additional approval gate. Existing plan switching/outer-workspace departure can still discard unsaved local inputs; durable draft recovery and broader UNKNOWN/history UX remain open. The review does not add retries or alter original task recovery. It is not a second assignment registry, automatic voice selector, TTS provider, voice-cloning flow or runtime-quality claim.

B03 remains PARTIAL. Actual browser/visual/native IME, HTTP integration, PG/P0/security, Windows/GPU/user-machine, real provider/TTS/voice quality and full RC are NOT_RUN. Source scope covers original chapter-based audiobook plans; no invented screenplay-line linkage. P0 BLOCKED, R3-GATE HOLD and production Prompt Adoption disabled are unchanged. No push or hosted CI due to unknown cost.

## Verification

Exact commands, isolated environment, exit codes and final source/log hashes are indexed in `voice-assignment-review-20261016.json`.

- 31 selected mock UI/pure tests pass, including ten new review cases: exact focus with dirty text, explicit original save, version changes without rebasing, missing/duplicate refs, divergent voices, bounded pages, IME, failed refresh, owner/stale replacement, cross-plan reused IDs and legacy emotion persistence.
- Three original nonsecurity File tests pass: only corrected audio invalidated with source text unchanged, unknown/narration/lock/reorder semantics, and literal safe pronunciation. No provider execution test was run.
- 30 PUBLIC packaging tests, forced TypeScript/Vite build, test discovery, global/scoped token guards, diff whitespace and 487-file PUBLIC closure pass. Chunk-size warning remains.
- Initial new test expected raw `Error` text, but original error UI deliberately uses a generic message; that test-only assertion was corrected. Failed and superseded receipts are retained. No permissions, dependency or environment bypass.

Containing local commit is the deliverable. Independent parent review is required before further tracked feature work.
