"""One fixed-model Windows Whisper process under Model Center's original owner.

Configuration never executes native code. Only an explicit trusted start may
launch the repository's fixed host. A private inherited pipe must prove the
actual locked-file model load; HTTP health, discovery and external servers do
not admit a model. Stop/exit/restart revokes the original route immediately.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import threading
import time

from .domain import Capability, ModelDefinition, ModelStatus, RuntimeDefinition, RuntimeInstance, RuntimeManagement, RuntimeState, RuntimeType
from .discovery_types import safe_local_path
from ..audio_processing_runtime import audio_digest
from ..local_whisper_cpp import LocalWhisperCppProvider
from ..model_runtime import GenerationRuntime, ModelDescriptor, Modality, ProviderDescriptor
from ..stable_identity import canonical_model_identity_key

HOST_PROTOCOL = "studio-fixed-whisper-host/1"
PROVIDER_ID = "host.whisper.cpp"
MAX_MODEL_BYTES = 8 * 1024**3
MAX_TOOL_BYTES = 1024**3


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("WHISPER_HOST_PIN_REQUIRED")
    return value


def _path(value):
    if not isinstance(value, str) or not value:
        raise ValueError("WHISPER_HOST_PATH_REQUIRED")
    return Path(safe_local_path(value))


def _identity(path):
    stat = path.stat(follow_symlinks=False)
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _closed_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('WHISPER_HOST_DUPLICATE_CONTROL_FIELD')
        result[key] = value
    return result


def _reject_number(value):
    raise ValueError('WHISPER_HOST_INVALID_CONTROL_NUMBER')


class _LockedFile:
    """Windows read handle forbidding concurrent writes and replacement."""
    def __init__(self, path, expected_hash, maximum, guard):
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                          wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        guard()
        safe_local_path(str(path))
        handle = create(str(path), 0x80000000, 0x1, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ValueError("WHISPER_HOST_FILE_LOCK_FAILED")
        self.file = None
        try:
            descriptor = msvcrt.open_osfhandle(int(handle), os.O_RDONLY | os.O_BINARY)
        except Exception:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)
            raise
        try:
            self.file = os.fdopen(descriptor, "rb")
            stat = os.fstat(self.file.fileno())
            if not 1 <= stat.st_size <= maximum:
                raise ValueError("WHISPER_HOST_FILE_CAPACITY_INVALID")
            digest = hashlib.sha256()
            while True:
                guard()
                block = self.file.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
            guard()
            if digest.hexdigest() != expected_hash:
                raise ValueError("WHISPER_HOST_FILE_PIN_MISMATCH")
            self.identity = _identity(path)
            if self.identity[:3] != (stat.st_dev, stat.st_ino, stat.st_size):
                raise ValueError("WHISPER_HOST_FILE_IDENTITY_CHANGED")
            self.path = path
            class FileInformation(ctypes.Structure):
                _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
                    ('access', wintypes.FILETIME), ('write', wintypes.FILETIME), ('volume', wintypes.DWORD),
                    ('size_high', wintypes.DWORD), ('size_low', wintypes.DWORD), ('links', wintypes.DWORD),
                    ('index_high', wintypes.DWORD), ('index_low', wintypes.DWORD)]
            kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(FileInformation)]
            kernel.GetFileInformationByHandle.restype = wintypes.BOOL
            information = FileInformation()
            if not kernel.GetFileInformationByHandle(msvcrt.get_osfhandle(self.file.fileno()), ctypes.byref(information)):
                raise ValueError('WHISPER_HOST_FILE_IDENTITY_UNAVAILABLE')
            self.native_file_id = f'{information.volume:08x}{information.index_high:08x}{information.index_low:08x}'
        except Exception:
            if self.file is not None:
                self.file.close()
            else:
                os.close(descriptor)
            raise

    def current(self):
        if self.file is None or self.file.closed or _identity(self.path) != self.identity:
            raise ValueError("WHISPER_HOST_FILE_IDENTITY_CHANGED")

    def close(self):
        if self.file is not None:
            self.file.close()


class _KillOnCloseJob:
    """An owned Windows Job keeps a dead backend from leaving an ASR process."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount",
                "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        information = Extended()
        information.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.kernel.SetInformationJobObject(
                self.handle, 9, ctypes.byref(information), ctypes.sizeof(information)):
            self.close()
            raise ValueError("WHISPER_HOST_JOB_REQUIRED")

    def attach(self, process):
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ValueError("WHISPER_HOST_JOB_REQUIRED")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


