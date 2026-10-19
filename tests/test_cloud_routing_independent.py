"""Independent boundary checks for the internal cloud routing foundation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

from app import provider_runtime_v2_routing_service as service
from app.provider_runtime_v2_contracts import (
    Decision, ExecutionNodeIdentity, Modality, PrivacyPolicy, ProviderRoutingRequest,
)

NODE = UUID('747a7b08-2269-4440-98f3-67e8f97161c2')
CANARY = '/private/credential-store/SECRET-CANARY'


@pytest.fixture(autouse=True)
def restore_global_settings():
    """These isolated checks do not initialize the application's global owners."""
    yield


def request():
    return ProviderRoutingRequest(
        modality=Modality.TEXT, workspace_id=UUID(int=2), user_id=UUID(int=3),
        local_node=ExecutionNodeIdentity(execution_node_id=NODE),
        privacy=PrivacyPolicy.DEVICE_ONLY,
    )


class ReadOnlyStore:
    def get(self, kind, key):
        assert (kind, key) == ('execution_node', 'local')
        return NODE

    def get_or_create(self, *args, **kwargs):
        pytest.fail('Routing must not create an identity')


class EmptyRegistry:
    def descriptors(self):
        return ()


def owners():
    return SimpleNamespace(
        runtime=SimpleNamespace(
            execution_node_identity=SimpleNamespace(store=ReadOnlyStore()),
            provider_registry=EmptyRegistry(), model_registry=EmptyRegistry(),
        ),
        model_center_service=SimpleNamespace(runtimes={}, models={}),
    )


def test_fresh_import_and_uninitialized_call_do_not_bootstrap_host(tmp_path):
    program = '''
import json, sys
from uuid import UUID
from app.provider_runtime_v2_routing_service import route_provider_request
from app.provider_runtime_v2_contracts import *
assert 'app.runtime' not in sys.modules
assert 'app.dependencies' not in sys.modules
r = ProviderRoutingRequest(modality=Modality.TEXT, workspace_id=UUID(int=2),
    user_id=UUID(int=3), local_node=ExecutionNodeIdentity(execution_node_id=UUID(int=4)),
    privacy=PrivacyPolicy.DEVICE_ONLY)
print(json.dumps(route_provider_request(r).to_dict()))
assert 'app.runtime' not in sys.modules
assert 'app.dependencies' not in sys.modules
'''
    environment = {**os.environ, 'HOME': str(tmp_path / 'home'),
                   'XDG_DATA_HOME': str(tmp_path / 'xdg'),
                   'NOVEL_DATA_PATH': str(tmp_path / 'novel'),
                   'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-c', program], env=environment,
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report['service_codes'] == ['HOST_NOT_INITIALIZED']
    assert report['decision']['decision'] == 'NO_COMPATIBLE_ROUTE'
    assert not tuple(tmp_path.iterdir())


@pytest.mark.skipif(sys.platform == 'win32', reason='Checks unsupported-platform production path')
def test_real_linux_collection_reports_unsupported_inventory():
    report = service._route_with_owners(request(), owners())
    assert report.snapshot_complete
    assert report.hardware_status is service.HardwareStatus.UNSUPPORTED_PLATFORM
    assert report.decision.decision is Decision.NO_COMPATIBLE_ROUTE


@pytest.mark.parametrize('failure', ['owner', 'registry', 'hardware'])
def test_owner_and_inventory_errors_never_serialize_exception_detail(monkeypatch, failure):
    owned = owners()

    def fail(*args, **kwargs):
        raise RuntimeError(CANARY)

    if failure == 'owner':
        owned.runtime.execution_node_identity.store.get = fail
    elif failure == 'registry':
        owned.runtime.provider_registry.descriptors = fail
    else:
        monkeypatch.setattr(service, 'collect_host_hardware_snapshot', fail)
    report = service._route_with_owners(request(), owned)
    assert CANARY not in json.dumps(report.to_dict())
    assert report.decision.decision is Decision.NO_COMPATIBLE_ROUTE
    assert report.service_codes
