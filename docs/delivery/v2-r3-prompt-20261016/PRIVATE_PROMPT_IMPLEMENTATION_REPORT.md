# Private Prompt implementation and evidence

Prepared 2026-10-17, Asia/Shanghai (2026-10-16 UTC), from continuation base `618affbca0aaf20d5bc669d697d8e2b1abb9b3fa`.

The private Prompt changes are implemented through the existing Asset, Prompt, project and identity owners. Latest bounded File validation is **PASS: 84 tests**. Overall acceptance remains **PARTIAL**: unified final PostgreSQL and browser acceptance are **PENDING** at this report date. Sources are held while the root coordinates resolver deadlock diagnostics/fix and the final reruns. The root's final report will record the final candidate and results; the File receipt below does not certify later source changes.

Production Prompt adoption remains disabled. These changes do not establish production adoption, provider/model quality, or full Director Workbench acceptance.

## Implemented behavior

### Private deletion through the original owner

`AssetLibraryService.delete` accepts the server-resolved `actor_id` and passes it to its existing `get(..., include_deleted=True)` lookup. `IndependentWorkspaceService.lifecycle` carries that actor through its initial/final lookup and deletion call. Existing asset mutation, project binding, incarnation and authorization boundaries remain the owners of the operation.

The lifecycle response for a deleted private Prompt reuses the original lineage projection of the already actor-checked row. This avoids an anonymous lookup failing after deletion has committed. It returns the existing Asset response shape, with private fields redacted; it does not introduce a new Prompt store or a second deletion authority.

| Request/control | Observed contract |
| --- | --- |
| Author deletes own private Prompt at expected version N | HTTP 200; version N+1; `deleted_at` populated; provenance integrity `DELETED` |
| Same author repeats deletion at the resulting version | HTTP 200; same result; no additional version |
| Stale expected version | HTTP 409 |
| Different actor with project write authority | Exact HTTP 404 `EXPERIMENTAL_NOT_FOUND` |
| Read-only actor | Exact HTTP 403 `PROJECT_SCOPE_FORBIDDEN` |
| Same author through a different branch | Exact HTTP 404 `EXPERIMENTAL_NOT_FOUND` |
| Restore a still-private Prompt through the generic restore route | Exact HTTP 404; metadata/version unchanged |

The original `.bin` content and identity remain retained. Earlier Prompt revisions and their bytes are not rewritten. Private-owner deletion is a tombstone operation, not physical cleanup.

The private restore restriction is deliberately narrow. Original approval through `promote_owned` clears `_owner_actor_id`; an approved shared Asset retains its existing supported restore semantics. An approved shared Asset returning 200 on explicit restore is not evidence that private restore bypassed its contract.

### Tombstones remain in family CAS and request accounting

Prompt authoring includes deleted rows when accounting for request IDs and family revisions. Deleting the latest revision does not free its revision number, predecessor identity, or request identity.

| Authoring operation | Required result |
| --- | --- |
| Replay a deleted request | HTTP 409 `PROMPT_REQUEST_DELETED` |
| Revise a family whose revisions are all deleted | HTTP 404 `EXPERIMENTAL_NOT_FOUND` |
| Family has active revision 1 and deleted latest revision 2; editor expects revision 1 | HTTP 409 `PROMPT_REVISION_STALE`, `current_revision: 2` |
| Same family; editor explicitly expects deleted head revision 2 | HTTP 409 `PROMPT_REVISION_DELETED` |
| Author creates a separate new family with a new request | HTTP 201; distinct family/Asset identity |

The existing Prompt detail projection retains deleted revision 2 as the family head and includes both revision identities. The revision-body endpoint returns a metadata-only tombstone: `state: DELETED`, `value: null`, `digest: null`, `available: false`, `verified: false`. It does not return the old body bytes. The active-only library excludes deleted rows and can display an older remaining active revision; server-side family CAS still accounts for the deleted latest revision. No read-projection or UI owner was changed by this slice.

### Completed replay is bound to its original target

Content equality alone no longer permits a completed request to return a receipt for a different route or family. A create replay must describe revision 1 with no predecessor. A revision replay must match the saved family, saved predecessor and saved revision (`expected_revision + 1`). Changing the family route, predecessor, revision expectation, or replaying a revision request through the create route returns exact HTTP 409 `PROMPT_REQUEST_ID_REUSED`.

The legitimate exact replay remains HTTP 201 with the same Asset and `idempotent_replay: true`. Refused operations preserve metadata and bytes and do not disclose the authored text or the other Asset identities in the error.

### Pending recovery has immutable initial origin

The server-only `AssetLibraryService.create(..., _initial_prompt_write=...)` argument persists `_prompt_write_origin` in the original first metadata commit, alongside the original body and owner binding. It participates in the existing Asset idempotency identity. No filename is interpreted as authority, and there is no second request ledger or store.

The closed origin fields are:

| Field | Meaning |
| --- | --- |
| `contract` | `studio-prompt-write-origin/1` |
| `operation` | `CREATE` or `REVISE` |
| `allocated_family_id` | Server-allocated family reused on recovery |
| `expected_previous_asset_id` | Original revision predecessor; `null` for CREATE |
| `expected_revision` | Original revision expectation; `null` for CREATE |
| `request_digest` | Digest binding the original actor/project/scope/route and full request content, including body text and request ID |

`Asset.public` removes the marker. The initial Prompt contract rejects incompatible combinations with the existing text/media/mask initial contracts. Completed legacy receipts remain replayable through their structured payload; the new marker is required to establish the full target of an incomplete write.

