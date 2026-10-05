"""Opt-in REAL TCP integration across two independent uvicorn processes/data roots.

RUN_B10_TCP_SYNC_TEST=1 pytest -q -s tests/test_r5_offline_sync_tcp.py
No TestClient, mocked transport, shared application singleton, accounts, TLS/E2EE
claim or external host. A blocked socket is a failure, never a fabricated pass.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest
from app.experimental.flags import FLAGS


class Endpoint:
    def __init__(self, root, label):
        self.root, self.label = root, label; root.mkdir(parents=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); self.port = sock.getsockname()[1]
        self.url = f'http://127.0.0.1:{self.port}/api'; self.process = None
        self.client = httpx.Client(base_url=self.url, headers={'X-Session-Token': 'synthetic-sync-' + label}, timeout=10, trust_env=False)
        self.log = (root / 'endpoint.log').open('w+')

    def start(self):
        env = {**os.environ, 'NOVEL_DATA_PATH': str(self.root / 'novels'), 'HOME': str(self.root), 'XDG_DATA_HOME': str(self.root / 'xdg'),
            'BACKUP_PATH': str(self.root / 'backups'), 'DATABASE_BACKUP_PATH': str(self.root / 'db-backups'), 'STORAGE_BACKEND': 'file',
            'KNOWLEDGE_SOURCE_PATH': str(self.root / 'novels'), 'ENABLE_COLLABORATION_RUNTIME': 'false', 'ENABLE_PACKAGED_RUNTIME': 'false',
            'ENABLE_CLOUD': 'false', 'MOCK_PROVIDER': 'false', 'EXPERIMENTAL_FEATURES': ','.join(FLAGS), 'V1_ACCEPTANCE_MODE': 'false',
            'CREDENTIAL_VAULT_BACKEND': 'memory', 'CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK': 'true',
            'COLLABORATION_DEV_SESSIONS_JSON': json.dumps([{'token': 'synthetic-sync-' + self.label, 'session_id': 'session-' + self.label,
                'client_id': 'client-' + self.label, 'actor_id': 'actor-' + self.label, 'workspace_id': 'workspace-' + self.label}])}
        self.process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(self.port), '--no-access-log'],
            cwd=Path(__file__).resolve().parents[1], env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self.process.poll() is not None: break
            try:
                if self.client.get('/health').status_code == 200: return
            except httpx.TransportError: pass
            time.sleep(.1)
        self.log.flush(); self.log.seek(0); tail = self.log.read()[-3000:]
        raise AssertionError('Real local endpoint did not start: ' + tail)

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=10)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait(timeout=10)

    def close(self): self.stop(); self.client.close(); self.log.close()
    def get(self, path):
        r = self.client.get(path); assert r.status_code == 200, r.text; return r.json()
    def post(self, path, body, status=200):
        r = self.client.post(path, json=body); assert r.status_code == status, r.text; return r.json()
    def records(self): return self.get(self.base + '/records')
    def channel(self): return self.records()['channels'][0]
    def put_document(self, text):
        chapter = self.get('/chapters/' + self.cid); document = chapter['document']; document['content'][-1] = {'type': 'paragraph', 'content': [{'type': 'text', 'text': text}]}
        r = self.client.put('/chapters/' + self.cid, json={'version': chapter['version'], 'document': document}); assert r.status_code == 200, r.text
    def queue(self, tombstone=False):
        channel = self.channel()
        return self.post(self.base + '/channels/' + channel['id'] + '/queue', {'expected_version': channel['version'], 'chapter_id': self.cid, 'request_id': uuid4().hex, 'tombstone': tombstone})
    def export(self, row): return self.post(self.base + '/outbox/' + row['id'] + '/export', {'expected_version': row['version'], 'envelope_digest': row['envelope_digest'], 'acknowledge_copy_boundary': True})
    def receive(self, out, new=False):
        channel = self.channel()
        return self.post(self.base + '/channels/' + channel['id'] + '/receive', {'expected_version': channel['version'], 'envelope': out['envelope'], 'target_chapter_id': None if new else self.cid, 'create_new': new})
    def review(self, row, choices=None): return self.post(self.base + '/inbox/' + row['id'] + '/review', {'expected_version': row['version'], 'choices': choices or {}})
    def apply(self, row, plan): return self.post(self.base + '/inbox/' + row['id'] + '/apply', {'expected_version': row['version'], 'preview_digest': plan['preview_digest'], 'choices': plan['choices'], 'confirmed': True})


@pytest.mark.file_backend_only
@pytest.mark.skipif(os.getenv('RUN_B10_TCP_SYNC_TEST') != '1', reason='explicit real-loopback subprocess gate; not an in-process substitute')
def test_two_isolated_tcp_endpoints_add_edit_conflict_disconnect_replay_tombstone_and_revocation(tmp_path):
    with ExitStack() as stack:
        a, b = Endpoint(tmp_path / 'endpoint-a', 'A'), Endpoint(tmp_path / 'endpoint-b', 'B')
        stack.callback(a.close); stack.callback(b.close); a.start(); b.start()
        assert a.process.pid != b.process.pid and a.root != b.root and a.port != b.port
        for endpoint in [a, b]:
            novel = endpoint.post('/novels', {'title': 'B10 synthetic TCP ' + endpoint.label}, 201)
            endpoint.nid = novel['id']; endpoint.base = '/novels/' + endpoint.nid + '/experimental/offline-sync'
        chapter = a.post('/novels/' + a.nid + '/chapters', {'title': 'Synthetic TCP chapter', 'content': 'Synthetic seed'}, 201); a.cid = chapter['id']
        stream = uuid4().hex
        a.post(a.base + '/channels', {'stream_id': stream, 'endpoint_id': 'A', 'peer_id': 'B', 'chapter_ids': [a.cid], 'allow_new_chapters': False}, 201)
        b.post(b.base + '/channels', {'stream_id': stream, 'endpoint_id': 'B', 'peer_id': 'A', 'chapter_ids': [], 'allow_new_chapters': True}, 201)
        add = a.export(a.queue()); inbox = b.receive(add, new=True); result = b.apply(inbox, b.review(inbox)); b.cid = result['target_chapter_id']
        assert b.cid != a.cid and b.get('/chapters/' + b.cid)['document'] == a.get('/chapters/' + a.cid)['document']
        assert b.receive(add, new=True)['duplicate']
        a.put_document('A saved offline edit'); edit = a.export(a.queue()); received = b.receive(edit); b.apply(received, b.review(received))
        assert 'A saved offline edit' in str(b.get('/chapters/' + b.cid)['document'])
        a.put_document('Incoming conflicting text'); b.put_document('Local conflicting text'); conflict = b.receive(a.export(a.queue()))
        plan = b.review(conflict); assert plan['unresolved'] == 1 and not plan['can_apply']
        assert 'Local conflicting text' in str(b.get('/chapters/' + b.cid)['document'])
        choices = {s['id']: 'INCOMING' for s in plan['segments'] if s['kind'] == 'CONFLICT'}; b.apply(conflict, b.review(conflict, choices))
        b.stop(); a.put_document('Saved while the other process is stopped'); pending = a.export(a.queue())
        with pytest.raises(httpx.TransportError): b.client.get('/health')
        failed = a.post(a.base + '/outbox/' + pending['id'] + '/delivery', {'expected_version': pending['version'], 'state': 'FAILED'})
        assert a.get('/chapters/' + a.cid)['document'] == pending['envelope']['snapshot']['document']
        b.start(); retry = a.export(failed); assert retry['envelope'] == pending['envelope']
        resumed = b.receive(retry); resumed_plan = b.review(resumed)
        # Fixed batch baseline deliberately requires renewed conflict choices.
        renewed = {s['id']: 'INCOMING' for s in resumed_plan['segments'] if s['kind'] == 'CONFLICT'}
        b.apply(resumed, b.review(resumed, renewed)); assert b.receive(retry)['duplicate']
        chapter = a.get('/chapters/' + a.cid); a.post('/chapters/' + a.cid + '/archive?expected_version=' + str(chapter['version']), {})
        tombstone = a.export(a.queue(tombstone=True)); removed = b.receive(tombstone); plan = b.review(removed)
        assert not b.get('/chapters/' + b.cid)['is_archived']; b.apply(removed, b.review(removed, {plan['segments'][0]['id']: 'INCOMING'}))
        assert b.get('/chapters/' + b.cid)['is_archived']
        channel = b.channel(); b.post(b.base + '/channels/' + channel['id'] + '/revoke', {'expected_version': channel['version']})
        rejected = b.client.post(b.base + '/channels/' + channel['id'] + '/receive', json={'expected_version': channel['version'] + 1, 'envelope': tombstone['envelope'], 'target_chapter_id': b.cid})
        assert rejected.status_code == 422 and 'REVOKED' in rejected.text
        # The previously received bytes still exist in this process, exactly as disclosed.
        assert add['envelope']['snapshot'] is not None
        print('B10_TCP_TRANSFER: REAL_HTTP_LOOPBACK, two independent uvicorn processes and isolated File roots; add/edit/conflict/disconnect/restart/replay/tombstone/revocation passed; no production cloud or E2EE claim.')
