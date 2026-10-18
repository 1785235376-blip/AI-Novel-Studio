# Workflow Agent execution authority fix

## Result and scope

Final File verification: **61 passed**, exit 0, with `sources_changed_during_check: false`. Receipt: `workflow-agent-authority-file-final-20261018.json`; log: `workflow-agent-authority-file-final-20261018.log`. Real PostgreSQL workflow coverage: **NOT_RUN**.

The mounted workflow queue route now supplies an execution-time authority callback to the original `AgentJobService.start`. It reuses the real trusted-session resolver, `_agent_job_actor_for_record`, workflow ownership checks, project/branch validation, and membership/role authorization. It does not remove ownership or substitute an unconditional permission check.

Changed source: `app/workflow_api.py`.
New tests: `tests/test_workflow_agent_authority.py`.
No change to `AgentJobService`, the direct AgentJob routes, Creative models/store, timeline code, or finding review service.

The callback checks the original session binding generation, the current workflow and node claim, the exact linked job and its request/scope, workflow run status/deadline, and the captured project incarnation on every invocation. The original AgentJobService maps a failed authority callback to `AGENT_PERMISSION_REVOKED` and never reaches provider send for those failures.

## Project identity and legacy behavior

New workflow runs capture the existing authoritative `creative_service.store` identity while holding its original owner lease. This is the same File project marker / PostgreSQL novel owner UUID used by the existing project store. Normal first use may create the shared File marker through that store's established behavior; there is no second identity registry or alternative minting path. This route does not enable or require a Creative/V2 feature flag.

Execution checks use the store's `existing_owner_only` policy, so a missing marker is never repaired or reminted by a stale worker. Retry preserves the verified original incarnation; it does not bind an old claim to whichever same-ID project exists now.

A persisted unbound legacy run returns HTTP 409 `WORKFLOW_EXECUTION_PROVENANCE_REQUIRED` for execution and retry, with an actionable message to create a new workflow run and review its agent step. The old record stays intact. A changed or missing original owner returns HTTP 409 `WORKFLOW_PROJECT_CHANGED`. No broad V1 migration was attempted.

This is an execution-authorization fix, not a complete audit of legacy workflow read/privacy paths. Existing durable workflow metadata remains in the V1 sidecar even in a PostgreSQL profile. Existing list/read/sync/manual workflow semantics outside the necessary new-run/retry provenance plumbing were not redesigned.

## Reproduction retained

The original mounted endpoint returned 202 and linked an owned AgentJob, but the job immediately failed with `AGENT_AUTHORITY_MISSING` before model dispatch. Both an unlinked owner and a real branch-role owner reproduced this through the mounted FastAPI application.

- `workflow-agent-authority-red-20261018.json` / `.log`: 2 expected failures on the original route.
- `workflow-agent-authority-red-observation-20261018.json`: safe synthetic persisted-job observations and the original route source hash.
- `workflow-agent-authority-green-debug-20261018.json` / `.log`: first 2 positive controls passed after wiring the callback.
- `workflow-agent-authority-controls-debug1-20261018.json` / `.log`: 36 focused checks passed.
- `workflow-agent-authority-controls-debug2-20261018.json` / `.log`: 61 focused checks passed on the frozen workflow source/test edits. This was a debug run while unrelated sources could still be changing; it is not the shared final source-freeze receipt.

## Verified behaviors

All checks use real local session, identity, membership, authorization and workflow storage, with the model route replaced by a no-network node. The actual async `AgentJobService.start` / worker / execute / dispatch-guard flow runs. Provider results explicitly identify themselves as `mock_standin`; no API key or real provider is used.

- Current unlinked owner and current branch-role owner complete, sync a successful receipt, and advance the downstream checkpoint; output remains unapplied.
- Missing session and another owner cannot claim execution.
- Session revocation, same-token session rebinding, inactive membership and revoked role fail closed before provider send.
- Role revocation at the provider-send boundary also fails closed.
- Paused workflow, replacement claim timestamp, relinked job, changed workflow owner/project/branch/definition and expired deadline cannot dispatch.
- Changing the queued job's owner or branch fails even when the initiating actor legitimately has access to both branches.
- Cancel stays terminal; a late worker does not advance the workflow.
- Existing start-failure handling still records `AGENT_START_FAILED` and leaves downstream work pending.
- After real access is restored, explicit sync retains the failure reason and explicit retry creates a review-required run with the same verified incarnation. No implicit replay occurs.
- A bound claim remains executable after the workflow service is reopened; unbound legacy execution/retry stays rejected without mutation.
- Deleting/recreating a project during an active job prevents stale dispatch. The old claim remains bound to the retired identity. An explicitly created new run in the replacement project receives the current identity and can execute normally. This delete/recreate behavior is verified on File only. Real PostgreSQL workflow execution and its FK deletion behavior are NOT_RUN; the PostgreSQL branch in the synthetic test is not evidence of executed PostgreSQL coverage.

## Verification command

Use the original runner and clean recovered interpreter:

```sh
.runtime/recovered-python-20261018/bin/python scripts/run_v2_checks.py LABEL -- python -m pytest tests/test_workflow_agent_authority.py tests/test_r2_workflow_execution.py tests/test_r2_agent_timeout_cleanup.py tests/test_phase6_agent_authorization.py tests/test_phase6_agent_jobs.py -q --basetemp .runtime/v2-checks/LABEL/pytest -p no:cacheprovider
```

The final shared-source File check completed after the parent task’s catalog refresh and source freeze: 61 passed, exit 0; the full runner source snapshots were unchanged during the check and both modified source/test hashes still match the final receipt. Real PostgreSQL workflow coverage is NOT_RUN: this bounded suite has no explicitly verified PostgreSQL fixture, and it must not be relabeled as PostgreSQL coverage merely by running the same unmarked tests under a PostgreSQL wrapper. Existing PostgreSQL evidence for other slices is separate. No full-suite, production-model, Windows, browser or deployment acceptance is claimed.

## Frozen source hashes

- `app/workflow_api.py`: `0eca8e006171b9b03bdc5d6bcb3b18cda17709588f48978289948454d7c5b147`
- `tests/test_workflow_agent_authority.py`: `c25dfc9cf01b65476ae53de10a52aa51b85ad6c5aad35c8e726b195c62c50fb3`
