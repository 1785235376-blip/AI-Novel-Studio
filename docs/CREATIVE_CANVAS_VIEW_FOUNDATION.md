# Independent media display-view persistence foundation

Status: bounded backend foundation; API/UI mounting and browser acceptance are NOT complete.

The existing CreativeGraphService now owns an additional display-view collection through its original CreativeProjectStore. It stores up to 1000 image/video/audio Asset reference cards separately from the execution definition's 96000-byte budget. Execution DAG limits remain exactly 16/24 nodes; view records have no ports, edges, model calls, runs or execution authority. No second workflow engine, Asset store or job queue exists.

The new collection participates in original incarnation filtering and the same shared Graph scope/record/history capacity checks. It has an eight-view collection bound, a 512000-byte definition bound, original bounded positions/viewports, actor-private access, strict CAS and fixed-create-request identity. Empty existing collections do not acquire extra legacy capacity overhead. Retained old-incarnation rows are not adopted by reused project IDs.

All asset metadata is checked inside the original scope → asset → project phase, with original leases retained through commit. Only original public project/branch image/video/audio references are accepted; actor-private candidates are refused. Reads label exact matches CURRENT_METADATA, source changes STALE and missing/private/deleted sources UNAVAILABLE. Unavailable bindings are omitted from the returned card. Explicit full replacement may remove unavailable cards, but cannot silently adopt stale/new source versions. Actor/project authority checks are not converted into ordinary unavailable-source states.

No binary payload is loaded for display metadata. Actual preview/download remains with the original Asset owner. The service explicitly reports binary_content_verified=false and execution_authority=false. Source filenames are returned only from exact current original metadata. History remains retained internally, not exposed through an unguarded new history route.

Evidence:
- Real File and PostgreSQL each saved, explicitly edited and reopened 1000 distinct display cards referencing four actually imported PNG assets. This is not a claim of 1000 unique assets or media decoding throughput.
- The thousand-card test forbids Asset.content during view operations and confirms no graph or run record is created.
- Actor separation, same-public-project-ID recreation, legal new-owner creation, stale/deleted masking, explicit removal, original private Asset refusal, request-ID/CAS rejection, collection quota and final-authority rollback are covered.
- Initial broader File/Graph/catalog/PUBLIC selection: 281 passed, 1 new test failed, 16 PostgreSQL cases deselected. The failure correctly required the original Asset project scope in the test's metadata update. Only that new test was corrected to use the original scope and a permitted metadata field; no old test or product guard changed. Corrected focused File selection: 5 passed, 5 deselected. PostgreSQL new and original Graph persistence: 16 passed, 16 deselected, OID 16384 retained and server stopped.
- Actual PUBLIC wheel/metadata tests passed within the initial broader selection. Product source is unchanged since that run; only the new test correction followed. The two STANDARD display-view modules were added to the existing public allowlist; private-backend exclusions are unchanged.

API routes have not been mounted and no user-visible canvas or thousand-card browser FPS/memory acceptance is claimed. New model/reference kinds, reusable subgraph behavior, UI culling/selection/editing, view cleanup and final product acceptance remain subsequent work. Existing frontend source/build is unchanged in this backend slice.

Current API count remains 2367; source fingerprint 816b8c056ab8db69aea3fc44eb05ac048f72e0102a89ac7f8ebdc4f38c11e15e.
