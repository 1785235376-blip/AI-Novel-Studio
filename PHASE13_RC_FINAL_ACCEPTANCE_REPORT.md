# PHASE13_RC_FINAL_ACCEPTANCE_REPORT — RC Final Acceptance Preparation

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform` · **Worktree:**
`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`

**Baseline:** `f598bee` (local = remote at phase start). `main` = `fed2404c`, never touched.
**PR #47:** `OPEN` / `isDraft: true`. No merge, no release, no tag.

**Status vocabulary — only these five values are used in §8:**
`IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.
`BLOCKED_EXTERNAL` / `BLOCKED_LOCAL_RUNTIME` are used in prose for a host-caused failure that is
demonstrably not a product defect. **No status was upgraded**, and no status was inferred from a
test count.

> Phase13 is not a feature phase. It fixed one pre-release engineering gap, produced a live
> evidence-backed answer on the other, and re-tested rather than re-asserted the surrounding
> contract. Nothing here claims a gate that was not actually passed.

---

## 1. Baseline re-verified and prior documents re-read

| Check | Result |
| --- | --- |
| `git rev-parse --short HEAD` | `f598bee`, branch `feature/v2-narrative-platform` |
| `git ls-remote origin …` | feature `f598bee…`, **main `fed2404c`** (untouched) |
| `gh pr view 47 --json state,isDraft,headRefOid` | `OPEN`, draft, `f598bee…` |
| tracked dirty / untracked | `0` / `39` (all protected baseline families) |

Per §二 the matrix, the Phase11 and Phase12 reports, the README and `docs/v2/` were re-read rather
than trusted. Where a prior statement is overtaken, it is superseded in the Phase13 append section
with the original row left intact. Hindsight memory was not available and was not relied on.

---

## 2. P0 gap 1 — the frontend port table (audited; migration not performed)

**Status: `PARTIAL`. I did not complete this migration, and I am not claiming I did.**

The audit located the duplication precisely, and it turned out to be **deliberate cross-pinning
rather than accidental drift**:

| Site | What it does |
| --- | --- |
| `app/creative/graph_models.py:753` | the catalog route **already** calls `definition_for(key, schema_version=5 if include_video else 3 if include_media else None)` — so the backend **already emits schema-resolved ports** and is already authoritative for them |
| `frontend/src/creative/studioGraphClient.ts:57-86` | a full local `ports` table plus `nodePorts()` re-deriving the same resolution (`media_review`/`timeline_export` at v5; `human_review`/`media_generate` at v3) |
| `frontend/src/creative/graphDraft.ts:8-10` | `graphCatalogForSchema` patches the same three cases again |
| `studioGraphClient.ts:421` | `catalogDefinition` **cross-checks the server's ports against its own table**, which is exactly why drift appears as a catalog load failure |

So the frontend table is not redundant duplication to delete — it is an **independent pin on the
server contract**, and the phase rule "do not delete port validation" rules out removing it. The
correct convergence is a single frontend projection that *prefers* the server-resolved ports while
keeping the structural checks (ids, `required`, `multiple`, type domain, counts), with the local
table retained only as a legacy fallback.

That change touches a strict validator whose failure mode is a whole-catalog load failure, and it
could not be implemented **and properly verified** within this phase's remaining budget. It is
therefore recorded as remaining work with evidence, not reported as done. The backend-authority
half is already true today (`graph_models.py:753`), which is the important half for compatibility.

---

## 3. P0 gap 2 — `validate_output_ports(schema_version=None)`

**Status: `IMPLEMENTED` (fixed, tested).**

### 3.1 Audit: compatibility default or missing validation? Both, and they separate cleanly

* **It is a deliberate compatibility default.** `definition_for(id, schema_version=None)` returns
  **exactly** the same definition as `schema_version=1` — only `5` and `3` change anything — and
  `parse_graph` (`graph_models.py:677`) fixes the authoritative version set at 1–5 with `1` as the
  fallback for a missing key. The callers that omit the version (`ai_execution.py:534`,
  `text_assets.py:86`) are the legacy v1 text paths, whose behaviour
  `tests/test_v2_ai_execution_contracts.py:61,67` already pins.
* **It is fail-closed, not permissive.** Every schema-specific port type refuses to validate under a
  version it does not own: planning ports need 4/5, `STORYBOARD_SHOT` needs 5, `IMAGE_PROMPT` and
  image references need 4, `VIDEO_CANDIDATE` needs 5. Omitting the version therefore cannot grant a
  newer schema.
* **The genuine gap:** an *illegal* version never raised. `0`, `6`, `-1`, `99`, `1.0`, `"4"`,
  `True` and `object()` all fell through every `not in {3,4,5}` style gate and were **silently
  validated as v1**.

### 3.2 Fix

