"""ctypes bindings for the Phase 2B AppContainer launcher.

Imported only on Windows launch. Job Object here is resource containment,
not a security sandbox. No pywin32.
"""

from __future__ import annotations

import os
import sys
from typing import IO, Any, Callable

from app.plugin_worker_sandbox_errors import (
    PROCESS_MEMORY_LIMIT_BYTES,
    REASON_SANDBOX_ACL_FAILED,
    REASON_SANDBOX_JOB_ASSIGNMENT_FAILED,
    REASON_SANDBOX_LAUNCH_FAILED,
    REASON_SANDBOX_PROFILE_CREATE_FAILED,
    REASON_SANDBOX_TOKEN_VERIFICATION_FAILED,
    SandboxError,
)


class WinProcess:
    """Popen-shaped wrapper around a CreateProcess AppContainer child."""

    def __init__(
        self,
        pid: int,
        stdin: IO[bytes],
        stdout: IO[bytes],
        stderr: IO[bytes],
        wait: Callable[..., int],
        terminate: Callable[[], None],
        poll: Callable[[], int | None],
    ):
        self.pid = pid
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self._wait = wait
        self._terminate = terminate
        self._poll = poll

    def poll(self) -> int | None:
        return self._poll()

    def wait(self, timeout: float | None = None) -> int:
        return self._wait(timeout)

    def terminate(self) -> None:
        self._terminate()

    def kill(self) -> None:
        self._terminate()


