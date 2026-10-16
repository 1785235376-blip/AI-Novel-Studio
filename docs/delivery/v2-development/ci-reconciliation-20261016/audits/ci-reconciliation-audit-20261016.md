# CI reconciliation audit

Static Git-blob audit of 72e636f87c7299a62cb3357bcb6a6e44a9388883. No tests or collection ran. No repository edits.

## Counts

{
  "frozen_v1_nodes": 9151,
  "v2_nodes": 15142,
  "v2_source_entries": 2372,
  "v2_stale_source_fingerprints": 129,
  "new_source_entries_under_existing_traversal": 143,
  "protected_v2_drift_files": 43,
  "unapproved_frozen_v1_protected_drift": 16,
  "new_backend_files_missing_inventory": 22
}

## Authoritative sources

Restore commit: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3
Frozen V1 SHA256: 6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262
V2 SHA256: 9d9b8157f1f342ff680e6119b4338a30332a1cec970d5cb00faa10fc01193aca
Old rows: 72e636f87c7299a62cb3357bcb6a6e44a9388883:docs/delivery/v2-creative-save-state-20261017/collection-confirmation-rows.json.gz
Old row gzip SHA256: 8a63aa4ad872695d1699816910647dec8070f2566f9a8aea3eb3943ffa9bbd34
Old row classification SHA256: e7e543708b0ac8ebd1f81f77262a4afa6503d222af2b2e0ad9e71d6a749754d6

## Disjoint work groups

### creative_and_canvasops

- frontend/src/canvasops/canvasOps.test.ts
- frontend/src/canvasops/canvasOpsPanels.test.tsx
- frontend/src/creative/AIDirectorPanel.test.tsx
- frontend/src/creative/AssetRelationshipsPanel.test.tsx
- frontend/src/creative/GraphCanvas.test.tsx
- frontend/src/creative/IndependentStudioAudioWav.test.tsx
- frontend/src/creative/IndependentStudioGraphWorkspace.test.tsx
- frontend/src/creative/IndependentStudioReadFences.test.tsx
- frontend/src/creative/IndependentStudioRelationships.test.tsx
- frontend/src/creative/IndependentStudioWorkspace.test.tsx
- frontend/src/creative/StudioImageGraphEditor.test.tsx
- frontend/src/creative/StudioImageRuntimeProduction.test.tsx
- frontend/src/creative/StudioProductionGraphEditor.test.tsx
- frontend/src/creative/StudioVideoGraphEditor.phase4.test.tsx
- frontend/src/creative/StudioVideoShotBinding.phase5.test.tsx
- frontend/src/creative/graphCanvasGeometry.test.ts
- frontend/src/creative/studioAudioFlacContract.phase6.test.tsx
- frontend/src/creative/studioGraphClient.test.ts

### other_frontend

- frontend/src/AppAuthorTaskNavigation.test.tsx
- frontend/src/delivery/DeliveryCenterPanel.test.tsx
- frontend/src/experimental/BranchManuscriptPanel.test.tsx
- frontend/src/experimental/ComicLayoutsPanel.test.tsx
- frontend/src/experimental/ExperimentalWorkbench.continuation.test.tsx
- frontend/src/experimental/InteractiveStoryPanel.test.tsx
- frontend/src/experimental/ModelBrokerPanel.test.tsx
- frontend/src/experimental/MultilingualEditionsPanel.test.tsx
- frontend/src/experimental/ProductionLineagePanel.test.tsx
- frontend/src/experimental/ResearchLibraryPanel.test.tsx
- frontend/src/experimental/StorySimulatorPanel.test.tsx
- frontend/src/experimental/StyleReviewPanels.test.tsx
- frontend/src/experimental/VoiceSubtitlePanels.test.tsx
- frontend/src/experimental/WriterRoomPanel.test.tsx
- frontend/src/modelcenter/ModelCenterPanel.test.tsx
- frontend/src/prompt/PromptWorkspace.test.tsx
- frontend/src/taskcenter/TaskCenter.test.tsx
- frontend/src/taskcenter/taskCenterClient.test.ts

### backend_seven_and_mp3

- tests/test_r4_story_simulator.py
- tests/test_r5_comic_layouts.py
- tests/test_r5_interactive_story.py
- tests/test_round2_bible.py
- tests/test_v2_audio_flac.py
- tests/test_v2_creative_graph_persistence.py
- tests/test_v2_director_workspace.py

## Extraction discipline

- Restore exact a072cf9 protected bytes after preserving genuine additions in NEW files.
- Extract only new scenarios and minimal fixtures/imports; do not duplicate whole suites.
- Never import frontend .test/.spec files as helpers; that re-registers suites.
- Python helper imports must not import test_* functions into collection scope.
- Changed old assertions/selectors do not count as added coverage.
- Ranges are from 47d85f7; all 43 protected blobs are verified unchanged at 72e636f.

## Per-file exact ledger

### frontend/src/AppAuthorTaskNavigation.test.tsx

