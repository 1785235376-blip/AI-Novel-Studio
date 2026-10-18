# Media and Comic engineering contracts (V2)

Version: `ENG-2026.10.19-r1`. This document records the media/visual contracts that exist at
`a072cf90` and defines the acceptance duties for the ones that do not. It separates
**real verified execution** from **contract-only** and **missing** capabilities.

## 1. Media owner map

| Domain | Owner | Current real-execution status |
| --- | --- | --- |
| Image assets, masks, cutout, provider recipes | `app/services/studio_image_*.py`, asset library | Real local CPU for deterministic operations; image model generation needs a configured local/authorized provider and is NOT run in this baseline |
| Video assembly / frames / execution | `app/video_assembly*.py`, `app/media_frames.py`, `app/services/studio_video_execution.py` | Real FFmpeg available; AI video generation requires authored provider routes, not run here |
| Audio production / mixdown / editing | `app/services/studio_audio_execution.py`, `studio_audio_trim_profiles.py`, `app/audio_production_store.py` | Real PCM/FFmpeg mixdown historically verified; TTS/ASR model execution NOT run here |
| Subtitle processing / timeline | `app/experimental/subtitle_timeline.py`, `subtitle_processing.py`, `subtitle_burn_in.py` | Local burn-in adapter seam and real container validation; ASR/forced-alignment model adapters NOT_CONFIGURED unless a trusted local adapter is injected |
| Timeline / NLE / render | `app/studio_timeline_edit.py`, `studio_timeline_schema.py`, `studio_timeline_render.py`, `app/creative/timeline_playback.py`, `timeline_transfer.py` | Timeline document + FFmpeg render path exist; a real MP4 must be produced and ffprobe-verified in acceptance |
| Export / delivery | `app/services/export_job_service.py`, `export_snapshot_authority.py`, `export_resource_snapshot.py` | Manifest/snapshot authority exists; real export artifacts must be produced per format |
| Comic / Webtoon layout | `app/experimental/comic_layouts.py` (+ `_api.py`), `frontend/src/experimental/ComicLayoutsPanel*` | Bounded **real** Pillow raster rendering with pinned Noto Sans SC; PNG segments/ZIP export; no AI panel generation |
| Interactive story / engine export | `app/experimental/interactive_story*.py`, `DirectorService/export adapters` | Godot/Ren'Py are data exporters; target runtimes NOT_RUN |

Rules:

1. A media task is not PASS because the module returned bytes. It is PASS only when the artifact is
   decoded by an independent parser (`ffprobe`/PIL/zip) and its duration, streams, dimensions,
   frame rate, subtitle track and SHA256 are recorded.
2. AI-generation claims require a configured/authorized runtime and a real produced artifact. No
   mock, synthetic fixture or container-valid bytes may be presented as model-quality acceptance.
3. Every lossy transform must report what was dropped. There is no silent loss from OTIO/SRT/VTT,
   engine export, format conversion or subtitle burn-in.

## 2. Comic / Webtoon contract (B06) — implemented subset

Data owner: `ExperimentalStore` scope transaction (File/PostgreSQL), flag `comic_layouts_v2`
requiring `asset_lineage_v2` + `ai_director_v2`; default-off, V1 acceptance mode wins.

Payload types (`app/experimental/comic_layouts.py`):

- `Rect` integer page geometry; `Bubble` (id, DIALOGUE/NARRATION, plain text ≤1,000 chars,
  optional speaker character id, font size 14–96); `AppearanceReference` (character id, approved
  asset id + expected version, note); `ComicPanel` (id, shot id, order 1–24, character ids,
  optional bound image asset + expected version, CONTAIN/COVER fit, bubbles ≤12, image brief,
  appearance references); `LayoutIn`/`LayoutEdit` (screenplay id + expected version,
  PAGE/WEBTOON preset, width/height/safe area/segment height, 1–24 panels).
- Limits: ≤24 panels, ≤80 bubbles, ≤10,000 total text characters, ≤16M page pixels, ≤20M decoded
  image pixels, ≤64 MiB source/output, 100 historic revisions; plain text only.

Supported closed loop (real): pick an existing screenplay's shots → generate a draft layout in a
PAGE/WEBTOON preset → bind and explicitly approve exact user-uploaded image asset versions
(generated/provider/derived assets must follow their normal review, not this shortcut) → edit
panel/bubble geometry and plain text → save versioned DRAFT (writes reset approval) → explicit
preflight (missing approved images, order, overlaps, safe area, font/glyph, measured text overflow,
resampling, crop, segment-cut bubbles) → single `compose` renderer produces real PNG segments →
review the exact digest-bound version → export requires the same approval and returns deterministic
ZIP: `segment-NNN.png` + `manifest.json` (geometry/checksums/panel sources) + complete `OFL.txt`.
Preview and export bytes are identical by contract; every route reauthorizes and returns
`Cache-Control: no-store` + `X-Content-Type-Options: nosniff`. Stale source/asset/character/
privacy invalidates content and approval; late responses cannot revive output.

