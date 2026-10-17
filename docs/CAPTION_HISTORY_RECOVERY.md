# B04 bounded caption history recovery

Source base: `0335e7a5c960804b8961530aba8d5b8690c5a5f1`.
Status: bounded implementation, primary verification and scoped independent verification complete. This is not full feature or release acceptance.

## Original owners and scope

The existing `SubtitleTimelineService`, original caption PUT, `DomainService.mutate`, and `common.change_row` retain ownership. Recovery reads the existing embedded snapshots and writes through the original current-head compare-and-swap (CAS). There is no second store, second save owner, migration, or new snapshot-writing path. The legacy records response still contains its existing raw history; this slice does not tighten that older DTO.

Routes are mounted under both `/api` and `/api/v1`, at `/novels/{nid}/experimental/subtitle-timeline`. Existing actor, project, branch, membership and three-feature gates (`subtitle_timeline_v2`, `voice_direction_v2`, `audiobook_v2`) remain authoritative. Read paths use read permission; historical previews and saves use write permission. Existing private-route no-store behavior is retained. Pre-return reauthorization and source/head checks reject changed authority and changed state.

## Exact additive contract

### GET `/records/{rid}/history`

- Required query: `expected_version=N`.
- Optional query: `before_version=V`, exclusive; `limit=20`, maximum 50.
- Query values must be positive decimal integer strings, without signs, leading zeros, fractions or boolean spellings. `before_version` cannot exceed the expected head.
- Response: `{record_id, expected_version, items, has_more, next_before_version}`.
- Each item contains only `{version, updated_at, status, timing_origin, cue_count}`.
- Results are newest first and exclude the current head. The continuation cursor is the last returned version if more results exist, otherwise null.
- Every page is anchored to the same exact current-head version. A changed head rejects the next page rather than mixing histories.

Pagination bounds the response only. The original store still loads its scope document, and the service examines existing embedded history. No bounded store-memory or streaming-history claim is made.

### POST `/records/{rid}/history-preview`

Request: `{expected_version, history_version}`, both strict positive JSON integers.

Response: `{record_id, expected_version, history_version, asset_id, asset_snapshot, timebase, plan_id, source_binding_digest, cues, warnings}`.

The selected version must uniquely identify an earlier snapshot with the current record's id, novel, scope, creator and creation identity. It must agree with the target's asset, asset snapshot, rational timebase, plan and stored measured-media metadata. Historical cues pass the original Cue schema, 2,000-cue limit, lossless canonical comparison and original duration/order/overlap validation. Empty historical cues are valid. Duplicate or boolean versions, coercive or stripping cue changes, unsupported fields and malformed snapshots fail closed.

Historical segment snapshots, speaker labels and chapter sources are recomputed from the historical cues themselves and compared to their historical pins; chapter sources are checked through original `assert_sources`. This is source equivalence, not a whole-plan revision comparison. No whole-plan version was stored in these snapshots, and none is invented. A history version whose speaker cues were removed from the current track remains recoverable while its own source evidence remains unchanged.

The lowercase SHA-256 `source_binding_digest` covers historical asset id/snapshot, timebase, plan id, segment snapshots, speakers and sources. It is a preview binding, not a new credential or authority grant. Current CAS plus unique historical version identifies the stored selection. Before returning, the service reauthorizes, rereads the exact head, revalidates the selected historical sources, and checks the selected snapshot remained identical. Preview never writes a record, history entry, task, approval or artifact.

### Original PUT `/records/{rid}`

Existing request `{expected_version, cues}` remains valid. Optional `restore_history_version` is a strict positive JSON integer.

When supplied, historical identity and original live source pins are revalidated inside the original mutation callback, before submitted cues replace current cues. Submitted cues may be manually edited; they need not equal the preview. The UI retains the selected historical version through subsequent edits so edits cannot bypass historical provenance checks. Then the original submitted-cue validation and source snapshot recomputation run normally.

A successful restore creates a new current version, preserving all earlier snapshots. It resets status to DRAFT, timing origin to MANUAL, alignment model to null and processing task id to null through the original update behavior. It never revives historical approval, model, processing or execution authority. Even a replacement identical to current cues is an explicit new version under the existing update semantics.

## UI behavior and boundaries

