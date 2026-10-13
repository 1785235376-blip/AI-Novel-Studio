# Standalone WAV controls: frontend reconstruction

## Bounded existing surface

The existing media production panel, controller and strict production client now expose optional controls for standalone `m8.audio.trim`:

- `gain_db`: finite numeric value from -60 to 12 dB.
- `sample_rate`: integer from 8000 to 96000 Hz.
- `channels`: 1 or 2.

Blank controls are omitted. The previous command serialization is preserved, with unchanged 48000 Hz stereo output and no gain filter when these controls are absent. Explicit zero gain remains an explicit input. The form rejects combined duration/rate/channel settings exceeding the backend's bounded WAV byte budget instead of silently changing inputs. Positive gain may clip; no normalization, speed or codec controls were added.

The source/version, preview consent, queue-only creation, explicit execution, CAS actions, shared workspace exclusion, identity-ABA fences, uncertain-request recovery, private candidate byte checks and explicit review flow remain in the original owners. Interrupted trim receipts expose the existing reconcile action for RUNNING, UNKNOWN and REVIEWING; reconcile is never a replay or automatic review.

## Measured output contract

The frontend accepts only the original trim recipe and a strict nine-field `PCM_DECODED` WAV receipt. It checks the measured sample rate and channels against the confirmed recipe, duration within 2 ms of the requested interval, PCM sample width 2, WAV/pcm_s16le, output byte bounds, and candidate digest when present. Reserved output with no candidate remains readable for explicit recovery. A measured queued row is rejected, and finalized measured success/review/approval rows must include their audio candidate.

Legacy receipts with no measurement remain readable and display no inferred output measurements. Successful receipts containing explicit new controls require measured proof. The panel displays actual output measurements only from validated receipts and does not portray requested gain as measured gain. Candidate loading additionally checks the measured byte count and WAV media type before allowing private preview/review.

Graph input admission, generated-audio controls, timeline measurement validation, provider catalogs, shell geometry and design tokens are unchanged.

## Evidence

Final verification on 2026-10-13: **321 tests passed across 12 targeted files**, including 86 additive contract cases and 28 additive mounted cases. TypeScript, Vite build, the 52-file UI token guard and whitespace checks passed. Vite reported the existing large-chunk warning.

All frontend checks use the already-installed original dependency tree. No dependency manifest, lockfile or original assertion was changed.

- Additive strict contract cases cover boundaries, malformed controls, exact omitted request bodies, known legacy null preview defaults, legacy receipts, measured-proof binding and omission, reserved-output recovery, response substitutions, and the closed Graph boundary.
- Additive mounted original-workspace cases cover blank/default and explicit controls, combined output budget, consent invalidation, source revisions, lost-create recovery, separate queue/execution/review, original cancellation CAS, global exclusion, private candidate checks, interrupted reconciliation and identity-ABA redaction/stale responses.
- `fixtures/audioWav.mounted.json` contains sanitized public responses from the backend worker's real mounted API test using synthetic owned PCM and guarded local FFmpeg. It includes preview, queued, measured execution and approved projections. Frontend tests decode them unchanged. This fixture is not user media or a browser/Windows acceptance record.
- Existing cutout, identity/read-fence, Graph transport/client, baseline type, UI token and geometry checks are included in the targeted verification set.
- The frontend build runs the installed `tsc -b` and `vite build` binaries directly. The system pnpm dispatcher reports 11.25.0 rather than the manifest's 10.6.5; no package-manager or dependency changes were made to work around that mismatch.

Browser screenshots, Playwright visual runs, Windows, live model services and paid APIs were not run. Product acceptance remains `LOCAL_REQUIRED`.

## Reproduction commands

Run from the repository root with its original frontend dependencies available:

```sh
frontend/node_modules/.bin/vitest run --root frontend \
  src/creative/studioAudioWavContract.test.ts \
  src/creative/IndependentStudioAudioWav.test.tsx \
  src/creative/studioCpuCutoutContract.test.ts \
  src/creative/IndependentStudioCpuCutout.test.tsx \
  src/creative/IndependentStudioIdentity.regression.test.tsx \
  src/creative/IndependentStudioReadFences.test.tsx \
  src/creative/studioGraphClient.test.ts \
  src/creative/studioGraphTransportForwarding.test.ts \
  src/creative/studioBaselineTypeSafety.test.tsx \
  tests/uiContracts.test.ts tests/localInteropLayout.test.ts \
  src/creative/graphCanvasGeometry.test.ts --reporter=dot
(cd frontend && node_modules/.bin/tsc -b --pretty false && node_modules/.bin/vite build)
node scripts/check_ui_design_tokens.mjs
git diff --check
```