class Win32:
    PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009
    EXTENDED_STARTUPINFO_PRESENT = 0x00080000
    CREATE_SUSPENDED = 0x00000004
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    CREATE_NO_WINDOW = 0x08000000
    STARTF_USESTDHANDLES = 0x00000100
    STARTF_USESHOWWINDOW = 0x00000001
    HANDLE_FLAG_INHERIT = 0x00000001
    TOKEN_QUERY = 0x0008
    TokenUser = 1
    TokenIsAppContainer = 19
    TokenAppContainerSid = 31
    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    SE_FILE_OBJECT = 1
    DACL_SECURITY_INFORMATION = 0x00000004
    PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
    GRANT_ACCESS = 1
    TRUSTEE_IS_SID = 0
    TRUSTEE_IS_USER = 1
    SUB_CONTAINERS_AND_OBJECTS_INHERIT = 0x3
    FILE_GENERIC_READ = 0x120089
    FILE_GENERIC_WRITE = 0x120116
    FILE_GENERIC_EXECUTE = 0x1200A0
    FILE_ALL_ACCESS = 0x1F01FF
    DELETE = 0x00010000
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 0x102
    S_OK = 0

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise SandboxError("WINDOWS_SANDBOX_UNAVAILABLE")
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.wintypes = wintypes
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.userenv = ctypes.WinDLL("userenv", use_last_error=True)
        self._define_structs()
        self._bind()

    def _define_structs(self) -> None:
        ctypes = self.ctypes
        wintypes = self.wintypes

        class SECURITY_ATTRIBUTES(ctypes.Structure):
            _fields_ = [
                ("nLength", wintypes.DWORD),
                ("lpSecurityDescriptor", wintypes.LPVOID),
                ("bInheritHandle", wintypes.BOOL),
            ]

        class STARTUPINFOW(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD),
                ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD),
                ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD),
                ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
                ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE),
                ("hStdError", wintypes.HANDLE),
            ]

        class STARTUPINFOEXW(ctypes.Structure):
            _fields_ = [
                ("StartupInfo", STARTUPINFOW),
                ("lpAttributeList", wintypes.LPVOID),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("hProcess", wintypes.HANDLE),
                ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD),
            ]

        class SID_AND_ATTRIBUTES(ctypes.Structure):
            _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

        class SECURITY_CAPABILITIES(ctypes.Structure):
            _fields_ = [
                ("AppContainerSid", wintypes.LPVOID),
                ("Capabilities", ctypes.POINTER(SID_AND_ATTRIBUTES)),
                ("CapabilityCount", wintypes.DWORD),
                ("Reserved", wintypes.DWORD),
            ]

        class TRUSTEE_W(ctypes.Structure):
            _fields_ = [
                ("pMultipleTrustee", wintypes.LPVOID),
                ("MultipleTrusteeOperation", ctypes.c_int),
                ("TrusteeForm", ctypes.c_int),
                ("TrusteeType", ctypes.c_int),
                ("ptstrName", wintypes.LPVOID),
            ]

        class EXPLICIT_ACCESS_W(ctypes.Structure):
            _fields_ = [
                ("grfAccessPermissions", wintypes.DWORD),
                ("grfAccessMode", ctypes.c_int),
                ("grfInheritance", wintypes.DWORD),
                ("Trustee", TRUSTEE_W),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class TOKEN_USER(ctypes.Structure):
            _fields_ = [("User", SID_AND_ATTRIBUTES)]

        self.SECURITY_ATTRIBUTES = SECURITY_ATTRIBUTES
        self.STARTUPINFOEXW = STARTUPINFOEXW
        self.PROCESS_INFORMATION = PROCESS_INFORMATION
        self.SECURITY_CAPABILITIES = SECURITY_CAPABILITIES
        self.EXPLICIT_ACCESS_W = EXPLICIT_ACCESS_W
        self.EXTENDED_LIMIT_INFORMATION = EXTENDED_LIMIT_INFORMATION
        self.TOKEN_USER = TOKEN_USER

    def _bind(self) -> None:
        ctypes = self.ctypes
        wintypes = self.wintypes
        k = self.kernel32
        k.CreatePipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k.CreatePipe.restype = wintypes.BOOL
        k.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        k.SetHandleInformation.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.CreateProcessW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        k.CreateProcessW.restype = wintypes.BOOL
        k.ResumeThread.argtypes = [wintypes.HANDLE]
        k.ResumeThread.restype = wintypes.DWORD
        k.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.TerminateProcess.restype = wintypes.BOOL
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.WaitForSingleObject.restype = wintypes.DWORD
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetExitCodeProcess.restype = wintypes.BOOL
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k.SetInformationJobObject.restype = wintypes.BOOL
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k.AssignProcessToJobObject.restype = wintypes.BOOL
        k.InitializeProcThreadAttributeList.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        k.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        k.UpdateProcThreadAttribute.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        k.UpdateProcThreadAttribute.restype = wintypes.BOOL
        k.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        k.DeleteProcThreadAttributeList.restype = None
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.LocalFree.argtypes = [wintypes.HLOCAL]
        k.LocalFree.restype = wintypes.HLOCAL
        a = self.advapi32
        a.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        a.OpenProcessToken.restype = wintypes.BOOL
        a.GetTokenInformation.restype = wintypes.BOOL
        a.FreeSid.argtypes = [ctypes.c_void_p]
        a.FreeSid.restype = wintypes.LPVOID
        a.SetEntriesInAclW.argtypes = [
            wintypes.ULONG,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        a.SetEntriesInAclW.restype = wintypes.DWORD
        a.SetNamedSecurityInfoW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.c_int,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        a.SetNamedSecurityInfoW.restype = wintypes.DWORD
        self.userenv.CreateAppContainerProfile.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.userenv.CreateAppContainerProfile.restype = ctypes.HRESULT
        self.userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.HRESULT
        self.userenv.DeleteAppContainerProfile.argtypes = [wintypes.LPCWSTR]
        self.userenv.DeleteAppContainerProfile.restype = ctypes.HRESULT

    def _winerr(self) -> int:
        return int(self.ctypes.get_last_error())

    def create_or_derive_profile(self, name: str) -> Any:
        ctypes = self.ctypes
        sid = ctypes.c_void_p()
        hr = self.userenv.CreateAppContainerProfile(name, name, name, None, 0, ctypes.byref(sid))
        if hr == self.S_OK and sid.value:
            return sid
        if sid.value:
            try:
                self.free_sid(sid)
            except Exception:
                pass
        sid = ctypes.c_void_p()
        hr2 = self.userenv.DeriveAppContainerSidFromAppContainerName(name, ctypes.byref(sid))
        if hr2 == self.S_OK and sid.value:
            return sid
        raise SandboxError(REASON_SANDBOX_PROFILE_CREATE_FAILED, winerr=int(hr2 or hr))

    def delete_profile(self, name: str) -> None:
        self.userenv.DeleteAppContainerProfile(name)

    def free_sid(self, sid: Any) -> None:
        if sid and getattr(sid, "value", None):
            self.advapi32.FreeSid(sid)

    def current_user_sid(self) -> Any:
        ctypes = self.ctypes
        wintypes = self.wintypes
        token = wintypes.HANDLE()
        if not self.advapi32.OpenProcessToken(self.kernel32.GetCurrentProcess(), self.TOKEN_QUERY, ctypes.byref(token)):
            raise SandboxError(REASON_SANDBOX_ACL_FAILED, winerr=self._winerr())
        try:
            needed = wintypes.DWORD(0)
            self.advapi32.GetTokenInformation(token, self.TokenUser, None, 0, ctypes.byref(needed))
            buf = ctypes.create_string_buffer(needed.value or 1)
            if not self.advapi32.GetTokenInformation(token, self.TokenUser, buf, needed, ctypes.byref(needed)):
                raise SandboxError(REASON_SANDBOX_ACL_FAILED, winerr=self._winerr())
            user = self.TOKEN_USER.from_buffer(buf)
            # Keep buf alive by attaching it to the SID pointer object.
            sid = ctypes.c_void_p(user.User.Sid)
            sid._buffer = buf  # type: ignore[attr-defined]
            return sid
        finally:
            self.close_handle(int(token.value) if token.value else 0)

    def grant_appcontainer_acl(self, path: str, sid: Any, *, execute: bool, write: bool) -> None:
        ctypes = self.ctypes
        access = self.FILE_GENERIC_READ
        if execute:
            access |= self.FILE_GENERIC_EXECUTE
        if write:
            access |= self.FILE_GENERIC_WRITE | self.DELETE
        host_sid = self.current_user_sid()
        entries = (self.EXPLICIT_ACCESS_W * 2)()
        entries[0].grfAccessPermissions = self.FILE_ALL_ACCESS
        entries[0].grfAccessMode = self.GRANT_ACCESS
        entries[0].grfInheritance = self.SUB_CONTAINERS_AND_OBJECTS_INHERIT
        entries[0].Trustee.TrusteeForm = self.TRUSTEE_IS_SID
        entries[0].Trustee.TrusteeType = self.TRUSTEE_IS_USER
        entries[0].Trustee.ptstrName = host_sid
        entries[1].grfAccessPermissions = access
        entries[1].grfAccessMode = self.GRANT_ACCESS
        entries[1].grfInheritance = self.SUB_CONTAINERS_AND_OBJECTS_INHERIT
        entries[1].Trustee.TrusteeForm = self.TRUSTEE_IS_SID
        entries[1].Trustee.TrusteeType = self.TRUSTEE_IS_USER
        entries[1].Trustee.ptstrName = sid
        new_acl = ctypes.c_void_p()
        status = self.advapi32.SetEntriesInAclW(2, entries, None, ctypes.byref(new_acl))
        if status != 0 or not new_acl:
            raise SandboxError(REASON_SANDBOX_ACL_FAILED, winerr=status)
        try:
            named = self.advapi32.SetNamedSecurityInfoW(
                path,
                self.SE_FILE_OBJECT,
                self.DACL_SECURITY_INFORMATION | self.PROTECTED_DACL_SECURITY_INFORMATION,
                None,
                None,
                new_acl,
                None,
            )
            if named != 0:
                raise SandboxError(REASON_SANDBOX_ACL_FAILED, winerr=named)
        finally:
            self.kernel32.LocalFree(new_acl)

    def create_stdio_pipes(self) -> dict[str, int]:
        ctypes = self.ctypes
        sa = self.SECURITY_ATTRIBUTES()
        sa.nLength = ctypes.sizeof(sa)
        sa.bInheritHandle = True
        sa.lpSecurityDescriptor = None

        def _pipe() -> tuple[int, int]:
            read = self.wintypes.HANDLE()
            write = self.wintypes.HANDLE()
            if not self.kernel32.CreatePipe(ctypes.byref(read), ctypes.byref(write), ctypes.byref(sa), 0):
                raise SandboxError(REASON_SANDBOX_LAUNCH_FAILED, winerr=self._winerr())
            return int(read.value), int(write.value)

        stdin_r, stdin_w = _pipe()
        stdout_r, stdout_w = _pipe()
        stderr_r, stderr_w = _pipe()
        for handle in (stdin_w, stdout_r, stderr_r):
            if not self.kernel32.SetHandleInformation(handle, self.HANDLE_FLAG_INHERIT, 0):
                raise SandboxError(REASON_SANDBOX_LAUNCH_FAILED, winerr=self._winerr())
        return {
            "stdin_r": stdin_r,
            "stdin_w": stdin_w,
            "stdout_r": stdout_r,
            "stdout_w": stdout_w,
            "stderr_r": stderr_r,
            "stderr_w": stderr_w,
        }

    def create_job_object(self) -> tuple[int, bool]:
        ctypes = self.ctypes
        handle = self.kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise SandboxError(REASON_SANDBOX_JOB_ASSIGNMENT_FAILED, winerr=self._winerr())
        job = int(handle)
        memory_ready = True
        limits = self.EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = (
            self.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | self.JOB_OBJECT_LIMIT_PROCESS_MEMORY
        )
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        limits.ProcessMemoryLimit = PROCESS_MEMORY_LIMIT_BYTES
        ok = self.kernel32.SetInformationJobObject(
            job, self.JobObjectExtendedLimitInformation, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        if not ok:
            memory_ready = False
            limits = self.EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = (
                self.JOB_OBJECT_LIMIT_ACTIVE_PROCESS | self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            limits.BasicLimitInformation.ActiveProcessLimit = 1
            ok = self.kernel32.SetInformationJobObject(
                job, self.JobObjectExtendedLimitInformation, ctypes.byref(limits), ctypes.sizeof(limits)
            )
            if not ok:
                self.close_handle(job)
                raise SandboxError(REASON_SANDBOX_JOB_ASSIGNMENT_FAILED, winerr=self._winerr())
        return job, memory_ready

    def create_appcontainer_process(
        self,
        *,
        application: str,
        cmdline: str,
        cwd: str,
        env: dict[str, str],
        sid: Any,
        pipes: dict[str, int],
    ) -> tuple[Any, dict[str, Any]]:
        ctypes = self.ctypes
        wintypes = self.wintypes
        caps = self.SECURITY_CAPABILITIES()
        caps.AppContainerSid = sid
        caps.Capabilities = None
        caps.CapabilityCount = 0
        caps.Reserved = 0
        size = ctypes.c_size_t(0)
        self.kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        if size.value == 0:
            raise SandboxError(REASON_SANDBOX_LAUNCH_FAILED, winerr=self._winerr())
        buf = ctypes.create_string_buffer(size.value)
        if not self.kernel32.InitializeProcThreadAttributeList(buf, 1, 0, ctypes.byref(size)):
            raise SandboxError(REASON_SANDBOX_LAUNCH_FAILED, winerr=self._winerr())
        attr_state = {"buf": buf, "initialized": True, "caps": caps}
        try:
            if not self.kernel32.UpdateProcThreadAttribute(
                buf,
                0,
                self.PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
                ctypes.byref(caps),
                ctypes.sizeof(caps),
                None,
                None,
            ):
                raise SandboxError(REASON_SANDBOX_LAUNCH_FAILED, winerr=self._winerr())
            siex = self.STARTUPINFOEXW()
            siex.StartupInfo.cb = ctypes.sizeof(siex)
            siex.StartupInfo.dwFlags = self.STARTF_USESTDHANDLES | self.STARTF_USESHOWWINDOW
            siex.StartupInfo.hStdInput = pipes["stdin_r"]
            siex.StartupInfo.hStdOutput = pipes["stdout_w"]
            siex.StartupInfo.hStdError = pipes["stderr_w"]
            siex.lpAttributeList = ctypes.cast(buf, wintypes.LPVOID)
            env_block = self._env_block(env)
            pi = self.PROCESS_INFORMATION()
            flags = (
                self.EXTENDED_STARTUPINFO_PRESENT
                | self.CREATE_SUSPENDED
                | self.CREATE_UNICODE_ENVIRONMENT
                | self.CREATE_NO_WINDOW
            )
            command = ctypes.create_unicode_buffer(cmdline)
            ok = self.kernel32.CreateProcessW(
                application,
                command,
                None,
                None,
                True,
                flags,
                env_block,
                cwd,
                ctypes.byref(siex),
                ctypes.byref(pi),
            )
            if not ok:
                raise SandboxError(REASON_SANDBOX_LAUNCH_FAILED, winerr=self._winerr())
            for key in ("stdin_r", "stdout_w", "stderr_w"):
                self.close_handle(pipes[key])
                pipes.pop(key, None)
            attr_state["env_block"] = env_block
            attr_state["command"] = command
            return pi, attr_state
        except Exception:
            self.free_attribute_list(attr_state)
            raise

    def assign_to_job(self, job: int, h_process: Any) -> None:
        if not self.kernel32.AssignProcessToJobObject(job, h_process):
            raise SandboxError(REASON_SANDBOX_JOB_ASSIGNMENT_FAILED, winerr=self._winerr())

    def verify_process_is_appcontainer(self, h_process: Any) -> tuple[bool, bool]:
        ctypes = self.ctypes
        wintypes = self.wintypes
        token = wintypes.HANDLE()
        if not self.advapi32.OpenProcessToken(h_process, self.TOKEN_QUERY, ctypes.byref(token)):
            raise SandboxError(REASON_SANDBOX_TOKEN_VERIFICATION_FAILED, winerr=self._winerr())
        try:
            value = wintypes.DWORD()
            needed = wintypes.DWORD()
            ok = self.advapi32.GetTokenInformation(
                token, self.TokenIsAppContainer, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(needed)
            )
            if not ok:
                raise SandboxError(REASON_SANDBOX_TOKEN_VERIFICATION_FAILED, winerr=self._winerr())
            is_ac = int(value.value) != 0
            sid_present = False
            needed = wintypes.DWORD(0)
            self.advapi32.GetTokenInformation(token, self.TokenAppContainerSid, None, 0, ctypes.byref(needed))
            if needed.value:
                buf = ctypes.create_string_buffer(needed.value)
                if self.advapi32.GetTokenInformation(
                    token, self.TokenAppContainerSid, buf, needed, ctypes.byref(needed)
                ):
                    sid_present = True
            return is_ac, sid_present
        finally:
            self.close_handle(int(token.value) if token.value else 0)

    def resume_thread(self, h_thread: Any) -> None:
        if self.kernel32.ResumeThread(h_thread) == 0xFFFFFFFF:
            raise SandboxError(REASON_SANDBOX_LAUNCH_FAILED, winerr=self._winerr())

    def terminate_process(self, h_process: Any) -> None:
        if h_process:
            self.kernel32.TerminateProcess(h_process, 1)

    def wait_process(self, h_process: Any, timeout_ms: int) -> None:
        self.kernel32.WaitForSingleObject(h_process, timeout_ms)

    def close_handle(self, handle: int) -> None:
        if handle:
            self.kernel32.CloseHandle(handle)

    def free_attribute_list(self, attr_state: dict[str, Any]) -> None:
        buf = attr_state.get("buf")
        if buf is not None and attr_state.get("initialized"):
            try:
                self.kernel32.DeleteProcThreadAttributeList(buf)
            except Exception:
                pass
            attr_state["initialized"] = False

    def quote_args(self, args: list[str]) -> str:
        parts: list[str] = []
        for arg in args:
            if not arg or any(ch in arg for ch in ' \t"'):
                parts.append('"' + arg.replace('"', '\\"') + '"')
            else:
                parts.append(arg)
        return " ".join(parts)

    def _env_block(self, env: dict[str, str]) -> Any:
        text = "".join(f"{key}={value}\0" for key, value in env.items()) + "\0"
        return self.ctypes.create_unicode_buffer(text)

    def wrap_process(self, proc_info: Any, pipes: dict[str, int]) -> WinProcess:
        import msvcrt

        stdin_fd = msvcrt.open_osfhandle(pipes["stdin_w"], os.O_WRONLY)
        stdout_fd = msvcrt.open_osfhandle(pipes["stdout_r"], os.O_RDONLY)
        stderr_fd = msvcrt.open_osfhandle(pipes["stderr_r"], os.O_RDONLY)
        pipes.pop("stdin_w", None)
        pipes.pop("stdout_r", None)
        pipes.pop("stderr_r", None)
        stdin = os.fdopen(stdin_fd, "wb", buffering=0)
        stdout = os.fdopen(stdout_fd, "rb", buffering=0)
        stderr = os.fdopen(stderr_fd, "rb", buffering=0)
        h_process = proc_info.hProcess
        exit_holder: dict[str, int | None] = {"code": None}

        def poll() -> int | None:
            if exit_holder["code"] is not None:
                return exit_holder["code"]
            wait = self.kernel32.WaitForSingleObject(h_process, 0)
            if wait == self.WAIT_OBJECT_0:
                code = self.wintypes.DWORD()
                if self.kernel32.GetExitCodeProcess(h_process, self.ctypes.byref(code)):
                    exit_holder["code"] = int(code.value)
                    return exit_holder["code"]
            return None

        def wait(timeout: float | None = None) -> int:
            ms = 0xFFFFFFFF if timeout is None else max(0, int(timeout * 1000))
            wait_rc = self.kernel32.WaitForSingleObject(h_process, ms)
            if wait_rc == self.WAIT_TIMEOUT:
                raise TimeoutError("SANDBOX_WAIT_TIMEOUT")
            code = self.wintypes.DWORD()
            self.kernel32.GetExitCodeProcess(h_process, self.ctypes.byref(code))
            exit_holder["code"] = int(code.value)
            return int(code.value)

        def terminate() -> None:
            self.terminate_process(h_process)

        return WinProcess(
            pid=int(proc_info.dwProcessId),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            wait=wait,
            terminate=terminate,
            poll=poll,
        )