- Classification: additions_and_shared_harness
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 4f2ede4cae19146e65978b9c1c1423a314eeeb20
- Expected SHA256: 4a487c21efed37b83f1875d52f923e4c692906497182810f0bb2a4fa5b06d5ba
- Current SHA256: c71612b2e904c0efd00c416ad9a9c467a5430cdf401ba6465c3dee10ee408d09
- Preserved local SHA256: c71612b2e904c0efd00c416ad9a9c467a5430cdf401ba6465c3dee10ee408d09
- Extract ranges: 179–187
- One new case; modified DeferredExperimentalWorkbench mock and flags/setup. Extract independent minimal harness; restore original mock/setup.

### frontend/src/canvasops/canvasOps.test.ts

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 702e7b1ba5b221692dce0c35e13600b38f040110
- Expected SHA256: b22b4aba7143a65a53e6dab9ad1a1a9b969346fb3a19827ac84e5a190b5b5541
- Current SHA256: c284713bc1788998f17cf46ad5f47520749e25f6dc9307f94185786adf86d3e7
- Preserved local SHA256: c284713bc1788998f17cf46ad5f47520749e25f6dc9307f94185786adf86d3e7
- Extract ranges: 191–206
- Tall-card layout; graphNodeHeight import.

### frontend/src/canvasops/canvasOpsPanels.test.tsx

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 7aadc6fdeb570019292df8be24c46a30b465691f
- Expected SHA256: ffd2214f07612bd2a7b5bfe209c4b3ac8a50b7b2d3c622b56dd8e40d139ef7c6
- Current SHA256: e3cee8da677f5780cca7c5846f88238dcf30a9dde069fdb83be6f987d2fc3b9a
- Preserved local SHA256: e3cee8da677f5780cca7c5846f88238dcf30a9dde069fdb83be6f987d2fc3b9a
- Extract ranges: 407–421
- Explicit original-owner apply callback; readonly/no-op/preview-only.

### frontend/src/creative/AIDirectorPanel.test.tsx

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 1f28192ead4a05ad5d5788c7b9b23b24a81712be
- Expected SHA256: d2bdffa0f00809bf634ec5f104f5690ac7826c82060c72d6d762b847006c807e
- Current SHA256: 6e487b0fc56cf37a01e3e69aec334ee9e7ab7ee492fb8ba5fb0eb3e6e5248dc4
- Preserved local SHA256: 6e487b0fc56cf37a01e3e69aec334ee9e7ab7ee492fb8ba5fb0eb3e6e5248dc4
- Extract ranges: 33–69
- Estimated totals/editable reasoning; Unicode genre bounds.

### frontend/src/creative/AssetRelationshipsPanel.test.tsx

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 5dbb000172d51abd9be7b9723b60dda11f0cb434
- Expected SHA256: d6519fb759c3eda33b6a34065ae07b55e9952672213ed9acfc3e3e8d8a9bb304
- Current SHA256: a94f6f49c496113ac343010bf3b8732a6d2de89f1612bb3bcb3cc86f016fb07a
- Preserved local SHA256: a94f6f49c496113ac343010bf3b8732a6d2de89f1612bb3bcb3cc86f016fb07a
- Extract ranges: 116–126
- Incoming-reference impact/incomplete coverage.

### frontend/src/creative/GraphCanvas.test.tsx

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 238069c0be98a76c7e9d19c88655c4d75816c5a9
- Expected SHA256: b43f83267da21c9e07d2abd1f2b5eda96c461d540ca83ef2d5c92aa65920e720
- Current SHA256: 88befc61c831311a672e58efa63a18b784d6581b0cef9661715d87432922e6d7
- Preserved local SHA256: 88befc61c831311a672e58efa63a18b784d6581b0cef9661715d87432922e6d7
- Extract ranges: 51–140; 288–889
- Groups, annotations, culling, keyboard directory/search, MiniMap, alignment, snapping, outlines/collapse/preferences/nesting, notes/IME. Preserve new helpers and act import.

### frontend/src/creative/IndependentStudioAudioWav.test.tsx

- Classification: legacy_rewrite_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / cfb92a40ad8b2650b4f72882e8eeddf9207ac3ef
- Expected SHA256: c77221921f4086306f1e8dbb2684adbd9d39a333df4c7d1611a69514f58fc301
- Current SHA256: 7ddfc98bbcee5a97365d001f26f7d0a600641bc656175e6c297650927830a748
- Preserved local SHA256: 7ddfc98bbcee5a97365d001f26f7d0a600641bc656175e6c297650927830a748
- Extract ranges: No appended scenario
- WAV missing-measurement text changed; no added scenario.

