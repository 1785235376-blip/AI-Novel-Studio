"""Transparent synthetic-store I/O instrumentation, never a replacement reader."""
import builtins
import io
import os
from pathlib import Path
import time
import tracemalloc


class ReadMeter:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.read_calls = self.read_bytes = self.read_opens = self.write_opens = 0
        self.files = set()
        self.write_calls = self.written_bytes = 0
        self.write_files = set()
        self.descriptors = {}

    def contains(self, name):
        try:
            return Path(name).resolve().is_relative_to(self.root)
        except (TypeError, ValueError, OSError):
            return False

    def wrap(self, handle, name, mode):
        if not self.contains(name):
            return handle
        if any(x in str(mode) for x in 'wax+'):
            self.write_opens += 1
        else:
            self.read_opens += 1
        meter = self
        class File:
            def __getattr__(self, key):
                return getattr(handle, key)
            def __enter__(self):
                handle.__enter__()
                return self
            def __exit__(self, *args):
                return handle.__exit__(*args)
            def write(self, data, *args):
                result = handle.write(data, *args)
                meter.write_calls += 1
                meter.written_bytes += len(data[:result].encode('utf-8') if isinstance(data, str) else data[:result])
                meter.write_files.add(str(Path(name).resolve().relative_to(meter.root)))
                return result
            def read(self, *args):
                result = handle.read(*args)
                meter.read_calls += 1
                meter.read_bytes += len(result.encode('utf-8') if isinstance(result, str) else result)
                meter.files.add(str(Path(name).resolve().relative_to(meter.root)))
                return result
        return File()

    def install(self, monkeypatch):
        for target in (builtins, io):
            original = target.open
            def opened(file, mode='r', *args, _original=original, **kwargs):
                return self.wrap(_original(file, mode, *args, **kwargs), file, mode)
            monkeypatch.setattr(target, 'open', opened)
        original_open, original_fdopen = os.open, os.fdopen
        def descriptor(path, *args, **kwargs):
            result = original_open(path, *args, **kwargs)
            self.descriptors[result] = path
            return result
        def fdopen(fd, mode='r', *args, **kwargs):
            return self.wrap(original_fdopen(fd, mode, *args, **kwargs), self.descriptors.get(fd), mode)
        monkeypatch.setattr(os, 'open', descriptor)
        monkeypatch.setattr(os, 'fdopen', fdopen)

    def result(self):
        return {'read_calls': self.read_calls, 'bytes_read': self.read_bytes,
                'file_read_opens': self.read_opens, 'distinct_files_read': len(self.files),
                'write_opens': self.write_opens, 'write_calls': self.write_calls,
                'written_bytes': self.written_bytes, 'write_files': sorted(self.write_files)}


def measured(e, monkeypatch, callback):
    meter = ReadMeter(e.rig.root)
    readers = {}
    with monkeypatch.context() as patch:
        meter.install(patch)
        for owner, names in ((type(e.graph), ('get', 'list', 'usage_get', 'usage_directory')), (type(e.production), ('timeline_get', 'timeline_list', 'timeline_usage_get', 'timeline_usage_directory'))):
            for name in names:
                if not hasattr(owner, name):
                    continue
                original = getattr(owner, name)
                def counted(*args, _original=original, _name=name, **kwargs):
                    readers[_name] = readers.get(_name, 0) + 1
                    return _original(*args, **kwargs)
                patch.setattr(owner, name, counted)
        tracemalloc.start()
        started = time.perf_counter()
        result = callback()
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return result, {**meter.result(), 'owner_reader_calls': readers, 'elapsed_seconds': elapsed, 'python_peak_bytes': peak,
                    'memory_scope': 'tracemalloc Python allocations during request; not RSS'}
