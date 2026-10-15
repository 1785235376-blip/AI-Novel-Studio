# V2_ADVANCED_CAPABILITY_GAP_REPORT

**Production-chain capability gap analysis at `feature/v2-narrative-platform` HEAD `47e0e3b`**
Date: 2026-10-15 · PR #47 (Draft) · `main` frozen at `fed2404c`

---

## 0. Evidence discipline (read this before trusting any row)

`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md` states its own provenance: **"M0 source inventory,
2026-10-09… Audited HEAD `4350a61`"**. This HEAD is dated **2026-10-15**, so M0 is **six days**
behind — not six weeks. An earlier revision of this report said "~6 weeks", which was a factual
error and is corrected here.

Six days is still enough for the `MISSING` column to be stale in places, because the intervening
work landed several rounds (R3-W, R3-U1/U2/U3-A/B/C, R3-U3-D) that M0 could not have seen. So its
`MISSING` entries are still **not** treated as current facts, but the reason is the rounds that
landed in those days, not the length of the interval. This report re-derives status from the source
tree as it exists now.

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

### Three distinct evidence statements — do not collapse these into one

1. **This round did not execute the full production chain.** No novel→…→export run was performed
   here, and no row in §1 is promoted on the strength of this round's work.
2. **Phase 6 did verify real CPU audio/video processing and MP4 output.** That is a genuine,
   *previously recorded* success at evidence level C — see `PHASE6_AUDIO_EDITING_REPORT.md`. It must
   not be downgraded to "unverified", and equally it must not be recycled as evidence for this
   round's chain, for AI generation quality, or for GPU/model acceptance.
3. **The complete AI narrative production chain and real local-model runs still have no product
   acceptance.** No round has produced an artefact end-to-end through the AI stages under
   acceptance, and local inference remains `LOCAL_REQUIRED`.

### A-level audit

Each level-A row in §1 rests on a suite **actually executed in this session** — not on another
test's green result:

| Row | Suite actually run | Where |
| --- | --- | --- |
| 小说 Novel | `tests/test_round2_bible.py` | R3-R / R3-U3 regression runs (exit 0) |
| 导演 Director, 镜头 Shot | `tests/test_v2_director_workspace.py` | same runs (exit 0) |
| 图像 Image, asset owner | `tests/test_v2_creative_workflows.py`, `tests/test_asset_library.py` | same runs (exit 0) |
| Prompt authoring/read | `tests/test_round3w_*.py`, `tests/test_round3r/s_*.py`, `tests/test_round3u_revision_body.py` | R3-W / R3-R / R3-S / R3-U2 runs (exit 0) |

Nothing in §1 was promoted from level C to level A on the basis that some other test passed.

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
| **Real CPU media processing (FFmpeg) and MP4 output** | **PARTIAL — real, historically verified** | C: `PHASE6_AUDIO_EDITING_REPORT.md` records actual CPU audio/video processing with MP4 output. Real work; not re-run this round and **not** evidence of AI generation quality |
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

## 3b. R3-I target-owner reconnaissance (done, so it need not be repeated)

The directive requires choosing a target owner that genuinely supports persisted revisions, CAS and
identity isolation, and forbids writing metadata behind the owner's back. Verified in source:

* **`CreativeService` is a valid target.** `app/creative/service.py` exposes `document_digest`,
  an `expected == {version, digest}` contract enforced by `_expected` and `assert_current`,
  `new_row`/`change_row` with retained history, and `update(nid, scope, actor, rid,
  expected_version, value, *, reauthorize)` at line 234 which commits through
  `change_row(row, actor, expected_version, replace_content)`.
* **Consequence:** adoption should be committed as a **new revision via `CreativeService.update`**
  with the document's expected version+digest, not by mutating stored metadata directly. Note that
  `update()` runs `value` through `prepare_content`, so the adoption block must be accepted by that
  schema (or carried in the document's existing content payload) — resolving that is the first
  implementation step, and it was **not** done this round.
* The generic `{owner}` route sketched in §4 is **not** to be built: the directive explicitly warns
  against a泛化 write API accepting every owner type.



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
