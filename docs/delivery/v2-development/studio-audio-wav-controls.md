# Standalone audio trim: bounded PCM WAV controls

## Scope and original owners

This reconstructs one bounded portion of AUDIO-05, AUDIO-12 and AUDIO-13 in
`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md`: explicit gain, resampling and mono/stereo
conversion on the existing standalone `m8.audio.trim` command.

The path remains `ProductionExecutionService` → `StudioAudioExecution` → the
original actor/branch-scoped `AudioProductionStore` → private `AssetLibraryService`
candidate → explicit original-owner review. No queue, provider, scheduler,
credentials, workflow state machine or model installation was added. Host session,
feature gates, scope/incarnation/source checks, request/version CAS, cancellation
and explicit interrupted-receipt recovery still belong to their existing owners.

The original Graph parameter schema and allowed controls are unchanged. Graph
nodes reject these additional fields, including explicit default values. An
internal Graph-bound trim request also rejects them before admission. This is not
an independent audio timeline, normalization, denoising, speed control, ASR/TTS
quality result, codec expansion or target-device acceptance.

## Request and recipe

The existing production preview/create APIs accept these optional trim parameters:

- `gain_db`: finite number from -60 through +12 dB
- `sample_rate`: integer from 8000 through 96000 Hz
- `channels`: integer 1 or 2

Only standalone trim accepts them. Other operations still reject them. No caller
can submit an executable, path, FFmpeg argument, filter expression or codec.
Omitting a control retains the old behavior: no gain filter, 48000 Hz, stereo,
16-bit signed little-endian PCM in WAV. Blank controls should be omitted by the
UI. Null optional fields are omitted from serialized command identity, while all
original null fields remain byte-for-byte represented as before.

Explicit controls are retained in the reviewed recipe and request hash even if
an explicit value equals the default. Changing any control invalidates the old
preview. The original default profile is still `PCM_S16LE_WAV_48000_STEREO`;
selected profiles use `PCM_S16LE_WAV_<sample rate>_<MONO|STEREO>`.

The existing interval rules remain: integer millisecond positions, maximum end
600000 ms, positive interval no longer than 120000 ms. Preview and queue admission
also reserve the predictable PCM payload plus 4096 bytes of WAV header headroom:

`ceil(duration_ms * sample_rate / 1000) * channels * 2 + 4096 <= 25 MiB`

An oversized recipe fails with `STUDIO_AUDIO_TRIM_BYTES_BUDGET_EXCEEDED`. It does
not silently shorten the interval or lower rate/channels. The actual output must
still satisfy the original Asset byte limit. Positive gain can clip/saturate when
converted to PCM16; this operation does not normalize, limit or prevent clipping.

## Actual output evidence

Execution uses the original guarded FFmpeg process runner: no stdin, single
codec thread, `file,pipe` protocol allowlist, one audio stream, no video/subtitle/
data streams, fixed `pcm_s16le` encoder, fixed WAV muxer, output size bound and
50-second timeout. The only new filter is a server-constructed numeric
`volume=<validated gain>dB`; resampling/channel flags are server-formatted
validated integers. No shell command is evaluated.

The completed WAV is decoded with the existing native PCM inspector. The actual
sample rate, channel count and sample width must match the reviewed settings;
actual duration must be within 2 ms of the reviewed interval. Before private
Asset publication, the existing audio receipt persists and hashes these nine
`media_measurement` fields:

- `duration_ms`, `byte_count`, `sample_rate`, `channels`, `sample_width`
- `container: wav`, `audio_codec: pcm_s16le`
- `profile_validation: PCM_DECODED`, `output_sha256`

The values come from decoded output bytes and their SHA-256, not requested values
reported as measurements. The original durable receipt binds them to the reviewed
request and source. Reopened reads verify their shape, profile, publication-ready
byte count/digest and receipt hash. When a candidate exists its digest must equal
`output_sha256`. Old persisted receipts may have no measurement and remain valid.
A receipt using explicit new controls cannot drop its measurement after output
reservation or publication; reads and review fail closed. An interrupted
publication can have a valid measurement but no candidate yet;
explicit reconciliation may recover only the matching private original Asset,
without reencoding or replay. Graph-bound output projections remain unchanged.

## Compatibility and verification

Additive tests are in `tests/test_v2_audio_wav_controls.py` and
`tests/test_v2_audio_wav_controls_api.py`. Existing assertions were not changed.
They cover strict request bounds, old identities, Graph exclusion/schema,
capacity admission, actual gain/resampling/channel bytes, preview changes,
original private publication/review/reopen, stale sources/CAS, cancellation,
receipt tampering, bad native outputs, explicit lost-publication recovery, both
mounted API prefixes, feature gates and late trusted-Host revocation/ABA.

The successful PCM test starts with a synthetic authored waveform. The actual
installed FFmpeg 7.1.5 CPU process converts it, and actual decoded samples prove
2000 → 1000 amplitude for -6.020599913279624 dB, with 700 ms of mono 22050 Hz
PCM16. Boundary cases verify -60 dB at 8000 Hz and +12 dB at 96000 Hz, including
authored stereo ±10000 saturating at +32767/-32768 with the frame count and
700 ms duration unchanged. Mono/stereo conversion uses FFmpeg's standard channel
rematrix coefficients; it does not promise amplitude-preserving duplication. The waveform and fault-injection fixtures are synthetic; media encoding,
PCM decoding, File/real PostgreSQL project owners, Asset bytes and review are not
mocked. No remote service, paid model, GPU or model-quality claim is involved.

Legacy golden identities were captured before changes from base
`005893ef873f15bf1745e6afef454fc50a8f8c84` and asserted exactly:

- Command: `12113d9776ca251b2ffc03a22345193e58b140da7c8dc0a2a4085fc7f9dacf27`
- Request: `2f90a075e3dd51ee00549d77fe46e952ad71992ba989dc477168b3fedda86a6f`
- Preview: `f7ece5c37a5a892e09e83df4fb6874301bd218361a6270ac1f4f63e8da267aef`
- Recipe: `bd7b3525f584ffcb10c5376c4822d02958233bd127ce5bae2ce7e2640dec8a3c`
- Audio owner request: `71f21f6bcc0a54198648a3978989decc59f0126071ac1b2067fdaee2f5e13c61`

The real CPU acceptance here covers PCM WAV inputs and outputs. Other input
containers still depend on the older generic FFmpeg/ffprobe inspector and its
existing limitations; no MP3/FLAC/non-WAV processing or cross-device playback
acceptance is implied. Default gates and frozen V1/Interop contracts are unchanged.

### Final scoped checks (2026-10-13)

Both final source-bound runs passed **159 tests**, with **44 opposite-backend
cases deselected** per run. These include the two new audio modules, existing
original audio listing, native process bounds, original audio API and provider
regressions. The File run used `scripts/run_v2_checks.py`. The PostgreSQL run used
`scripts/run_v2_postgres_checks.py --fresh-database`, confirmed a new empty
PostgreSQL 17.11 database, applied all 20 original migrations, and stopped the
owned server afterward. The original audio store remains its existing file
owner in both profiles; the project/scope owners are actual PostgreSQL in that
profile. Neither run changed its source snapshot.

The sanitized summary and exact selected source/log hashes are in
[`studio-audio-wav-controls-validation.json`](studio-audio-wav-controls-validation.json).
Raw logs, process environments, database paths, Host sessions and private queue
contents are intentionally not committed. A wider run including the baseline
Graph contracts found two existing target-budget failures (362 passed, 2 failed);
those are a separate reconstruction slice, not weakened or changed here.