@dataclass(frozen=True)
class FixedWhisperConfiguration:
    executable: Path
    executable_sha256: str
    model_path: Path
    model_sha256: str
    ffmpeg_path: Path
    ffmpeg_sha256: str
    port: int = 8178
    threads: int = 4
    use_gpu: bool = True

    def __post_init__(self):
        for key in ("executable", "model_path", "ffmpeg_path"):
            object.__setattr__(self, key, _path(str(getattr(self, key))))
        for key in ("executable_sha256", "model_sha256", "ffmpeg_sha256"):
            _hash(getattr(self, key))
        if (type(self.port) is not int or not 1024 <= self.port <= 65535
                or type(self.threads) is not int or not 1 <= self.threads <= 64 or type(self.use_gpu) is not bool
                or self.executable == self.model_path or self.model_path == self.ffmpeg_path
                or self.executable == self.ffmpeg_path):
            raise ValueError("WHISPER_HOST_CONFIGURATION_INVALID")


class OwnedWhisperHost:
    def __init__(self, center, runtime, config):
        self.center, self.runtime, self.config = center, runtime, config
        generation = runtime if isinstance(runtime, GenerationRuntime) else getattr(runtime, 'generation_runtime', None)
        if not isinstance(generation, GenerationRuntime):
            raise ValueError('WHISPER_HOST_ORIGINAL_GENERATION_RUNTIME_REQUIRED')
        self.providers, self.models, self.node = generation.providers, generation.models, generation.audio_processing_node
        if (generation is not runtime and (getattr(runtime, 'provider_registry', None) is not self.providers
                or getattr(runtime, 'model_registry', None) is not self.models)):
            raise ValueError('WHISPER_HOST_ORIGINAL_REGISTRY_OWNER_REQUIRED')
        if (center.identity_store is None or self.providers.identity_store is None
                or center.identity_store.path != self.providers.identity_store.path
                or self.models.identity_store is None
                or center.identity_store.path != self.models.identity_store.path):
            raise ValueError("WHISPER_HOST_ORIGINAL_IDENTITY_STORE_REQUIRED")
        self.provider_id = PROVIDER_ID
        self.model_id = "whisper-fixed-" + config.model_sha256[:32]
        self.runtime_id = "whisper-fixed-local"
        identities = center.identity_store
        self.runtime_uuid = identities.get_or_create("runtime", self.runtime_id)
        self.model_uuid = identities.get_or_create("model", canonical_model_identity_key(self.provider_id, self.model_id))
        identities.get_or_create("provider", self.provider_id)
        if identities.get("execution_node", "local") is None:
            raise ValueError("WHISPER_HOST_ORIGINAL_EXECUTION_NODE_REQUIRED")
        self.endpoint = "http://127.0.0.1:" + str(config.port)
        self.definition = RuntimeDefinition(self.runtime_id, RuntimeType.WHISPER_CPP, str(config.executable),
            self.endpoint, "127.0.0.1", config.port, str(config.executable.parent), capabilities=(Capability.AUDIO,),
            provider_adapter="STUDIO_FIXED_WHISPER_HOST", management=RuntimeManagement.MANAGED,
            model_path=str(config.model_path), threads=config.threads, identity_id=self.runtime_uuid)
        self.model = ModelDefinition(self.model_id, "Whisper 本地字幕模型", "WHISPER", "FIXED_LOCAL", "1",
            (Capability.AUDIO,), RuntimeType.WHISPER_CPP, "GGML", local_paths=(), status=ModelStatus.VALIDATION_REQUIRED,
            metadata={"sha256": config.model_sha256, "local_discovery": True, "host_fixed_model": True,
                      "verification": "LOCAL_REQUIRED", "model_loaded": False}, identity_id=self.model_uuid)
        self._lock = threading.RLock()
        self._process = self._job = None
        self._files, self._proof, self._token, self._ready, self._adapter = [], None, None, None, None
        self._revision = 0
        self._subtitle = None
        self._subtitle_digest = None

    def _revoke(self, state, error=None):
        self._proof, self._token, self._ready = None, None, None
        self._subtitle = self._subtitle_digest = None
        instance = self.center.lifecycle.instances.get(self.runtime_id)
        if instance is not None:
            instance.state, instance.error = state, error
            instance.safe_error_code = error
            instance.loaded_models = []
            instance.http_reachable = False
            instance.health = {"reachable": False, "model_loaded": False, "verification": "LOCAL_REQUIRED"}
        self.center.models[self.model_id] = replace(self.model, status=ModelStatus.VALIDATION_REQUIRED)
        if self._adapter is not None:
            current = next((item for item in self.providers.descriptors()
                            if item.provider_id == self.provider_id), None)
            if current is not None:
                self.providers.register(replace(current, available=False, health_status="host_process_not_admitted"),
                    self._adapter, replace=True)
            model = next((item for item in self.models.descriptors()
                          if item.provider_id == self.provider_id and item.model_id == self.model_id), None)
            if model is not None:
                self.models.register(replace(model, enabled=False), replace=True)

    def refresh(self):
        with self._lock:
            process = self._process
            instance = self.center.lifecycle.instances.get(self.runtime_id)
            if process is not None and process.poll() is not None:
                self._revoke(RuntimeState.FAILED, "WHISPER_HOST_PROCESS_EXITED")
                if instance is not None:
                    instance.process_alive = False
                    instance.health["exit_code"] = process.returncode
            elif process is not None:
                try:
                    for file in self._files:
                        file.current()
                except (OSError, ValueError):
                    self._revoke(RuntimeState.FAILED, "WHISPER_HOST_FILE_IDENTITY_CHANGED")
            return instance

    def admission(self):
        with self._lock:
            instance = self.refresh()
            expected_model = replace(self.model, status=ModelStatus.READY,
                metadata={**self.model.metadata, 'model_loaded': True})
            if (self._proof is None or self._process is None or self._process.poll() is not None
                    or instance is None or instance.state != RuntimeState.RUNNING
                    or self.center.runtimes.get(self.runtime_id) != self.definition
                    or self.center.models.get(self.model_id) != expected_model):
                raise ValueError("WHISPER_HOST_NOT_ADMITTED")
            return dict(self._proof)

    def authorization(self):
        with self._lock:
            proof = self.admission()
            if self._token is None:
                raise ValueError("WHISPER_HOST_NOT_ADMITTED")
            return {"X-Studio-Whisper-Token": self._token, "X-Studio-Whisper-Revision": str(proof["revision"]),
                    "X-Studio-Whisper-PID": str(proof["process_id"])}

    def _ready_frame(self, process, nonce, revision, authority_guard):
        try:
            raw = process.stdout.readline(8193)
            if len(raw) > 8192 or not raw.endswith(b"\n"):
                raise ValueError("WHISPER_HOST_CONTROL_FRAME_INVALID")
            ready = json.loads(raw.decode("utf-8"), object_pairs_hook=_closed_object, parse_constant=_reject_number)
            with self._lock:
                if self._process is not process or revision != self._revision or len(self._files) != 3:
                    return
                model_bytes = self._files[1].identity[2]
                model_file_id = self._files[1].native_file_id
            fields = {"schema", "event", "startup_nonce", "revision", "pid", "model_sha256", "executable_sha256",
                      "port", "whisper_version", "model_file_id", "model_bytes"}
            if (not isinstance(ready, dict) or set(ready) != fields or ready["schema"] != HOST_PROTOCOL
                    or ready["event"] != "MODEL_LOADED_AND_BOUND" or ready["startup_nonce"] != nonce
                    or type(ready["revision"]) is not int or ready["revision"] != revision
                    or type(ready["pid"]) is not int or ready["pid"] != process.pid
                    or ready["model_sha256"] != self.config.model_sha256
                    or ready["executable_sha256"] != self.config.executable_sha256
                    or type(ready["port"]) is not int or ready["port"] != self.config.port
                    or ready["whisper_version"] != "1.8.2"
                    or ready["model_file_id"] != model_file_id
                    or type(ready["model_bytes"]) is not int or ready["model_bytes"] != model_bytes):
                raise ValueError("WHISPER_HOST_CONTROL_PROOF_MISMATCH")
            authority_guard()
            with self._lock:
                if self._process is not process or process.poll() is not None or revision != self._revision:
                    return
                for file in self._files:
                    file.current()
                self._ready = ready
                self._proof = {"schema": "host-local-model-admission/2", "provider_id": self.provider_id,
                    "model_id": self.model_id, "endpoint": self.endpoint, "model_sha256": self.config.model_sha256,
                    "runtime_kind": "WHISPER_CPP", "management": "MANAGED", "enabled": True,
                    "model_locality": "LOCAL_VERIFIED", "revision": revision, "runtime_uuid": str(self.runtime_uuid),
                    "process_id": process.pid, "executable_sha256": self.config.executable_sha256,
                    "startup_nonce": nonce, "ready_digest": audio_digest(ready)}
                adapter = LocalWhisperCppProvider(provider_id=self.provider_id, model_id=self.model_id,
                    endpoint=self.endpoint, model_sha256=self.config.model_sha256, ffmpeg_path=str(self.config.ffmpeg_path),
                    admission_guard=self.admission, request_authorization=self.authorization)
                # Only this original owner may replace its previous route.
                if self._adapter is None and self.providers.contains(self.provider_id):
                    raise ValueError("WHISPER_HOST_PROVIDER_ALREADY_OWNED")
                if self._adapter is None and self.models.contains(self.provider_id, self.model_id):
                    raise ValueError("WHISPER_HOST_MODEL_ALREADY_OWNED")
                replacing = self._adapter is not None
                self._adapter = adapter
                self.providers.register(ProviderDescriptor(self.provider_id, self.model.display_name, "local",
                    frozenset({Modality.AUDIO}), True, True, "host_model_loaded_inference_not_run"), adapter,
                    replace=replacing)
                self.models.register(ModelDescriptor(self.model_id, self.provider_id, self.model.display_name,
                    Modality.AUDIO, frozenset({"TRANSCRIBE"}), enabled=True), replace=replacing)
                instance = self.center.lifecycle.instances[self.runtime_id]
                instance.state, instance.safe_error_code, instance.error = RuntimeState.RUNNING, None, None
                instance.process_alive, instance.http_reachable = True, True
                instance.version = ready['whisper_version']
                instance.loaded_models = [self.model_id]
                instance.health = {"reachable": True, "model_loaded": True, "admission": "OWNED_PRIVATE_PIPE",
                                   "inference": "NOT_RUN", "verification": "LOCAL_REQUIRED"}
                self.center.models[self.model_id] = replace(self.model, status=ModelStatus.READY,
                    metadata={**self.model.metadata, "model_loaded": True})
                self.center.set_runtime_version(self.runtime_id, ready["whisper_version"])
        except Exception:
            with self._lock:
                if self._process is process:
                    self._revoke(RuntimeState.FAILED, "WHISPER_HOST_STARTUP_PROOF_REJECTED")
                    if process.poll() is None:
                        try:
                            process.terminate()
                        except OSError:
                            if self._job is not None:
                                self._job.close()

    def _watch_start(self, process, revision, authority_guard):
        deadline = time.monotonic() + 300
        while process.poll() is None:
            with self._lock:
                if self._process is not process or revision != self._revision:
                    return
                admitted = self._proof is not None
            if admitted:
                return
            try:
                authority_guard()
                if time.monotonic() >= deadline:
                    raise ValueError("WHISPER_HOST_STARTUP_TIMEOUT")
            except Exception:
                with self._lock:
                    if self._process is process:
                        self._revoke(RuntimeState.FAILED, "WHISPER_HOST_STARTUP_AUTHORITY_OR_TIMEOUT")
                        try:
                            process.terminate()
                        except OSError:
                            if self._job is not None:
                                self._job.close()
                return
            time.sleep(0.25)

    def _watch_exit(self, process, revision):
        process.wait()
        with self._lock:
            if self._process is process and self._revision == revision:
                self._revoke(RuntimeState.FAILED, "WHISPER_HOST_PROCESS_EXITED")
                instance = self.center.lifecycle.instances.get(self.runtime_id)
                if instance is not None:
                    instance.process_alive = False
                    instance.health['exit_code'] = process.returncode
                self._dispose()

    def _drain_stderr(self, process):
        stream = process.stderr
        try:
            while True:
                raw = stream.readline(4097)
                if not raw:
                    return
                selected = raw[:4096]
                while raw and not raw.endswith(b'\n'):
                    raw = stream.readline(4097)
                with self._lock:
                    if self._process is process:
                        self.center.lifecycle._logs[self.runtime_id]['stderr'].append(
                            selected.decode('utf-8', errors='replace').rstrip())
        finally:
            stream.close()

    def start(self, authority_guard):
        if os.name != "nt":
            raise ValueError("WHISPER_HOST_WINDOWS_REQUIRED")
        if not callable(authority_guard):
            raise ValueError("WHISPER_HOST_SESSION_GUARD_REQUIRED")
        authority_guard()
        with self._lock:
            self.refresh()
            if self._process is not None and self._process.poll() is None:
                if self.center.lifecycle.instances[self.runtime_id].state == RuntimeState.FAILED:
                    self._revoke(RuntimeState.FAILED, 'WHISPER_HOST_EXPLICIT_RESTART')
                    self._dispose()
                else:
                    if self._proof is not None:
                        self.admission()
                    return self.center.lifecycle.instances[self.runtime_id]
            self._dispose()
            self._revision += 1
            if self._revision > 2**53 - 1:
                raise ValueError("WHISPER_HOST_REVISION_EXHAUSTED")
            try:
                for path, digest, maximum in ((self.config.executable, self.config.executable_sha256, MAX_TOOL_BYTES),
                        (self.config.model_path, self.config.model_sha256, MAX_MODEL_BYTES),
                        (self.config.ffmpeg_path, self.config.ffmpeg_sha256, MAX_TOOL_BYTES)):
                    self._files.append(_LockedFile(path, digest, maximum, authority_guard))
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port:
                    port.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    port.bind(("127.0.0.1", self.config.port))
                self._job = _KillOnCloseJob()
                from .service import _safe_runtime_environment
                process = subprocess.Popen([str(self.config.executable)], cwd=str(self.config.executable.parent),
                    env=_safe_runtime_environment({}), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                self._process = process
                self._job.attach(process)
                self._token, nonce = secrets.token_hex(32), secrets.token_hex(32)
                frame = {"schema": HOST_PROTOCOL, "model_path": str(self.config.model_path),
                    "model_sha256": self.config.model_sha256, "executable_sha256": self.config.executable_sha256,
                    "token": self._token, "startup_nonce": nonce, "revision": self._revision,
                    "port": self.config.port, "threads": self.config.threads, "use_gpu": self.config.use_gpu}
                process.stdin.write((json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
                process.stdin.flush()
                instance = RuntimeInstance(self.runtime_id, process.pid, RuntimeState.STARTING, self.endpoint,
                    datetime.now(timezone.utc).isoformat(), management=RuntimeManagement.MANAGED, process_alive=True,
                    health={"reachable": False, "model_loaded": False, "verification": "LOCAL_REQUIRED"})
                self.center.lifecycle._owned[self.runtime_id] = process
                self.center.lifecycle.instances[self.runtime_id] = instance
                self.center.lifecycle._logs[self.runtime_id] = {"stdout": (), "stderr": deque(maxlen=200)}
                threading.Thread(target=self._drain_stderr,
                    args=(process,), daemon=True, name="whisper-owned-stderr").start()
                revision = self._revision
                threading.Thread(target=self._ready_frame, args=(process, nonce, revision, authority_guard),
                    daemon=True, name="whisper-private-load-proof").start()
                threading.Thread(target=self._watch_start, args=(process, revision, authority_guard),
                    daemon=True, name="whisper-private-start-fence").start()
                threading.Thread(target=self._watch_exit, args=(process, revision),
                    daemon=True, name="whisper-private-process-lifetime").start()
                return instance
            except Exception:
                self._revoke(RuntimeState.FAILED, "WHISPER_HOST_START_FAILED")
                self._dispose()
                raise ValueError("WHISPER_HOST_START_FAILED") from None

    def _dispose(self):
        process = self._process
        self._process = None
        # Closing this parent's job guarantees termination of the assigned
        # process even when it exits between poll and a normal terminate call.
        if self._job is not None:
            self._job.close()
            self._job = None
        if process is not None:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            if process.stdout is not None:
                process.stdout.close()
        self.center.lifecycle._owned.pop(self.runtime_id, None)
        for file in self._files:
            file.close()
        self._files = []

    def stop(self):
        with self._lock:
            self._revoke(RuntimeState.STOPPED)
            self._dispose()
            instance = self.center.lifecycle.instances.setdefault(self.runtime_id, RuntimeInstance(self.runtime_id))
            instance.process_id, instance.process_alive = None, False
            instance.state = RuntimeState.STOPPED
            return instance

    def subtitle_adapter(self):
        with self._lock:
            self.admission()
            binding = self.node.binding(self.provider_id, self.model_id, "ASR")
            if self._subtitle is None or self._subtitle_digest != binding["route_digest"]:
                from ..experimental.subtitle_asr import ModelRuntimeSubtitleAdapter
                self._subtitle = ModelRuntimeSubtitleAdapter(self.node,
                    provider_id=self.provider_id, model_id=self.model_id)
                self._subtitle_digest = binding["route_digest"]
            return self._subtitle


def install_fixed_whisper_host(center, runtime, *, executable, executable_sha256, model_path, model_sha256,
        ffmpeg_path, ffmpeg_sha256, port=8178, threads=4, use_gpu=True):
    """Host configuration only; never accepted as an HTTP runtime profile."""
    config = FixedWhisperConfiguration(_path(executable), _hash(executable_sha256), _path(model_path),
        _hash(model_sha256), _path(ffmpeg_path), _hash(ffmpeg_sha256), port, threads, use_gpu)
    owner = OwnedWhisperHost(center, runtime, config)
    with center._config_lock:
        if owner.runtime_id in center.runtimes or owner.model_id in center.models:
            raise ValueError("WHISPER_HOST_ALREADY_CONFIGURED")
        center.runtimes[owner.runtime_id] = owner.definition
        center.models[owner.model_id] = owner.model
        center.lifecycle._trusted_whisper[owner.runtime_id] = owner
    return owner
