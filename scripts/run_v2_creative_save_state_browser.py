"""Real Creative save-state browser acceptance using only the ordinary backend.

The original LocalSessionBootstrap issues the real session. Production Prompt
adoption stays literal False; this launcher never changes any module boolean.
The spec delays only real original request dispatch and then calls route.continue().
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
    parser.add_argument('--grep')
    args = parser.parse_args()
    if not re.fullmatch(r'creative-save-[a-z0-9-]+', args.label):
        parser.error('Use a new bounded creative-save-* label')
    root = Path(__file__).resolve().parents[1]
    gate_path = root / 'app/creative/prompt_adoption_api.py'
    source = gate_path.read_bytes()
    assignments = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'PROMPT_ADOPTION_WRITE_ENABLED'
                for target in node.targets)]
    assert len(assignments) == 1 and isinstance(assignments[0].value, ast.Constant)
    assert assignments[0].value.value is False
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
    receipts = root / 'docs/delivery/v2-creative-save-state-20261017' / args.label
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
        'backend_process': 'ordinary uvicorn app.main:app', 'production_literal_gate': False,
        'production_gate_override': False, 'production_environment_toggle': False,
        'gate_source_sha256': hashlib.sha256(source).hexdigest(), 'development_sessions': False,
        'response_mocks': False, 'model_provider_mock': False,
        'latency_schedule': 'real Creative PUT and history GET dispatch held, then route.continue',
        'request_not_dispatched_until_release': True,
        'model_execution': 'NOT_REQUESTED', 'model_counter': 'NOT_INSTRUMENTED'}

    def call(path, body=None, token=None):
        headers = {'Origin': origin}
        if token:
            headers['X-Session-Token'] = token
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        try:
            response = urlopen(Request(api + path, data=data, headers=headers), timeout=20)
        except HTTPError as response:
            return response.code, json.loads(response.read())
        with response:
            return response.status, json.load(response) if response.status != 204 else None

    def checked(path, expected, **kwargs):
        status, value = call(path, **kwargs)
        assert status == expected, {'path': path, 'status': status, 'body': value}
        return value

    secret, instance = secrets.token_urlsafe(48), str(uuid4())
    env = dict(os.environ, PROJECT_ROOT=str(root), NOVEL_DATA_PATH=str(runtime / 'novel-data'),
        STORAGE_BACKEND=args.storage_backend, ENABLE_PACKAGED_RUNTIME='true', ENABLE_COLLABORATION_RUNTIME='true',
        COLLABORATION_DEV_SESSIONS_JSON='', PACKAGED_RUNTIME_INSTANCE_ID=instance,
        PACKAGED_BOOTSTRAP_SECRET=secret, FRONTEND_ORIGIN=origin,
        PACKAGED_FRONTEND_DIST=str(root / 'frontend/dist'), PYTHONUTF8='1',
        EXPERIMENTAL_FEATURES='narrative_production_v2,asset_lineage_v2', V061_API_URL=api,
        MOCK_PROVIDER='false', ENABLE_CLOUD='false', ENABLE_PROVIDER_FALLBACK='false', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    if args.storage_backend == 'file':
        for name in ('DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL', 'E2E_DATABASE_URL'):
            env.pop(name, None)

    def start(command, cwd, name):
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

    try:
        backend = start([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8138'], root, 'backend')
        deadline, observed = time.monotonic() + 45, None
        while True:
            if backend.poll() is not None:
                raise RuntimeError('Owned ordinary backend exited before readiness')
            try:
                status, health = call('/api/health')
                observed = health.get('storage')
                if status == 200 and observed == args.storage_backend:
                    break
            except (URLError, OSError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f'Backend readiness deadline: expected {args.storage_backend}, observed {observed}')
            time.sleep(.2)
        issued = checked('/api/packaged/bootstrap', 200,
            body={'bootstrap_secret': secret, 'runtime_instance_id': instance})
        token = issued['session_token']
        workspace = checked('/api/packaged/initial-workspace', 200, body={}, token=token)
        assert workspace['id'] == 'workspace-a'
        result['health_storage'] = observed
        vite = start([node, 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5208', '--strictPort'], root / 'frontend', 'vite')
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
        child_env = dict(env, STUDIO_CREATIVE_SAVE_BROWSER_TOKEN=token,
            STUDIO_CREATIVE_SAVE_BROWSER_RECEIPTS=str(receipts), STUDIO_CREATIVE_SAVE_BROWSER_BASE_URL=origin)
        command = [node, 'node_modules/@playwright/test/cli.js', 'test', '--config', 'playwright.creative-save-live.config.ts']
        if args.project:
            command += ['--project', args.project]
        if args.grep:
            command += ['--grep', args.grep]
        with (receipts / 'playwright.log').open('w', encoding='utf-8') as log:
            completed = subprocess.run(command, cwd=root / 'frontend', env=child_env, stdout=log, stderr=subprocess.STDOUT)
        result['playwright_exit'] = completed.returncode
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
        (receipts / 'launcher.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result))
        if not result['gate_source_unchanged']:
            raise RuntimeError('Production gate source changed during acceptance')


if __name__ == '__main__':
    raise SystemExit(main())
