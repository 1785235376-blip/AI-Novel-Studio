"""Wave 5 additive templates, constrained SDK and pinned comic references.

Fixtures run File and an opt-in disposable real PostgreSQL endpoint. Local
model, GPU and executable third-party integration are deliberately not invoked.
"""
import base64
import copy
from dataclasses import replace
import io
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.declarative_agents import DeclarativeAgentsService, WorkflowAuthoring, default_definition
from app.experimental.declarative_agents_api import create_declarative_agents_router
from app.experimental.declarative_adapter_sdk import AdapterCapabilities, AdapterRequest, definition_contract, run_trusted_local
from app.experimental.template_library import TemplateLibraryService, extended_builtin_packages, parse_package
from app.experimental.template_library_api import create_template_library_router
from app.experimental.planning import digest
from app.experimental.comic_layouts import ComicLayoutsService, LayoutIn
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r4_reader_sessions import env as storage_env
from test_r5_declarative_templates import env, install
from test_r3_media_support import rig
from test_r4_production_lineage import production, declaration
from test_r5_comic_layouts import comic, image_asset, layout, save, preflight, approve, synthetic_png


def starter(kind):
    return next(p for p in extended_builtin_packages() if p['manifest']['type'] == kind)


def copied(e, kind, request_id='wave5-copy'):
    p = starter(kind)
    return e.library.copy(e.ctx, {'package_id': p['manifest']['id'], 'package_digest': digest(p), 'request_id': request_id})


def test_extended_catalog_is_read_only_additive_and_original_authorities_remain(env):
    e = env; before = e.store.read(e.ctx.novel_id, e.ctx.scope)
    catalog = e.library.catalog(e.ctx)
    assert len(catalog['items']) == 9
    assert {r['package']['manifest']['type'] for r in catalog['extended_items']} == {'novel', 'genre', 'world', 'agent', 'story_structure'}
    assert len(catalog['extended_items']) == 5 and catalog['permission_grants'] == []
    assert catalog['import_mode'] == 'READ_ONLY_DECLARATION'
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before
    for entry in catalog['extended_items']:
        assert entry['package']['manifest']['permissions'] == {'execute': False, 'network': False, 'manuscript_write': False, 'grant_capabilities': False, 'executable_plugins': 'DENY_ALL'}
    row = copied(e, 'agent'); target = row['linked_target']
    assert target['feature'] == 'declarative_agents_v2'
    definitions = e.agents.definitions(e.ctx)['items']
    assert len(definitions) == 1 and definitions[0]['id'] == target['id']
    assert definitions[0]['definition']['agent']['review_required'] is True
    assert definitions[0]['status'] == 'DRAFT' and definitions[0]['applied'] is False
    assert e.agents.runs(e.ctx)['items'] == []
    assert e.agents.definitions(replace(e.ctx, actor='other'))['items'] == []
    assert e.library.catalog(replace(e.ctx, actor='other'))['extended_items'][0]['version'] == 0


@pytest.mark.parametrize('kind', ['novel', 'genre', 'world', 'story_structure'])
def test_new_declarative_brief_types_persist_edit_restore_restart_without_source_write(env, kind):
    e = env; original = copy.deepcopy(e.chapters.get(e.cid)); row = copied(e, kind)
    assert row['linked_target'] is None and row['status'] == 'DRAFT'
    content = copy.deepcopy(row['content']); content['sections'][0]['text'] = 'An independent user edit.'
    edited = e.library.edit(e.ctx, row['id'], {'expected_version': 1, 'content': content})
    with pytest.raises(CapabilityVersionConflict): e.library.edit(e.ctx, row['id'], {'expected_version': 1, 'content': content})
    reopened = TemplateLibraryService(e.store, e.novels, e.chapters, planning=e.planning, enabled_features=lambda: e.enabled)
    assert reopened.instances(e.ctx)['items'][0]['content'] == content
    restored = reopened.revert(e.ctx, row['id'], {'expected_version': edited['version'], 'restore_version': 1})
    assert restored['version'] == 3 and restored['content'] == starter(kind)['content']
    assert e.chapters.get(e.cid) == original
    assert all(not rows for name, rows in e.store.read(e.ctx.novel_id, e.ctx.scope)['collections'].items() if name != e.library.INSTANCES)


