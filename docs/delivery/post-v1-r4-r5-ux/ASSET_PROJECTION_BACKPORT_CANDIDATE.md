# Shared asset and media projection hardening candidate

This is a follow-on shared-surface fix, not an authorized backport. PR37 and its frozen acceptance evidence are unchanged.

Legacy asset upload/list/get/import/accept/derivative/trash/restore responses now use `AssetLibraryService.public`. It copies the response and hides only the new reserved `parameters.asset_lineage_v2` field when A09 is disabled or V1 acceptance mode is active. Persisted metadata, original asset bytes, pre-existing `source_asset_ids` and unrelated parameters remain intact. Internal asset reads are not stripped.

Legacy media task projections similarly hide new queue/runtime provenance and production pointers, including historical task snapshots, when A13 capture is disabled. These projections do not turn off existing media operations or erase history. The reserved lineage parameter cannot be manufactured or erased by old user-controlled generation parameters.

Candidate applicability: useful only where the new experimental metadata exists. A frozen older build has no such fields; review whether any backport is actually warranted before porting. Separate user authorization, a narrowly scoped port and full frozen-target regressions are required. No merge, release, backport or acceptance is implied.

Verification is in `test_r4_media_evidence.py` and `test_r4_production_mounted.py`: opt-in evidence then OFF/V1 projection, idempotent upload response, normal list/get, trash/restore, unchanged internal evidence and ordinary fields. File and real-PostgreSQL parametrizations are kept distinct; hosted exact-SHA receipts establish which profile ran.
