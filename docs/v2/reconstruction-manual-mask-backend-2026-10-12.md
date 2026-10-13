# Fresh reconstruction: manual binary mask Asset save

Base: `4534bed9129bcf2a549b44a91f062c79a77e173b`. This is newly implemented and tested source. Historical lost-workspace results are not acceptance evidence for this change.

## Closed contract and ownership

`POST /api/projects/{nid}/studio/assets/{source_id}/mask` and the original `/api/v1` alias accept only `contract: manual-binary-mask/1`, `source_version`, `source_sha256`, `width`, `height`, `bitplane_base64`, and `idempotency_key`. Dimensions are 64–1024, multiples of eight, and must equal the source dimensions. The canonical base64 represents exact row-major MSB-first bits: white KEEP, black REMOVE, with both colors present. No resizing or inferred segmentation occurs.

The source must be a visible, current, verified original image Asset with the exact version/digest. This initial source contract admits at most 8 MiB of noninterlaced 8-bit PNG, color types 0/2/4/6, with only IHDR, contiguous IDAT and IEND. Ancillary, indexed, animated and oriented variants fail closed. Decoded bytes are bounded by 1024 rows of 4097 bytes. The bitplane is at most 131072 bytes. The fixed grayscale encoder uses explicit stored-DEFLATE framing; canonical output is at most 1049748 bytes. It has no image-library, native-process, provider, model or download dependency.

The response is `{asset, receipt}`. `asset` is the existing Studio Asset projection. The closed receipt contains contract, source_asset_id, source_version, source_sha256, width, height, bitplane_sha256, keep_pixels, remove_pixels and mask_sha256. The first original metadata write includes MANUAL_EDIT lineage and the immutable captured parent revision. Only PNG bytes and compact identity/provenance are stored; no raw bitplane or second draft store is persisted.

The new route requires both `narrative_production_v2` and `asset_lineage_v2`, original domain.write, and the existing direct Host principal/session/epoch/Origin guard. The production invocation function was extracted without changing its body. Ordinary workspace imports remain unchanged. A mask-only streamed 192 KiB body ceiling precedes JSON parsing; validation errors are fixed, private-input-free and no-store.

Original Asset → project leases protect publication. Pure encoding is outside the lease, with fresh checks at phase boundaries and every 64 callbacks; publication and return checks remain unconditional. The Asset owner independently verifies canonical output and source identity before its first metadata commit. Generic metadata and lineage APIs cannot erase/relabel/rebase the captured source. Original filesystem staging/cleanup semantics apply; this is not a general filesystem transaction guarantee.

Scoped idempotency includes actor, source revision/digest, project incarnation and canonical pixel identity, excluding generated timestamps and mutable annotation/license/history. Same-key replay returns the same Asset without a new binary or disk reservation. An observed receipt cannot disappear or change identity and fall through to unreserved creation. Corrupt potential receipts produce a fixed error. Unreadable metadata whose scope cannot be established conservatively blocks this new action; legacy listing behavior is unchanged.

Every replay still requires the captured source to be current. After an uncertain response followed by source drift, the request returns `EXPERIMENTAL_SOURCE_STALE`; a committed mask may already exist in original Assets with honestly stale lineage. There is no automatic retry, source rebinding or execution.

## Fresh verification

All final runs used the original isolated runners and the existing environment pinned to the original CI constraints. Source hashes remained unchanged during each run.

- New pixel + File owner/mounted suite: **119 passed, 86 PostgreSQL cases deselected**.
- New actual PostgreSQL owner/mounted suite: **86 passed, 86 File cases deselected**.
- Original Asset/safety/lifecycle/workspace/API/text/adaptation/storage File selection: **340 passed, 208 PostgreSQL cases deselected**.
- Same original selection on actual PostgreSQL: **208 passed, 340 File cases deselected**.
- Opt-in real mounted response capture: **2 passed, 90 deselected**, covering both aliases. Capture remains private in the pytest-owned temporary directory.
- The initial missing-helper reproduction had **33 failures**; the subsequent pure-helper run had **33 passes**. Both historical receipts remain preserved; only the final-byte results above establish acceptance.
- PostgreSQL 17.11 ran each suite in a fresh verified-empty database through all 20 original migrations, with real original project-owner rows. Both servers stopped normally. Asset metadata/binaries remain the original filesystem owner in both modes; this does not claim they migrated to PostgreSQL.
- Maximum 1024×1024 cases passed on File and PostgreSQL, including a deterministic 30–64 live-guard-call bound for that fixture. This is not a wall-clock performance guarantee.
- Independent read-only source review cleared the six production files and three additive test files. Existing tests, migrations, CI gates and fixtures have no byte changes. The pinned Starlette TestClient deprecation warning remains visible.

