import threading
import os
import subprocess
import sys
from pathlib import Path
import pytest
from contextlib import contextmanager
from test_studio_asset_query import rig, shared_scope

@pytest.mark.skipif(os.environ.get('AUDIO_LOCK_PROBE_CHILD') != '1', reason='subprocess-only lock probe')
def test_lock_probe_child(rig, monkeypatch):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    scope, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    rig.grants.assign_permission(PermissionAssignment('query-write', 'reader', 'domain.write', ModalityDomain.NOVEL, grant_scope, 'fixture'))
    asset = rig.seed('synthetic.wav', 'audio', scope_value=scope)
    url = f'/api/projects/{rig.nid}/studio/assets/{asset["id"]}'
    assert rig.client.get(url + '/history', headers=headers).status_code == 200
    writer_ready, reader_asset, session_entered = threading.Event(), threading.Event(), threading.Event()
    from app.repositories.file.scope import FileAuthorizationRepository
    writer_thread = []
    original_mutation = FileAuthorizationRepository.mutation
    authority_entered = threading.Event()
    @contextmanager
    def tracked_mutation(self):
        with original_mutation(self):
            if writer_thread and threading.get_ident() == writer_thread[0]:
                print('writer-authority-lock-entered', flush=True)
                authority_entered.set()
            yield
    monkeypatch.setattr(FileAuthorizationRepository, 'mutation', tracked_mutation)
    original_binding = rig.sessions.binding_lease
    original_content = rig.assets.content
    @contextmanager
    def binding(token):
        print('writer-at-binding', flush=True)
        writer_ready.set()
        assert reader_asset.wait(5)
        with original_binding(token) as actor:
            writer_thread.append(threading.get_ident())
            print('writer-session-entered', flush=True)
            session_entered.set()
            yield actor
    def writer():
        response = rig.client.delete(url, params={'expected_version':1}, headers=headers)
        print('writer-finished', response.status_code, flush=True)
    def content(*args, **kwargs):
        print('reader-asset-entered', flush=True)
        reader_asset.set()
        assert authority_entered.wait(5)
        print('reader-resuming', flush=True)
        return original_content(*args, **kwargs)
    monkeypatch.setattr(rig.sessions, 'binding_lease', binding)
    monkeypatch.setattr(rig.assets, 'content', content)
    worker = threading.Thread(target=writer, daemon=True)
    worker.start()
    assert writer_ready.wait(5)
    response = rig.client.get(url + '/history', headers=headers)
    print('reader-finished', response.status_code, flush=True)
    worker.join(5)
    assert not worker.is_alive()



def test_competing_metadata_lifecycle_and_history_read_in_subprocess():
    env = dict(os.environ, AUDIO_LOCK_PROBE_CHILD='1')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-s',
        str(Path(__file__).resolve()) + '::test_lock_probe_child'],
        env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'writer-authority-lock-entered' in result.stdout
    assert 'reader-finished 200' in result.stdout and 'writer-finished 200' in result.stdout
