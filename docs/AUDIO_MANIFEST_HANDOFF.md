# A13: modern Studio Audio result manifests

Base: `19d90d51eed4a9683c4290592dd91495125e5fcf`. Inspection confirmed the A13 gap: the matrix remains PARTIAL and the legacy lineage manifest reads old `media.TASKS`/`proposal_ids`; approved modern Audio assets cannot enter that path. This slice adds a separate manual Audio manifest. Legacy manifests/replay remain unchanged.

## Shared mounting is pending

The dedicated adapter is intentionally **not mounted in the product tree**. The coordinating Graph owner exclusively owns `app/experimental/api.py`, `app/creative/workspace_api.py`, `app/services/studio_image_execution.py` and `app/creative/production_execution.py`; none is changed here. `app/creative/api.py` and generic authorization are also unchanged.

Factory provided by `app/experimental/audio_manifest_api.py`:

```python
create_audio_manifest_router(production_service, studio_host_call)
```

Required injected call contract, matching the existing original Production invoker:

```python
studio_host_call(request, nid, token, branch, permission, callback, *, model=False)
# callback(actor, scope, current_guard)
```

It must retain original `require_host_session`, `model_host_authority.principal` and `authority.guard()`, current actor/scope/incarnation and permission rechecks. It must not be a bare novel authorization or a model execution fallback. The shared owner should use its unified Studio Host invoker and add, inside the existing `if production_service is not None` branch of `create_independent_workspace_router`:

```python
from ..experimental.audio_manifest_api import create_audio_manifest_router
router.include_router(create_audio_manifest_router(production_service, shared_studio_host_call))
```

`shared_studio_host_call` above names the coordinator's unified invoker, not a new optional bypass. With no callable invoker, the adapter refuses with 403. All adapter routes enter `production_service.store.existing_owner_only()` before original authorization/owner access. Mounting and real Host acceptance await the shared owner; no production end-to-end completion is claimed here.

## API and authority

Route prefix: `/novels/{nid}/experimental/production/audio-manifests` (under the application's existing `/api` prefix). The dedicated frontend adapter uses the captured original `ExperimentalClient` session/branch; it never builds a private download URL.

- `GET /results`: current original standalone Production Audio jobs that are APPROVED and ORIGINAL_OWNER_REVIEWED; no candidate or unreviewed result is eligible.
- `GET /results/{job_id}`: explicitly inspect the original job, formal promoted asset, current sources and capture digest.
- `POST` at the prefix: manually record the inspected capture with `job_id`, `expected_job_version`, `reviewed_capture_digest`, stable `request_id` and strict `confirmed: true`.
- `GET` at the prefix, `GET /{manifest_id}` and `GET /{manifest_id}/export`: authorized list, reopen and bounded JSON export.

Every read uses the original Host call with `domain.read`. POST first acquires that same read authority, then `domain.write`; actor/scope must match and the final transaction guard rechecks both captured guards. Novel write permission alone is insufficient. The original actor-scoped Audio get/candidate owner remains authoritative. Graph/benchmark-bound jobs remain subject to original standalone Production admission, rather than being adopted by this surface.

## Manifest binding and safety

The whitelist capture binds job ID/version, original request ID/digest, durable receipt digest, operation ID, reviewed output digest, formal audio Asset ID/version/digest and original source ID/version/digest pins. The original candidate read checks review/promotion provenance and actual output bytes. Sources are rechecked. The record phase retains the original queue → scope → asset → project order, holds asset/project leases through the original scope atomic commit, and rechecks current formal/source bytes, feature/provenance bindings, incarnation and authority before commit.

The new `studio_audio_manifests_v1` collection lives in the existing scope document. Its module explicitly filters actor, scope and project incarnation; no shared collection registry change is needed. Current-owner quota is 64 manifests. An identical manual request ID/body is idempotent; a changed binding with the same key refuses. Old incarnations are never adopted. Delete, changed formal/source version, altered bytes, changed owner, revoked read/write or missing identity refuses rather than replacing the saved proof or recreating an identity.

Public manifests/export contain no raw prompt, command body, URL, session token, credential or actor identity. Unattested model hash/runtime/hardware are explicitly UNKNOWN. The manifest's created time is a recording time, not an execution-environment attestation. `replayable` and replay support are false. This module calls no create/execute/review/promote/replay operation and introduces no review owner.

## UI behavior and reproduction

`ProductionLineagePanel` has only one import and one independent Audio workspace insertion. It does not depend on the legacy manifest flag and performs no new automatic Audio reads. The existing legacy clear/replay navigation behavior is retained; Audio interactions retire the existing pristine navigation capability.

After shared mounting, open the existing **资产来源与生产复现** panel. Click **读取已审核音频与清单**, select an original approved Audio result, then **核对所选音频结果与正式资产**. Inspect the displayed job/version, request/output digests, formal Asset/version and expandable receipt/source binding. Explicitly tick the confirmation and click **明确记录所选音频清单**. Reopen from **现代音频清单列表** and use **导出已核对音频清单 JSON**; export performs a fresh authorized backend read.

Client/selection/confirmation changes retire retained callbacks; repeated clicks are fenced before another request allocation. Denial clears private results/details and prevents cached export. An uncertain POST retains only its original request ID, clears private proof and does not retry or allocate a replacement. Manual reading can find and reopen the original persisted request; no match does not prove failure and does not unlock a replacement record automatically.

## Evidence and untested scope

Local companion `../audio-manifest-evidence/`: 8 real File tests, with 8 PostgreSQL parameters excluded; 37 frontend tests (8 new Audio + 29 existing lineage/legacy manifest/replay); full frontend TypeScript check and Vite production build. The File fixture imports a synthetic WAV, executes the existing local CPU trim, explicitly reviews through the original owner, obtains a formal Asset, then manually records/reopens/exports the manifest. It verifies idempotency, no job/asset mutation, source/formal deletion/version rejection, actor/incarnation and missing-marker rejection, final revoked guard rollback, and dedicated route read/write/Host-principal checks using the original `create_production_invoker` with synthetic Host callbacks.

No real Host session or PostgreSQL run occurred. The dedicated router is tested in an isolated FastAPI application, not mounted product HTTP acceptance. Four screenshots are conspicuously synthetic UI fixtures of the actual original panel/component, without a live backend or generated audio. Geometry checks cover AUDIO at 1366×768, 1440×900, 1920×1080, plus NOVEL/IMAGE/VIDEO at 1440×900; no page errors or document horizontal overflow. No shared screenshot baseline was updated. Vite's existing large-chunk warning remains; build passed and no bundling refactor was made.

No paid model, purchase, push, Release or shared file edit. Only this task's visual port and reconstructable runtime data are cleaned; source and unique evidence remain. Product shared mounting, real Host, PostgreSQL, broader Audio operations/source combinations and actual replay/environment reproducibility remain outside this verification.
