# Requirement sources and evidence authority (V2)

This is the single entry for requirement provenance. The tracking index itself is
[requirements-traceability.json](requirements-traceability.json); this page records which
source text is authoritative, how it was verified, and what is still external.

## 1. SPEC-2026.10.19-r1 (release-scope supplement) — INGESTED

| Item | Value |
| --- | --- |
| Requirement document | `PoemSeed_Studio_V2_Release_Scope_20261019.txt` (provided by the product owner) |
| SPEC version | `SPEC-2026.10.19-r1` |
| In-repository copy | [spec/SPEC-2026.10.19-r1.txt](spec/SPEC-2026.10.19-r1.txt) |
| Bytes / lines | 37,693 bytes / 352 lines |
| SHA256 | `a681eb0f1deff156bbb2a7db437e19cabc11f290d28416f9f0c8fe8bd07785ac` |
| Encoding / integrity | valid UTF-8; source copy and in-repository copy byte-identical (SHA256 match) |
| Header check | starts with the SPEC title and contains the `SPEC-2026.10.19-r1` marker |
| Ingestion date | 2026-10-19 |

The file was copied byte-for-byte (no reformatting) and is verified by
`scripts/validate_requirements_traceability.py` on every run: the validator recomputes the
SHA256/byte/line values and fails if the matrix records a different document.

### What it governs

- `DIF-01` … `DIF-12`: every row's `spec.must` / `spec.acceptance` is bound from this file
  (section 2 headings). No feature is marked complete because its name appears in the SPEC.
- `IMAGE-COMIC-01` … `IMAGE-COMIC-20`: every row's `spec.requirement` is bound from section
  3.2, and the navigating constraint (comic stays inside Image Studio, no new top-level
  module, no parallel Asset/Job/Model/Timeline owner) is a release gate.
- The release policy: original V2 Master Roadmap + all 12 DIF + all 20 comic items + final
  same-build acceptance. Pre-release of V2.1/V2.2/V3 cannot defer them.

### Matrix binding

Each DIF/COMIC row carries `spec.document`, `spec.path`, `spec.sha256`, `spec.section`,
`spec.line`, `spec.title` and the bound requirement text. `spec_coverage` records
`dif_bound = 12` and `comic_bound = 20`. The validator rejects a row with a stale SHA,
empty binding or an unbound requirement id.

## 2. Original V2 Master Roadmap — EXTERNAL REFERENCE

The original roadmap is referenced from the user workspace at
`D:/PoemSeed/Documents/AI-Novel-Studio_V2/AI_NOVEL_STUDIO_V2_MASTER_ROADMAP.md` and is
not ingested into this repository. The 25 `V2-*` rows in the matrix are the in-repository
index of its release-required items and cross-cutting contracts (M0–M12). The
`coverage` object on each original row resolves its owner sources, test files and evidence
paths to real repository files; this is the detail-level coverage proof, not a completion
claim.

## 3. In-tree capability registry — PARSED FROM TREE

The 40 A/B/U/F advanced capability rows are parsed from
`app/experimental/capabilities.py` (server-owned registry). The validator fails if the
registry and matrix diverge.

## 4. Evidence authority rules

1. A requirement is never promoted to `INTEGRATION_VERIFIED` or `ACCEPTED` by a document
   edit: a bound test result with an existing evidence path is required, and `ACCEPTED`
   requires same-candidate human acceptance (not provided by this engineering branch).
2. Test results are reported as `PASS / FAIL / PARTIAL / BLOCKED / NOT_RUN`; a Mock/contract
   result never implies model quality, Windows install acceptance or a public release.
3. If the authoritative source is missing, the row must say `SOURCE_MISSING` and cannot be
   promoted. This happened to DIF/comic rows before the SPEC was provided; it is no longer
   acceptable now that the SPEC is ingested.
4. Old failure evidence is preserved; new rounds append evidence instead of overwriting the
   previous receipts.

## 5. Update procedure for a new SPEC revision

1. Put the new document under `docs/v2/engineering/spec/` byte-for-byte.
2. Update `SPEC_ID` / `SPEC_PATH` / `SPEC_TITLE` in
   `scripts/build_requirements_traceability.py` (and the validator constants).
3. Regenerate the matrix; the loader refuses a wrong title, missing version marker or
   incomplete 12/20 coverage.
4. Update this page's hash/size table and the baseline/release-gate references.
5. Never hand-edit the generated matrix; never delete the previous SPEC copy from git history.