@pytest.mark.parametrize('mutation', [
    lambda p: p['manifest']['permissions'].update(execute=True),
    lambda p: p['manifest']['permissions'].update(network=True),
    lambda p: p['manifest']['permissions'].update(manuscript_write=True),
    lambda p: p['manifest']['permissions'].update(grant_capabilities=True),
    lambda p: p['manifest']['permissions'].update(executable_plugins='ALLOW'),
    lambda p: p['manifest']['compatibility'].update(protocol='REMOTE_MARKETPLACE_V1'),
    lambda p: p['manifest']['compatibility'].update(schema_versions=[2]),
    lambda p: p['manifest']['compatibility'].update(import_mode='EXECUTE'),
    lambda p: p['manifest'].update(entry_point='os.system'),
    lambda p: p['content']['agent'].update(review_required=False),
])
def test_manifest_compatibility_and_permission_claims_never_grant_authority(env, mutation):
    e = env; before = e.store.read(e.ctx.novel_id, e.ctx.scope); p = starter('agent'); mutation(p)
    with pytest.raises(ValueError): e.library.preview(e.ctx, {'package': json.dumps(p)})
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before


def test_extended_install_dependency_revocation_and_scope_fences(env):
    e = env; p = starter('agent'); e.enabled.discard('declarative_agents_v2')
    record = install(e, p)
    assert record['status'] == 'INSTALLED' and 'declarative_agents_v2' not in e.enabled
    with pytest.raises(ValueError, match='DEPENDENCY'): copied(e, 'agent')
    e.enabled.add('declarative_agents_v2')
    def deny(): raise HTTPException(403)
    with pytest.raises(HTTPException): e.library.copy(e.ctx, {'package_id': p['manifest']['id'], 'package_digest': digest(p), 'request_id': 'denied'}, deny)
    assert e.agents.definitions(e.ctx)['items'] == []
    assert e.library.instances(e.ctx)['items'] == []
    with pytest.raises(StaleSourceError): e.library.copy(e.ctx, {'package_id': p['manifest']['id'], 'package_digest': '0' * 64, 'request_id': 'stale'})


def test_sdk_requirements_are_persisted_original_definition_and_preflight_contract(env):
    e = env; definition = default_definition()
    definition['agent'].update(capability_requirements=['LOCAL_RULES'], runtime_requirement='TRUSTED_IN_PROCESS_LOCAL')
    saved = e.agents.save(e.ctx, None, {'definition': definition})
    restarted = DeclarativeAgentsService(e.store, e.novels, e.chapters, sources=e.sources)
    found = restarted.definitions(e.ctx)['items'][0]
    assert found['definition'] == saved['definition']
    report = restarted.preflight(e.ctx, found['definition'])
    contract = report['adapter_contract']
    assert report['execution_available'] and contract['model_capability'] == 'NONE'
    assert contract['runtime_requirement'] == 'TRUSTED_IN_PROCESS_LOCAL'
    assert contract['input_schema'] == found['definition']['agent']['input_schema']
    assert contract['output_schema'] == found['definition']['agent']['output_schema']
    assert contract['permission_grants'] == [] and contract['executable_plugins'] == 'DENY_ALL'
    assert restarted.runs(e.ctx)['items'] == []
    assert restarted.catalog(e.ctx)['sdk_contract']['review_required']


@pytest.mark.parametrize('fields', [
    {'capability_requirements': ['SHELL']}, {'capability_requirements': ['TEXT']},
    {'capability_requirements': ['LOCAL_RULES', 'LOCAL_RULES']},
    {'runtime_requirement': 'ORIGINAL_BOUND_LOCAL_MODEL'}, {'runtime_requirement': 'python:module'},
    {'runtime_requirement': 'TRUSTED_IN_PROCESS_LOCAL', 'model_route': 'unregistered'},
])
def test_unsupported_or_contradictory_sdk_requirements_fail_closed(fields):
    definition = default_definition(); definition['agent'].update(fields)
    with pytest.raises(ValueError): WorkflowAuthoring.model_validate(definition)


