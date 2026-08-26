"""Strict DesktopHost -> launcher control framing."""
from __future__ import annotations
import json
from ..credential_vault import SUPPORTED_PROVIDERS

PREFIX = "AI_NOVEL_HOST_CONTROL_V1\t"
PROTOCOL = "packaged-host-control/v1"
MAX_FRAME_BYTES = 2048
CREDENTIAL_PREFIX = "AI_NOVEL_HOST_CREDENTIAL_V1\t"
CREDENTIAL_PROTOCOL = "packaged-host-credential/v1"
CREDENTIAL_MAX_BYTES = 4096

def parse_host_ping(line: str, runtime_instance_id: str) -> bool:
    if not line.startswith(PREFIX) or len(line.encode("utf-8")) > MAX_FRAME_BYTES:
        return False
    try:
        value = json.loads(line[len(PREFIX):])
    except (json.JSONDecodeError, UnicodeError):
        return False
    if not isinstance(value, dict):
        return False
    return (
        value.get("protocol") == PROTOCOL
        and value.get("type") == "PING"
        and value.get("runtime_instance_id") == runtime_instance_id
        and set(value) == {"protocol", "type", "runtime_instance_id"}
    )

def encode_host_ping(runtime_instance_id: str) -> str:
    return PREFIX + json.dumps({
        "protocol": PROTOCOL,
        "type": "PING",
        "runtime_instance_id": runtime_instance_id,
    }, separators=(",", ":"))

def parse_host_credential(line: str, runtime_instance_id: str) -> dict | None:
    if not line.startswith(CREDENTIAL_PREFIX) or len(line.encode()) > CREDENTIAL_MAX_BYTES: return None
    try: value = json.loads(line[len(CREDENTIAL_PREFIX):])
    except (json.JSONDecodeError, UnicodeError): return None
    if (not isinstance(value, dict) or value.get("protocol") != CREDENTIAL_PROTOCOL
            or value.get("runtime_instance_id") != runtime_instance_id
            or value.get("provider") not in SUPPORTED_PROVIDERS): return None
    typ = value.get("type")
    expected = {"protocol", "type", "runtime_instance_id", "provider"}
    if typ == "CLEAR_PROVIDER_CREDENTIAL": return value if set(value) == expected else None
    if typ != "SET_PROVIDER_CREDENTIAL" or set(value) != expected | {"credential"}: return None
    credential = value.get("credential")
    if not isinstance(credential, str) or not credential or len(credential.encode()) > 1024 or any(c in credential for c in "\0\r\n"): return None
    return value

def encode_backend_credential(message: dict) -> bytes:
    value = {"protocol": "packaged-credential/v1", "type": message["type"], "runtime_instance_id": message["runtime_instance_id"], "provider": message["provider"]}
    if message["type"] == "SET_PROVIDER_CREDENTIAL": value["credential"] = message["credential"]
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()
