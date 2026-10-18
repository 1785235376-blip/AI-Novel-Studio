# Current implementation gaps after full Master Roadmap recovery

Audit source: 2a85d9287a1c3c41ff8de0005538ceb64d4c9e42, 2026-10-18 15:32 UTC. Basis: complete original 904-line roadmap and later frozen-product-anchor-20261016.txt, current code and original-owner wiring. This is a bounded source-backed gap shortlist, not whole-V2 acceptance or a numeric completion estimate. Historical inventory labels remain historical. Newer uncommitted work must not be counted as complete.

The source normalizer was also probed read-only with the existing clean dependency interpreter: video+audio accepted; audio-only rejected with STUDIO_TIMELINE_VIDEO_TRACK_REQUIRED; clip color and caption style rejected with STUDIO_TIMELINE_FIELDS_INVALID. Initial system-Python import failed because sqlalchemy was absent; the clean-interpreter probe exited 0. This was not a media render or full test run.

## Confirmed code gaps by core module

| Module | Existing implementation that must not be rebuilt | Remaining bounded implementation |
|---|---|---|
| Text | Independent SCRIPT/SCREENPLAY, actual single-chapter semantic adaptation, difference report and reviewed adoption | Multi-chapter/range adaptation; current adaptation_models request accepts one chapter_id and optional exact selection |
| Image | T2I/I2I/reference/inpaint/upscale, painted masks, CPU cutout, source-bound review/Asset output | Outpaint/expanded-canvas operation; executable LoRA/control parameters in closed provider recipes; broaden deliberately narrow manual-mask PNG intake |
| Director | Semantic SCREENPLAY/STORYBOARD proposal paths, original preview/review, source evidence, multi-console comparison and selected-scene child drafts | Direct image/video/3D-reference analysis; structured audience/target duration/platform/budget intent; direct audio/postproduction suggestion contracts; structured camera geometry bridge |
| Storyboard | Independent documents, stable shot IDs, ordering/timing, CSV, Shot→Image/Video links | Verified image-thumbnail Shot Board/comparison and broader batch field authoring |
| Video | Async provider lifecycle, T2V/I2V Comfy recipes, configured HTTP V2V contract, reviewed candidate output | Source-interval/keyframe selection and temporal-reference preprocessing; current reference command takes one whole source video |
| Audio | Import/audition, TTS/MUSIC/SFX, trim/gain/fades/rate/channels/peak processing, WAV/FLAC/MP3; ASR/MFA/Whisper under original subtitle owner | Independent multitrack audio timeline and audio-only preview/mixdown through original timeline owner |
| Editing | Real tracks/edit operations/captions/FFmpeg render/preview cache/history and OTIO transfer | Basic color adjustment and caption styling; their fields are currently rejected by the closed schema |
| 3D | Bounded GLB, transformed mesh/material inspection, diagnostic orbit view, CPU clay/depth PNG and reviewed image Asset output | Actual authored-camera extraction/export and concrete minimal Blender/UE exchange; diagnostic yaw/pitch projection is not authored camera data |

Evidence pointers: app/creative/adaptation_models.py and adaptation_generation.py; app/creative/production_execution_models.py; app/services/studio_image_provider_recipes.py; frontend/src/creative/StudioManualMaskPanel.tsx; app/creative/proposals.py and director_model_api.py; app/creative/models.py and graph_models.py; frontend/src/storyboard/ShotCard.tsx; app/services/studio_video_provider.py; app/services/studio_timeline_schema.py, studio_timeline_edit.py and studio_timeline_renderer.py; app/creative/model_reference_scene.py and model_reference_depth.py.

## Advanced capability gaps and corrections

- A07: model_benchmark.py explicitly rejects VIDEO_WORKFLOW execution as import-only. Executed records leave tokens_per_second and gpu_memory_bytes unset, cold_start_state NOT_MEASURED. Text/image execution and evidence/preferences already exist. Missing measurement implementation differs from absent target hardware for acceptance.
- A08: experimental/director.py already owns CameraGrammar and exact camera_checks. The existing geometry checker remains tied to the older screenplay plan; Creative Director/Graph has no equivalent source-bound bridge. Reuse that checker and original document owner, keeping user-authored geometry and model suggestions distinguishable.
- A09: production_lineage.py and change_impact.py consolidate older consumers but do not enumerate all newer Creative Graph/Studio Timeline consumers. Those newer owners have source guards; an incomplete consolidated impact view is not a claim that source protection is absent.
- A13: production manifests/replay currently resolve original image MediaService tasks. A whole-production selection layer across existing video/audio/Graph/Timeline receipts is missing. Do not add another queue or replace individual approval owners.
- B10: durable manual chapter exchange, selection changes, deduplication, three-way conflicts, original CAS, tombstones and UNKNOWN recovery already exist. Limits: local-project chapters only, first 100 chapter choices, 20 selected chapters/channel, no asset/branch exchange. Production transport/encryption are injected fixtures, not a deployed authenticated service. Original roadmap defers production cloud/realtime; later B10 remains required, without authorizing paid hosting.