def test_bound_model_contract_is_declaration_only_and_does_not_satisfy_missing_runtime(env):
    from types import SimpleNamespace
    e = env; e.agents.broker = SimpleNamespace(candidates=lambda: [{'route_id': 'registered', 'capability': 'TEXT', 'model_id': 'm', 'provider_id': 'p'}])
    d = default_definition(); d['agent'].update(model_route='registered', capability_requirements=['TEXT'], runtime_requirement='ORIGINAL_BOUND_LOCAL_MODEL'); d['nodes'][0]['type'] = 'agent_task'
    report = e.agents.preflight(e.ctx, d)
    assert not report['execution_available'] and report['blockers'] == ['CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED']
    assert report['adapter_contract']['model_capability'] == 'TEXT'
    assert report['adapter_contract']['real_model_verification'] == 'NOT_RUN'
    assert e.agents.runs(e.ctx)['items'] == []


def test_sdk_host_validates_explicit_scalar_schemas_before_dispatch_and_receipt():
    schema = {'fields': [{'name': 'draft', 'type': 'string', 'max_length': 20}]}
    class Echo:
        capabilities = AdapterCapabilities('trusted.example', '1.0.0', ('echo',), input_schema=schema, output_schema=schema)
        calls = 0
        def execute(self, request): self.calls += 1; return request.input
    adapter = Echo(); request = AdapterRequest('echo', {'draft': 'Bounded'}, 'request', 'scope')
    assert run_trusted_local(adapter, request, authorize=lambda: None).output == request.input
    with pytest.raises(ValueError): run_trusted_local(adapter, replace(request, input={'script': 'arbitrary'}), authorize=lambda: None)
    assert adapter.calls == 1
    adapter.capabilities = replace(adapter.capabilities, runtime_requirement='ORIGINAL_BOUND_LOCAL_MODEL')
    with pytest.raises(ValueError, match='RUNTIME_CAPABILITY'): run_trusted_local(adapter, request, authorize=lambda: None)
    assert adapter.calls == 1
    adapter.capabilities = replace(adapter.capabilities, runtime_requirement='TRUSTED_IN_PROCESS_LOCAL', output_schema={'fields': [{'name': 'different'}]})
    with pytest.raises(ValueError): run_trusted_local(adapter, request, authorize=lambda: None)


def test_extended_template_and_sdk_mounted_api_keep_permission_and_scope_guards(env):
    e = env; denied = [False]; calls = []
    def authorize(nid, token, branch, permission):
        calls.append(permission)
        if denied[0]: raise HTTPException(403)
        return e.ctx.actor, e.ctx.scope
    def flag(name):
        if name not in e.enabled: raise HTTPException(404)
    app = FastAPI(); app.include_router(create_template_library_router(e.library, authorize, flag)); app.include_router(create_declarative_agents_router(e.agents, authorize, flag))
    client = TestClient(app); base = f'/novels/{e.ctx.novel_id}/experimental'
    catalog = client.get(base + '/template-library'); assert catalog.headers['cache-control'] == 'no-store'
    agent = next(r for r in catalog.json()['extended_items'] if r['package']['manifest']['type'] == 'agent')
    copied = client.post(base + '/template-library/instances', json={'package_id': agent['id'], 'package_digest': agent['digest'], 'request_id': 'api-agent'})
    assert copied.status_code == 201 and 'domain.write' in calls
    definitions = client.get(base + '/declarative-agents/definitions').json()['items']
    assert definitions[0]['id'] == copied.json()['linked_target']['id']
    preflight = client.post(base + '/declarative-agents/preflight', json=definitions[0]['definition'])
    assert preflight.status_code == 200 and preflight.json()['adapter_contract']['executable_plugins'] == 'DENY_ALL'
    denied[0] = True
    assert client.get(base + '/template-library').status_code == 403
    denied[0] = False; e.enabled.clear()
    assert client.get(base + '/template-library').status_code == 404
    assert client.post(base + '/declarative-agents/preflight', json=definitions[0]['definition']).status_code == 404