Tests interrupt the original `assets.update_metadata` once after the body Asset has committed. Exact CREATE and REVISE retries resume the same Asset and allocated family, complete one revision, preserve the origin and original bytes, and remain idempotently replayable. Changing the operation, family, predecessor, expected revision, parameters, purpose, negative prompt or text returns exact HTTP 409 `PROMPT_REQUEST_ID_REUSED`; a subsequent valid retry still succeeds without duplication.

A legacy pending body with no origin is retained but cannot prove its full original target. Its retry returns exact HTTP 409 `PROMPT_REQUEST_ORIGIN_UNVERIFIED`, with metadata and bytes unchanged. The tests model that state through the real Asset owner while omitting only the new server-only initial argument; identity, membership, session and authorization owners are not replaced.

## Sources and test boundary

- [Original Asset owner](../../../app/services/asset_library_service.py): actor-aware deletion, initial Prompt origin validation/persistence and public redaction.
- [Workspace consumer](../../../app/creative/workspace.py): actor-aware lifecycle lookup/deletion and existing lineage response projection.
- [Prompt authoring adapter](../../../app/creative/prompt_authoring.py): tombstone accounting, completed target replay and pending-origin recovery.
- [Existing Prompt reads](../../../app/creative/prompt_workspace.py): metadata-only tombstones and retained family detail.
- [Additive mounted tests](../../../tests/test_v2_private_prompt_lifecycle.py): 48 File and 48 PostgreSQL variants, including both `/api` and `/api/v1` aliases.

The tests use original mounted routes, packaged session exchange, identity/membership/permission owners and real File persistence. Failure injection is restricted to the stated Asset write boundary. Original frozen test bodies were not edited; the existing workspace API tests and original Round3W T06/T06b tests were run unchanged.

## Retained raw evidence

All rows below are bounded File runs. Each JSON includes the executed command, source hashes before/after, status and log hash. Each linked log retains the original pytest output. Earlier failures and intermediate results are preserved.

| Receipt | Result | Purpose |
| --- | --- | --- |
| [delete-before JSON](../v2-development/r3-private-delete-before.json) / [raw log](../v2-development/r3-private-delete-before.log) | **FAIL:** 6 failed, 2 passed, 8 deselected; 7.78 s | Reproduces authorized private deletion returning exact 404 |
| [delete-file-r1 JSON](../v2-development/r3-private-delete-file-r1.json) / [raw log](../v2-development/r3-private-delete-file-r1.log) | **PASS:** 8 passed, 8 deselected; 7.91 s | Initial actor-aware deletion controls |
| [delete-file-regression JSON](../v2-development/r3-private-delete-file-regression.json) / [raw log](../v2-development/r3-private-delete-file-regression.log) | **PASS:** 42 passed, 42 deselected; 19.78 s | Initial private cases plus existing workspace API regression |
| [delete-file-final JSON](../v2-development/r3-private-delete-file-final.json) / [raw log](../v2-development/r3-private-delete-file-final.log) | **PASS:** 44 passed, 44 deselected; 22.43 s | Tombstone-aware family CAS and request behavior |
| [replay-identity-before JSON](../v2-development/r3-private-replay-identity-before.json) / [raw log](../v2-development/r3-private-replay-identity-before.log) | **FAIL:** 8 failed, 28 deselected; 9.17 s | Exact valid replay passes first; altered target incorrectly returns HTTP 201 |
| [replay-identity-file-final JSON](../v2-development/r3-private-replay-identity-file-final.json) / [raw log](../v2-development/r3-private-replay-identity-file-final.log) | **PASS:** 52 passed, 52 deselected; 25.82 s | Fixed completed receipt identity plus prior API regression |
| [pending-origin-file-final JSON](../v2-development/r3-private-pending-origin-file-final.json) / [raw log](../v2-development/r3-private-pending-origin-file-final.log) | **PASS:** 84 passed, 82 deselected; 43.11 s | Latest bounded marker/recovery validation plus unchanged original retry tests |

The latest 84 consists of 48 private Prompt cases, 34 existing workspace API cases, and the original T06/T06b failure/lost-response retry cases. The 82 deselections are PostgreSQL variants excluded by the explicit File selection; they are not PostgreSQL passes or silent runtime skips. The only reported warning is the existing Starlette/httpx TestClient deprecation.

The latest run finished at `2026-10-16T16:01:14.161180+00:00`, used Python **3.12.9** with pytest **8.4.2** from `D:/PoemSeed/Cache/Tests/expansion-20261013-97da10e1/venv/Scripts/python.exe`, and reports `sources_changed_during_check: false`. Its receipt's full `source_sha256` map is the authoritative tested-source binding, rather than HEAD alone (the continuation is uncommitted).

The command used the existing `scripts/run_v2_checks.py` with label `r3-private-pending-origin-file-final`, an owned `.runtime/v2-checks/` profile, and this pytest selection:

```text
python -m pytest -q -p no:cacheprovider
  tests/test_v2_private_prompt_lifecycle.py
  tests/test_v2_independent_workspace_api.py
  tests/test_round3w_authoring.py::test_t06_metadata_failure_then_retry_produces_exactly_one_revision
  tests/test_round3w_authoring.py::test_t06b_a_lost_response_is_replayable
  -m "not postgres_backend_only"
  --basetemp .runtime/v2-checks/r3-private-pending-origin-file-final/pytest
```

## Pending unified acceptance

At this report date, unified final real PostgreSQL, real browser, cross-process authority/revocation and post-resolver-fix reruns are **PENDING**. Intermediate browser and diagnostics directories in this delivery folder remain retained, including failed attempts. This report does not convert those artifacts or the File suite into a final runtime PASS. The root's final report must name the final source snapshot and authoritative PG/browser receipts.

No source or test changes were made while preparing this report. No commits, pushes, merges, model calls, paid-provider actions, baseline regeneration or cleanup were performed by this documentation step.
