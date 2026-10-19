# Requirements traceability — unique V2 index

Version: `ENG-2026.10.19-r1`
Machine-readable source of truth: [requirements-traceability.json](requirements-traceability.json)
Generator: `scripts/build_requirements_traceability.py`
Validator: `scripts/validate_requirements_traceability.py`
Guard test: `tests/test_engineering_traceability.py`

## Why this index exists

The release decision of 2026-10-19 requires the official V2 to include **the original Master
Roadmap release items + DIF-01..DIF-12 + IMAGE-COMIC-01..IMAGE-COMIC-20 + final same-build
acceptance**. Before this index there was no single artifact that covered all three families with
the same vocabulary. This is now that single index; other documents link here instead of keeping
private status tables.

## Source status (honest)

| Source | Status |
| --- | --- |
| `SPEC-2026.10.19-r1` / `PoemSeed_Studio_V2_Release_Scope_20261019.txt` | **INGESTED + HASH-VERIFIED** at [spec/SPEC-2026.10.19-r1.txt](spec/SPEC-2026.10.19-r1.txt): SHA256 `a681eb0f1deff156bbb2a7db437e19cabc11f290d28416f9f0c8fe8bd07785ac`, 37,693 bytes, 352 lines, valid UTF-8. Every DIF/COMIC row binds its section/line/title/MUST/acceptance; the validator recomputes the hash. |
| Original `AI_NOVEL_STUDIO_V2_MASTER_ROADMAP` | Present outside the repository at `D:/PoemSeed/Documents/AI-Novel-Studio_V2/` (MD and TXT). Milestones M0–M12 and module requirements were read directly. |
| `AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md` | Present in repo (append-only history, 2026-10-09 M0 inventory through 2026-10-17 checkpoints). Treated as history, not current status. |
| A/B/U advanced packages | Authoritative in-tree registry: `app/experimental/capabilities.py` — 40 packages (F00 + U01–U16 + A01–A13 + B01–B10), each with flag, dependencies, wave, model/network requirement. The matrix parses this file, never duplicates it. |
| DIF-01..DIF-12 | IDs and titles from the 2026-10-19 instruction; SPEC body missing (see above). |
| IMAGE-COMIC-01..20 | IDs and titles from the 2026-10-19 instruction; SPEC body missing. Existing B06 owner covers a bounded subset and is mapped honestly below. |

## Coverage and counts

The matrix contains four groups. Counts are regenerated into the JSON; run
`python scripts/build_requirements_traceability.py` after editing definitions, then
`python scripts/validate_requirements_traceability.py`.

| Group | Contents |
| --- | --- |
| `ORIGINAL_V2` | M0–M12 milestone obligations plus cross-cutting requirements (single authority, scope/permission, migrations/backup, asset CAS/review, job/UNKNOWN/cancel, model admission, no-model mode, privacy/consent, public/internal edition isolation, UI design system, CI truth, test isolation and cleanup). |
| `ABU_PACKAGE` | Exactly the 40 registry packages, generated from `capabilities.py`. Status reflects `INTEGRATED_PACKAGES` (PARTIAL_INTEGRATED) and becomes `INTEGRATION_VERIFIED` only when its focused owning tests actually pass in this round. |
| `DIF` | 12 differentiated capabilities. All currently `PLANNED`: requirements are now defined by the ingested SPEC (section 2 MUST/acceptance bound per row), but no DIF implementation/acceptance exists. Each row records the closest existing owner (e.g. DIF-02→U06, DIF-08→A06/A07, DIF-09→A02, DIF-12→A09/A13/U14) so future work extends that owner instead of building a parallel one. |
| `IMAGE_COMIC` | 20 comic sub-features. IMPLEMENTED subset: 01 sub-entry, 09 bubbles, 13 page/webtoon; bounded export (18) and a few contracts are partial; the rest are PLANNED. No ORA/CBZ/PDF/EPUB, layers, AI panel generation, pose control, colorization, SFX, pacing, dynamic-comic handoff or comic agent review exist. |

## Current counts (generated at the recorded SHA)

| Axis | Counts |
| --- | --- |
| Total rows | 97 = 25 ORIGINAL_V2 + 40 ABU_PACKAGE + 12 DIF + 20 IMAGE_COMIC |
| Status | 2 BLOCKED, 33 IMPLEMENTED, 36 INTEGRATION_VERIFIED, 26 PLANNED |
| Test result | 1 BLOCKED, 43 NOT_RUN, 17 PARTIAL, 36 PASS |
| Release blocking | 49 HIGH, 47 MEDIUM, 1 NONE |
| Original coverage | 25/25 rows have a resolved owner source; coverage objects record owner/test/evidence existence |
| SPEC coverage | DIF 12/12 and COMIC 20/20 bound to SPEC-2026.10.19-r1 |

Comic rows 01/02/04/09/13/15/18 are IMPLEMENTED/PARTIAL after the round-3 standalone page edit-loop slice;
the remaining comic rows and all DIF rows are PLANNED. No row is ACCEPTED (same-candidate human
acceptance has not happened).

## Status vocabulary (fixed; do not mix with test results)

| Requirement status | Meaning |
| --- | --- |
| `PLANNED` | Not delivered; may have reusable owners or partial contracts |
| `IMPLEMENTED` | Owning source exists and is wired; not yet verified end-to-end |
| `INTEGRATION_VERIFIED` | A real executed integration/browser/media/DB test at the recorded SHA passed |
| `ACCEPTED` | Explicit human/product acceptance under @RELEASE_GATES.md; no automated run grants it |
| `BLOCKED` | Cannot proceed because the environment/source/authority is unavailable; blocker named |

| Test result | Meaning |
| --- | --- |
| `PASS` | The named command executed at the recorded SHA and passed |
| `FAIL` | Executed and failed (defect or test-infra issue) |
| `PARTIAL` | Some layers ran, others are MISSING/NOT_RUN by design |
| `BLOCKED` | Could not execute for an external/environmental reason |
| `NOT_RUN` | Not executed in this round; no claim |

Rule: `PLANNED`/`BLOCKED` requirements cannot carry a PASS result; `INTEGRATION_VERIFIED`
requires `test_result: PASS` and an existing evidence path.

## How to update a row

1. Change the definition in `scripts/build_requirements_traceability.py` (hand-authored groups) or
   `app/experimental/capabilities.py` (A/B/U packages — never edit the JSON directly).
2. Record real evidence under `docs/v2/engineering/evidence/` and update
   `docs/v2/engineering/test-evidence-20261019-r1.json`.
3. Regenerate: `python scripts/build_requirements_traceability.py`.
4. Validate: `python scripts/validate_requirements_traceability.py && python -m pytest -q tests/test_engineering_traceability.py`.
5. Commit the generator change, evidence file and regenerated JSON together.

## Non-claims

- The matrix is a tracking index, not a release certificate.
- `INTEGRATION_VERIFIED` is not `ACCEPTED`.
- The existence of a reusable owner does not make a DIF or COMIC row complete.
- The current baseline is **NOT RELEASE_READY** (see [RELEASE_GATES.md](RELEASE_GATES.md) §6).
