"""Exercise the unchanged mounted chapter routes with the packaged defaults.

These use actual isolated repositories/permissions, not an inference substitute.
Native packaged model generation is separately recorded in RC acceptance.
"""
import json
from types import SimpleNamespace

from app.packaging.packaged_processes import PackagedProcessConfig
from test_packaged_process_factory_v070 import layout, paths
from test_r3_mounted_contracts import mounted, prefix, checked  # noqa: F401
from test_surface_branch_manuscript import doc
from test_surface_branch_manuscript_mounted import branch_env  # noqa: F401


def test_packaged_default_closes_scoped_chapter_gate_without_permission_fallback(branch_env, tmp_path, monkeypatch):
    import app.dependencies as dependencies
    e = branch_env
    read = dependencies.collaboration_read_service
    for name, value in {'sessions':e.sessions, 'membership_authorization':e.membership,
        'identity':e.identity, 'authorization':e.authorization, 'scopes':e.scopes,
        'chapters':e.bundle.chapters, 'generations':e.bundle.generations,
        'novels':e.bundle.novels, 'branch_manuscripts':e.owner,
        'collaboration_application':e.application}.items():
        monkeypatch.setattr(read, name, value)
    base = e.prefix + f'/collaboration/workspaces/{e.workspace}/projects/{e.nid}/storylines/{e.storyline}/branches/{e.branch}/chapters'
    # The previous packaged environment had no EXPERIMENTAL_FEATURES entry.
    # A clean inherited environment therefore stopped the existing UI route.
    monkeypatch.delenv('EXPERIMENTAL_FEATURES', raising=False)
    before = e.client.get(base, headers=e.headers)
    assert before.status_code == 404
    assert before.json()['detail']['feature'] == 'branch_manuscript_v1'
    assert before.json()['detail']['code'] == 'EXPERIMENTAL_FEATURE_DISABLED'
    # Derive the real defaults; only filesystem/version probes are fixtures.
    monkeypatch.setattr('app.packaging.packaged_processes._run',
        lambda argv, **_: SimpleNamespace(stdout='(3, 12)' if 'python.exe' in str(argv[0]) else 'postgres (PostgreSQL) 16.4', returncode=0))
    config = PackagedProcessConfig.create(layout(tmp_path), paths(tmp_path))
    env = config.environment(database_port=55432, backend_port=58123)
    assert env['EXPERIMENTAL_FEATURES'] == 'branch_manuscript_v1'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', env['EXPERIMENTAL_FEATURES'])
    assert checked(e.client.get(base, headers=e.headers))['items'] == []
    created = checked(e.client.post(base, headers=e.headers, json={'title':'Default first chapter'}), 201)
    assert created['id'].startswith(e.nid + ':~b') and created['version']==1
    assert [r['id'] for r in checked(e.client.get(base, headers=e.headers))['items']]==[created['id']]
    detail = e.prefix + f"/chapters/{created['id']}"
    saved = checked(e.client.put(detail, headers=e.headers,
        json={'document':doc('Saved under the packaged default'), 'version':1}))
    assert saved['version']==2
    stale = e.client.put(detail, headers=e.headers,
        json={'document':doc('Stale must fail'), 'version':1})
    assert stale.status_code == 409
    assert checked(e.client.get(detail, headers=e.headers))['document']==saved['document']
    assert e.client.get(base).status_code==401
    assert e.client.post(base, headers=e.viewer_headers, json={'title':'Denied'}).status_code==403
    assert e.client.get(e.prefix+f"/chapters/{e.chapter['id']}",headers=e.headers).status_code==404
    assert e.chapters.get(e.chapter['id']) == e.chapter
    # Explicit opt-out and the V1 freeze still fail closed. No API gate bypass.
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    assert e.client.get(base,headers=e.headers).status_code==404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',env['EXPERIMENTAL_FEATURES'])
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert e.client.get(base,headers=e.headers).status_code==404
    print('RC_NATIVE_DEFAULT_PROFILE '+json.dumps({'backend':e.backend,'prefix':e.prefix,
        'old_default_response':{'status':before.status_code,'body':before.json()},
        'new_default_allowlist':env['EXPERIMENTAL_FEATURES'], 'create_status':201,
        'save_version':saved['version'],'stale_status':stale.status_code,
        'global_opt_out_and_freeze_remain_closed':True}))
