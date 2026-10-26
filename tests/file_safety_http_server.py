"""Transparent TCP test host: original app, synthetic settings, observation only."""
import contextvars
import builtins
from functools import wraps
import hashlib
import ipaddress
import io
import json
import os
from pathlib import Path
import sys

import uvicorn

active = contextvars.ContextVar('file_safety_get', default=None)
records = []
watched = []
root = Path(os.environ['PROJECT_ROOT']).resolve()
data = Path(os.environ['NOVEL_DATA_PATH']).resolve()
receipt = Path(os.environ['FILE_SAFETY_RECEIPT'])


def audit(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        host = args[1][0] if event == 'socket.connect' else args[0]
        if host not in (None, 'localhost'):
            try:
                allowed = ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                raise RuntimeError('synthetic HTTP host blocks external network')
    record = active.get()
    if record is None:
        return
    if event == 'open' and isinstance(args[0], (str, bytes)):
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(x in mode for x in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR):
            try:
                path = Path(os.fsdecode(args[0])).resolve()
                name = path.relative_to(data).as_posix()
            except ValueError:
                return
            record['write_opens'].append(name)
            if flags & os.O_CREAT and not path.exists():
                record['file_creations'].append(name)
    elif event in {'os.mkdir', 'os.remove', 'os.rename'}:
        try:
            path = Path(os.fsdecode(args[0])).resolve()
            name = path.relative_to(data).as_posix()
        except (ValueError, TypeError):
            return
        if event != 'os.mkdir' or not path.exists():
            record['filesystem_mutations'].append(event + ':' + name)


def observe_command(original, label):
    @wraps(original)
    def observed(*args, **kwargs):
        record = active.get()
        if record is not None:
            record['command_calls'].append(label)
        return original(*args, **kwargs)
    return observed


sys.addaudithook(audit)
from app.main import app as original_app
from app.creative.asset_usage_budget import UsageReadBudget
from app import dependencies, api as legacy_api

# Storage/queue acceptance uses a deterministic stub executor, never a real
# export renderer. Keep the original singleton, snapshotter, queue and writers.
assert dependencies.export_job_service is legacy_api.export_job_service
synthetic_export_calls = []
def synthetic_exporter(novel_id, format, **kwargs):
    synthetic_export_calls.append(format)
    record = active.get()
    if record is not None:
        record['command_calls'].append('synthetic_exporter')
    return {'format': format, 'filename': 'synthetic.txt', 'media_type': 'text/plain',
            'content': 'Synthetic storage-only export fixture.\n'}
dependencies.export_job_service.exporter = synthetic_exporter

# Count actual Python write calls separately from Windows lock r+b opens.
descriptors = {}
original_os_open, original_fdopen = os.open, os.fdopen
def descriptor_open(name, *args, **kwargs):
    fd = original_os_open(name, *args, **kwargs)
    descriptors[fd] = name
    return fd

def observe_handle(handle, name, mode):
    if active.get() is None or not any(c in mode for c in 'wax+') or getattr(handle, '_safety_write_observer', False):
        return handle
    if isinstance(name, int):
        name = descriptors.get(name)
    try:
        relative = Path(name).resolve().relative_to(data).as_posix()
    except (TypeError, ValueError):
        return handle
    class ObservedFile:
        _safety_write_observer = True
        def __getattr__(self, key):
            return getattr(handle, key)
        def __enter__(self):
            handle.__enter__()
            return self
        def __exit__(self, *args):
            return handle.__exit__(*args)
        def write(self, value, *args):
            record = active.get()
            if record is not None:
                record['write_calls'].append(relative)
            return handle.write(value, *args)
        def writelines(self, lines):
            record = active.get()
            if record is not None:
                record['write_calls'].append(relative)
            return handle.writelines(lines)
        def truncate(self, *args):
            record = active.get()
            if record is not None:
                record['write_calls'].append(relative)
            return handle.truncate(*args)
    return ObservedFile()

os.open = descriptor_open
def fdopen(fd, mode='r', *args, **kwargs):
    return observe_handle(original_fdopen(fd, mode, *args, **kwargs), descriptors.get(fd), mode)
os.fdopen = fdopen
for owner in (builtins, io):
    original = owner.open
    def opened(name, mode='r', *args, _original=original, **kwargs):
        return observe_handle(_original(name, mode, *args, **kwargs), name, mode)
    owner.open = opened

original_read_bytes = UsageReadBudget._read_bytes
@wraps(original_read_bytes)
def observe_read_bytes(self, *args, **kwargs):
    try:
        return original_read_bytes(self, *args, **kwargs)
    finally:
        record = active.get()
        if record is not None:
            record['budget_reads'].append({'read_bytes': self.read_bytes, 'reads': self.reads, 'maximum': self.MAX_READ_BYTES})
UsageReadBudget._read_bytes = observe_read_bytes
command_names = {'_submit', '_run', 'execute', 'process', 'create_job', 'create_run', 'transition',
                 'generate', 'generate_text', 'generate_image', 'generate_audio', 'transcribe', 'synthesize',
                 'cancel', 'retry', 'review', 'adopt', 'approve', 'reject', '_recover_on_startup', 'dispatch',
                 '_invoke_exporter', 'export', 'export_snapshot_result'}
seen = set()
for module_name, module in tuple(sys.modules.items()):
    if not module_name.startswith('app.'):
        continue
    for obj in tuple(vars(module).values()):
        if not isinstance(obj, type) or obj in seen or not getattr(obj, '__module__', '').startswith('app.'):
            continue
        seen.add(obj)
        for name, member in tuple(vars(obj).items()):
            code = getattr(member, '__code__', None)
            if code is not None and ({name, getattr(member, '__name__', ''), code.co_name} & command_names):
                label = obj.__module__ + '.' + obj.__qualname__ + ':' + name
                setattr(obj, name, observe_command(member, label))
                watched.append(label)
assert all('app.services.export_job_service.ExportJobService:'+name in watched
           for name in ('cancel', 'retry', '_submit', '_recover_on_startup'))

# Transparent observers above delegate to the unchanged original methods.
# Test-only reduction exercises the real cumulative budget failure.
if os.environ.get('FILE_SAFETY_MAX_READ_BYTES'):
    UsageReadBudget.MAX_READ_BYTES = int(os.environ['FILE_SAFETY_MAX_READ_BYTES'])

def save():
    modules = {}
    for name, module in tuple(sys.modules.items()):
        path = getattr(module, '__file__', None)
        if name.startswith('app.') and path and Path(path).suffix == '.py':
            resolved = Path(path).resolve()
            modules[name] = {'path': str(resolved), 'sha256': hashlib.sha256(resolved.read_bytes()).hexdigest()}
    receipt.write_text(json.dumps({'source_root': str(root), 'loaded_modules': modules,
        'synthetic_exporter': {'mode': 'deterministic_stub', 'calls': len(synthetic_export_calls),
                               'snapshotter': 'original provider-free input snapshot'},
        'observed_command_methods': watched, 'summary': {
            'get_count': len(records), 'command_calls': sum(len(r['command_calls']) for r in records),
            'actual_write_calls': sum(len(r['write_calls']) for r in records),
            'business_write_calls': sum(sum('.workspace-mutation-locks' not in p.split('/') for p in r['write_calls']) for r in records),
            'coordinator_write_calls': sum(sum('.workspace-mutation-locks' in p.split('/') for p in r['write_calls']) for r in records),
            'strict_write_calls': sum(len(r['write_calls']) for r in records if r['strict']),
            'strict_file_creations': sum(len(r['file_creations']) for r in records if r['strict']),
            'strict_directory_creations': sum(sum(x.startswith('os.mkdir:') for x in r['filesystem_mutations']) for r in records if r['strict'])},
        'gets': records}, indent=2), encoding='utf-8')


async def app(scope, receive, send):
    if scope['type'] != 'http' or scope['method'] != 'GET':
        return await original_app(scope, receive, send)
    record = {'path': scope['path'], 'completed': False, 'strict': b'strict_read_only=true' in scope['query_string'],
              'write_opens': [], 'write_calls': [], 'file_creations': [], 'filesystem_mutations': [], 'command_calls': [], 'budget_reads': []}
    token = active.set(record)
    saved = False
    async def observed_send(message):
        nonlocal saved
        if message['type'] == 'http.response.start':
            record['status'] = message['status']
        # Append before the first body chunk: Content-Length clients can finish
        # before ASGI's trailing empty more_body=False message is delivered.
        if message['type'] == 'http.response.body':
            paused = active.set(None)
            try:
                if not saved:
                    records.append(record)
                save()
                saved = True
            finally:
                active.reset(paused)
        await send(message)
    try:
        await original_app(scope, receive, observed_send)
    finally:
        active.reset(token)
        record['completed'] = True
        if not saved:
            records.append(record)
        save()


if __name__ == '__main__':
    save()
    uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[1]), log_level='warning', proxy_headers=False)