### frontend/src/creative/IndependentStudioGraphWorkspace.test.tsx

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 8e779703c5a556794b2fb7d8bd0995cf2e184775
- Expected SHA256: e1784ac7fff429a65120f0a31d0d9155ed3bf50637db4812ea76d3c6d7c4a017
- Current SHA256: eab9b0ed4a9b740fb196b7e4484b9619e553bfb06f2aeb70fc08c5533d33e7a2
- Preserved local SHA256: eab9b0ed4a9b740fb196b7e4484b9619e553bfb06f2aeb70fc08c5533d33e7a2
- Extract ranges: 68–201; 231–414; 446–469
- Copy/paste/presentation/dirty navigation/layout/snapping/camera/search/save failure/nested groups. autoLayout import.

### frontend/src/creative/IndependentStudioReadFences.test.tsx

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: this_round_only
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / c32089cc3d74870c46828e19b095516ab5648229
- Expected SHA256: 8c46f4c8adbb93a8fe9c41f101facccd9b77d0f945a88c74242edf172d0aedd7
- Current SHA256: ea1665baac97b28fd87f0d31423ef5ec0f4d4d34c8dddc690a0ed30233447ce4
- Preserved local SHA256: 8c46f4c8adbb93a8fe9c41f101facccd9b77d0f945a88c74242edf172d0aedd7
- Extract ranges: 54–81
- New parameterized refresh fences and 401/403 private-view removal.

### frontend/src/creative/IndependentStudioRelationships.test.tsx

- Classification: legacy_rewrite_only
- Group: creative_and_canvasops
- Provenance: inherited_and_this_round
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / cfe3959b120b92da4e9a9faee5379f34aa777b76
- Expected SHA256: 22aad113c48d1d776c88f61aee416f56f76ffe4a13d5551e1963166a8650e76b
- Current SHA256: 33881c75d4b4c0a20275c00f97078a6c22825d7a19a43b9081f2f6bea7b6097e
- Preserved local SHA256: 8b49d5e2e7757e8572ca447d9297a2a501d3a2bc34f1b8b3d5d74c2a8f979f71
- Extract ranges: No appended scenario
- CAS alert selector changed; no proven production defect statically.

### frontend/src/creative/IndependentStudioWorkspace.test.tsx

- Classification: additions_and_legacy_rewrite
- Group: creative_and_canvasops
- Provenance: inherited_and_this_round
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / f7dbb025443b965fd88f7265769810e8f139abc5
- Expected SHA256: 91c6abb128213910e79bdaf9772f92a73c3ca0309e7235ce79332be927935cec
- Current SHA256: 8e20681a7e02fad408afbc631d7b608d703d668dc0d83d68be78b323a1f831dd
- Preserved local SHA256: bee5ca1868dfa66a78a614c279171a1c54ec5e9757643dce07458f60d727b56b
- Extract ranges: 149–300
- New asset/timeline/image/video/TaskCenter/relationship/ABA navigation. Restore original generic CAS alert selector; no proven production bug from selector rewrite.

### frontend/src/creative/StudioImageGraphEditor.test.tsx

- Classification: legacy_rewrite_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 0fad28328809081f08b1eb8dfb659c6ecd981d3a
- Expected SHA256: b5088d2b896079eb7f70870acd30e2a0cbfa03005151064cfb6c5633adecc689
- Current SHA256: 54f7a3f530a1e7c6152ccab576021b5db0a7531b59543d73a467b52bd058922a
- Preserved local SHA256: 54f7a3f530a1e7c6152ccab576021b5db0a7531b59543d73a467b52bd058922a
- Extract ranges: No appended scenario
- Old raw provider/model authoring rewritten to picker; shared mock added. Preserve focused new picker variant only.

### frontend/src/creative/StudioImageRuntimeProduction.test.tsx

- Classification: legacy_rewrite_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 913b74695f0c1c633764675e3073e0ed0bf21049
- Expected SHA256: 1aa762009842fc6432047cccb7fc826c624ab1b2a776f8266aa3388f32fa0e08
- Current SHA256: cface23447f119430acc562c19c545946562b0bb1627574d79c8a715254d6e0e
- Preserved local SHA256: cface23447f119430acc562c19c545946562b0bb1627574d79c8a715254d6e0e
- Extract ranges: No appended scenario
- Shared choose() now selects cloud for remote fixture; no new scenario.

### frontend/src/creative/StudioProductionGraphEditor.test.tsx

- Classification: additions_and_legacy_rewrite
- Group: creative_and_canvasops
- Provenance: inherited_and_this_round
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 64fb41bab1c4bdd61a5b77cfeadf76496274af0b
- Expected SHA256: 6663a2cb4fb2f63b1d0aabf7e41a6ca9e2b8bd47f20a969c5909c55fcaab26af
- Current SHA256: 814ca68447d2dd16dd5ad3a84e2ed1a2b2ca4e62a46d05ff9ab6bf1fe9c41b2f
- Preserved local SHA256: d93b207b4fca182d30cf307ba1e4b435dadc6efa699d404a1e7a5cad3969a6ec
- Extract ranges: 80–96; 115–248
- New Director pins/create/save/reopen/unknown-outcome/storyboard/proposal cases. Restore original direct upscale-provider/model input scenario; focused picker variant separately if distinct.

