# A12 · Bounded native OTIO exchange

## Deduplication and scope

EXTEND: existing screenplay shots/transitions provide ordered editorial source data; existing AssetLibrary/A09 supplies current media identities and lineage checks. Existing `VideoAssemblyService` remains the renderer/ordered-cut job authority. This package stores only actor-private exchange snapshots and import receipts in the existing isolated `ExperimentalStore`. It is not another editable timeline, media library, renderer, or target NLE project system.

Mounted routes use `/novels/{nid}/experimental/timeline-exchange` through `/api` and `/api/v1`, with `timeline_exchange_v2` plus `asset_lineage_v2`, native actor/project/branch permissions, and post-work current-authority checks. Default OFF and V1 acceptance force OFF cannot be bypassed with a client parameter.

## Working actions

- Import a selected UTF-8 `.otio` file (2 MiB maximum), normalize its supported subset, show an explicit loss/warning report, and persist a new exchange copy.
- Select existing screenplay shots in original order, bind current visual assets or explicitly retain missing media, choose a rational frame rate, and create a source/version-bound exchange snapshot.
- Inspect exact rational start/duration summaries, missing/external media references, and information loss. After explicit review, download a newly named actual `.otio` attachment.
- Imported files/externally referenced projects are never modified. No input path is written, no media is fetched, no URL is opened, no assets are packaged, and no generation/rendering occurs.

## Supported subset

| Data | Scope |
| --- | --- |
| Root | One native OTIO Timeline with enabled, untrimmed root Stack |
| Tracks | Up to 16 enabled, untrimmed top-level Video/Audio Tracks |
| Items | Up to 2,000 Clips, Gaps and representable SMPTE_Dissolve transitions |
| Media | Active ExternalReference or MissingReference; original external URL preserved as inert text |
| Time | Rational frame values and rates, half-open source ranges, global start time, available ranges |
| Cut summaries | Exact Fraction addition; transitions do not double-count clip timeline duration |
| Bounds | At most 24 hours per track, finite rates/times, 32 JSON nesting levels, bounded document complexity |

The internal representation uses numerator/denominator pairs and `Fraction`, with no floating-point accumulation. Floats are used only at the official OTIO Python API boundary. Namespace metadata preserves exact frame/rate fractions for generated items and is verified against the native numeric time on reimport. No drop-frame timecode formatter or general conform operation is claimed.

SMPTE dissolve offsets are preserved and checked against neighboring clip durations. Actual source-media handles and target application playback are not verified. A generated shot-duration snapshot can contain fractional frames at fractional frame rates; it is editorial duration information, not a promise of frame-aligned decoded media.

## Loss/rejection policy

- Effects and speed/time effects are reported separately; retimed-result duration is explicitly unverified.
- Mixing/subtitle/application metadata, markers, alternate media references, and unknown track kinds receive explicit reports and are omitted from the normalized copy.
- Resolvable nested compositions become same-duration Gaps with an explicit loss; unresolved duration, trimmed/disabled root or top-level track, impossible dissolve placement, invalid times, or unsupported root are rejected.
- Unsupported transitions become cuts with a report; disabled items become gaps with a report.
- Missing media stays missing. Library-backed generated references are relative `media/<content-digest>.<extension>` names, with a warning that bytes are not packaged; no personal filesystem path is exported.
- External URL credentials, query strings, fragments, control characters, and non-file/http/https schemes are rejected. Otherwise external references remain inert, including missing local references. Parsing does not prove media availability or usage rights.
- No FCPXML, old Final Cut XML, CMX EDL, AAF, or native Resolve/Premiere project support is claimed. These are future individually bounded formats, not extension renames.

## Official parser/dependency evidence

Official documentation/release checked 2026-10-05:

- [ASWF OTIO native format](https://opentimelineio.readthedocs.io/en/latest/tutorials/otio-file-format-specification.html)
- [OpenTimelineIO 0.18.1 on PyPI](https://pypi.org/project/OpenTimelineIO/0.18.1/)
- [Official source](https://github.com/AcademySoftwareFoundation/OpenTimelineIO)

The project has an optional `otio = ["opentimelineio==0.18.1"]` extra. Application startup does not import OTIO or install it. Missing/wrong-version parser is a supported unavailable state. An environment maintainer may explicitly install this extra; no user Python/CUDA/model/runtime configuration is changed automatically.

Implementation invokes only allowlisted `otio.core.deserialize_json_from_string` and `otio.core.serialize_json_to_string`. It never selects adapters from user input, calls adapter/plugin discovery, or dispatches OTIO hooks. Malicious metadata and `OTIO_PLUGIN_MANIFEST_PATH` remain inert in the tested path. The serialized output is re-parsed with the official parser and compared for media relationships and exact normalized timing semantics before it is returned.

The free isolated test dependency came from standard PyPI: `opentimelineio-0.18.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl`, SHA-256 `8f0924f818b496cf771612d489082bdb83f42b6bd97ed06589dd2e2c086742c9`. Apache-2.0 package licensing is metadata, not a media-rights/legal verification.

## Privacy, consistency and verification boundaries

Snapshots bind creating actor, full current scope, screenplay version, chapter version/digest/current privacy and chosen asset version/digest/current lineage. Changes invalidate export. Unavailable scoped assets hide their exchange row, references and ID/count; stale snapshots hide detailed media/timing. Permissions/flags/V1 are checked again after parsing/projection and immediately before file delivery. Import snapshot data remains LOCAL_ONLY.

Actual local verification includes the official parser, actual `.otio` files, read/write round trips, rational mixed frame/audio rates, gaps/dissolves, unsupported-data loss reports, malformed files, inert plugin metadata, missing parser, File persistence/restart, current source/media/actor/branch fences, mounted production APIs on both prefixes, and React File-input/review/error/scope tests. Fixtures are synthetic, not model-generated or claimed decoded media.

Real PostgreSQL cases are parametrized but local PG is NOT_RUN because no disposable server/DSN was available. The actual browser journey and size checks are authored in `frontend/tests/e2e/r4-director-exchange.spec.ts`; local browser/screenshots remain NOT_RUN due verified Chromium EPERM. Hosted CI must run these and report current results. Resolve and Premiere opening/playing the output are NOT_RUN. Actual model/GPU/Windows/user acceptance are separate and not inferred from parsing or UI tests.
