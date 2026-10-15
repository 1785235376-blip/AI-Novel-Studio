# V2_ADVANCED_CAPABILITY_GAP_REPORT

**Production-chain capability gap analysis at `feature/v2-narrative-platform` HEAD `47e0e3b`**
Date: 2026-10-15 · PR #47 (Draft) · `main` frozen at `fed2404c`

---

## 0. Evidence discipline (read this before trusting any row)

`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md` states its own provenance: **"M0 source inventory,
2026-10-09… Audited HEAD `4350a61`"**. It is ~6 weeks and many commits behind this HEAD, so per the
directive its `MISSING` entries are **not** treated as current facts. This report re-derives status
from the source tree as it exists now.

**What this report is based on, and what it is not:**

| Evidence level | Meaning | How obtained |
| --- | --- | --- |
| **A — exercised** | A test I ran in this session passed and covers this path | named test file / suite |
| **B — code present** | The module, route and owner exist in the tree and are wired | file inventory + targeted reading |
| **C — claimed by a prior report** | A phase report documents it | report exists; **not re-verified now** |

**I did not run the storyboard, director, video, audio, NLE or export stages end-to-end this
round.** No row below is marked `IMPLEMENTED` on level C alone. Where capability rests on level C,
the row says so. Model execution, GPU and clean-Windows acceptance were not run and are out of
scope for this round.

---

## 1. Production chain — current status

| # | Stage | Status | Evidence | User-visible gap |
| --- | --- | --- | --- | --- |
| 1 | 小说 Novel | **IMPLEMENTED** | A (`tests/test_round2_bible.py`, novel/chapter services run every regression) | none material |
| 2 | 剧本 Screenplay | **PARTIAL** | B (`app/repositories/file/novel.py` "screenplay-records"; `frontend/src/novel`) | no independent screenplay revision/approval flow verified |
| 3 | 导演 Director | **PARTIAL** | A (`tests/test_v2_director_workspace.py` passed), B (`app/creative/director_*.py`, `frontend/src/director`) | intent is captured and projected; **shot-level directability is not verified end-to-end** |
| 4 | 镜头 Shot | **PARTIAL** | A (director workspace tests), B (`project_shot_cards`, shot binding on prompts) | shots exist as documents/cards; no shot editor verified in a browser this round |
| 5 | 分镜 Storyboard | **PARTIAL** | B (`frontend/src/storyboard`, `DIRECTOR_STORYBOARD_IMAGE_PHASE_REPORT.md` = level C) | storyboard→image dispatch not executed this round |
| 6 | 图像 Image | **PARTIAL** | A (`test_v2_creative_workflows`, asset library), B (`studio_video_execution`, image defs) | generation requires local/authorised providers; not run here |
| 7 | 视频 Video | **PARTIAL** | B (`studio_video_execution.py`, `studio_video_provider*.py`, `video_assembly_service.py`) | provider handoff exists; **no real video produced this round** |
| 8 | 配音与音效 Audio | **PARTIAL** | B (`studio_audio_execution.py`, `studio_audio_trim_profiles.py`, `audiobook_service.py`) | TTS/ASR/music/SFX execution not run; `LOCAL_REQUIRED` for real synthesis |
| 9 | 时间线剪辑 Timeline | **PARTIAL** | B (`studio_timeline_edit/schema/render/exchange/subtitles.py`, `frontend/src/nle`) | edit model exists; real render not executed |
| 10 | 成片导出 Export | **PARTIAL** | B (`export_job_service.py`, `export_snapshot_authority.py`, `export_resource_snapshot.py`, `frontend/src/delivery`) | export pipeline exists; **no real artefact produced/verified this round** |

**Reading of this table:** the chain is *structurally present* — every stage has an owning module,
and the studio has a real asset/job/timeline backbone. What is missing is not architecture but
**verified execution**: no stage past the Prompt/Bible/director layer has been driven to a real
output under this round's acceptance.

---

## 2. Cross-cutting capability

| Capability | Status | Evidence |
| --- | --- | --- |
| Asset owner (immutable bytes, CAS metadata, lineage, review) | **IMPLEMENTED** | A — heavily exercised this session |
| Job/task execution + review inbox | **PARTIAL** | B (`asset_task_worker.py`, `taskcenter`, `production`) |
| Timeline schema + exchange | **PARTIAL** | B; not run |
| Subtitle pipeline | **PARTIAL** | B (`studio_timeline_subtitles.py`) |
| Export snapshot authority | **PARTIAL** | B; not run |
| Model centre / provider registry | **PARTIAL** | B (`app/model_center`, `frontend/src/modelcenter`) |
| **Prompt → production application** | **MISSING** | R3-I never started: no route applies a chosen revision to a creative draft |
| Cross-stage provenance graph | **MISSING** | Round 4 not started; only `asset_relationships_v2` edges exist |
| Local model inference | **LOCAL_REQUIRED** | needs the user's own runtime; never run here |
| Cloud API providers | **BLOCKED by policy** | paid APIs excluded by standing instruction |
| Windows/GPU/installation acceptance | **NOT_RUN** | out of scope until functional completion |

