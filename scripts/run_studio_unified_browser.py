"""Real browser + original File app + deterministic loopback Mock provider.

Only fresh synthetic state is accepted. Each phase launches a new Chromium;
the final phase also replaces the backend process and Vite proxy target.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from threading import Thread
import argparse
import base64
import importlib.util
import json
import os
import subprocess
import sys
import time

import httpx
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--chrome', type=Path, required=True)
    parser.add_argument('--node', default='node')
    parser.add_argument('--response-loss', action='store_true')
    parser.add_argument('--allow-dirty', action='store_true', help='Development only; never a frozen acceptance')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    runtime = out / 'runtime'
    runtime.mkdir()

    def git(*argv):
        return subprocess.check_output(['git', *argv], cwd=root, text=True).strip()

    def hashes():
        paths = git('ls-files', '--', 'app', 'frontend', 'tests', 'scripts', 'contracts', 'config', 'pyproject.toml').splitlines()
        # Include these new files during explicitly labelled development runs.
        paths += ['scripts/run_studio_unified_browser.py', 'frontend/scripts/pw_unified_image_loop.mjs']
        return {p: sha256((root / p).read_bytes()).hexdigest() for p in sorted(set(paths)) if (root / p).is_file()}

    before = hashes()
    dirty = git('status', '--porcelain')
    assert args.allow_dirty or not dirty, 'Frozen browser verification requires a clean checkout'
    receipt = dict(head=git('rev-parse', 'HEAD'), tree=git('rev-parse', 'HEAD^{tree}'),
                   source_root=str(root), python=sys.executable, chrome=str(args.chrome),
                   started_utc=datetime.now(timezone.utc).isoformat(), initial_status=dirty,
                   mode='REAL_FRONTEND_BACKEND_FILE_HTTP_PLUS_MOCK_PROVIDER',
                   acceptance=not args.allow_dirty, response_loss=args.response_loss, phases=[])
    (out / 'source-before.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    # This helper imports no application globals before installing isolated env.
    spec = importlib.util.spec_from_file_location('isolated_process_helper', root / 'tests/test_studio_process_reopen_v2.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    receipt['helper_module'] = str(Path(helper.__file__).resolve())
    png_stream = BytesIO()
    Image.new('RGB', (64, 64), (37, 107, 173)).save(png_stream, format='PNG')
    encoded = base64.b64encode(png_stream.getvalue()).decode('ascii')
    calls = []

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def reply(self, value):
            payload = json.dumps(value).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self.reply([{'title': 'synthetic.safetensors'}])

        def do_POST(self):
            assert self.path == '/sdapi/v1/txt2img', self.path
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            (out / 'provider-calls.json').write_text(json.dumps(calls, indent=2), encoding='utf-8')
            self.reply({'images': [encoded]})

    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    thread = Thread(target=provider.serve_forever, daemon=True)
    thread.start()
    config = runtime / 'providers.json'
    config.write_text(json.dumps({'automatic1111': {
        'endpoint': f'http://127.0.0.1:{provider.server_port}', 'default_model': 'synthetic.safetensors',
        'api_style': 'automatic1111', 'local': True, 'enabled': True, 'requires_credential': False}}), encoding='utf-8')
    ui_port = helper.unused_port()
    base = f'http://127.0.0.1:{ui_port}'
    previous_origin = os.environ.get('FRONTEND_ORIGIN')
    os.environ['FRONTEND_ORIGIN'] = base

    @contextmanager
    def frontend(backend, label):
        env = os.environ.copy()
        env.update(V061_API_URL=str(backend.base_url).rstrip('/'))
        argv = [args.node, 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(ui_port), '--strictPort']
        with (out / f'{label}-vite.log').open('w', encoding='utf-8') as log:
            proc = subprocess.Popen(argv, cwd=root / 'frontend', env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 45
                with httpx.Client(trust_env=False) as probe:
                    while True:
                        assert proc.poll() is None, 'Vite exited before readiness'
                        try:
                            if probe.get(base, timeout=1).status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        assert time.monotonic() < deadline, 'Vite readiness timeout'
                        time.sleep(.05)
                yield
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)

    def phase(nid, name):
        env = os.environ.copy()
        env.update(UNIFIED_BASE_URL=base, UNIFIED_OUT=str(out), UNIFIED_NOVEL=nid,
                   UNIFIED_PHASE=name, UNIFIED_LOSS='1' if args.response_loss else '0', CHROME=str(args.chrome))
        argv = [args.node, 'scripts/pw_unified_image_loop.mjs']
        started = time.monotonic()
        with (out / f'{name}-browser.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(argv, cwd=root / 'frontend', env=env, stdout=log, stderr=subprocess.STDOUT, timeout=420)
        receipt['phases'].append(dict(name=name, argv=argv, exit_code=result.returncode,
                                      elapsed_seconds=time.monotonic() - started, provider_calls=len(calls)))
        assert result.returncode == 0, f'{name} browser failed; see preserved browser log'
        assert len(calls) == 1, 'Exactly one original provider dispatch across all phases'

    try:
        with helper.original_application(root, runtime, config, 'first-backend.log') as backend:
            created = backend.post('/api/novels', json={'title': 'Synthetic unified browser only'})
            assert created.status_code == 201, created.text
            nid = created.json()['id']
            activated = backend.post(f'/api/projects/{nid}/studio/activate')
            assert activated.status_code == 200, activated.text
            receipt['synthetic_project'] = nid
            receipt['first_backend'] = str(backend.base_url)
            with frontend(backend, 'first'):
                phase(nid, 'flow')
                phase(nid, 'browser-reopen')
        with helper.original_application(root, runtime, config, 'restarted-backend.log') as backend:
            receipt['restarted_backend'] = str(backend.base_url)
            assert receipt['first_backend'] != receipt['restarted_backend']
            with frontend(backend, 'restart'):
                phase(nid, 'backend-restart')
    except Exception as error:
        receipt['error'] = repr(error)
        raise
    finally:
        provider.shutdown()
        provider.server_close()
        thread.join(timeout=5)
        if previous_origin is None:
            os.environ.pop('FRONTEND_ORIGIN', None)
        else:
            os.environ['FRONTEND_ORIGIN'] = previous_origin
        after = hashes()
        (out / 'source-after.json').write_text(json.dumps(after, indent=2), encoding='utf-8')
        receipt.update(source_unchanged=before == after, final_status=git('status', '--porcelain'),
                       provider_calls=len(calls), ended_utc=datetime.now(timezone.utc).isoformat())
        receipt['passed'] = len(receipt['phases']) == 3 and all(p['exit_code'] == 0 for p in receipt['phases']) and before == after and len(calls) == 1
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