def with_reference(rig, image_asset):
    body = layout(rig, image_asset); panel = body['panels'][0]
    panel.update(character_ids=['alice'], image_brief='Alice studies a tide map; preserve her blue coat.',
        appearance_references=[{'character_id': 'alice', 'asset_id': image_asset['id'], 'expected_asset_version': image_asset['version'], 'note': 'Blue coat, short hair.'}])
    return body


def test_comic_brief_appearance_scene_chain_persists_restores_and_exports(rig, comic, image_asset):
    body = with_reference(rig, image_asset); row = save(comic, rig, body)
    assert row['document']['panels'][0]['image_brief'] == body['panels'][0]['image_brief']
    reopened = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    assert reopened.records(rig.nid, rig.scope, rig.actor)['items'][0]['document'] == row['document']
    approved = approve(comic, rig, row)
    import zipfile
    with zipfile.ZipFile(io.BytesIO(comic.export(rig.nid, rig.scope, rig.actor, row['id'], approved['version']))) as archive:
        manifest = json.loads(archive.read('manifest.json')); panel = manifest['panel_sources'][0]
        assert panel['image_brief'] == body['panels'][0]['image_brief'] and panel['scene_id'] == row['scene_ids']['panel']
        assert panel['appearance_references'][0]['expected_asset_version'] == image_asset['version']
        assert manifest['asset_bindings'][image_asset['id']]['sha256'] == image_asset['sha256']
    changed = copy.deepcopy(row['document']); changed['panels'][0]['image_brief'] = 'Revised composition.'
    edited = comic.save(rig.nid, rig.scope, rig.actor, changed, rid=row['id'], expected_version=approved['version'])
    assert edited['status'] == 'DRAFT'
    restored = comic.restore(rig.nid, rig.scope, rig.actor, row['id'], edited['version'], 1)
    assert restored['document'] == row['document']
    assert len(rig.assets.list(rig.nid)) == 1


@pytest.mark.parametrize('mutation', ['unapproved', 'wrong_version', 'missing', 'other_novel', 'unknown_character', 'duplicate'])
def test_comic_appearance_references_are_original_approved_scoped_assets(rig, comic, image_asset, mutation):
    body = with_reference(rig, image_asset); ref = body['panels'][0]['appearance_references'][0]
    if mutation == 'unapproved':
        asset = rig.assets.create(rig.nid, 'unapproved.png', base64.b64encode(synthetic_png()).decode(), 'image/png')
        ref.update(asset_id=asset['id'], expected_asset_version=asset['version'])
    elif mutation == 'wrong_version': ref['expected_asset_version'] += 1
    elif mutation == 'missing': ref['asset_id'] = 'missing'
    elif mutation == 'other_novel':
        other = rig.novels.create({'title': 'Other project'})['id']
        asset = rig.assets.create(other, 'other.png', base64.b64encode(synthetic_png()).decode(), 'image/png')
        ref.update(asset_id=asset['id'], expected_asset_version=asset['version'])
    elif mutation == 'unknown_character': ref['character_id'] = 'unknown'
    elif mutation == 'duplicate': body['panels'][0]['appearance_references'].append(copy.deepcopy(ref))
    with pytest.raises((ValueError, FileNotFoundError)): save(comic, rig, body)
    assert comic.records(rig.nid, rig.scope, rig.actor)['items'] == []


def test_reference_only_asset_privacy_or_version_change_hides_brief_and_blocks_export(rig, comic, image_asset, production):
    from app.source_privacy import review_source_privacy, content_digest
    body = with_reference(rig, image_asset)
    chapter = rig.chapters.create(rig.nid, {'title': 'Reference-only source', 'content': 'Private appearance evidence.'})
    chapter = rig.chapters.get(chapter['id'])
    asset = rig.assets.create(rig.nid, 'reference.png', base64.b64encode(synthetic_png()).decode(), 'image/png')
    production.annotate(rig.nid, rig.scope, rig.actor, asset['id'], declaration(asset['version'], chapter_ids=[chapter['id']]))
    asset = rig.assets.get(asset['id'])
    comic.approve_image(rig.nid, rig.scope, rig.actor, asset['id'], asset['version'])
    asset = rig.assets.get(asset['id'])
    body['panels'][0]['appearance_references'][0].update(asset_id=asset['id'], expected_asset_version=asset['version'])
    row = approve(comic, rig, save(comic, rig, body))
    review_source_privacy(chapter, None, rig.actor, 'CLOUD_ALLOWED', chapter['version'], content_digest(chapter), rig.root)
    view = comic.records(rig.nid, rig.scope, rig.actor)['items'][0]
    assert view['stale'] and 'document' not in view
    with pytest.raises(StaleSourceError): comic.export(rig.nid, rig.scope, rig.actor, row['id'], row['version'])