### frontend/src/creative/StudioVideoGraphEditor.phase4.test.tsx

- Classification: legacy_rewrite_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / ef110aaf6d6c81293b267854303dd3d2b835c6d2
- Expected SHA256: c1692f4a68969fa3fb728061804546453f2c1bdf394bb7a00f794d114dfaf3a3
- Current SHA256: 7cc222e3744a1708b90aeeff8eae711d014274b9d04b9327e32a2d2179d3a5d6
- Preserved local SHA256: 7cc222e3744a1708b90aeeff8eae711d014274b9d04b9327e32a2d2179d3a5d6
- Extract ranges: No appended scenario
- Old raw provider/model authoring rewritten to picker; shared mock added.

### frontend/src/creative/StudioVideoShotBinding.phase5.test.tsx

- Classification: legacy_rewrite_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / f4589820a7637e05e7086174fe62cfc4ba13c11a
- Expected SHA256: 3d1984b1984d19f1c0fa42d74d3f136c648ecb42eb15cfe5885c408161ab087e
- Current SHA256: a25a3b8b802efc80a8e0d7985f0b843031fa365089b662109dc747134291de78
- Preserved local SHA256: a25a3b8b802efc80a8e0d7985f0b843031fa365089b662109dc747134291de78
- Extract ranges: No appended scenario
- Old unbound-video authoring rewritten to picker; shared mock added.

### frontend/src/creative/graphCanvasGeometry.test.ts

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / ad2b7580458fd213dbad945da59e22599abf489b
- Expected SHA256: b0f03093d808b07d21d9f8d62231e2f31c3f756f75d37a0e98a22ba65f74441b
- Current SHA256: 7c37d461af7fcff3594a453068302636caa4845b8b96fca2abaf388b01aa3c30
- Preserved local SHA256: 7c37d461af7fcff3594a453068302636caa4845b8b96fca2abaf388b01aa3c30
- Extract ranges: 19–29; 104–163
- Deleted group membership/alignment/snapping; added imports.

### frontend/src/creative/studioAudioFlacContract.phase6.test.tsx

- Classification: legacy_rewrite_only
- Group: creative_and_canvasops
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 699000a06541fe97a474082912b3e448270a6bff
- Expected SHA256: 4ff56d7828b78fbcae16119d5f1cc6d69e9e5f4d5c9c8e32d28745d5cbc6718b
- Current SHA256: 9d014df459625f56016c4e3ad00766c6aa91a3cbc8a98a0ed326027fe930a3fd
- Preserved local SHA256: 9d014df459625f56016c4e3ad00766c6aa91a3cbc8a98a0ed326027fe930a3fd
- Extract ranges: No appended scenario
- Negative MP3 parameter replaced by mp3; actual old contract conflict.

### frontend/src/creative/studioGraphClient.test.ts

- Classification: additions_only
- Group: creative_and_canvasops
- Provenance: inherited_and_this_round
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 61c26fe057155f88a6defc1449255ca026194311
- Expected SHA256: fd2cc0df2be525c1fa333979168757cbda9d4118c091d8597f0169ec0604dd7b
- Current SHA256: a250b74c3e409063b8aa008f687f0856efc03391058ccb9fb9e24168162489fd
- Preserved local SHA256: 0c89deccade879344b722392ae6eec9fdc10080819521e89caceae3faf635eb0
- Extract ranges: 60–167
- Capacity/presentation/notes/preferences/nested-group transport.

### frontend/src/delivery/DeliveryCenterPanel.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 98f2926c3f542cf7f58fed5030b2ed6f63ac7068
- Expected SHA256: faf10568ab7f33bb6330bd1d148a0a7e72024ccb141184a541e8869c16f67965
- Current SHA256: 4a2abdc60b9a0e842804b727a68bdbe6de26c14189670d1fd54261c04f331901
- Preserved local SHA256: 4a2abdc60b9a0e842804b727a68bdbe6de26c14189670d1fd54261c04f331901
- Extract ranges: 208–252
- Loading/failed receipt recovery and pagination distinction; act import.

### frontend/src/experimental/BranchManuscriptPanel.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 6c9bc39ae29570aae29a25ce7eaecca0e13339b8
- Expected SHA256: 4572228cdf7e1a6fc4c6bfd852cebdb0bfadd13b1dff7dad9331eaed5008340f
- Current SHA256: 14bd53f5ee41a19b1a9e7388147dc63e6e23a7d061c211d9c9eddbb32fb04eaf
- Preserved local SHA256: 14bd53f5ee41a19b1a9e7388147dc63e6e23a7d061c211d9c9eddbb32fb04eaf
- Extract ranges: 98–133
- Comparison review/manual preservation and cancellation after owner replacement.

