"""Launcher-owned anonymous control pipe for packaged runtimes."""
from __future__ import annotations
import json, os, sys, threading
from dataclasses import dataclass
from ..credential_vault import SUPPORTED_PROVIDERS, credential_vault

PROTOCOL = "packaged-control/v1"
MAX_FRAME_BYTES = 4096
CREDENTIAL_PROTOCOL = "packaged-credential/v1"
_module_runtime_key_present = "PACKAGED_RUNTIME_INSTANCE_ID" in os.environ
_module_runtime_value_nonempty = bool(os.environ.get("PACKAGED_RUNTIME_INSTANCE_ID"))

class ProcessCredentialStore:
    __slots__ = ("_values",)
    def __init__(self): self._values: dict[str, str] = {}
    def set(self, provider: str, credential: str) -> None:
        if provider not in SUPPORTED_PROVIDERS: raise ValueError("unsupported provider")
        credential_vault.set(provider, credential); self._values[provider] = credential
    def clear(self, provider: str) -> None:
        credential_vault.clear(provider); self._values.pop(provider, None)
    def has(self, provider: str) -> bool: return credential_vault.has(provider)
    def resolve(self, provider: str) -> str | None: return credential_vault.resolve(provider)

credential_store = ProcessCredentialStore()

class ControlReaderStatus:
    def __init__(self):
        self._lock = threading.Lock(); self.module_import_runtime_key_present = _module_runtime_key_present; self.module_import_runtime_value_nonempty = _module_runtime_value_nonempty; self.entry_runtime_key_present = False; self.entry_runtime_value_nonempty = False; self.lookup_runtime_value_nonempty = False; self.invoked = False; self.runtime_env_present = False; self.stdin_available = False; self.start_result = "NOT_INVOKED"; self.started = False; self.alive = False
        self.frames_read = 0; self.frames_dispatched = 0; self.frames_rejected = 0; self.frames_applied = 0
    def reset(self):
        with self._lock:
            self.entry_runtime_key_present = self.entry_runtime_value_nonempty = self.lookup_runtime_value_nonempty = False; self.invoked = self.runtime_env_present = self.stdin_available = False; self.start_result = "NOT_INVOKED"; self.started = self.alive = False; self.frames_read = self.frames_dispatched = self.frames_rejected = self.frames_applied = 0
    def snapshot(self):
        with self._lock:
            return {"module_import_runtime_key_present": self.module_import_runtime_key_present, "module_import_runtime_value_nonempty": self.module_import_runtime_value_nonempty, "entry_runtime_key_present": self.entry_runtime_key_present, "entry_runtime_value_nonempty": self.entry_runtime_value_nonempty, "lookup_runtime_value_nonempty": self.lookup_runtime_value_nonempty, "invoked": self.invoked, "runtime_env_present": self.runtime_env_present, "stdin_available": self.stdin_available, "start_result": self.start_result, "started": self.started, "alive": self.alive, "frames_read": self.frames_read, "frames_dispatched": self.frames_dispatched, "frames_rejected": self.frames_rejected, "frames_applied": self.frames_applied}
    def inc(self, name):
        with self._lock: setattr(self, name, getattr(self, name) + 1)

control_reader_status = ControlReaderStatus()
def get_packaged_control_reader_status(): return control_reader_status.snapshot()

@dataclass(frozen=True)
class ControlMessage:
    protocol: str
    type: str
    runtime_instance_id: str

