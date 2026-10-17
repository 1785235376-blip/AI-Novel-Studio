# Saved Timeline Selected-Clip PCM16 Preview

## Scope and acceptance boundary

This slice adds an explicit, ephemeral source-envelope observation for one selected,
saved, clean audio clip in the independent Studio Timeline editor. It reuses the
original production, timeline, asset and project owners. Existing subtitle PCM16
waveforms predate this slice; this is a new bounded Timeline entry point, not a new
decoder owner or a claim that the product previously had no waveform support.

The preview is not playback, rendered audio, mixed loudness, speech alignment,
gain/fade/mute processing, a proxy or a persistent peak cache. It never changes
source pins, measured-duration save authority, trim, selection, history or the
timeline schema. Unsupported formats have no native fallback.

Windows native behavior, browser geometry, packaged-runtime execution, PostgreSQL,
provider/model quality, real rendering and full release acceptance remain NOT_RUN.
The optional bounded file reader requires safe no-follow and nonblocking open
primitives; platforms without them return `STUDIO_WAVEFORM_PLATFORM_UNSUPPORTED`.
In particular, this work does not establish Windows support for this entry point.

## Request and response

The original production router exposes:

`POST /api/projects/{nid}/studio/production/timelines/{tid}/waveform-preview`

The strict request carries `expected_version`, `reviewed_timeline_digest`, one
`clip_id`, and the exact audio `source_snapshot` (`id`, `kind: ASSET`,
`asset_kind: audio`, `version`, `digest`). The selected saved clip must match all
pins; no newer asset version is substituted. Extra/coerced fields are rejected.
Only this new route has a 4096-byte streamed request cap and fixed validation
errors. Successful and error responses are private/no-store.

The closed `studio-timeline-waveform-preview/1` result identifies the project,
branch, exact timeline version/digest, clip and source; it includes `byte_count`,
`frame_count`, `sample_rate`, `channels`, and exact observational
`duration_seconds: {num: frame_count, den: sample_rate}`. That fraction is
deliberately unreduced. `scope` is `CLIP_SOURCE_ENVELOPE` and `status` is
`MEASURED_PCM16_PEAKS`.

The source interval is half-open:

- `start_frame = ceil(in_ms * sample_rate / 1000)`
- `end_frame = ceil(out_ms * sample_rate / 1000)`
- Both are validated against the actual source frame count, and the interval
  must contain at least one frame.
- `samples_per_bucket = ceil((end_frame - start_frame) / 512)`.
- Bucket `i` is `[start_frame + i * samples_per_bucket,
  min(end_frame, start_frame + (i + 1) * samples_per_bucket))`.
- Each peak is the maximum absolute PCM16 scalar sample across the included
  channel(s), divided by 32768. Peaks are finite, in `[0, 1]`, with at most 512
  entries. Samples outside the saved trim cannot contaminate boundary buckets.

The response also includes saved `clip` placement, trim and rational speed. The
frontend maps source frame `f` to timeline milliseconds using
`start_ms + (1000*f/sample_rate - in_ms) * speed_den/speed_num`, retaining rational
coordinates until drawing and clipping the final display to the saved clip edge.
No rounded duration becomes permission to save a longer trim.

## Authority, leases and bounded reads

The route uses the original `domain.read` production invoker, current project
authority, feature gating, Host binding and repeated authority checks. The UI
retains the editor's stricter readiness/current-source gate and requires an
explicit click; it does not scan assets on render or selection changes.

Mounted positive evidence uses the original local-author/local-scope resolution.
A replacement valid Host before a new request or a branch header in that local
mode does not redefine the original local author/scope. In-flight Host changes
and ABA are separately rejected. Scoped collaboration evidence covers Host
denial only; it does not claim a successful collaboration/branch waveform path.

The service uses the existing read-only `timeline_inputs.phase`:

1. Original raw scope transaction.
2. Original asset library lock/workspace lease.
3. Original project lifecycle lease and incarnation.
4. Exact saved timeline/selected-source resolution and bounded measurement.
5. Final source content verification, read-only canonical checks and raw
   transaction completion under the original leases.

No scope, job or alternative owner transaction is opened beneath an asset lease.
PostgreSQL's inherited raw transaction includes its existing
`INSERT ... ON CONFLICT DO NOTHING` before locking the scope row. This is not a
promise of zero SQL write statements; no new or changed product records are
admitted by the preview, and PostgreSQL execution was not performed.

An opt-in, per-store ContextVar on `CreativeProjectStore.existing_owner_only()`
prevents missing File incarnation markers from being provisioned by a stale
preview. It covers the complete mounted invoker, including pre-callback guards,
and direct service calls. Defaults, parser and lock ordering remain unchanged.
The service checks actual incarnation again after releasing the original phase,
when its original leased-owner cache no longer masks an injected retirement.

