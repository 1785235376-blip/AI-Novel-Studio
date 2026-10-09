"""The catalog must not keep the removed shared discovery authorizer annotation."""
import copy
from types import SimpleNamespace

import pytest

from scripts.refresh_product_api_catalog import refresh_discovery_authority


def mounted_routes():
    from app.main import app
    from fastapi.routing import APIRoute
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
        elif hasattr(route, 'effective_route_contexts'):
            routes.extend(route.effective_route_contexts())
    return routes


def test_current_mounted_discovery_annotations_replace_stale_shared_authority():
    selected = [route for route in mounted_routes()
                if route.endpoint.__module__ == 'app.model_center.discovery_api']
    assert len(selected) == 32
    for route in selected:
        owner = {'observed_authority_functions': ['app.main._model_center_mutation_authorization'],
                 'observed_permission_literals': ['retained unrelated evidence']}
        refresh_discovery_authority(owner, route)
        assert owner['observed_authority_functions'] == [
            'app.main._local_discovery_host_authority',
            'app.model_center.discovery_authority.resolve_discovery_authority',
            'app.model_center.discovery_api.create_local_discovery_router.<locals>.require_session']
        assert owner['router_dependency_functions'] == [owner['observed_authority_functions'][-1]]
        assert owner['observed_permission_literals'] == ['retained unrelated evidence']
        assert owner['original_service_classes'] == ['app.model_center.discovery.LocalDiscoveryService']
        gated = route.path.endswith('/environment') or '/onboarding/' in route.path
        assert owner['observed_reused_feature_flags'] == (['narrative_production_v2'] if gated else [])
        assert len(owner['conditional_feature_checks']) == int(gated)
        if gated:
            assert owner['conditional_feature_checks'][0]['conditional'] is False
            assert owner['conditional_feature_checks'][0]['expression'] == "'narrative_production_v2'"


def test_other_original_owner_annotations_are_preserved_exactly():
    owner = {'observed_authority_functions': ['original'], 'conditional_feature_checks': [{'original': True}]}
    original = copy.deepcopy(owner)
    for route in mounted_routes():
        if route.endpoint.__module__ != 'app.model_center.discovery_api':
            refresh_discovery_authority(owner, route)
            assert owner == original


def test_catalog_fails_closed_if_host_dependency_is_not_mounted():
    def endpoint():
        pass
    endpoint.__module__ = 'app.model_center.discovery_api'
    route = SimpleNamespace(endpoint=endpoint, dependant=SimpleNamespace(dependencies=[]))
    with pytest.raises(RuntimeError, match='current host-authority provenance'):
        refresh_discovery_authority({}, route)
