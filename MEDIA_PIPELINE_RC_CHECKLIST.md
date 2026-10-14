# MEDIA_PIPELINE_RC_CHECKLIST — Phase11 P2

**Nature:** the *executable* checklist for real media-chain acceptance at release-candidate
level. It is a preparation artifact: **no real generation, render or export was run for it**,
and every execution row below is `NOT_RUN`.

**Baseline:** `0c5128b` (`feature/v2-narrative-platform`, PR #47 OPEN/draft).

**Relationship to the documents that already exist — this file does not replace them:**

| Document | Role |
| --- | --- |
| `MEDIA_PIPELINE_VALIDATION_PLAN.md` (Phase9) | defines scope and which existing owner owns each step |
| `MEDIA_PIPELINE_RC_VALIDATION.md` (Phase10 B2) | the record table and the mandatory per-step checks |
| **`MEDIA_PIPELINE_RC_CHECKLIST.md`** (this file) | the operator checklist: real owners, real version/digest fields, runnable preflight, and the exact command per step |

**Status vocabulary for this file:** `PASS` · `PARTIAL` · `BLOCKED` · `NOT_RUN`, plus
`BLOCKED_EXTERNAL` for a failure caused by the host environment rather than the product.

**Iron rule, unchanged from Phase10:** a mock, fixture or synthetic result may **never** fill
in an Asset ID / Version / Digest / Status cell. An unexecuted row stays `NOT_RUN`. A failing
row records *why* and is not turned green by editing an assertion, adding a skip or deleting a
case.

---

## 1. The chain, with the real owner and the real identity fields

Chain: **Text → Director → Storyboard → Image → Video → Audio → Timeline → Export**

Every step binds to an existing owner. No new engine, store, timeline or asset system is
introduced by this checklist.

| # | Step | Owner (existing) | Input | Expected output | Asset ID | Version | Digest | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Text** | `app/creative/generation.py`, `app/creative/text_execution_receipt.py` | a fixed short Chinese text + 1 chapter | document row + version + execution receipt | — | 待填 | 待填 | `NOT_RUN` |
| 2 | **Director** | `app/creative/graph_planning_nodes.py`, `app/creative/production_workflow.py` | the step-1 document **version + digest** | DIRECTOR document + proposals (`NEEDS_REVIEW`) | — | 待填 | 待填 | `NOT_RUN` |
| 3 | **Storyboard** | `app/creative/storyboard.py` | the Director document version | storyboard document + N shots with **stable `shot_id`** | — | 待填 | 待填 | `NOT_RUN` |
| 4 | **Image** | `app/services/studio_image_execution.py`, `app/services/studio_image_control_contract.py` | storyboard shot + image graph v4 | image asset + private candidate → human review | 待填 | 待填 | 待填 | `NOT_RUN` |
| 5 | **Video** | `app/services/studio_video_execution.py`, `app/services/studio_video_provider.py` | the **approved** storyboard + video graph v5 | video asset bound to a `storyboard shot pin` | 待填 | 待填 | 待填 | `NOT_RUN` |
| 6 | **Audio** | `app/services/studio_audio_execution.py`, `app/services/studio_audio_trim_profiles.py` | an operator-supplied WAV, or a generated audio asset | audio asset + verifiable PCM properties | 待填 | 待填 | 待填 | `NOT_RUN` |
| 7 | **Timeline** | `app/services/studio_timeline_edit.py`, `studio_timeline_schema.py`, `studio_timeline_render.py` | the asset **versions** from steps 4–6 | timeline draft on an integer/rational time base | — | 待填 | 待填 | `NOT_RUN` |
| 8 | **Export** | `app/services/export_job_service.py`, `app/services/studio_timeline_export.py`, `app/services/export_snapshot_authority.py` | the timeline + explicit selections | export receipt + artefact file + digest | — | 待填 | 待填 | `NOT_RUN` |

### The identity fields are real, not invented

They come from `app/creative/production_execution_models.py`, and a reviewer should expect
exactly these:

| Field | Where it is declared | Meaning |
| --- | --- | --- |
| `StoryboardShotPin.shot_version` / `.shot_digest` | `production_execution_models.py:112-117` | a video step must pin the exact shot revision it approved |
| `StoryboardDocumentSnapshot.version` / `.digest` | `:106-109` | the Director→Storyboard hand-off identity |
| `MediaCreate.reviewed_preview_digest` | `:253-255` | a promotion is only valid against the preview a human actually reviewed |
| `MediaJobAction.expected_version` / `.expected_request_digest` | `:258-260` | optimistic concurrency on a media job |
| `TimelineRender` / `TimelineEdit` / `TimelineExport` `.expected_version` + `.reviewed_*_digest` | `:267-317` | every timeline mutation carries the reviewed digest |
| `TimelineAssetSnapshot.version` / `.digest` | `:320-325` | the asset revision bound into the timeline |
| `TimelineRestore.restore_version` / `.restore_digest` | `:301-305` | restoring is itself versioned and digested |

A row may only be marked `PASS` when the recorded digest and version match the ones the
request carried — "the file exists" is not the check.

---

## 2. Contract preflight — what was actually verified in this phase

Executed (real, no generation) to prove the chain's contracts are wired before anyone attempts
generation, so a later failure can be attributed to execution rather than to a missing contract:

```
scripts/run_v2_checks.py phase11-media-chain-contract-preflight -- python -m pytest \
  tests/test_v2_text_execution_receipts.py tests/test_v2_director_storyboard_production.py \
  tests/test_phase8_storyboard.py tests/test_phase8_asset_execution.py \
  tests/test_v2_storyboard_video_pipeline_api.py tests/test_v2_independent_media_job.py \
  tests/test_phase4_timeline.py tests/test_v2_screenplay_export.py \
  -q --basetemp .runtime/v2-checks/phase11-media-chain-contract-preflight/pytest -p no:cacheprovider
```

**Result: `86 passed, 79 skipped, 1 failed` (78.87 s), exit 1.**
Receipt: `docs/delivery/v2-development/phase11-media-chain-contract-preflight.json`.

| Step | Contract file | Result |
| --- | --- | --- |
| Text | `tests/test_v2_text_execution_receipts.py` | contract green |
| Director | `tests/test_v2_director_storyboard_production.py` | contract green |
| Storyboard | `tests/test_phase8_storyboard.py` | contract green |
| Image | `tests/test_phase8_asset_execution.py` | contract green |
| Video | `tests/test_v2_storyboard_video_pipeline_api.py` | contract green |
| Audio / media job | `tests/test_v2_independent_media_job.py` | **1 failed — `BLOCKED_EXTERNAL`** |
| Timeline | `tests/test_phase4_timeline.py` | contract green |
| Export | `tests/test_v2_screenplay_export.py` | contract green |

**The single failure is environmental, not a product defect.**
`test_media_job_is_explicit_bounded_and_has_real_official_prerequisites` runs
`subprocess.run(["bash", "-n"], ...)` to syntax-check a shell job; this host has **no `bash`**,
so `subprocess` raises `FileNotFoundError [WinError 2]`. It is the same POSIX-only class as
the pre-existing `tests/test_v2_media_prerequisites.py` failures. Note that `ffmpeg` and
`ffprobe` **are** present on this host (`D:\ffmpeg\ffmpeg-8.1.2-essentials_build\bin`), so the
audio/video tooling prerequisite is satisfied even though this test cannot run here.

**Caveat on `79 skipped`:** skips are not passes. They are conditional paths (platform,
optional dependency, opt-in flag) and must not be counted toward the chain as if they ran.

---

## 3. Per-step mandatory checks (all must hold)

The full table is `MEDIA_PIPELINE_RC_VALIDATION.md` §2; these are the ones that decide a row.

| Check | Decision rule |
| --- | --- |
| Artefact exists and is locatable | reproducible path, non-zero size |
| Artefact parses | image dimensions/format; audio sample rate/channels/duration; video duration/codec |
| Version/digest consistent | identical to the version + digest recorded at request time |
| Reference independence | rebinding one reference does not silently change another; impact is inspectable |
| Status is real | status comes from the owner; unfinished shows `UNKNOWN`; **a failure never renders as success** |
| Limits unchanged | 600 000 ms / 8 tracks / 30 clips / 1920×1080 / 25 MiB per asset / 200 MiB total source / 120 s render / 500 subtitles & 192 000 B / 1–40 edit ops |
| Quality tiers separated | a preview (`REVIEW_MP4`) must never be labelled a delivery master; `deliveryReady` stays false |

---

## 4. Environment and preconditions (verified in this phase, not assumed)

| Item | Fact |
| --- | --- |
| Backend | `uvicorn app.main:app --host 127.0.0.1 --port <port>`; **8000 is unusable** (Windows excluded range, held by PID 4) and **8100 is now occupied** by the unrelated ASUS `GearLink_KBService` — use 8110 or another free port |
| Frontend | Vite; with `--host 127.0.0.1` it binds IPv4, so `http://127.0.0.1:5173` works. Without `--host` it binds IPv6 only and the base URL must be `http://localhost:5173` |
| Browser | the installed system Edge via `channel: msedge`; **never** run `playwright install` |
| Storage | File for browser/media acceptance; a real disposable PostgreSQL cluster for persistence acceptance (see `PHASE10_RELEASE_HARDENING_REPORT.md` §5.6 for the exact runner syntax) |
| Tools | `ffmpeg` / `ffprobe` present at `D:\ffmpeg\ffmpeg-8.1.2-essentials_build\bin`; **`bash` absent** (POSIX-only tests cannot run here) |
| Assets | operator-supplied or self-made; **downloading a large model is forbidden** |

---

## 5. Failure scenarios that must each be exercised once

Carried over from `MEDIA_PIPELINE_RC_VALIDATION.md` §3 and still all `NOT_RUN`: missing tool
(ffmpeg/ffprobe), missing/unauthorised model, out-of-memory or VRAM exhaustion, render timeout
(>120 s, must not re-dispatch a second time on the same idempotency key), lost receipt (re-read
the original only; missing shows `UNKNOWN`), unsupported format (machine code + Chinese reason
+ supported list; never a fake export), and revoked authority (refuse and clear displayed data).

---

## 6. Completion criteria

1. All eight rows carry a **real** artefact, Asset ID, Version, Digest and status.
2. Each of the seven failure scenarios has been exercised at least once.
3. Any failure records its cause and recovery action; nothing is made green by weakening a test.
4. `deliveryReady` is only ever true after a real delivery-master render, never from a preview.

---

## 7. Phase12 execution record — one real model-free chain (2026-10-15, `82d1282`+)

Executed against a **real running backend** (`uvicorn app.main:app`, `STORAGE_BACKEND=file`,
`EXPERIMENTAL_FEATURES=narrative_production_v2`, `MOCK_PROVIDER=false`) through the app's own HTTP
API, in a sandbox data directory. **No generative model was involved in any row below**, so these
rows are real product operations with real artefacts and digests — not mock output. Image, Video
and Audio are absent precisely because they *require* a model runtime that this host does not have.

| # | Step | Input | Output | Asset ID | Version | Digest (sha256) | Review state | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Text** | author-supplied Chinese prose (97 chars, 3 paragraphs) | chapter row, `word_count: 97`, document JSON | `phase12:1` | `1` | `e7f4164aca49d1bc4459cca5494774baca86f374218ab352d22352209af6b0a7` | `Draft` | **PASS** |
| 2 | **Director / Screenplay** | chapter `phase12:1` v1 | screenplay with 1 scene pinned to the source (`source_chapter_id: phase12:1`, `source_version: 1`) | `a15f7d00-cfd2-4c6d-8f7a-02ae7ede65b6` | `revision 1`, `edit_version 1→2` | `789549816f59b53cddd47fc210929425a570182ed1f875457dddc106cf22000c` | `DRAFT → APPROVED` | **PASS** |
| 3 | **Shot plan** | approved screenplay | shot plan | same screenplay | `edit_version 3→4`, `shot_revision 1` | `deebe0ce3b2663b0857238ac19467ffd609a59c283d5407f796bebbbf44b9b82` | `APPROVED` | **PASS** |
| 4 | **Storyboard** | approved shot plan | storyboard | same screenplay | `edit_version 4→5`, `storyboard_revision 1` | `60079fa502575f347b5809a97c70eb0bc33b52e6c66ca2fa1499df5ab8be47d3` | `APPROVED` | **PASS** |
| 4a | Storyboard approval | storyboard | approval transition | same screenplay | `edit_version 5→6` | `4a0b4e51006290694332d3dc76152ece09f66d30e26291539f13d8c8b9c154d1` | `APPROVED` | **PASS** |
| 5 | **Export** | novel `phase12` + approved screenplay | export job + **real artefact file** (1930 bytes) | job `51155d19-4999-4a2b-b31a-850e04a13e46` | `snapshot_id 935c5c78-…`, sources pinned | artefact `92ad87bcf51de2adff1db44567f6bd4ef190007b327ff52aea3a03f5e02b9e26` | `succeeded` (progress 100) | **PASS** |
| 6 | **Image** | — | — | — | — | — | — | **BLOCKED** — no local image runtime (ComfyUI 8188 has no listener) |
| 7 | **Video** | — | — | — | — | — | — | **BLOCKED** — no local video runtime |
| 8 | **Audio** | — | — | — | — | — | — | **BLOCKED** — no local ASR/TTS runtime (Whisper host not configured) |
| 9 | **Timeline** | — | — | — | — | — | — | **BLOCKED** — needs real media assets from steps 6–8 |

A second export path also produced a real payload artefact with the chapter content embedded:
`phase12.json`, digest `be77ebb00104670e44fdfcf32aca91f6e3b67a0c4613d7de812e5fdd421409bc`.

### Real gates discovered while running this (product behaviour, not defects)

1. **Approval is gated on the review state.** `POST …/shots` before the screenplay was approved
   returned `400 screenplay must be approved before shot planning`; `POST …/storyboard` before the
   shot plan was approved returned `400 shot plan must be approved before storyboard`. This is a
   correctly fail-closed chain, and the chain above went *through* the gates rather than around them.
2. **Every approval is an optimistic-concurrency write.** Omitting the precondition returns
   `428 PRECONDITION_REQUIRED`: *"Read the current screenplay edit_version and include
   expected_version before editing or approving."* Sending a stale value returns
   `409 VERSION_CONFLICT`. **`expected_version` is the screenplay `edit_version`**, not the
   per-artefact revision — sending `shot_revision` (1) where `edit_version` (3) was required is what
   produced the first 409.
3. **The current `edit_version` is only readable indirectly.** There is no `GET` for one screenplay
   (`GET …/screenplays/{id}` → 404) and `GET …/screenplays/{id}/shots` → `405 Method Not Allowed`,
   so a client must read the revision from an export job's `source_versions`. That is a real
   usability gap for API clients, recorded here rather than worked around.

### What this does and does not establish

It establishes that **Text → Director/Screenplay → Shot plan → Storyboard → Export is real,
versioned, digested, review-gated and reproducible on the current head without a generative model**.

It does **not** establish the media chain: Image, Video and Audio require a local runtime that does
not exist on this host, and Timeline depends on their assets. Those rows stay `BLOCKED`, and no
mock or cloud result was substituted for them.