class PackagedControlReader:
    def __init__(self, runtime_instance_id: str, stream=None, observer=None):
        self.runtime_instance_id = runtime_instance_id
        self.stream = stream or getattr(sys.stdin, "buffer", sys.stdin)
        self.ping_count = 0
        self.observer = observer
        self._thread = None

    def start(self):
        if self._thread is None:
            control_reader_status.started = True; control_reader_status.alive = True
            self._thread = threading.Thread(target=self._read, name="packaged-control", daemon=True)
            self._thread.start()

    def _read(self):
        while True:
            try: frame = self.stream.readline(MAX_FRAME_BYTES + 1)
            except (OSError, ValueError): control_reader_status.alive = False; return
            if not frame: control_reader_status.alive = False; return
            control_reader_status.inc("frames_read")
            if len(frame) > MAX_FRAME_BYTES: control_reader_status.inc("frames_rejected"); continue
            try:
                value = json.loads(frame.decode("utf-8"))
                message = ControlMessage(str(value["protocol"]), str(value["type"]), str(value["runtime_instance_id"]))
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError): control_reader_status.inc("frames_rejected"); continue
            if message.protocol == PROTOCOL and message.type == "ping" and message.runtime_instance_id == self.runtime_instance_id:
                self.ping_count += 1; control_reader_status.inc("frames_dispatched"); control_reader_status.inc("frames_applied")
                if self.observer is not None:
                    self.observer("BACKEND_PING_ACCEPTED_FROM_WEBVIEW")
            elif self._credential(value, message):
                control_reader_status.inc("frames_dispatched"); control_reader_status.inc("frames_applied"); continue
            else:
                control_reader_status.inc("frames_rejected")

    def _credential(self, value: object, message: ControlMessage) -> bool:
        if (not isinstance(value, dict) or message.protocol != CREDENTIAL_PROTOCOL
                or message.runtime_instance_id != self.runtime_instance_id
                or value.get("provider") not in SUPPORTED_PROVIDERS): return False
        provider = value["provider"]
        typ = value.get("type")
        fields = {"protocol", "type", "runtime_instance_id", "provider"}
        if typ == "CLEAR_PROVIDER_CREDENTIAL":
            if set(value) != fields: return False
            credential_store.clear(provider); return True
        if typ != "SET_PROVIDER_CREDENTIAL" or set(value) != fields | {"credential"}: return False
        credential = value.get("credential")
        if not isinstance(credential, str) or not credential or len(credential.encode()) > 1024 or any(c in credential for c in "\0\r\n"): return False
        try:
            credential_store.set(provider, credential)
        except ValueError:
            return False
        return True

def start_packaged_control_reader():
    entry_key_present = "PACKAGED_RUNTIME_INSTANCE_ID" in os.environ
    entry_value_nonempty = bool(os.environ.get("PACKAGED_RUNTIME_INSTANCE_ID"))
    control_reader_status.reset()
    with control_reader_status._lock: control_reader_status.entry_runtime_key_present = entry_key_present; control_reader_status.entry_runtime_value_nonempty = entry_value_nonempty
    with control_reader_status._lock: control_reader_status.invoked = True
    if os.getenv("PACKAGED_WINDOWS_MODE", "false").lower() != "true":
        with control_reader_status._lock: control_reader_status.start_result = "NOT_PACKAGED_MODE"
        return None
    runtime_instance_id = os.getenv("PACKAGED_RUNTIME_INSTANCE_ID", "")
    with control_reader_status._lock: control_reader_status.lookup_runtime_value_nonempty = bool(runtime_instance_id)
    with control_reader_status._lock: control_reader_status.runtime_env_present = bool(runtime_instance_id)
    if not runtime_instance_id:
        with control_reader_status._lock: control_reader_status.start_result = "MISSING_RUNTIME_INSTANCE_ID"
        return None
    stdin = getattr(sys.stdin, "buffer", None)
    with control_reader_status._lock: control_reader_status.stdin_available = stdin is not None and hasattr(stdin, "readline")
    if not control_reader_status.stdin_available:
        with control_reader_status._lock: control_reader_status.start_result = "STDIN_UNAVAILABLE"
        return None
    reader = PackagedControlReader(runtime_instance_id)
    try: reader.start()
    except Exception:
        with control_reader_status._lock: control_reader_status.start_result = "THREAD_START_FAILED"
        return None
    with control_reader_status._lock: control_reader_status.start_result = "STARTED"
    return reader

def encode_ping(runtime_instance_id: str) -> bytes:
    return (json.dumps({"protocol": PROTOCOL, "type": "ping", "runtime_instance_id": runtime_instance_id}, separators=(",", ":")) + "\n").encode()
