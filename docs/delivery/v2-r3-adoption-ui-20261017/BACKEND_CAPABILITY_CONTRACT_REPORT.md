# Adoption UI backend capability contract

Base: `95420aa59acb4c196d92e7292df0744098f6d2ff`. Prepared 2026-10-17 Asia/Shanghai. Status: implemented; focused File preparation tests pass, unified final source-frozen File/PG/browser acceptance is pending.

The existing authorized GET `/api[/v1]/projects/{nid}/studio/documents/{document_id}/prompt-adoption` now adds `write_enabled: boolean` to the original `adoption.read(...)` projection. It reads `PROMPT_ADOPTION_WRITE_ENABLED is True` in the current backend process. No new endpoint, owner, environment toggle, client-controlled switch or persisted state is introduced.

The production source still declares `PROMPT_ADOPTION_WRITE_ENABLED = False`. Original POST DTO, gate, `adopt_atomic`, read service and `invoke` authorization remain unchanged. Query parameters, headers and request-body fields cannot enable adoption. A valid authorized POST in the closed process still returns exact HTTP 503 `PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED` without owner mutation; an extra body `write_enabled` field is rejected with 422.

`write_enabled` is the server's global capability, not a permission grant. A viewer may read `true` in an explicitly enabled test process, while their POST still receives exact 403 `PROJECT_SCOPE_FORBIDDEN`. The UI must retain the existing host/session/read-only/write-permission gates and fail closed when capability is absent or false.

## Original-owner success requirements

1. Approve the selected revision through the existing Prompt approval endpoint, with the Asset metadata version. Approval is not client-supplied metadata.
2. Re-read the original Prompt family/detail and revision-body endpoints. Require the current approved head, complete history/read coverage, complete nontruncated verified original bytes, exact family/Asset/revision and original-byte digest.
3. Read the original CreativeDocument and adoption GET for one exact target version/digest. Send only the existing closed adoption DTO: `shot_id`, `family_id`, `asset_id`, `revision`, `expected_digest`, `expected_version`, `expected_digest_target`, `request_id`.
4. On the first commit require `committed: true`, version +1, exact source identity/digest, exact proof target version/digest and `result_version` equal to the committed version. Refresh both original document and adoption read; the actual target shot text and returned document digest must agree with the committed record.
5. Retry a lost response with the same request ID and identical snapshot/body. An historical replay may return the current document version while its proof retains the original `result_version`; consult fresh `still_applied`, not `replayed` alone, before saying the current shot still carries the adoption.

`source_bindings_verified: true` describes all declared bindings at commit time, under the original shared phase/owner leases. Character/Scene rows, target-document Shot identity and reference/output Asset bytes are resolved through their original owners. Empty declarations can legitimately yield an empty snapshot with `true`. Read does not revalidate every historical binding target. This flag is not current-source freshness, source review, shot approval or render/model permission.

## Focused tests and retained failure

New independent module: [test_v2_prompt_adoption_ui_capability.py](../../../tests/test_v2_prompt_adoption_ui_capability.py). Six scenarios across two API aliases and File/PG provide 12 File and 12 PG variants. They retain real packaged identity/session, membership, authorization, original Asset review and CreativeDocument persistence.

| Evidence | Result | Qualification |
| --- | --- | --- |
| [r1 receipt](../v2-development/r3-adoption-ui-capability-file-r1.json), [raw log](../v2-development/r3-adoption-ui-capability-file-r1.log) | 11 passed, 1 failed, 12 deselected; 9.57 s | Second alias's positive adoption returned 404; retained unchanged |
| [r2 receipt](../v2-development/r3-adoption-ui-capability-file-r2.json), [raw log](../v2-development/r3-adoption-ui-capability-file-r2.log) | 12 passed, 12 deselected; 9.64 s | Runner status PASS, but whole-source drift occurred; preparation evidence only |

The r1 cause was a test fixture lifetime mismatch, **not missing `EXPERIMENTAL_FEATURES`**. The mounted fixture rebinds its singleton workspace to a fresh real store per case. The first positive case lazily cached `PromptAdoptionService._inputs` with that prior fixture's store; the next alias then looked for its new document in the old store. Only the new test module's setup changed: it clears the stale lazy adapter so the original factory binds the current case's real owner. No application workaround, mocked authority or relaxed HTTP 200 assertion was added.

The r2 receipt explicitly records `sources_changed_during_check: true`; the sole changed path was `frontend/src/creative/CreativeWorkspace.tsx` from concurrent UI development. Backend capability and its test source did not change during that run. Passing pytest/runner status does not erase this source-drift qualification. The root must rerun the combined selection after the entire candidate freezes.

The focused command uses the existing runner and pinned Python/pytest runtime:

```text
D:/PoemSeed/Cache/Tests/expansion-20261013-97da10e1/venv/Scripts/python.exe
  -X utf8 -B scripts/run_v2_checks.py r3-adoption-ui-capability-file-r2
  -- python -m pytest -q -p no:cacheprovider
  tests/test_v2_prompt_adoption_ui_capability.py
  -m "not postgres_backend_only"
  --basetemp .runtime/v2-checks/r3-adoption-ui-capability-file-r2/pytest
```

PG variants were not run by this slice. They require the coordinated original PostgreSQL wrapper. Existing frozen test bodies remain unchanged.

## Isolation review

The acceptance launcher design uses an owned Python child that imports `app.main` and then explicitly changes only that child's existing adoption module variable to `True`. Ordinary backend processes before and after it keep the source default `False`, must expose GET capability false, and must actually return exact 503 with unchanged original owner state. There is no product environment enable switch. This is a reviewed design boundary; final retained runtime receipts must establish that the implementation follows it.

The UI extension and browser harness belong to their original assigned owners. This backend slice changes only [the existing GET projection](../../../app/creative/prompt_adoption_api.py) and adds the independent test module. It does not open production adoption, create a second workflow authority, or claim final unified acceptance.
