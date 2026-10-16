"""Isolated Prompt adoption UI acceptance over the original packaged runtime.

The production module remains literal False. Only the explicitly launched
acceptance backend changes its in-memory boolean, after importing app.main.
Ordinary production backends before and after it must really refuse with 503.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--storage-backend', choices=('file', 'postgres'), default='file')
    parser.add_argument('--project')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]+', args.label):
        parser.error('label must be bounded lowercase alphanumeric text')
    root = Path(__file__).resolve().parents[1]
    gate_path = root / 'app/creative/prompt_adoption_api.py'
    source = gate_path.read_bytes()
    tree = ast.parse(source)
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'PROMPT_ADOPTION_WRITE_ENABLED' for target in node.targets)]
    assert len(assignments) == 1 and isinstance(assignments[0].value, ast.Constant) and assignments[0].value.value is False
    database_identity = None
    if args.storage_backend == 'postgres':
        url = os.environ.get('DATABASE_URL', '')
        parsed = urlsplit(url)
        if (not url or url != os.environ.get('TEST_POSTGRES_DATABASE_URL')
                or parsed.scheme not in {'postgres', 'postgresql'}
                or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or not parsed.port or not re.fullmatch(r'/v2_[A-Za-z0-9_]+', parsed.path)
                or parsed.query or parsed.fragment):
            parser.error('Use the original PostgreSQL wrapper with its loopback v2_* database')
        import psycopg
        with psycopg.connect(url, connect_timeout=5, autocommit=True,
                            options='-c statement_timeout=5000') as connection:
            row = connection.execute('SELECT version(),current_database(),host(inet_server_addr()),inet_server_port(),'
                '(SELECT oid::bigint FROM pg_database WHERE datname=current_database())').fetchone()
        assert row[1] == parsed.path[1:] and row[2] in {'127.0.0.1', '::1'} and row[3] == parsed.port
        database_identity = dict(zip(('version', 'database', 'host', 'port', 'database_oid'), row))
    receipts = root / 'docs/delivery/v2-r3-adoption-ui-20261017' / args.label
    runtime = root / '.runtime' / args.label
    receipts.mkdir(parents=True, exist_ok=False)
    runtime.mkdir(parents=True, exist_ok=False)
    for port in (8138, 5208):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Existing Node runtime unavailable')
    api, origin = 'http://127.0.0.1:8138', 'http://127.0.0.1:5208'
    owned, logs = [], []
    result = {'storage_backend': args.storage_backend, 'database_identity': database_identity,
        'identity_owner': 'LocalSessionBootstrap', 'asset_storage_owner': 'original File AssetLibraryService',
        'production_literal_gate': False, 'isolated_acceptance': True, 'production_environment_toggle': False,
        'gate_source_sha256': hashlib.sha256(source).hexdigest(), 'development_sessions': False,
        'response_mocks': False, 'model_execution': 'NOT_REQUESTED', 'model_counter': 'NOT_INSTRUMENTED'}

    def save(name, value):
        (receipts / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def call(path, body=None, token=None, branch=None, method=None):
        headers = {'Origin': origin}
        if token:
            headers['X-Session-Token'] = token
        if branch:
            headers['X-Branch-ID'] = branch
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        try:
            response = urlopen(Request(api + path, data=data, headers=headers, method=method), timeout=20)
        except HTTPError as response:
            return response.code, json.loads(response.read())
        with response:
            return response.status, json.load(response) if response.status != 204 else None

    def checked(path, expected, **kwargs):
        status, value = call(path, **kwargs)
        assert status == expected, {'path': path, 'status': status, 'body': value}
        return value

    def environment(secret=None, instance=None):
        env = dict(os.environ, PROJECT_ROOT=str(root), NOVEL_DATA_PATH=str(runtime / 'novel-data'),
            STORAGE_BACKEND=args.storage_backend, ENABLE_PACKAGED_RUNTIME='true', ENABLE_COLLABORATION_RUNTIME='true',
            COLLABORATION_DEV_SESSIONS_JSON='', PACKAGED_RUNTIME_INSTANCE_ID=instance or '',
            PACKAGED_BOOTSTRAP_SECRET=secret or '', FRONTEND_ORIGIN=origin,
            PACKAGED_FRONTEND_DIST=str(root / 'frontend/dist'), PYTHONUTF8='1',
            EXPERIMENTAL_FEATURES='narrative_production_v2,asset_lineage_v2', V061_API_URL=api,
            ENABLE_CLOUD='false', ENABLE_PROVIDER_FALLBACK='false', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        if args.storage_backend == 'file':
            for name in ('DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL', 'E2E_DATABASE_URL'):
                env.pop(name, None)
        return env

    def start(command, cwd, name, env):
        stdout = (receipts / f'{name}.stdout.log').open('w', encoding='utf-8')
        stderr = (receipts / f'{name}.stderr.log').open('w', encoding='utf-8')
        logs.extend([stdout, stderr])
        child = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        owned.append((name, child))
        return child

    def stop(name, child):
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        result[f'owned_{name}_pid'] = child.pid
        result[f'owned_{name}_stopped'] = child.poll() is not None

    def bootstrap(name, isolated=False):
        secret, instance = secrets.token_urlsafe(48), str(uuid4())
        command = [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8138']
        if isolated:
            code = ('import json,os; import app.main as original; '
                'import app.creative.prompt_adoption_api as gate; import uvicorn; '
                'assert gate.PROMPT_ADOPTION_WRITE_ENABLED is False; '
                'gate.PROMPT_ADOPTION_WRITE_ENABLED=True; '
                'print(json.dumps(dict(marker="PROMPT_ADOPTION_UI_ISOLATED_PROCESS",pid=os.getpid(),'
                'original_gate=False,process_gate=gate.PROMPT_ADOPTION_WRITE_ENABLED)),flush=True); '
                'uvicorn.run(original.app,host="127.0.0.1",port=8138)')
            command = [sys.executable, '-c', code]
        child = start(command, root, name, environment(secret, instance))
        deadline = time.monotonic() + 45
        observed = None
        while True:
            if child.poll() is not None:
                raise RuntimeError(f'Owned {name} exited before readiness')
            try:
                status, health = call('/api/health')
                observed = health.get('storage')
                if status == 200 and observed == args.storage_backend:
                    break
            except (URLError, OSError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f'{name} readiness deadline: expected {args.storage_backend}, observed {observed}')
            time.sleep(.2)
        issued = checked('/api/packaged/bootstrap', 200,
            body={'bootstrap_secret': secret, 'runtime_instance_id': instance})
        token = issued['session_token']
        workspace = checked('/api/packaged/initial-workspace', 200, body={}, token=token)
        assert workspace['id'] == 'workspace-a'
        result[name + '_health_storage'] = observed
        return child, token

    control = None

    def refusal(token, phase):
        assert control is not None
        nid, branch, board = control['nid'], control['branch'], control['board']
        studio = f'/api/projects/{nid}/studio'
        raw = f'/api/novels/{nid}/experimental/creative/documents/{board["id"]}'
        before = checked(raw, 200, token=token, branch=branch)
        projection = checked(studio + f'/documents/{board["id"]}/prompt-adoption', 200, token=token, branch=branch)
        assert projection['write_enabled'] is False
        dto = dict(control['dto'], request_id=uuid4().hex)
        status, body = call(studio + f'/documents/{board["id"]}/shots/{board["shots"][0]["id"]}/prompt-adoption',
                            body=dto, token=token, branch=branch)
        assert status == 503 and body['detail']['code'] == 'PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED', (status, body)
        after = checked(raw, 200, token=token, branch=branch)
        assert before == after
        digest = hashlib.sha256(json.dumps(before, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        save(phase + '.json', {'status': 503, 'code': body['detail']['code'], 'write_enabled': False,
            'target_id': board['id'], 'target_version': before['version'], 'before_owner_sha256': digest,
            'after_owner_sha256': digest, 'owner_unchanged': True})

    try:
        ordinary, token = bootstrap('production_before')
        admin = '/api/collaboration/admin/workspaces/workspace-a'
        project = checked(admin + '/projects', 201, body={'title': 'Adoption UI production control', 'genre': ''}, token=token)
        nid = project['id']
        navigation = checked(admin + '/navigation', 200, token=token)
        branch = next(row['branch_id'] for row in navigation['eligible_paths'] if row['project_id'] == nid)
        studio = f'/api/projects/{nid}/studio'
        checked(studio + '/activate', 200, body={}, token=token, branch=branch)
        prompt = checked(studio + '/prompts', 201, token=token, branch=branch,
            body={'text': 'Production control source 中文 🙂', 'purpose': 'IMAGE', 'origin': 'MANUAL', 'request_id': uuid4().hex})
        checked(studio + f'/prompts/{prompt["family_id"]}/revisions/{prompt["asset_id"]}/approve?expected_version={prompt["asset_version"]}',
            200, body={}, token=token, branch=branch)
        creative = f'/api/novels/{nid}/experimental/creative/documents'
        script = checked(creative, 201, token=token, branch=branch, body={'mode': 'SCREENPLAY', 'title': 'Gate control',
            'source_independent': True, 'scenes': [{'id': 'control-scene', 'sequence': 1, 'heading': 'INT. ROOM - DAY', 'action': 'A visitor arrives.'}]})
        board = checked(creative + f'/{script["id"]}/derive', 201, token=token, branch=branch,
            body={'expected_version': script['version'], 'mode': 'STORYBOARD', 'title': 'Gate control target', 'shot_policy': 'SCENE'})
        projection = checked(studio + f'/documents/{board["id"]}/prompt-adoption', 200, token=token, branch=branch)
        body = checked(studio + f'/prompts/{prompt["family_id"]}/revisions/{prompt["asset_id"]}/body', 200, token=token, branch=branch)
        control = {'nid': nid, 'branch': branch, 'board': board, 'dto': {'shot_id': board['shots'][0]['id'],
            'family_id': prompt['family_id'], 'asset_id': prompt['asset_id'], 'revision': 1,
            'expected_digest': body['digest'], 'expected_version': projection['version'],
            'expected_digest_target': projection['digest']}}
        refusal(token, 'production-before-control')
        stop('production_before', ordinary)
        isolated, token = bootstrap('isolated_acceptance', isolated=True)
        enabled = checked(studio + f'/documents/{board["id"]}/prompt-adoption', 200, token=token, branch=branch)
        assert enabled['write_enabled'] is True
        result['isolated_http_write_enabled'] = True
        vite = start([node, 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5208', '--strictPort'],
            root / 'frontend', 'vite', environment())
        deadline = time.monotonic() + 45
        while True:
            if vite.poll() is not None:
                raise RuntimeError('Owned Vite exited before readiness')
            try:
                with urlopen(origin, timeout=3) as response:
                    if response.status == 200:
                        break
            except (URLError, OSError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError('Owned Vite readiness deadline')
            time.sleep(.2)
        child_env = dict(os.environ, STUDIO_PROMPT_ADOPTION_UI_BROWSER_TOKEN=token,
            STUDIO_PROMPT_ADOPTION_UI_BROWSER_RECEIPTS=str(receipts), STUDIO_PROMPT_ADOPTION_UI_BROWSER_BASE_URL=origin)
        command = [node, 'node_modules/@playwright/test/cli.js', 'test', '--config', 'playwright.prompt-adoption-ui-live.config.ts']
        if args.project:
            command += ['--project', args.project]
        with (receipts / 'playwright.log').open('w', encoding='utf-8') as log:
            completed = subprocess.run(command, cwd=root / 'frontend', env=child_env, stdout=log, stderr=subprocess.STDOUT)
        result['playwright_exit'] = completed.returncode
        stop('vite', vite)
        stop('isolated_acceptance', isolated)
        ordinary, token = bootstrap('production_after')
        refusal(token, 'production-after-control')
        checked(admin + f'/projects/{nid}', 204, token=token, method='DELETE')
        result['production_controls'] = 'before503/isolatedTrue/after503'
        return completed.returncode
    except BaseException as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        for name, child in reversed(owned):
            stop(name, child)
        for log in logs:
            log.close()
        result['gate_source_unchanged'] = gate_path.read_bytes() == source
        save('launcher.json', result)
        print(json.dumps(result))
        if not result['gate_source_unchanged']:
            raise RuntimeError('Production gate source changed during acceptance; evidence is diagnostic only')


if __name__ == '__main__':
    raise SystemExit(main())