The existing caption panel displays bounded history metadata and an explicit read-only preview. Replacing the local draft requires an explicit confirmation; saving remains a separate original-owner action. Historical restoration provenance survives manual text edits until a successful save or explicit replacement. Split and merge cannot bypass a staged restoration pin. Strict typed DTO checks reject malformed pages, version/cursor drift and mismatched preview identity. Request generations, owner/head checks and busy guards protect asynchronous UI completion.

Local drafts and selection are session state. The existing save owner has no durable UNKNOWN-outcome write lock or crash-proof reconciliation mechanism; this slice does not add or claim one. A timed-out save must not be represented as known persistence success. Browser/geometry, native input, target-platform, packaged-runtime, PostgreSQL, live model/provider quality and full E2E acceptance remain NOT_RUN/open. These checks used synthetic PCM16 media, real File storage and mounted in-process HTTP, plus separately mocked jsdom UI transports. No PostgreSQL, browser, provider, network model call, installation, remote push, merge, tag or release was performed for this slice.

## Primary verification

All commands used the previously verified clean interpreter and unchanged `scripts/run_v2_checks.py`. Actual normal Python startup was recorded with outer PYTHONPATH unset and natural cwd resolution; the actual original runner child independently recorded its runner-provided current-root PYTHONPATH. Neither proof replaced `sys.path`, imported product modules nor imported pytest. Actual paths, dependency origins, startup finders and absence of old roots/hooks were checked.

- Backend r2: **187 passed, 186 PostgreSQL cases deselected**, one existing Starlette/httpx deprecation warning. Both mounted aliases, raw persisted-byte nonmutation, original exports and fresh File reopen are exercised.
- UI r1: **138 passed**, including **67 new history cases**. This is mocked transport/jsdom evidence, separate from backend coverage.
- Forced TypeScript, production build and original design-token guard passed; token guard checked **52 files**.
- Relevant full source manifests were byte-stable during checks; original protected tests and runner bytes were unchanged. Each original runner receipt reports `sources_changed_during_check: false`.
- Independent repeated verification: **90 File backend passes with 90 PostgreSQL deselections**, plus **67 UI passes**. These overlap the primary totals and are not added. The review verified all **2,539 current source entries**, **1,285 protected baseline paths** and **1,270 tracked test/snapshot paths** unchanged, with exact original log hashes.

Backend r1 is retained unchanged: 185 passed, two failed, 186 deselected. Both failures were the same new historical-only drift fixture on the two route aliases: changing original segment text invalidated the entire plan's manuscript evidence before the intended historical pin check. Only the additive fixture changed. It now uses the real mounted direction-edit route with unchanged source text and changed direction, proving the current empty-cue caption remains valid while historical-only source pins reject restore, including manually edited or empty submitted cues. Runtime source was not changed to make this test pass.

## Byte-exact evidence index

Paths below are repository-relative. SHA-256 values bind the actual retained bytes; logs and receipts were not rewritten. The origin probe, normal-startup receipt and source brackets were copied byte-for-byte into this docs evidence directory and compared with their original local bytes. The original-runner origin receipt and log are also retained under docs. Embedded execution paths describe the original run and were not rewritten.