Do not re-create these implemented paths based on older indexed owner files:
- A01/A02/A03/A11 and B02/B05: mounted UI and original AuthorPreparer→Broker→JobManager coordinators.
- A04/A05: reviewed temporal knowledge in character-restricted authoring.
- A10: native image/PDF OCR and embedding/hybrid-search paths.
- B04: actual MFA/Whisper adapters and trusted host configuration.
- B09: BranchManuscriptService fork, three-way merge and recovery plus mounted BranchManuscriptPanel. The older ProjectForks service is not the complete feature.
- A12: original Studio multitrack OTIO transfer exists. References-only media and effects/subtitles retained in Studio metadata are exact limitations; target NLE acceptance remains unrun. Optional FCPXML/EDL are not automatically mandatory.
- B07: Ren'Py text/menu export and typed Godot data adapter exist. A typed adapter is not a playable game project or deployed media package.

## Next substantial original-owner slice

Independent audio timeline finish line: AUDIO → import two WAVs → arrange two audio tracks with trim/gain/fade → save/reopen → explicit mixed-audio preview → reviewed genuine WAV Asset/export.

Preserve schema-1/2 video bytes/digests; introduce an explicit versioned audio-only shape under the original timeline owner, never a dummy VIDEO track. Reuse original CAS/edit/history/source guards and budgets. Start with one closed PCM16/48kHz/stereo WAV profile; enforce the existing 25 MiB output cap using actual uncompressed sample count. Reuse FFmpeg audio filters but remove video mapping and black-frame generation. Update original candidate/review/recovery expected-kind checks from the exact bound profile, not a caller-supplied arbitrary kind. Existing Graph timeline exports can retain video-only contract initially. Playback must use the same source/profile-pinned cache and UNKNOWN lifecycle with actual audio/wav and HTMLAudioElement, without automatic rendering on open.

Critical existing video assumptions are in video_assembly_service.py, creative/production_execution.py, studio_timeline_export.py, timeline_playback.py, useStudioTimelinePlayback.ts and StudioTimelinePlaybackPanel.tsx. Merely removing the VIDEO-track guard is insufficient.

## Acceptance and scope boundaries

Real model/literary/visual quality, target Windows/IME/install/upgrade, true browser interaction/performance, and final 2V/2A/subtitle product journey remain separate acceptance stages. Prior CPU render receipts remain valid at their own source, not automatically at final source. Full DCC, auto-rigging, complete 3D camera simulator, Resolve-equivalent grading and advanced realtime voice/cloning are separately scoped extensions in original Appendix A; respect later specific additions without silently requiring entire external products.

U01–U16 and FS/CORE still need complete current functional reconciliation. Their structural owner index cannot support a whole-product percentage. Maintain implementation gaps and acceptance gaps separately; do not calculate a false completion rate from test count or source-file presence.

## U01–U16 consumer follow-through (read-only review at f53f4324)

Concrete additional gaps:
- U07 / FS_REVIEW: independent Studio's Tasks surface routes through TaskOwnerResult, whose exact reopen supports only older experimental MediaService. Newer Studio production jobs and Graph runs are absent from that original experimental task projection. Their own production list/get endpoints already exist. Add an explicit read-only original-owner projection and exact reopen; never route these jobs through generic experimental cancellation/review.
- U06: consolidated downstream impact excludes newer Creative Graph/Studio Timeline consumers (individual source guards remain).
- U14 / Storage: selected chapter/media portable exchange and relinking exist. Collaboration restore/relink are intentionally unavailable. StudioStorageAdmission already checks real filesystem capacity/reserve. General directory migration/recovery and configurable cache-limit workflows remain; portable export-cache cleanup is not all storage management.
- U16: safe_batches supports PROOF/EXPORT/SYNTHETIC_MEDIA/REGISTERED_MEDIA/VOICE_REDO, but not newer Studio video/Graph/Timeline execution. Existing safety machinery must be extended through original owners, not replaced.
- U04: focus typography, reference split, bookmarks and inspiration exist in the same editor. Separate multiwindow authoring/coordination is not evidenced; the later frozen anchor includes multiwindow.