`normalise_schema_version()` maps `None` to the explicit `LEGACY_SCHEMA_VERSION = 1` and refuses
anything that is not an **exact** `int` in `SUPPORTED_SCHEMA_VERSIONS = {1,2,3,4,5}` with
`CREATIVE_GRAPH_SCHEMA_VERSION_INVALID`. The type check is exact on purpose, because `True == 1` in
Python — matching this module's existing `GraphCreate.exact_zero` convention. `validate_output_ports`
normalises at entry and is otherwise untouched, so `None` becomes an *explicit* v1 instead of an
implicit one and every legitimate caller keeps its exact behaviour: **old rows stay readable and
nothing is force-upgraded.**

### 3.3 Evidence

`tests/test_v2_graph_schema_version_gate.py` (new) covers the three required cases — version
present, version missing, version illegal — plus `None ≡ v1` across **every** definition in the
catalog, and re-asserts that schema-specific port types stay gated.

```
442 passed, 35 skipped, exit 0
receipt: docs/delivery/v2-development/phase13-schema-version-gate-r2.json
```

That run includes the 260-case creative-graph contract suite and the pre-existing legacy-default
assertions, which is the evidence that behaviour was preserved rather than changed. The intermediate
FAIL run is committed as produced: it failed on **my own** wrong expectation of the exception type
(the structural check fires before pydantic), not on the product.

---

## 4. P1 — Local Runtime registration closure

**Status: `BLOCKED` by the product's own authority gate; `LOCAL_REQUIRED` retained.**

Everything up to registration was already verified in Phase12 — detection, identity, capability
mapping, connectivity, confirmation, and **one real inference** reaching observation level ⑤
`READY` — with a user-confirmed descriptor prepared (`generates_tasks=false`,
`auto_enabled=false`, registration `performed: false`).

Phase13 exercised the next step against a real backend and it is **refused by design**:

```
POST /api/model-center/local-ai/runtimes
  {"name":"Strata (observed)","type":"CUSTOM_HTTP","endpoint":"http://127.0.0.1:8080"}
→ HTTP 401 {"code":"SESSION_REQUIRED", ...}
```

This confirms `app/model_center/discovery_api.py:50-68`: `require_session` is a **router-level
dependency** that raises unless the injected host authority reports `can_mutate`. It is an
intentional security boundary, not a defect, and obtaining or fabricating that session would be a
**bypass of a security control**, which the phase rules forbid. The backend was stopped cleanly
afterwards (port 8111 free).

Consequences, stated plainly: **Registration `BLOCKED`**, **Task Routing `NOT_RUN`**, and
**Live local runtime end-to-end stays `LOCAL_REQUIRED`**. Per the brief's own instruction, it is
*not* upgraded and no success is fabricated.

Evidence: `docs/delivery/v2-development/phase13-runtime-registration-probe.json`.

---

## 5. P2 — real media pipeline

**Status: `PARTIAL` (unchanged from Phase12). No new real chain was claimed this phase.**

The Phase12 chain stands as recorded — Text → Director/Screenplay → shot plan → storyboard →
Export, every row a real product operation with real ids, versions, review transitions, digests and
a real 1930-byte export artefact — and it was **not** re-run here, so it is cited as history rather
than re-claimed.

Image, Video and Audio remain **`BLOCKED_LOCAL_RUNTIME`**: this host has no local image, video or
ASR/TTS runtime (ComfyUI 8188 and the others have no listener; the Whisper host is not configured),
and Timeline depends on their assets. **Nothing mock or cloud was substituted**, per §六.

---

## 6. P3 — Windows RC preparation

`WINDOWS_RC_EXECUTION_GUIDE.md` gained a completeness matrix covering every enumerated item with its
owner and honest state: clean install / uninstall / first start; launcher / backend / DesktopHost /
PostgreSQL; Chinese, space and long paths; crash, restart and cache recovery; and GPU CUDA
discovery / VRAM / model load / image generation / video generation.

Already-verified rows are marked as such and nothing more: the **dev** backend invocation is `PASS`
(8110, `/docs` 200, cleanly stopped) and the **portable-cluster** PostgreSQL path is `PASS` from
Phase10 `phase10-a1-r4`. Everything else is `NOT_RUN`, including all packaged-path items
(`ENABLE_PACKAGED_RUNTIME=false`). GPU image/video generation is
`BLOCKED_LOCAL_RUNTIME`. **No clean-machine execution was performed.**

---

## 7. Standing rules re-affirmed

* **GPU:** capability comes only from hardware discovery; no component detection is treated as
  inference, no VRAM threshold was lowered, and nothing vendor- or model-specific is hardcoded. The
  Phase12 identity fix (`82d1282`) is what keeps discovery truthful — one physical GPU reported once,
  and capability actually granted instead of `(None, 0)`.