### frontend/src/experimental/ComicLayoutsPanel.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / a43874ab48659e168e7bc52a211175a003b11a70
- Expected SHA256: 9a93f27b9bb27b19a09cbc61aec2a6baa9135ec49c360ba895bb35ee574a037b
- Current SHA256: 60ff70aa0f8da2996f891a463a9a4d16689579bf6dca4192f96bf6e5d5abd5fe
- Preserved local SHA256: 60ff70aa0f8da2996f891a463a9a4d16689579bf6dca4192f96bf6e5d5abd5fe
- Extract ranges: 122–208
- Arrangement preview/apply/undo/save/invalidation/callback fencing/409/500/ABA.

### frontend/src/experimental/ExperimentalWorkbench.continuation.test.tsx

- Classification: additions_and_shared_harness
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / f0512cf61e6dc6196e8056d08485b7225fa04e34
- Expected SHA256: bc729f8375b617fd0eb0b319743ce069b04b1f12f8ed7959392fe88cb9b5dc0c
- Current SHA256: 33aa2fa77288d6af9e24365885825951378c2d5a1346b473ad9ecbd5ca9d85ba
- Preserved local SHA256: 33aa2fa77288d6af9e24365885825951378c2d5a1346b473ad9ecbd5ca9d85ba
- Extract ranges: 44–63
- New planning/simulator mocks/captures and exact-reference/disabled-feature cases. Independent minimal harness.

### frontend/src/experimental/InteractiveStoryPanel.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / fff62b8b90f3c03da9376e59c84f0b4b3b05f0bc
- Expected SHA256: 1505388472a0d9b7c97cb7e0ad1dfcac8d945fc31414417aa91c5fadaf6f6a85
- Current SHA256: 35e1898bb7a1e4aced9093c6430ad207960fa14f314d5d4cd3a23fa0f48f082d
- Preserved local SHA256: 35e1898bb7a1e4aced9093c6430ad207960fa14f314d5d4cd3a23fa0f48f082d
- Extract ranges: 153–311
- Issue identities/pagination/dirty+IME preservation/pending save/version/ABA.

### frontend/src/experimental/ModelBrokerPanel.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 3941a4b6dded8600faa8091d4bbc6fb1ee12ecd8
- Expected SHA256: e0827c1f6240974ecf2c612871f0de5d3d4e629a354a4a7a0e2269fe78179075
- Current SHA256: aead0f49773c962c5a02347be4b9afc53d1f1c96c246c4eb6962bac99ce3ddcc
- Preserved local SHA256: aead0f49773c962c5a02347be4b9afc53d1f1c96c246c4eb6962bac99ce3ddcc
- Extract ranges: 175–261
- Explicit routes/ambiguous identical retry/saved-chapter gating/pre-dispatch outcomes.

### frontend/src/experimental/MultilingualEditionsPanel.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / fe0af3aa8c82ec96fd73e80c858626f23c9cba77
- Expected SHA256: 2fac8a2d10d48b54834042a81bdbaf2194ff0a75a14cd67f2a11b2b44f64dda2
- Current SHA256: 54be2f23bec2cecbe300967755827124a9c0d3dbcdd4ab523a9416d12ddad72f
- Preserved local SHA256: 54be2f23bec2cecbe300967755827124a9c0d3dbcdd4ab523a9416d12ddad72f
- Extract ranges: 136–200
- Terminology exact-rule navigation/withheld and same-edition evidence/IME.

### frontend/src/experimental/ProductionLineagePanel.test.tsx

- Classification: legacy_rewrite_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 832d1c03bdea6444d6d42b3d49dd0bb0fba7c335
- Expected SHA256: 20e1d4c01948e102ddb3aaed381255447f701c0fe312f924e489f2ce46923ec2
- Current SHA256: dc3c7a621f7fd253d4c12c2144077b7da14d35ac2296fd14737411d02e509ecf
- Preserved local SHA256: dc3c7a621f7fd253d4c12c2144077b7da14d35ac2296fd14737411d02e509ecf
- Extract ranges: 138–141 rewrite only
- Old single-click navigation replaced by two-step exact-source confirmation. Zero new declarations; retain exact-source verification in production.

### frontend/src/experimental/ResearchLibraryPanel.test.tsx

- Classification: additions_and_legacy_rewrite
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / c1839fedd901294f8da126935beef7ba8dbe1255
- Expected SHA256: 05dd318c616a7fd93847531df9614b1f84f666ffcc548728be815cbe00e997ce
- Current SHA256: de00574e6b922ca534870a23da376b19cf483b75e947596fc20471167fbeb1e9
- Preserved local SHA256: de00574e6b922ca534870a23da376b19cf483b75e947596fc20471167fbeb1e9
- Extract ranges: 157–170
- New page-only citation location case; restore old line-27 wording assertion.

### frontend/src/experimental/StorySimulatorPanel.test.tsx

