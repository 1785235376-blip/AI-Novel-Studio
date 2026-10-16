"""Real File/Edge smoke using the original one-shot packaged trust bootstrap.

No dev-session registry, auth override, response mock, model or raw SQL. The
bootstrap secret and issued session remain in launcher/child memory only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--project')
    args = parser.parse_args()
    if not args.label.replace('-', '').isalnum():
        parser.error('label must be bounded alphanumeric text')
    root = Path(__file__).resolve().parents[1]
    receipts = root / 'docs/delivery/v2-development' / args.label
    runtime = root / '.runtime' / args.label
    receipts.mkdir(parents=True, exist_ok=False)
    runtime.mkdir(parents=True, exist_ok=False)
    origin, api = 'http://127.0.0.1:5198', 'http://127.0.0.1:8128'
    secret, instance = secrets.token_urlsafe(48), str(uuid4())
    env = dict(os.environ, PROJECT_ROOT=str(root), NOVEL_DATA_PATH=str(runtime / 'novel-data'),
               STORAGE_BACKEND='file', ENABLE_PACKAGED_RUNTIME='true', ENABLE_COLLABORATION_RUNTIME='true',
               COLLABORATION_DEV_SESSIONS_JSON='', PACKAGED_RUNTIME_INSTANCE_ID=instance,
               PACKAGED_BOOTSTRAP_SECRET=secret, FRONTEND_ORIGIN=origin,
               PACKAGED_FRONTEND_DIST=str(root / 'frontend/dist'), PYTHONUTF8='1',
               EXPERIMENTAL_FEATURES='branch_manuscript_v1,narrative_production_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2', ENABLE_CLOUD='false', ENABLE_PROVIDER_FALLBACK='false')
    def call(path, body=None, token=None):
        headers = {'Origin': origin}
        if token:
            headers['X-Session-Token'] = token
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        with urlopen(Request(api + path, data=data, headers=headers), timeout=5) as response:
            return response.status, json.load(response)
    result = {'backend': 'real File', 'identity_owner': 'LocalSessionBootstrap',
              'development_sessions': False, 'response_mocks': False,
              'model_execution': 'NOT_REQUESTED', 'runtime_model_counter': 'NOT_INSTRUMENTED'}
    with (receipts / 'backend.stdout.log').open('w', encoding='utf-8') as stdout, \
            (receipts / 'backend.stderr.log').open('w', encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8128'],
            cwd=root, env=env, stdout=stdout, stderr=stderr,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        result['owned_backend_pid'] = process.pid
        try:
            deadline = time.monotonic() + 40
            while True:
                if process.poll() is not None:
                    raise RuntimeError('owned backend exited before readiness; inspect retained backend log')
                try:
                    status, health = call('/api/health')
                    if status == 200 and health.get('storage') == 'file':
                        break
                except (URLError, OSError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError('owned backend readiness timed out') from None
                time.sleep(.2)
            status, issued = call('/api/packaged/bootstrap', {'bootstrap_secret': secret, 'runtime_instance_id': instance})
            assert status == 200 and issued.get('session_token')
            token = issued['session_token']
            status, workspace = call('/api/packaged/initial-workspace', {}, token)
            assert status == 200 and workspace['id'] == 'workspace-a'
            result['bootstrap_status'], result['workspace_status'] = 200, 200
            child = dict(os.environ, STUDIO_DIRECTOR_BROWSER_TOKEN=token,
                         STUDIO_DIRECTOR_BROWSER_RECEIPTS=str(receipts), STUDIO_DIRECTOR_BROWSER_BASE_URL=origin)
            node = shutil.which('node')
            if not node:
                raise RuntimeError('Node runtime unavailable')
            command = [node, 'node_modules/@playwright/test/cli.js', 'test', '--config', 'playwright.director-console.config.ts']
            if args.project:
                command += ['--project', args.project]
            with (receipts / 'playwright.log').open('w', encoding='utf-8') as log:
                completed = subprocess.run(command, cwd=root / 'frontend', env=child, stdout=log, stderr=subprocess.STDOUT)
            result['playwright_exit'] = completed.returncode
            return completed.returncode
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            result['owned_backend_stopped'] = process.poll() is not None
            (receipts / 'launcher.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result))


if __name__ == '__main__':
    raise SystemExit(main())