| Evidence | SHA-256 |
| --- | --- |
| `docs/delivery/v2-development/caption-history-origin/origin-probe.py` | `ecdd5530d79c5943f8f16715d54be6e981f40d883629ff5056eb9523faaaaa06` |
| `docs/delivery/v2-development/caption-history-origin/normal-startup.json` | `346baf54082c49451b1ccd9dfb7e942d322b65a5e9d56c7e514a2f735b36559d` |
| `docs/delivery/v2-development/caption-history-origin/normal-startup.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `docs/delivery/v2-development/caption-history-origin-r1.json` | `adb5b90d71eae4128ed79a7464feb032069afb8d17a2b24b6015d94ee08888b2` |
| `docs/delivery/v2-development/caption-history-origin-r1.log` | `932c69d2f7786c3b0b1d93a50ae4b8310fee3bef0911cbaadb4b85749e8e2a26` |
| `docs/delivery/v2-development/caption-history-backend-r1.json` | `863ec9e862060c5858e0df200280f91a8014aea56722938f947b0c824d1b52d0` |
| `docs/delivery/v2-development/caption-history-backend-r1.log` | `fbff607bc2dd9e0c4296946f145b6fb680280885a00008a10d49abd4cdddbd3f` |
| `docs/delivery/v2-development/caption-history-backend-r2.json` | `efe2d75157978463b0718a92af7a18b274365009e23ad942ac6c7a130d478319` |
| `docs/delivery/v2-development/caption-history-backend-r2.log` | `961de00ecb7739c4941b16dc7942d6a439c48726aa5f87e10ca056ab58baf37a` |
| `docs/delivery/v2-development/caption-history-ui-r1.json` | `f9d47fc6115895a9ada5a2e69bc3628c6320553ddfb4c1c4b95f2a053ec1a0c9` |
| `docs/delivery/v2-development/caption-history-ui-r1.log` | `ebd544afc34b06f26dd53574e8b9dfc04971298d981456c2f9fba68658ddc7e6` |
| `docs/delivery/v2-development/caption-history-tsc-r1.json` | `17a164412164aff92a8c0a8ee3967562f5abc5792af1a9a142f33ba193c2ff4a` |
| `docs/delivery/v2-development/caption-history-tsc-r1.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `docs/delivery/v2-development/caption-history-build-r1.json` | `b78c506a4885b74515095a0be5e96b9b074b237e29005f36d9c728374aed21be` |
| `docs/delivery/v2-development/caption-history-build-r1.log` | `498c3f4382dc8c3ff090e6d93459b9672209a843dfb3d31ee44755ac3ea7c3de` |
| `docs/delivery/v2-development/caption-history-tokens-r1.json` | `ca140d19f2a8d5f28913947b287818e1f89b33715f4d77a8b6ddd56564514bc2` |
| `docs/delivery/v2-development/caption-history-tokens-r1.log` | `720c976bb800c2f989255bfef0431c263b72c50e0b2c052599e3b39e1cb1de50` |

Independent review passed at 2026-10-17 04:34 UTC. The report also records two UI retained-handler findings repaired before final verification: stale history-read/confirmation closures now use request epochs, and pre-restoration save/split/merge closures now use semantic draft/admission epochs. The final independent report binds those fixes and their additive regressions.

| Independent evidence | SHA-256 |
| --- | --- |
| `docs/delivery/v2-development/caption-history-independent-review.json` | `cc7312ee2eff02fb7e4219d58ab7ed9368a8b7603411af5d31ae10674c2aed82` |
| `docs/delivery/v2-development/caption-history-independent-backend-r1.json` | `2268f7530950e452f5487fc64aba731bf589b9614e83a0f595f417a66985f03d` |
| `docs/delivery/v2-development/caption-history-independent-backend-r1.log` | `05fcfd909bf8a1e8dba5386a04b34aa1329ef7a49a5007cbbbce710f41fb7f37` |
| `docs/delivery/v2-development/caption-history-independent-ui-r1.json` | `31ca3c809d69f5fcf447a40e1f8efb4cc08347ad399c6dfe2272a9975fcfe3f3` |
| `docs/delivery/v2-development/caption-history-independent-ui-r1.log` | `a2b9d0cad0d4b86a11d3bd21144aa0baa1dc78c350598161b5ee9e4e5da80e74` |

| Original source brackets (byte-exact copies) | SHA-256 |
| --- | --- |
| `docs/delivery/v2-development/caption-history-origin/full-source-after.sha256` | `b4c5e2fac9359b4ab43d90bdccd579b707047d414b9bd5e70f468aa2521fc0c8` |
| `docs/delivery/v2-development/caption-history-origin/full-source-before.sha256` | `b4c5e2fac9359b4ab43d90bdccd579b707047d414b9bd5e70f468aa2521fc0c8` |
| `docs/delivery/v2-development/caption-history-origin/full-source-r2-after.sha256` | `88fe77923193ba104f409c5b9ce671bc64c789346fa5e84d2e946033f26f9b91` |
| `docs/delivery/v2-development/caption-history-origin/full-source-r2-before.sha256` | `88fe77923193ba104f409c5b9ce671bc64c789346fa5e84d2e946033f26f9b91` |
| `docs/delivery/v2-development/caption-history-origin/protected-before.sha256` | `4113aa4727ddcc1e312f19f58d496cdb986009189681e63de743936fdacafa05` |