- Classification: additions_and_legacy_rewrite
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 3a77f0566a2a29ee99ba4031c8e70628e9ae1147
- Expected SHA256: c9e50d46275dd39baf98b684630c0a83e89f2fa1d84e1e68dfcf58e3c14099aa
- Current SHA256: 62347f6c757041e6b83247960f7fdc98d954586439331039fcd315134832022f
- Preserved local SHA256: 62347f6c757041e6b83247960f7fdc98d954586439331039fcd315134832022f
- Extract ranges: 233–297
- New durable-review/wrong-run/ABA/consent-clearing and SimulatorInput import. Restore old exact callback payload at line 76.

### frontend/src/experimental/StyleReviewPanels.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / b4d8dff581f1dc1200ab9bc61e9bad8d706dfc99
- Expected SHA256: c64c520aee5b550954a17d28270955271ed94a6540c466c9e2e12852aaff347f
- Current SHA256: 20623169bd2c17abf31dd6702f82496aa950f63fda65bcbf927e4cd085ef90ad
- Preserved local SHA256: 20623169bd2c17abf31dd6702f82496aa950f63fda65bcbf927e4cd085ef90ad
- Extract ranges: 234–251
- Saved target comparison/cancelled navigation preserves manual input.

### frontend/src/experimental/VoiceSubtitlePanels.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / f0965e6c09a9b322e944644bd461885a19e86e3e
- Expected SHA256: d81ab1d6b07667e7897dad116c6a6c0b5bb6df0ee33ec7d2ee5994ad4ca523c5
- Current SHA256: 86d702c3fef1822a35c43daf5cc8c682afed70eea634a9693e6233ad979040bc
- Preserved local SHA256: 86d702c3fef1822a35c43daf5cc8c682afed70eea634a9693e6233ad979040bc
- Extract ranges: 82–101
- Subtitle compatibility review/focus/unsaved preservation/refresh failure/reset.

### frontend/src/experimental/WriterRoomPanel.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 188a23a3207d7041054ea332bf9c6fa3bb5330ff
- Expected SHA256: 6328fe83551721ff88fd5b6d0196494923b6ec94ca8815999b2b3ff242d99d14
- Current SHA256: 7050e594f92ca971f41752ef85b1ddbcacf7427877a3c2f625779a6998141e35
- Preserved local SHA256: 7050e594f92ca971f41752ef85b1ddbcacf7427877a3c2f625779a6998141e35
- Extract ranges: 126–199
- Pinned revision/unavailable revision/notes/unknown transition/delayed-context cancellation.

### frontend/src/modelcenter/ModelCenterPanel.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 5a0fd93c54aa5cf8276e393026afbe750f31c721
- Expected SHA256: a4f10468dca1f10cd1a8e1fa1d565ced2430315dff3687c57c867f61f877d3ed
- Current SHA256: 169e50d5bbfda7b3339dacba0b9288e53aaf9fdf87ca48a9353627283218cbb9
- Preserved local SHA256: 169e50d5bbfda7b3339dacba0b9288e53aaf9fdf87ca48a9353627283218cbb9
- Extract ranges: 324–412
- Partial-read recovery/unknown-empty distinction/retained facts/loading/denied advice.

### frontend/src/prompt/PromptWorkspace.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / a87d37f4ed9d25fa3ca2d51116593c7422409143
- Expected SHA256: cc238d1c16293c18757e48cdd399b9cc71c4c5763307e2cbe08502b3142a9a13
- Current SHA256: a2989c9df5e8b462ea64a7c61e222f4f3446528fbdfec6b5dd5f1dbb133aa18b
- Preserved local SHA256: a2989c9df5e8b462ea64a7c61e222f4f3446528fbdfec6b5dd5f1dbb133aa18b
- Extract ranges: 189–332
- History search/comparison/advanced correction/family errors/clipboard rescue.

### frontend/src/taskcenter/TaskCenter.test.tsx

- Classification: additions_only
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 93f5e098acab3c130807ccc171c455ac6fc1bd12
- Expected SHA256: 40f7bbe957e898b5b781395c4261981b70d05a2691dbeca4c2dd63c7de7bf1c8
- Current SHA256: 316e5439ce061b4b4aa8e24754285d83f7f90b55814d798e29679838cb0246f4
- Preserved local SHA256: 316e5439ce061b4b4aa8e24754285d83f7f90b55814d798e29679838cb0246f4
- Extract ranges: 336–391
- Receipt evidence/retained tasks after read failure/unsupported media guidance.

### frontend/src/taskcenter/taskCenterClient.test.ts

- Classification: additions_and_legacy_rewrite
- Group: other_frontend
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 92ad6ac18ca08701d6d2bc80ad72b6aefc5b97e0
- Expected SHA256: 2f5b57f703c2a4f5c7b5ca5d67936fc153174b8ddaddd6ec2a1f5e4489c8dbf3
- Current SHA256: d4000520e6117ff6c5bcb1f588b9f8698c95fcb7e5e0f793ee97669827a0c84b
- Preserved local SHA256: d4000520e6117ff6c5bcb1f588b9f8698c95fcb7e5e0f793ee97669827a0c84b
- Extract ranges: 195–238
- New receipt transport/failure/scope cases. Restore original title/five-key API; separate companion interface.

