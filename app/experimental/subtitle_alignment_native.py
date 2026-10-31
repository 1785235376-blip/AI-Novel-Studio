"""Bounded local alignment CLI execution, owned by the subtitle adapter.

Windows starts suspended and joins a kill-on-close Job before its first
instruction. POSIX uses an isolated process group. Closing the original task
fence therefore stops children as well as the CLI. This is not a task queue.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


class _WindowsProcess:
    def __init__(self, command, cwd, env, stdin, stdout, stderr):
        import ctypes
        from ctypes import wintypes as w
        import msvcrt

        class Startup(ctypes.Structure):
            _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR),
                ('title', w.LPWSTR), ('x', w.DWORD), ('y', w.DWORD), ('width', w.DWORD),
                ('height', w.DWORD), ('xchars', w.DWORD), ('ychars', w.DWORD),
                ('fill', w.DWORD), ('flags', w.DWORD), ('show', w.WORD), ('reserved2size', w.WORD),
                ('reserved2', ctypes.POINTER(w.BYTE)), ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE)]

        class Info(ctypes.Structure):
            _fields_ = [('process', w.HANDLE), ('thread', w.HANDLE), ('pid', w.DWORD), ('tid', w.DWORD)]

        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', w.DWORD), ('minimum_working_set', ctypes.c_size_t),
                ('maximum_working_set', ctypes.c_size_t), ('active_processes', w.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                ('read_operations', 'write_operations', 'other_operations', 'read_bytes', 'write_bytes', 'other_bytes')]

        class Limits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', IoCounters),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            'SetInformationJobObject': ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            'GetCurrentProcess': ([], w.HANDLE),
            'DuplicateHandle': ([w.HANDLE, w.HANDLE, w.HANDLE, ctypes.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD], w.BOOL),
            'CreateProcessW': ([w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL,
                w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(Startup), ctypes.POINTER(Info)], w.BOOL),
            'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
            'ResumeThread': ([w.HANDLE], w.DWORD),
            'WaitForSingleObject': ([w.HANDLE, w.DWORD], w.DWORD),
            'GetExitCodeProcess': ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            'TerminateJobObject': ([w.HANDLE, w.UINT], w.BOOL),
            'TerminateProcess': ([w.HANDLE, w.UINT], w.BOOL),
            'CloseHandle': ([w.HANDLE], w.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(kernel, name)
            function.argtypes, function.restype = arguments, result
        self._kernel, self._process, self._job = kernel, None, None
        duplicates, information = [], Info()
        try:
            self._job = kernel.CreateJobObjectW(None, None)
            if not self._job:
                raise ValueError('PROCESSING_ALIGNMENT_PROCESS_CONTAINMENT_REQUIRED')
            limits = Limits()
            limits.basic.flags = 0x2000 | 0x8 | 0x200  # kill-on-close, active processes, job memory
            limits.basic.active_processes, limits.job_memory = 16, 4 * 1024 * 1024 * 1024
            if not kernel.SetInformationJobObject(self._job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ValueError('PROCESSING_ALIGNMENT_PROCESS_CONTAINMENT_REQUIRED')
            current = kernel.GetCurrentProcess()
            for stream in (stdin, stdout, stderr):
                duplicate = w.HANDLE()
                if not kernel.DuplicateHandle(current, msvcrt.get_osfhandle(stream.fileno()), current,
                        ctypes.byref(duplicate), 0, True, 2):
                    raise ValueError('PROCESSING_ALIGNMENT_PROCESS_CONTAINMENT_REQUIRED')
                duplicates.append(duplicate.value)
            startup = Startup()
            startup.cb, startup.flags = ctypes.sizeof(startup), 0x100
            startup.stdin, startup.stdout, startup.stderr = duplicates
            environment = ctypes.create_unicode_buffer('\0'.join(f'{key}={env[key]}'
                for key in sorted(env, key=str.casefold)) + '\0\0')
            arguments = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
            if not kernel.CreateProcessW(command[0], arguments, None, None, True,
                    0x4 | 0x400 | 0x08000000, environment, str(cwd), ctypes.byref(startup), ctypes.byref(information)):
                raise ValueError('PROCESSING_ALIGNMENT_PROCESS_START_FAILED')
            self._process = information.process
            if not kernel.AssignProcessToJobObject(self._job, self._process):
                raise ValueError('PROCESSING_ALIGNMENT_PROCESS_CONTAINMENT_REQUIRED')
            if kernel.ResumeThread(information.thread) == 0xFFFFFFFF:
                raise ValueError('PROCESSING_ALIGNMENT_PROCESS_START_FAILED')
        except Exception:
            if self._process:
                kernel.TerminateProcess(self._process, 1)
            self.close()
            raise
        finally:
            if information.thread:
                kernel.CloseHandle(information.thread)
            for handle in duplicates:
                kernel.CloseHandle(handle)

    def poll(self):
        import ctypes
        from ctypes import wintypes as w
        status = self._kernel.WaitForSingleObject(self._process, 0)
        if status == 258:
            return None
        result = w.DWORD()
        if status != 0 or not self._kernel.GetExitCodeProcess(self._process, ctypes.byref(result)):
            raise ValueError('PROCESSING_ALIGNMENT_PROCESS_STATE_INVALID')
        return result.value

    def close(self):
        if self._job:
            self._kernel.TerminateJobObject(self._job, 1)
            self._kernel.CloseHandle(self._job)
            self._job = None
        if self._process:
            self._kernel.WaitForSingleObject(self._process, 2000)
            self._kernel.CloseHandle(self._process)
            self._process = None


def _workspace_size(directory):
    total, count = 0, 0
    for parent, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            count += 1
            if count > 4000:
                raise ValueError('PROCESSING_ALIGNMENT_TEMPORARY_OUTPUT_LIMIT')
            path = Path(parent) / name
            try:
                info = path.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue  # The trusted engine can rename/remove its temporary files.
            if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('PROCESSING_ALIGNMENT_LINKED_OUTPUT_REJECTED')
        for name in files:
            try:
                total += (Path(parent) / name).stat().st_size
            except FileNotFoundError:
                continue
            if total > 512 * 1024 * 1024:
                raise ValueError('PROCESSING_ALIGNMENT_TEMPORARY_OUTPUT_LIMIT')


def run_alignment_process(command, *, cwd, env, guard, timeout, stdout_path=None):
    """Execute one fixed local command; never persist native stderr or argv."""
    guard()
    process = None
    with tempfile.TemporaryFile() as stderr, tempfile.TemporaryFile() as discard, open(os.devnull, 'rb') as stdin:
        target = open(stdout_path, 'wb') if stdout_path is not None else discard
        try:
            if os.name == 'nt':
                process = _WindowsProcess(command, cwd, env, stdin, target, stderr)
            else:
                process = subprocess.Popen(command, cwd=str(cwd), env=env, stdin=stdin,
                    stdout=target, stderr=stderr, shell=False, start_new_session=True)
            deadline, next_size_check = time.monotonic() + timeout, 0
            while process.poll() is None:
                guard()
                now = time.monotonic()
                if now >= deadline:
                    raise ValueError('PROCESSING_ALIGNMENT_NATIVE_TIMEOUT')
                if os.fstat(stderr.fileno()).st_size > 1_048_576 or os.fstat(target.fileno()).st_size > 1_048_576:
                    raise ValueError('PROCESSING_ALIGNMENT_NATIVE_OUTPUT_LIMIT')
                if now >= next_size_check:
                    _workspace_size(cwd)
                    next_size_check = now + 1
                time.sleep(0.25)
            guard()
            _workspace_size(cwd)
            if process.poll() != 0:
                raise ValueError('PROCESSING_ALIGNMENT_NATIVE_FAILED')
            if os.fstat(stderr.fileno()).st_size > 1_048_576 or os.fstat(target.fileno()).st_size > 1_048_576:
                raise ValueError('PROCESSING_ALIGNMENT_NATIVE_OUTPUT_LIMIT')
        finally:
            if isinstance(process, _WindowsProcess):
                process.close()
            elif process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
            if stdout_path is not None:
                target.close()
