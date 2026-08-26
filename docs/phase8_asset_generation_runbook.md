# Phase 8 Asset Generation Runbook

## Preconditions

- Storyboard status is `APPROVED`.
- Asset requirements are `APPROVED`.
- `ASSET_OPENAI_ENDPOINT` is configured in the runtime environment.
- The provider credential is stored in the configured `CredentialVault`; secrets are never placed in source or screenplay data.
- Each task has an explicit `provider_id` and `model_id`.

## Lifecycle

`PENDING -> RUNNING -> SUCCEEDED | FAILED | CANCELLED`

The executor writes `asset_uri` only after the Provider returns a valid URL. Missing credentials, an unregistered Provider, transport errors, or malformed responses produce `FAILED` with an error message. No placeholder asset is created.

## Verification

Run the Phase 8 regression suite:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_phase8_screenplay.py tests/test_phase8_shots.py tests/test_phase8_storyboard.py tests/test_phase8_transitions.py tests/test_phase8_assets.py tests/test_phase8_asset_tasks.py tests/test_phase8_asset_execution.py tests/test_asset_provider_contract.py tests/test_asset_provider_adapter.py --basetemp=.pytest_tmp_phase8
```