Coverage includes real PNG pixels/CRC/canonicality, strict source framing, source revision/deletion/recreation, mixed/private origins, inherited feature restrictions, recursive marker privacy, immutable lineage, concurrent same-key requests, low disk replay, corrupted/disappeared receipts, precommit revocation, Host absence/rebinding/epoch ABA, feature revocation, malformed-body canaries, and misdeclared/chunked body limits. Original tests cover unchanged import versioning and original staging/commit/recovery/lease contracts.

### Repeatable selections

Use an existing CI-pinned Python environment; all basetemps must be under the checkout's `.runtime`.

```sh
NEW="tests/test_v2_manual_mask_owner.py tests/test_v2_manual_mask_api.py"
OLD="tests/test_asset_library.py tests/test_asset_safety.py tests/test_asset_lifecycle_r2.py tests/test_v2_independent_workspace.py tests/test_v2_independent_workspace_api.py tests/test_v2_text_asset_owner.py tests/test_v2_adaptation_asset_owner.py tests/test_v2_storage_admission.py"
python -B scripts/run_v2_checks.py mask-owner-api-first -- python -m pytest -q -p no:cacheprovider tests/test_v2_manual_mask_pixels.py $NEW -m 'not postgres_backend_only' --basetemp=.runtime/mask-rebuild/owner-api-first
python -B scripts/run_v2_checks.py mask-original-file -- python -m pytest -q -p no:cacheprovider $OLD -m 'not postgres_backend_only' --basetemp=.runtime/mask-rebuild/original-file
# Existing owned stopped cluster; PG_BIN is the installed PostgreSQL bin directory.
python -B scripts/run_v2_postgres_checks.py --pg-bin "$PG_BIN" --data .runtime/mask-rebuild/pg-data --port 55448 --user postgres --fresh-database --database v2_mask_reconstruction_20261013 mask-owner-api-pg -- python -m pytest -q -p no:cacheprovider $NEW -m postgres_backend_only --basetemp=.runtime/mask-rebuild/owner-api-pg
python -B scripts/run_v2_postgres_checks.py --pg-bin "$PG_BIN" --data .runtime/mask-rebuild/pg-data --port 55448 --user postgres --fresh-database --database v2_mask_originals_20261013 mask-original-pg -- python -m pytest -q -p no:cacheprovider $OLD -m postgres_backend_only --basetemp=.runtime/mask-rebuild/original-pg
STUDIO_CAPTURE_MANUAL_MASK=1 python -B scripts/run_v2_checks.py mask-mounted-capture -- python -m pytest -q -p no:cacheprovider tests/test_v2_manual_mask_api.py -m 'not postgres_backend_only' -k mounted_real_save --basetemp=.runtime/mask-rebuild/mounted-capture
```

Use new labels, basetemps and database names for reruns; preserve earlier evidence. Raw receipts, runtime configuration, databases and response captures are private and excluded from this source commit.

## Source binding and remaining scope

| Production file | SHA256 |
| --- | --- |
| app/creative/production_execution_api.py | a0bcd00ecc520fabf042219129e9dc1b7a87b1875ed356398979af05a2f9012f |
| app/creative/workspace.py | f796772b21007d902625370e1c6b2177f3658c6b80bdba3dd204d4d477c43cca |
| app/creative/workspace_api.py | dafcd4e8a83eba0ca68f29655d71c59aa8b5bcd85e11ff40339fb7f606d62c01 |
| app/creative/workspace_models.py | 5f38c1d510dfeca63d0372782a5076f10589984386d0c8680b0feea13ccdb9b3 |
| app/services/asset_library_service.py | 3dbaa70db6caf50d4fee32e11f5a3e20a7dcfadbf4dfeffd0448450728ea0bfe |
| app/services/studio_image_mask_authoring.py | d6f61fabfbb4233d99c0c2be8216e0be017f3db11009249adf640717e6a5fcb5 |

This backend slice saves an authored mask Asset. CPU cutout execution, broader formats, browser/Windows acceptance, and whole-product restoration are outside this result. No GPU, user model, paid API or external provider was invoked. Frontend integration and remote publication are separately verified by the integration owner.
