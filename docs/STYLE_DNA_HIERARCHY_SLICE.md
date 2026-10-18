# DIF-09: versioned multimodal STYLE hierarchy (bounded backend slice)

## Ownership and coverage

The existing CreationWorkbenchService `creation_records` STYLE row remains the
only canonical style owner. This slice adds optional `style_dna` to that owner;
legacy omitted fields, old STYLE storage and approval histories remain unchanged.
Legacy `style/profile.json` / novel metadata, VisualTarget, Creative Scene/Shot,
Comic layout/panel and production graph owners are not rewritten or duplicated.

Rules cover writing tone, camera language, composition, color, linework/halftone,
character design, sound and music theme. Explicit precedence is global, chapter,
Creative scene, Creative shot. Targets use original source IDs plus exact
chapter version/content digest or enclosing Creative document version/digest.
Scene and shot ancestry is verified through original owners. Independent scenes
have no inferred chapter. Duplicate same-level target IDs are rejected.

The new POST `/novels/{nid}/experimental/style-analysis/profiles/{rid}/resolve`
returns effective rules, source pins, contributors, overridden values, lexical
conflicts with authored VisualTarget/shot text, and uncovered dimensions. It
requires an approved profile plus expected version/digest. The digest is that
of the persisted row excluding history, using the existing canonical digest.
Generic list/get responses for bound STYLE add `style_dna_resolution`, containing
`stale`, `source_digest` and `execution_adoption: UNSUPPORTED`. This is a response
projection only: do not include it when computing a persisted-row digest.

This is a local, deterministic, read-only preview. It is not semantic conflict
verification, style quality measurement, generation approval or automatic
adoption. No model, queue, asset mutation, manuscript edit or target write occurs.
Full Comic page/panel integration, licensed asset imports, Impact Engine STYLE
sources, production graph consumption and UI remain pending. Existing A02
analysis and execution/adoption for new multimodal STYLE are explicitly rejected
with a bounded unsupported response; ordinary legacy STYLE retains A02 behavior.

## Lifetime, access and repair

A new multimodal STYLE is stamped server-side at explicit creation with the
original Creative project incarnation. Only that explicit create may initialize
an original owner marker. Unbound historical STYLE is not adopted on read/edit;
create a new profile instead. Reads use `existing_owner_only`. Reused public
project IDs cannot adopt old rows, even with identical chapter IDs and text.

All original generic STYLE write/approve/archive/restore/generated-write paths
are fenced. Client epoch injection is rejected. Existing bound rows keep their
original epoch, cannot clear the extension, and cannot restore unbound snapshots.
Generated candidates cannot mint multimodal STYLE. Bound conflict responses
contain only ID/version/status, never original rules/history/source pins.

Source access checks cover current and historical snapshots. Missing, hidden,
secret, retired or privacy-changed chapter/Creative dependencies hide the whole
bound record and its history; generic list does not expose a count or label.
Mere accessible source version/content drift permits a clearly stale repair
read, but resolution/approval cannot use it as current. Editing to fresh pins
is explicit; historical pins remain historical and never become new authority.

HTTP entry points reuse `_workbench_authority_lease` outside Workbench -> scope
-> project leases, preserving original session/role/project ordering. Final
reauthorization protects success and errors. Factory defaults still support
legacy profiles; new bound writes require the injected authority lease.

## Manual integration hooks

The isolated worktree is based on commit
`1c4bd7b383ffb35ca9e311ee30ffed3372b5c78f`. Primary files were not edited.

1. `app/api.py`: pass `authority_lease=_workbench_authority_lease` to the original
   `create_workbench_router` call, retaining surrounding work.
2. `app/experimental/api.py`: pass
   `authority_lease=legacy_api._workbench_authority_lease` to
   `create_style_analysis_router`.
3. Immediately after original `creative_service` construction, instantiate
   `StyleDNAService(creative_service, legacy_api.creation_workbench_service, ...)`
   and assign it to `legacy_api.creation_workbench_service.style_dna_service`.
   Its original feature callbacks require `style_dna_v2`, plus
   `narrative_production_v2` for Creative document reads. Preserve Story/Comic
   wiring in that same area; do not replace their edited API file wholesale.

## Verification scope

Tests use actual existing File repository owners, durable capability sidecars,
ExperimentalStore and mounted production HTTP aliases/authorization. They cover
restart, hierarchy, sibling isolation, source drift, no target mutations,
owner recreation, old-row non-adoption, strict payloads, generic privacy/history
suppression, stale repair labels, sanitized CAS, missing injection, unsupported
bound A02 and revocation between initial authorization and commit/read output.
PostgreSQL cases are parametrized but were not run in this isolated slice. No
PostgreSQL server was started. UI and full DIF-09 acceptance are not claimed.