Explicit non-capabilities (must not be claimed): arbitrary fonts/fallback, rich text, SVG/HTML,
scripts/animation, rotated/skewed panels, custom speech tails, HTML composition, server-side
inpainting, AI panel generation, ORA/PSD layers, CBZ/PDF/EPUB comic export, dynamic-comic rendering.

## 3. IMAGE-COMIC-01–20 status (honest)

| ID | Requirement | Status | Existing evidence / gap |
| --- | --- | --- | --- |
| 01 | Comic sub-entry under Image Studio | IMPLEMENTED | ExperimentalWorkbench → 漫画与 Webtoon panel; no new top-level module |
| 02 | Comic project tree / volume-chapter-page structure | PLANNED | Layout records exist; no comic volume/chapter/page tree owner |
| 03 | Smart episode/panel splitting | PLANNED (PARTIAL evidence) | PAGE/WEBTOON presets from screenplay shots (≤4/6 initial), manual add; no intelligent splitting |
| 04 | Professional panel canvas | PLANNED (PARTIAL evidence) | Numeric geometry + server raster preview; existing ImageInfiniteCanvas cannot represent variable-size panels |
| 05 | Per-panel generation | PLANNED | Only approved existing assets can be bound; no image model dispatch from comic panel |
| 06 | Character/costume consistency | PLANNED (PARTIAL contract) | character_ids + appearance references pin approved assets/versions; no generation/consistency engine |
| 07 | Pose / spatial control | PLANNED | No pose/depth/3D control in comic layout |
| 08 | Local repaint / inpainting | PLANNED | Image Studio mask/inpaint exists for image, not connected as comic-panel repaint |
| 09 | Independent bubble text | IMPLEMENTED (bounded) | Plain text bubbles/narration with speaker, font size, measured layout, overflow blockers; no rich text |
| 10 | SFX / onomatopoeia effects | PLANNED | No SFX glyph/effect model |
| 11 | Line-art colorization | PLANNED | Not implemented |
| 12 | Cross-panel continuity | PLANNED | No continuity analysis between panels |
| 13 | Page comic / webtoon | IMPLEMENTED | PAGE 800×1120 and WEBTOON 800×2400 presets with segmented rendering |
| 14 | Pacing / page-turn rhythm | PLANNED | No pacing/reading-rhythm model |
| 15 | Layers / ORA | PLANNED | No layer model or ORA/PSD import/export |
| 16 | Multilingual typesetting | PLANNED | Only Noto Sans SC; no language selection/line-breaking per locale |
| 17 | Local re-layout / remake | PLANNED (PARTIAL evidence) | Version restore creates new draft; no partial re-layout engine |
| 18 | Comic format export | PLANNED (PARTIAL evidence) | PNG segments + ZIP + manifest only; no CBZ/PDF/EPUB |
| 19 | Dynamic-comic handoff | PLANNED | No timeline/video handoff from comic layouts |
| 20 | Comic Agent review | PLANNED | Human digest review exists; no comic-specific agent review |

A row is PLANNED even where a related owner exists unless the requirement's user behavior is
actually delivered. Do not upgrade these rows because B06 passes its contract tests.

## 4. Subtitle/timeline processing contract

- Input: existing caption id + version, adapter id, operation (ASR / FORCED_ALIGNMENT / BURN_IN),
  bounded transcript only for alignment. No URL, command, plugin, credential, path or arbitrary
  parameter accepted.
- Persisted task: immutable actor/project/scope; caption+media version/digest; adapter identity;
  attempt count; claim token + process-instance identity; result or sanitized error; CAS/history;
  exact review digest. Public projections omit claim/raw transcript/history/binary payload.
- Transitions: QUEUED only with an explicitly host-configured adapter, otherwise NOT_CONFIGURED;
  execute → RUNNING claim → NEEDS_REVIEW after authority/source/adapter checks; cancel →
  CANCELLED with late output discarded; interrupted RUNNING survives restart and must be explicitly
  recovered (INTERRUPTED) and resumed; no automatic replay; approve/reject requires
  `domain.review` + current CAS + exact preview digest.
- Bounds: 1–2,000 cues, ≤100,000 text chars, 8 MiB input/output media, 32 MiB retained per scope,
  200 tasks/scope, 50 attempts/task. Burn-in duration must match source within 1 ms and MIME must
  match; larger production media needs a future streaming implementation (NOT claimed).
- Real quality (ASR accuracy, lip sync, visual burn-in quality) is NOT inferred from valid cues.

## 5. Real media verification recipe

For every produced media artifact record: producing module + SQL/job receipt id, input asset
versions/digests, command, tool versions (`ffmpeg -version`, Pillow, font manifest), output path,
byte size, SHA256, `ffprobe -show_streams -show_format` excerpt, and the independently parsed
facts (duration/fps/dimensions/audio+subtitle streams). Store hashes and recipes, not large
regenerated media, in Git.

## 6. Loss and limitation reporting

Any converter (OTIO, SRT/VTT, Godot data export, Ren'Py text export, ZIP manifest) must emit a
machine-readable loss report listing unsupported features it dropped. A converter that silently
drops tracks/effects/fonts is a defect. Engine exports are data adapters: Godot and Ren'Py runtimes,
media deployment and target import remain NOT_RUN unless explicitly executed and evidenced.
