"""Real Edge/HTTP Prompt evidence using the original packaged bootstrap.

Owns and stops only its backend and Vite children. No route responses, identity,
adoption gate, model execution, or existing acceptance spec is replaced.
"""
from __future__ import annotations

import argparse
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
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--project')
    parser.add_argument('--storage-backend', choices=('file', 'postgres'), default='file')
    args = parser.parse_args()
    if not args.label.replace('-', '').isalnum():
        parser.error('label must be bounded alphanumeric text')
    database_identity = None
    if args.storage_backend == 'postgres':
        url = os.environ.get('DATABASE_URL', '')
        parsed = urlsplit(url)
        if (not url or url != os.environ.get('TEST_POSTGRES_DATABASE_URL')
                or parsed.scheme not in {'postgres', 'postgresql'}
                or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or not parsed.port or not re.fullmatch(r'/v2_[A-Za-z0-9_]+', parsed.path)
                or parsed.query or parsed.fragment):
            parser.error('PostgreSQL requires the original wrapper-provided loopback v2_* database URL')
        import psycopg
        with psycopg.connect(url, connect_timeout=5, autocommit=True,
                            options='-c statement_timeout=5000') as connection:
            row = connection.execute('SELECT version(),current_database(),host(inet_server_addr()),inet_server_port(),'
                '(SELECT oid::bigint FROM pg_database WHERE datname=current_database())').fetchone()
        if row[1] != parsed.path[1:] or row[2] not in {'127.0.0.1', '::1'} or row[3] != parsed.port:
            raise RuntimeError('Original PostgreSQL runtime identity does not match the validated target')
        database_identity = dict(zip(('version', 'database', 'host', 'port', 'database_oid'), row))
    root = Path(__file__).resolve().parents[1]
    receipts = root / 'docs/delivery/v2-r3-prompt-20261016' / args.label
    runtime = root / '.runtime' / args.label
    receipts.mkdir(parents=True, exist_ok=False)
    runtime.mkdir(parents=True, exist_ok=False)
    api, origin = 'http://127.0.0.1:8138', 'http://127.0.0.1:5208'
    for port in (8138, 5208):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Existing Node runtime unavailable')
    secret, instance = secrets.token_urlsafe(48), str(uuid4())
    env = dict(os.environ, PROJECT_ROOT=str(root), NOVEL_DATA_PATH=str(runtime / 'novel-data'),
        STORAGE_BACKEND=args.storage_backend, ENABLE_PACKAGED_RUNTIME='true', ENABLE_COLLABORATION_RUNTIME='true',
        COLLABORATION_DEV_SESSIONS_JSON='', PACKAGED_RUNTIME_INSTANCE_ID=instance,
        PACKAGED_BOOTSTRAP_SECRET=secret, FRONTEND_ORIGIN=origin, PACKAGED_FRONTEND_DIST=str(root / 'frontend/dist'),
        PYTHONUTF8='1', EXPERIMENTAL_FEATURES='narrative_production_v2,asset_lineage_v2',
        ENABLE_CLOUD='false', ENABLE_PROVIDER_FALLBACK='false', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        V061_API_URL=api)
    if args.storage_backend == 'file':
        for name in ('DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL', 'E2E_DATABASE_URL'):
            env.pop(name, None)
    result = {'backend': 'real PostgreSQL' if args.storage_backend == 'postgres' else 'real File',
        'storage_backend': args.storage_backend, 'database_identity': database_identity,
        'asset_storage_owner': 'original File AssetLibraryService', 'identity_owner': 'LocalSessionBootstrap',
        'development_sessions': False, 'response_mocks': False, 'production_adoption_gate': False,
        'model_execution': 'NOT_REQUESTED', 'model_counter': 'NOT_INSTRUMENTED'}
    owned = []
    logs = []

    def call(path, body=None, token=None):
        headers = {'Origin': origin}
        if token:
            headers['X-Session-Token'] = token
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        with urlopen(Request(api + path, data=data, headers=headers), timeout=5) as response:
            return response.status, json.load(response)

    def start(command, cwd, name):
        stdout = (receipts / f'{name}.stdout.log').open('w', encoding='utf-8')
        stderr = (receipts / f'{name}.stderr.log').open('w', encoding='utf-8')
        logs.extend([stdout, stderr])
        child = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        owned.append((name, child))
        return child

    try:
        backend = start([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8138'], root, 'backend')
        deadline = time.monotonic() + 40
        last_storage = None
        while True:
            if backend.poll() is not None:
                raise RuntimeError('Owned backend exited before readiness; retained log contains evidence')
            try:
                status, health = call('/api/health')
                last_storage = health.get('storage')
                if status == 200 and last_storage == args.storage_backend:
                    result['health_storage'] = last_storage
                    break
            except (URLError, OSError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f'Owned backend readiness timed out: expected storage {args.storage_backend}, observed {last_storage}')
            time.sleep(.2)
        status, issued = call('/api/packaged/bootstrap', {'bootstrap_secret': secret, 'runtime_instance_id': instance})
        assert status == 200 and issued.get('session_token')
        token = issued['session_token']
        status, workspace = call('/api/packaged/initial-workspace', {}, token)
        assert status == 200 and workspace['id'] == 'workspace-a'
        result.update(bootstrap_status=200, workspace_status=200)
        vite = start([node, 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5208', '--strictPort'], root / 'frontend', 'vite')
        deadline = time.monotonic() + 40
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
                raise RuntimeError('Owned Vite readiness timed out')
            time.sleep(.2)
        child_env = dict(os.environ, STUDIO_PROMPT_R3_BROWSER_TOKEN=token,
            STUDIO_PROMPT_R3_BROWSER_RECEIPTS=str(receipts), STUDIO_PROMPT_R3_BROWSER_BASE_URL=origin)
        command = [node, 'node_modules/@playwright/test/cli.js', 'test', '--config', 'playwright.prompt-r3-live.config.ts']
        if args.project:
            command += ['--project', args.project]
        with (receipts / 'playwright.log').open('w', encoding='utf-8') as log:
            completed = subprocess.run(command, cwd=root / 'frontend', env=child_env, stdout=log, stderr=subprocess.STDOUT)
        result['playwright_exit'] = completed.returncode
        return completed.returncode
    except BaseException as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        for name, child in reversed(owned):
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            result[f'owned_{name}_pid'] = child.pid
            result[f'owned_{name}_stopped'] = child.poll() is not None
        for log in logs:
            log.close()
        (receipts / 'launcher.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))


if __name__ == '__main__':
    raise SystemExit(main())