def test_legacy_installed_manifest_upgrade_accepts_unchanged_version_without_rewriting_old_history(env):
    e = env; p = starter('agent'); installed = install(e, p)
    # Simulate the additive metadata gap in a pre-upgrade stored declaration.
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as state:
        entry = state['collections'][e.library.PACKAGES][installed['id']]
        entry['package']['manifest'].pop('compatibility'); entry['package']['manifest'].pop('permissions')
        entry['package']['content']['agent'].pop('capability_requirements')
        entry['package']['content']['agent'].pop('runtime_requirement')
        entry['package_digest'] = digest(entry['package'])
        legacy = copy.deepcopy(entry['package'])
    before = e.store.read(e.ctx.novel_id, e.ctx.scope)
    catalog = e.library.catalog(e.ctx)
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before
    normalized = next(r['package'] for r in catalog['extended_items'] if r['id'] == p['manifest']['id'])
    assert normalized['manifest']['permissions']['execute'] is False
    updated = install(e, normalized)
    assert updated['version'] == 2
    saved = e.store.read(e.ctx.novel_id, e.ctx.scope)['collections'][e.library.PACKAGES][installed['id']]
    assert saved['history'][0]['package'] == legacy


def test_legacy_comic_record_without_new_fields_reads_exports_and_restores_additively(rig, comic, image_asset):
    row = save(comic, rig, layout(rig, image_asset))
    with rig.store.transaction(rig.nid, rig.scope) as state:
        panel = state['collections'][comic.RECORDS][row['id']]['document']['panels'][0]
        panel.pop('image_brief'); panel.pop('appearance_references')
    before = rig.store.read(rig.nid, rig.scope)
    reopened = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    current = reopened.records(rig.nid, rig.scope, rig.actor)['items'][0]
    assert not current['stale'] and 'image_brief' not in current['document']['panels'][0]
    assert rig.store.read(rig.nid, rig.scope) == before
    approved = approve(reopened, rig, current)
    import zipfile
    with zipfile.ZipFile(io.BytesIO(reopened.export(rig.nid, rig.scope, rig.actor, current['id'], approved['version']))) as archive:
        panel = json.loads(archive.read('manifest.json'))['panel_sources'][0]
        assert panel['image_brief'] == '' and panel['appearance_references'] == []
    restored = reopened.restore(rig.nid, rig.scope, rig.actor, row['id'], approved['version'], 1)
    assert restored['document']['panels'][0]['image_brief'] == '' and restored['status'] == 'DRAFT'


from test_r3_mounted_contracts import mounted, checked, prefix
from test_r5_comic_mounted import create_layout


def test_comic_reference_fields_on_original_mounted_router_are_cas_and_privacy_bound(mounted):
    e = mounted; row, asset, body = create_layout(e)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Alice'})
    body['panels'][0].update(character_ids=['alice'], image_brief='Private reference-bound image brief.',
        appearance_references=[{'character_id': 'alice', 'asset_id': asset['id'], 'expected_asset_version': asset['version'] + 1, 'note': 'Approved character appearance.'}])
    path = e.base + '/comic-layouts/records/' + row['id']
    updated = checked(e.client.put(path, json={**body, 'expected_version': row['version']}))
    assert updated['document']['panels'][0]['appearance_references'][0]['asset_id'] == asset['id']
    assert e.client.put(path, json={**body, 'expected_version': row['version']}).status_code == 409
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Changed Alice'})
    projection = e.client.get(e.base + '/comic-layouts/records')
    assert projection.json()['items'][0]['stale']
    assert 'Private reference-bound' not in projection.text and asset['id'] not in projection.text
    assert e.client.post(path + '/preflight', json={'expected_version': updated['version']}).status_code == 409
