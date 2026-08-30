import ast
import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from app.provider_runtime_v2_contracts import *


@pytest.fixture(autouse=True)
def restore_global_settings():
    """Avoid app/runtime/Vault initialization for these isolated contracts."""
    yield


@pytest.mark.parametrize('name', ['api_key', 'token', 'password', 'secret'])
def test_raw_credentials_rejected_and_not_serialized(name):
    ref = CredentialReference(handle=UUID(int=1), scope=CredentialScope.SYSTEM)
    with pytest.raises(ValidationError):
        CredentialReference.model_validate({**dict(ref), name: 'sensitive-value'})
    with pytest.raises(ValidationError):
        CredentialReference.model_validate_json(json.dumps({'handle': 'sensitive-value', 'scope': 'SYSTEM'}))
    assert 'sensitive-value' not in ref.model_dump_json()
    assert set(ref.model_dump()) == {'handle', 'scope', 'scope_id'}
    assert CredentialReference.model_validate_json(ref.model_dump_json()) == ref


def test_closed_strict_immutable_contracts():
    assert {m.value for m in Modality} == {'TEXT', 'IMAGE', 'VIDEO', 'TTS', 'AUDIO', 'EMBEDDING'}
    ref = CredentialReference(handle=UUID(int=1), scope=CredentialScope.SYSTEM)
    with pytest.raises(ValidationError):
        ref.handle = UUID(int=2)
    with pytest.raises(ValidationError):
        CredentialReference(handle=UUID(int=1), scope=CredentialScope.USER)
    with pytest.raises(ValidationError):
        CredentialReference(handle=UUID(int=1), scope=CredentialScope.SYSTEM, scope_id=UUID(int=2))
    with pytest.raises(ValidationError):
        BudgetPolicy(maximum_cost_microusd=True)
    with pytest.raises(ValidationError):
        BudgetPolicy(maximum_cost_microusd=-1)
    with pytest.raises(ValidationError):
        RouteIdentity(provider=ModelIdentity(model_id=UUID(int=1)), model=ModelIdentity(model_id=UUID(int=1)),
                      runtime=RuntimeIdentity(runtime_id=UUID(int=1)), node=ExecutionNodeIdentity(execution_node_id=UUID(int=1)))


def test_decision_consistency():
    with pytest.raises(ValidationError):
        ProviderRoutingDecision(decision=Decision.ALLOW, reason_code=ReasonCode.SELECTED)
    with pytest.raises(ValidationError):
        ProviderRoutingDecision(decision=Decision.DENY, reason_code=ReasonCode.SELECTED)
    with pytest.raises(ValidationError):
        ProviderRoutingDecision(decision=Decision.NO_COMPATIBLE_ROUTE, reason_code=ReasonCode.NO_CANDIDATES,
                                credential_handle=UUID(int=1))


def test_no_io_dependencies_or_secret_fields():
    root = Path(__file__).resolve().parents[1]
    permitted = {'enum', 'typing', 'uuid', 'pydantic', 'app.provider_runtime_v2_contracts'}
    for name in ('provider_runtime_v2_contracts.py', 'provider_routing_policy_v2.py'):
        tree = ast.parse((root / 'app' / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in permitted
            if isinstance(node, ast.Import):
                assert all(alias.name in permitted for alias in node.names)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {'open', 'exec', 'eval', '__import__', 'compile'}
    for cls in Contract.__subclasses__():
        assert not {'api_key', 'token', 'password', 'secret', 'prompt', 'path', 'url'} & cls.model_fields.keys()