---

## 3. What is genuinely absent (not merely unverified)

1. **Prompt → production application (R3-I).** No user flow takes a *chosen* Prompt revision —
   asset_id, revision, digest, binding source versions — and applies it to an existing creative
   draft with recorded provenance, so a reopened task cannot drift to a newer prompt. This is the
   single highest-value gap: the Prompt library can now be authored with real revisions, but nothing
   downstream consumes a pinned revision.
2. **Stage-to-stage adoption traceability.** Assets record lineage, but there is no user-facing path
   from "this shot" to "the prompt revision, reference images and audio take that produced it".
   Round 4's relationship graph is the intended home.
3. **Verified end-to-end production run.** No round has driven novel → screenplay → shot →
   storyboard → image → video → audio → timeline → export against real (even local) providers with a
   produced artefact as evidence.

---

## 4. Recommended next slice

**Slice: R3-I — pinned Prompt revision adoption into an existing creative draft.**

Chosen because it is (a) the highest-value gap, (b) independently completable without any model
execution, (c) built entirely on owners that already exist, and (d) the prerequisite for Round 4's
traceability graph.

* **Reuse, do not rebuild:** `AssetLibraryService` (asset/version/CAS), `IndependentWorkspaceService`
  (project binding + `_asset_scope`), the existing production/manifest owner for the target draft,
  and the R3-U2 authorised revision-body read.
* **Design:** a `prompt_adoption` record written onto the *target* draft's existing metadata, holding
  `prompt_asset_id`, `prompt_revision`, `prompt_digest`, `adopted_at`, `adopted_by`, and the source
  versions consulted (`character/scene/shot/reference` ids with their versions and digests at
  adoption time). Adoption is a **new immutable revision of the target draft**, never an in-place
  mutation, and never triggers generation.
* **Interfaces:** `POST /api/projects/{nid}/studio/production/{owner}/{id}/adopt-prompt` (closed
  admission), plus a read projection on the existing detail route. Strict DTO: the client supplies
  the chosen `asset_id`, `revision` and expected digests; the server re-reads the revision under the
  caller's actor, verifies the digest matches what the client claims, and refuses on mismatch
  (`PROMPT_ADOPTION_DIGEST_MISMATCH`).
* **Drift rule:** re-opening shows the pinned revision; if the family has newer revisions the UI says
  "a newer revision exists" and offers re-adoption as an explicit user action. It never rebinds.
* **Files:** `app/creative/prompt_adoption.py` (adapter), `app/creative/prompt_adoption_api.py`
  (route), admission update in `app/creative/workspace_api.py`, frontend
  `frontend/src/prompt/PromptAdoptionPanel.tsx` + wiring in the production surface, tests
  `tests/test_round3i_prompt_adoption.py` and a jsdom component test.
* **Acceptance:** adopt revision N onto a real draft; reopen and assert the recorded asset_id,
  revision and digest are unchanged; assert a newer revision does not silently rebind; assert an
  unauthorised actor cannot adopt or read the record; assert no model call occurs; File **and**
  PostgreSQL legs; then a real Edge pass.

---

## 5. Still-open R3-U items (unchanged, not to be read as passed)

| Item | Status |
| --- | --- |
| Refresh draft **text** restore | **PARTIAL** — a content-free marker warns; text is never written to browser storage |
| Cross-process concurrency | **NOT_RUN** |
| Write-time binding target verification | **NOT_RUN** |
| Private-revision deletion / tombstone | **NOT_RUN** — owner `delete()` has no `actor_id` |
| Edge specialisation matrix (409, UNKNOWN, 422, permission isolation, display mask, truncated history, dual mode, real `beforeunload`) | **NOT_RUN** |
| Case 1 server-side body read-back / Case 5 unconditional warning | **NOT_RUN** |
| PostgreSQL S4 | **NOT_RUN** |
| R3-R-08 display-mask cross-route guarantee | **PARTIAL** |

**R3-U stays PARTIAL.** No release readiness is claimed; `main` is untouched and PR #47 remains
Draft.