### tests/test_r4_story_simulator.py

- Classification: additions_only
- Group: backend_seven_and_mp3
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 5ccc18e6f7a7bd4e3a9fd579c9820de943c18c79
- Expected SHA256: 766f002bc7b2e2a7114baa61e6ae7374ce4b981831995b8a8984f6199e74f038
- Current SHA256: 63b5139cfed2670d5eafebdd32e408622e7fd4cccb1287bc1da0799fa4040e77
- Preserved local SHA256: 63b5139cfed2670d5eafebdd32e408622e7fd4cccb1287bc1da0799fa4040e77
- Extract ranges: 248–end
- One appended saved-route restart/reopen test; original AST unchanged.

### tests/test_r5_comic_layouts.py

- Classification: additions_only
- Group: backend_seven_and_mp3
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 82196794a2a58da9b105f127578ca68fa5d8a992
- Expected SHA256: 2d24b7dd1b8a244cffef94d9d9106fb1b5dffd91ae92061e32f8a5a2a9dc9120
- Current SHA256: c4d66c56bad34f23635af5373ee477ac38dc9b6b41c44b7a5d2f7ad8912965ff
- Preserved local SHA256: c4d66c56bad34f23635af5373ee477ac38dc9b6b41c44b7a5d2f7ad8912965ff
- Extract ranges: 221–end
- One appended arrangement/history test; original AST unchanged.

### tests/test_r5_interactive_story.py

- Classification: additions_only
- Group: backend_seven_and_mp3
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / e7a89f6312269ce955af320618625db572ef9344
- Expected SHA256: 8f4bc6e70581ce5f5512517df425e793713604c77854594bdac44f7d2cb6a907
- Current SHA256: f2f355c417f8c2def70afdb8dca4728ecd4773b9fec6215b0e362971de3d1414
- Preserved local SHA256: f2f355c417f8c2def70afdb8dca4728ecd4773b9fec6215b0e362971de3d1414
- Extract ranges: 316–end
- One appended issue repair/reopen/export test; original AST unchanged.

### tests/test_round2_bible.py

- Classification: additions_only
- Group: backend_seven_and_mp3
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 0d593052b58ca2e4200f4f2c38da0c24f6270c5b
- Expected SHA256: c8c303a03d78cf32f1a8c1d997eb25b0fe48bb3b4d0707268fdadad38ea8c544
- Current SHA256: d7da05009119e408cd38dabf01b3797536ab26a72f79a5c7fc47cca0c06be8c1
- Preserved local SHA256: d7da05009119e408cd38dabf01b3797536ab26a72f79a5c7fc47cca0c06be8c1
- Extract ranges: 458–end
- Two new functions: parameterized visual owner/history roundtrip, Unicode bounds; original AST unchanged.

### tests/test_v2_audio_flac.py

- Classification: legacy_rewrite_only
- Group: backend_seven_and_mp3
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 41dcc646b95b343ece282757c439bd4ee704206b
- Expected SHA256: cda2870e6112f593186055c4c17579c6d0e73ccb332e2ed0bb964ffb5d37b88c
- Current SHA256: d0b72170b9a7392e15e9a3deff614ef8a8a9e3a42b158f1ba50778e212a6e6db
- Preserved local SHA256: d0b72170b9a7392e15e9a3deff614ef8a8a9e3a42b158f1ba50778e212a6e6db
- Extract ranges: 63 parameter rewrite
- Old [MP3] literal replaced by [mp3]. Preserve old node; explicit versioned MP3 seam required.

### tests/test_v2_creative_graph_persistence.py

- Classification: additions_only
- Group: backend_seven_and_mp3
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / a3289942fb0fa801fe516d5c59dcd71f0cdd6c9c
- Expected SHA256: 0e15d0e88389b45a2d16544ccaf30c70d4e88b5e73a60d47b59d7bdcb2a8f44d
- Current SHA256: 1732ee5a0c0430eacc3fdac1fb9090f54ec240a7ad93fa9e6fe6b7b702582fe9
- Preserved local SHA256: 1732ee5a0c0430eacc3fdac1fb9090f54ec240a7ad93fa9e6fe6b7b702582fe9
- Extract ranges: 215–end
- Nine appended presentation/group/copy/preferences/note tests; original AST unchanged.

### tests/test_v2_director_workspace.py

- Classification: additions_only
- Group: backend_seven_and_mp3
- Provenance: inherited_unchanged
- Authoritative ref/blob: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3 / 08bac6df26d0f184c6322f92ea8d2706a145be5d
- Expected SHA256: cb119b5e88ae3909386d2c540ee38d0e78b734909e1f0b4e4e144fb4737689d2
- Current SHA256: cdf5f1877e7aff4783e2f26d7ee50e5ac19ea5a236ebf04246ea7189630323c0
- Preserved local SHA256: cdf5f1877e7aff4783e2f26d7ee50e5ac19ea5a236ebf04246ea7189630323c0
- Extract ranges: 503–590
- Three inserted genre/time functions. Preserve old later route test; original AST unchanged.