* **Model Center:** 发现 ≠ 可运行 is preserved —
  `NOT_OBSERVED → DISCOVERED → RUNTIME_AVAILABLE → REACHABLE → CAPABILITY_UNKNOWN → READY`, with
  `READY` reachable only on real inference evidence. A scanned model is never presented as
  executable.
* **Content policy:** `CONTENT_POLICY_FRAMEWORK` remains **`RESERVED`** — no NSFW/Mature mode, no UI
  entry point, no model filtering, no content-filter system. Only fields, compatibility and their
  tests.

---

## 8. Status table

| Item | Status | Evidence |
| --- | --- | --- |
| Baseline integrity (`f598bee`, `main` `fed2404c`, PR draft) | `IMPLEMENTED` | §1; nothing merged, released or tagged |
| Graph `schema_version` gate | **`IMPLEMENTED` (fixed)** | `5c100e9`; 442 passed, exit 0; illegal versions now refused |
| Frontend port-table duplication | `PARTIAL` | audited precisely (§2); migration **not** performed |
| Runtime level ⑤ `READY` | `IMPLEMENTED` (Phase12, unchanged) | one real inference, 53.7 s, 65 tokens |
| Local runtime registration closure | **`BLOCKED`** (`SESSION_REQUIRED`) | live 401 against a real backend |
| Task routing to a local runtime | `NOT_RUN` | depends on registration |
| Live local runtime end-to-end | **`LOCAL_REQUIRED`** | deliberately not upgraded |
| Real media pipeline | `PARTIAL` | Phase12 model-free chain stands; Image/Video/Audio `BLOCKED_LOCAL_RUNTIME` |
| Windows RC preparation | `IMPLEMENTED` (prep) / `NOT_RUN` (execution) | completeness matrix added; nothing run on a clean machine |
| Clean install / uninstall / packaged DesktopHost | `NOT_RUN` | packaged path never exercised |
| GPU CUDA execution / model load / image / video | `NOT_RUN` / `BLOCKED_LOCAL_RUNTIME` | VRAM measured only |
| Hosted CI | `BLOCKED` | `BLOCKED_ACCOUNT_PLATFORM` — never counted as passing |
| `CONTENT_POLICY_FRAMEWORK` | `RESERVED` | unchanged |

---

## 9. Release-candidate conclusion

**`NOT ESTABLISHED`.** Phase13 fixed one named engineering gap with tests and produced a definitive,
evidence-backed answer for the other: registration is blocked by an intentional authority gate, and
the frontend port table is deliberate cross-pinning whose migration remains open. The remaining
release gates are unchanged and substantial: clean install/uninstall, the packaged DesktopHost
trusted session, a real local runtime actually registered and routed, the media chain's
model-dependent steps, export packaging, and a full CI run.

`M4` stays `PARTIAL`, `M5–M9` `LOCAL_REQUIRED`, the V1 freeze and F00 INTEGRATED + 39 PARTIAL
markers are unchanged, and `CONTENT_POLICY_FRAMEWORK` remains `RESERVED`.

QingJian stayed read-only: no modification, no Interop development, no dual-project linkage. Other
worktrees and other agents' traces were observed only, never altered.

---

## 10. Commits in this phase

| Commit | Content |
| --- | --- |
| `5c100e9` | the `schema_version` gate fix + `tests/test_v2_graph_schema_version_gate.py` |
| final docs commit | this report, the Phase13 matrix append, the registration probe receipt and the Windows guide completeness matrix |

End state: HEAD = remote; PR #47 `OPEN`/draft; `main` untouched; no tracked file dirty; the 39
untracked entries are all protected; no service started by this phase is still running (ports 8110
and 8111 free; the user's Strata server was never stopped).

---

## 11. Limits and recommended next steps

**Limits.** The frontend migration was **not** done (§2) — the largest honest gap in this phase's
scope. Registration could not be completed by a scripted client and was not worked around. The media
chain was not re-run, so its figures are cited from Phase12. Hindsight memory was unavailable.

**Recommended order for the next phase:**

1. **Land the frontend port projection** (§2) — single source, prefer the server-resolved ports,
   keep every structural check; verify with `pnpm exec tsc -b --force` plus the frontend graph tests
   before touching the catalog path.
2. **Register a runtime the supported way**, i.e. through the host-session authority that
   `SESSION_REQUIRED` is protecting — this is the only route that moves "live local runtime
   end-to-end" off `LOCAL_REQUIRED`.
3. **Close the §4 client gap from Phase12** (no readable screenplay `edit_version`) — small, and it
   blocks scripted clients from completing the chain without an export round-trip.
4. **Run the media chain's model-dependent steps** once an image/video/audio runtime exists, filling
   the `BLOCKED_LOCAL_RUNTIME` rows with real artefacts and digests.
5. **Clean-machine Windows pass** (install / launcher / DesktopHost / recovery), then **export
   packaging**, then a full-CI attempt or an explicit decision to stay `BLOCKED_ACCOUNT_PLATFORM`.