The optional original asset-reader branch admits metadata and actual file size
before reading, rejects nonregular files/reparse points, opens the final component
with no-follow/nonblocking flags, checks inode/stat identity, reads/hashes in
guarded chunks of at most 64 KiB, and verifies final identity, size and SHA-256.
The original owner's root/ancestor directories remain trusted; this does not claim
protection against hostile replacement of every ancestor. The default content
reader remains unchanged. No adapter reads filesystem paths independently.

Preview limits are simultaneous, not alternatives:

- Verified file size at most 8 MiB.
- RIFF/WAVE PCM16, uncompressed, one or two channels.
- Positive rate at most 192000 Hz and positive source frame count.
- Exact source duration at most 600 seconds.
- At most 4194304 scalar samples.
- Full declared PCM data must exist even if only an early interval is selected.

Full-source validation reads at most 32768 scalar samples per PCM chunk, checking
authority around chunks while aggregating only the selected interval. Declared
RIFF-size mismatches, truncated frames and residual partial-frame bytes fail.
The shared pure helper preserves the old subtitle path's original all-at-once
algorithm and malformed-input behavior; preview bounds do not silently restrict
the older endpoint.

## UI lifecycle

The original editor/controller supplies the exact saved row and selection.
Networking remains outside the NLE presentation component. One request can be in
flight; the result is only ephemeral state. Scope, client, authority, source,
revision or selection changes invalidate it, including change-and-undo ABA.
Late results, retained callbacks, unmounts and permission loss cannot restore an
obsolete result. Unsupported media/platforms show an explanation and do not
fall back to a native decoder. The displayed envelope explicitly excludes gain,
mute and fade processing.

## Evidence and corrections

Primary backend receipts:

- `delivery/v2-development/waveform-backend-additive-r3.json`: 151 passed across
  five new pure/helper, bounded-reader, owner-context, File and mounted API suites.
- `delivery/v2-development/waveform-backend-protected-r3.json`: 66 passed,
  1 deselected across unchanged asset, subtitle and Timeline handoff regressions.
- `delivery/v2-development/waveform-origin-backend-r3.json`: natural startup and
  actual unchanged-runner child PathFinder evidence, without product imports.
- `delivery/v2-development/waveform-origin-backend/receipt-verification-r3.json`:
  identical 2578-source before/after maps and verified log hashes.

Primary frontend receipts `waveform-frontend-{new,regression,type,token,build}-r1`
record 66 new tests, 254 protected regression tests, TypeScript, the 52-file token
guard, and a production frontend build passing. The build retains its bundle-size
warning. These are jsdom/static/build checks, not browser geometry acceptance.

`delivery/v2-development/waveform-packaging-r1.json` records 87 existing offline
PUBLIC packaging tests passing. The two actual wheels and two actual source
distributions were built without application imports, network access, installation
or native media execution. The already-installed build interpreter's binary hash and
tool origins are recorded separately from the sole clean test interpreter.
The manifest input stayed unchanged during packaging. Archive inspection verifies
all receipt-listed payload bytes against current source, including both new
runtime files and all ten changed runtime modules. Source distributions retain
their existing `FUTURE_FORMAT_VERIFICATION` qualification.

Actual archive hashes, build logs, stage/artifact receipts and full payload
inventories are retained in
`delivery/v2-development/waveform-packaging/packaging-evidence/index.json`.
The first supplemental inspector stopped before writing evidence because pytest's
two `*current` aliases made four real build receipts appear as six paths. Its
script and failed log remain retained. The separate r2 inspector resolves owned
receipt paths, asserts exactly two real wheel and two real sdist builds, and
verifies every payload; no test or product behavior was changed for this repair.

The initial failures remain retained. r1 found an original empty wrong-scope lock
artifact; the new test now identifies exactly that one empty housekeeping file
and compares all remaining bytes, without broadly excluding lock or product
files. r2 found real missing-incarnation provisioning on rejected recreated IDs.
That was fixed in the original owner with the opt-in no-provision context; the
recreate no-write test was not weakened or preinitialized to conceal the write.

The packaging manifest change is exactly two sorted runtime entries:
`app/creative/timeline_waveform.py` and `app/services/pcm16_envelope.py`.
The original verification runner does not include this manifest in its normal
source map, so its before/after and actual packaging-input hashes are separately
retained under `delivery/v2-development/waveform-packaging/`.

Independent review and rerun evidence is retained in
`delivery/v2-development/waveform-independent/verified-evidence.json`:

- 217 backend tests passed; 1 PostgreSQL case excluded.
- 320 UI tests passed in 16 files.
- Fresh natural and actual runner-child origins, identical 2578-source maps,
  and actual current source hashes checked independently.
- Four real archives inspected independently; all 476 runtime source entries
  per archive and all ten touched modules match their exact current bytes.

These independent counts overlap primary coverage and must not be summed as
unique acceptance. The complete bounded packet and dependency hashes are in
`delivery/v2-development/waveform-evidence-index.json`. Approval is scoped to
Linux File, jsdom/static/build and offline PUBLIC artifact evidence; it does not
close the NOT_RUN acceptance gates listed above.