## Compatibility seams

- mp3: Unversioned legacy submission remains WAV/FLAC only; new MP3 requires explicit versioned marker. Same original owner. Separate strict new-submission validation from server-loaded persisted-row decoder preserving all original body/context bytes and hashes.
- provider_inputs: Assess explicit advanced editable IDs alongside picker with full owner/provider validation; no silent cloud/consent switch.
- legacy_callbacks: Keep exact callback payload shape; add owner disambiguation in host adapter.
- cost_receipt: Separate companion interface preserves exact original five-method client.
- lineage: Do not remove newer exact-source verification for old test compatibility; report irreconcilable semantic boundary.
- wav_wording: Retain truthful WAV-specific fallback for legacy WAV jobs.
- cas_selectors: Restore original generic alert selectors; static audit does not prove a production defect.

## MP3 recorded-row boundary

- get and list parse stored bodies through _body, not only dispatch.
- Tightening _body alone makes old unmarked MP3 jobs unreadable.
- Recorded decoder must keep owner/scope/incarnation/request SHA/measurement/receipt checks and exact original bytes.
- Existing accepted jobs may retain ORIGINAL explicit execute/reconcile path only after server-loaded validation; never auto-run, migrate, duplicate, or expose public allow-legacy flag.

## Sole approved frozen-byte exception

{
  "path": "tests/test_windows_portable_entry.py",
  "commit": "1b7ff50a7e64742916bc64730df884cea819b379",
  "before_sha256": "d100e27589fb45cb921c13a82a83a911485fef1c0ed82a1e50eb5efc94f24799",
  "after_sha256": "9f0d2d5f78a44e54a0fcc00925dc6d67038060408d3bd44753461ca57152fe1f",
  "single_exact_B_before_I_change_verified": true,
  "current_matches_after": true,
  "action": "Preserve approved current -B form; do not restore pre-migration V1 bytes."
}

## Manifest/coordinator plan

- No manifest mutation or broad collection before parent release.
- Do not edit frozen V1, coverage gates/generator, old node IDs/order/classification or skips.
- After stabilization run only approved narrow original/new compatibility tests first; preserve failures.
- When full collection authorized use existing extend_v2_coverage_manifest.py review mode and unique evidence paths.
- Independently compare all old V2 raw rows/order/classification against archived evidence; generic generator success alone is insufficient.
- After source/node review explicitly authorized --write updates separate V2 only.
- Independent confirmation collection and self-checks require authorization; inventory is not execution coverage.
- Do not use update_recovery_coverage_manifest.py: default output rewrites frozen V1.

## Sources omitted by current traversal

- frontend/e2e/README.md
- frontend/e2e/prompt-acceptance-s0.spec.ts
- frontend/e2e/prompt-workspace-acceptance.spec.ts
- frontend/e2e/promptAcceptanceEntry.ts
- frontend/e2e/studio-release-acceptance.spec.ts
- frontend/scripts/benchmark-canvas-notes.mjs
- frontend/scripts/benchmark-graph-display.mjs
- frontend/scripts/check-test-discovery.mjs
- frontend/scripts/local_interop_browser_host.py
- frontend/scripts/measure_interop_bundle.mjs
- frontend/scripts/run-experimental-http.mjs

The JSON companion includes every stale fingerprint, new source hash and missing backend test function.

## Guard and manifest exact boundaries

- .github/ci/coverage_manifest.json.gz: 6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262 (immutable historical V1)
- .github/ci/coverage_manifest_v2.json.gz: 9d9b8157f1f342ff680e6119b4338a30332a1cec970d5cb00faa10fc01193aca (no write before parent release)
- .github/ci/suite_coverage.py: 570892af0975c125868710e250eb7f30cc5e51ba7cbef9429a3b0f8f10238da7 (no guard/generator changes)
- .github/ci/coverage_reconcile.py: f097904d51cc21cb6f1ce8dcc688f692cf89bdd473f3952605eba3b1ae02e66a (no guard/generator changes)
- .github/ci/postgres_gate.py: d18ee804595ab98f8aec4c25745a7961e65a36755e318c8f4f257663b4358a8c (no guard/generator changes)
- scripts/extend_v2_coverage_manifest.py: 337466ae33d15b2aafaeb15f2191ccdb0c65b22274e1b4d98ba10501dd30135e (no guard/generator changes)
- scripts/run_v2_checks.py: 64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5 (no guard/generator changes)

## Existing narrow infrastructure self-check proposal

Historical command is the three explicit modules test_suite_coverage.py, test_coverage_reconcile.py, test_v2_manifest_extension.py, through existing run_v2_checks.py and a verified pinned environment. Parent approval required. No command has been executed.
