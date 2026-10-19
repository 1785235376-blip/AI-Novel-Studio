# Single-authority map: Graph / Asset / Job / Review / Timeline

This page is the shared authority map for the V2 engineering work. It states who owns
each concept, how cross-media dependencies are recorded, and which recovery rules must be
preserved. It introduces no second store, queue, registry or database.

## 1. Current owners (source of truth)

| Concept | Owner (single authority) | Evidence / tests |
| --- | --- | --- |
| Project scope / incarnation / actor / session | app/collaboration*, app/trusted_sessions.py, app/actor_context.py, project/scope repositories | origin/revocation/scope tests; workspace_mutation coordination |
| Chapter/text + versions | repositories novel/chapter owners + app/services/chapter_service.py, CAS version/digest | chapter/CAS/stable-identity suites |
| Story graph / typed graph ports | app/creative/ graph owners + app/experimental/story_graph*; typed port validation | graph suites |
| Assets, versions, lineage references | app/services/asset_library_service.py, app/experimental/production_lineage.py, asset_lineage_v2 flag | tests/test_r4_production_lineage.py, asset lifecycle suites |
| Jobs / generation / media tasks | app/jobs.py single JobManager path, app/services/agent_job_service.py, media execution owners | job/cancel/unknown-state tests; UNKNOWN_UPSTREAM no auto-replay |
| Review / approval | review inbox/finding owners (unified_review_inbox, review adapters) | review and comic/image approval tests |
| Timeline / export | app/experimental/studio_timeline*, app/services/studio_timeline_*.py, app/services/video_assembly_service.py | timeline/trim/comic export tests |
| Comic pages/panels/bubbles | app/experimental/comic_layouts.py (+ mounted API) inside Image Studio | test_r5_comic_layouts.py, test_r5_comic_mounted.py, test_v2_comic_blank_edit_loop.py |

## 2. Cross-media dependency rules

1. Downstream assets/screenplays/comic pages record the source identity + version + digest
   they were derived from (asset bindings, screenshot digests, sources maps). A source
   change marks dependent views stale; it never rewrites approved assets.
2. Version conflicts are CAS conflicts (version mismatch), not last-writer-wins.
3. Asset reuse requires an approved asset reference through the original asset owner;
   cross-project reuse must pass the same scope authorization.
4. Local rework creates a new draft/candidate version and keeps the approved version
   available; failure must leave the old formal version intact.
5. Unknown upstream state (network interruption, provider uncertainty) must not be
   automatically replayed or re-paid; expose recovery only.

## 3. DIF/Comic implications

- DIF-01 Story Kernel may add only verifiable relations and derived views over the
  existing text/world owners; it must not create a second canon database.
- DIF-02 Impact Engine must use the recorded dependency graph and show source evidence;
  a name/RAG match is not a proven relation.
- DIF-04 Semantic Rebuild must classify actions (re-typeset / local image / regenerate /
  re-export) before executing and must not regenerate unaffected approved bytes.
- Comic pages follow the same asset/review/CAS owners; the comic demo verifies that a
  text-only bubble edit leaves the panel image bytes and asset version unchanged.

## 4. Current coverage and gaps

- Implemented and integration-tested: version/CAS, asset lineage bindings, change-impact
  preview primitives (app/experimental/change_impact.py, mounted tests), comic page
  review/export, job cancellation boundaries.
- Partially implemented: semantic dependency tracking across Text→Screenplay→Comic→Image→
  Video. Existing lineage covers asset parent/child and pinned source digests; the full
  semantic fact model (DIF-01) is still PLANNED, so end-to-end semantic impact analysis
  cannot be marked verified yet.
- Not implemented: automatic conflict adjudication, cross-media impact acceptance UI,
  Story Kernel fact arbitration.