Historical branch-adapter statements are not automatically current: experimental/api.py binds BranchManuscriptService readers to writing-focus and workspace-tools owners. Reader preflight, sessions and portable readers consume those bindings; author_context_sources also uses scoped chapters. Do not propagate old absent-adapter claims into U01/U03/U04/U05/U08/U11.

No additional concrete code omission was established in the bounded inspection of U01/U02/U05/U08/U09/U10/U11/U12/U13/U15. This is not a completion claim: native IME, screen reader, publishing layout and hardware/model acceptance were not run. U03 has bounded lexical search and module navigation; global index breadth differs from complete semantic search. OS/background notifications are not automatically required merely because notices are in-app.

FS/CORE inspection covered interaction, review, branch-reader integration, generation selection/context and asset storage. Other FS/CORE rows were not fully audited, including Canon, continuity, foreshadowing, import, planning, realtime, SDK, universe, visual, broader research and export internals. No whole-product percentage is derived from this bounded audit.

## Superseding implementation slices after the audit

At source 3fe05b171e05f777dba6553c3fad185592b72774, the bounded independent AUDIO timeline gap above has been implemented: schema-3 audio-only tracks, original editing/CAS/history, explicit PCM16/48kHz/stereo WAV preview and reviewed export. Actual File and PostgreSQL output has 96,000 stereo frames / 384,044 bytes / zero video streams. Original output budgets remain; the WAV profile limits renderable duration to 136,533 ms. This does not complete every Audio feature or target-platform acceptance. See ../delivery/v2-development/audio-only-timeline-mixdown-20261018.md.

The U07 independent Tasks consumer gap is partially closed at the same source: original Studio image/video jobs are listed and exact receipt opening uses the existing production panel. Other owners and Graph runs remain out of this bounded projection. See ../STUDIO_PRODUCTION_TASK_REOPENING.md. No generic task cancellation/review is applied to these owners.

Original node-removal impact confirmation and bounded offline JSON file intake were completed at 33e7ad09 and 4924980d, integrated verification at 91a3f328. Therefore B10 file intake is no longer a pending implementation item; broader offline/asset/branch/transport limits still apply.

## 16:32 superseding audit and implementation

Source 501ff11b implements authored camera geometry in original Director/Storyboard consumers, basic VIDEO clip color, implicit reviewed narrative progress and original workflow Agent authority callbacks. Geometry is supplementary authored evidence, not video/image analysis. Basic color is not advanced grading. Original red failures and precise File/PG coverage are retained in ../delivery/v2-development/director-color-authority-wave-20261018.md. Archive 7b9f70727fb9a21b2e4df4fc9f3da0d914440727 is anonymously verified.

The bounded FS/CORE review now additionally identifies these concrete gaps:
- FS_CANON: newly accepted mainline generation produces a placeholder candidate without exact accepted chapter version/digest. Review UI already exists; producer provenance and meaningful proposal extraction need work.
- FS_PLANNING: mounted layered generation is mock-only. A local model bridge is now under development, reusing original owners and explicit preview/approval, not the separate unsafe direct execution path.
- FS_VISUAL: review adapter execution is MOCK_ONLY and no complete visual-check authoring consumer was found. Approved visual memory and source-bound receipts do exist.
- CORE_MODELS: discovery, registration and diagnostics exist; controlled download/pause/resume/integrity/cleanup remain disabled.
- CORE_EXPORT: current portable export is not a restorable whole-Creative package with Graph and Timeline relationships; offline backup is a separate existing capability.
- FS_IMPORT: real parsers and reviewed checkpoint apply exist, but semantic extraction uses a local heuristic path.

FS_REALTIME retains original deferred production-cloud scope; do not purchase hosting. FS_UNIVERSE has bounded immutable snapshot references. FS_CONTINUITY, STORY_DATABASE, TIMELINE and CORE_CREATION have mounted source/review/CAS paths; no additional concrete omission was established in this bounded review. SDK declarative recipes and trusted adapters exist; executable plugins are intentionally denied. Native Windows NamedPipe transport exists; target integration remains a separate acceptance boundary. Neither this inspection nor the structural index is a whole-product completion percentage.
