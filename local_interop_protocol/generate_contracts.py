"""Deterministically regenerate public contracts and parity manifest.

Run: python -m local_interop_protocol.generate_contracts
No product imports, network access or credential access.
"""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from . import models

SCHEMAS = {
    "handshake": models.HandshakeHello,
    "product": models.ProductDescriptor,
    "capability": models.CapabilityDescriptor,
    "context-capsule": models.AppContextCapsule,
    "context-evidence": models.ContextEvidence,
    "event": models.InteropEvent,
    "diagnostic": models.DiagnosticCapsule,
    "handoff": models.HandoffRequest,
    "model-registry": models.ModelRegistry,
    "tutor-request": models.TutorRequest,
    "tutor-response": models.TutorGuidance,
    "verifier-request": models.VerifierRequest,
    "verifier-result": models.VerifierResult,
    "case-candidate": models.CaseCandidate,
    "error": models.InteropError,
    "hello-result": models.HelloResult,
    "capability-negotiation": models.CapabilityNegotiation,
    "session": models.SessionDescriptor,
    "session-open-request": models.SessionOpenRequest,
    "session-open-result": models.SessionOpenResult,
    "task-requirement": models.TaskRequirement,
    "handoff-result": models.HandoffResult,
    "discovery": models.DiscoveryRecord,
    "heartbeat": models.Heartbeat,
    "cancel-request": models.CancelRequest,
    "cancel-result": models.CancelResult,
    "transport-request": models.TransportRequest,
    "transport-response": models.TransportResponse,
}


def _constraints(schema: dict) -> None:
    # Structural invariants are mirrored for non-Python clients. Checksums,
    # freshness, trusted provenance, permissions and actual consent are runtime.
    title = schema.get("title")
    if title == "ContextContent":
        schema["allOf"] = [
            {
                "if": {"properties": {"level": {"const": "NONE"}}},
                "then": {"properties": {"text": {"type": "null"}, "consent_id": {"type": "null"}}},
                "else": {
                    "required": ["text", "consent_id"],
                    "properties": {"text": {"type": "string"}, "consent_id": {"type": "string"}},
                },
            },
            {
                "if": {"properties": {"level": {"const": "SELECTED_TEXT"}}, "required": ["level"]},
                "then": {"properties": {"text": {"maxLength": 16384}}},
            },
        ]
    if title == "AppContextCapsule":
        schema.setdefault("allOf", []).extend(
            [
                {
                    "if": {
                        "properties": {"project_id": {"type": "string"}},
                        "required": ["project_id"],
                    },
                    "then": {
                        "required": ["project_version"],
                        "properties": {"project_version": {"type": "string"}},
                    },
                },
                {
                    "if": {
                        "properties": {"chapter_id": {"type": "string"}},
                        "required": ["chapter_id"],
                    },
                    "then": {
                        "required": ["project_id", "chapter_version"],
                        "properties": {
                            "project_id": {"type": "string"},
                            "chapter_version": {"type": "integer"},
                        },
                    },
                },
            ]
        )
        for level, required in {
            "SELECTED_TEXT": ["selection_id", "selection_hash"],
            "CURRENT_CHAPTER": ["chapter_id"],
            "PROJECT_CONTEXT": ["project_id"],
        }.items():
            schema["allOf"].append(
                {
                    "if": {
                        "required": ["content"],
                        "properties": {
                            "content": {
                                "required": ["level"],
                                "properties": {"level": {"const": level}},
                            }
                        },
                    },
                    "then": {
                        "required": required,
                        "properties": {name: {"type": "string"} for name in required},
                    },
                }
            )
    if title in ("AppContextCapsule", "DiagnosticCapsule", "VerifierResult", "CaseCandidate"):
        for source_privacy, permitted in {
            "LOCAL_ONLY": ["LOCAL_ONLY"],
            "REDACTION_REQUIRED": ["LOCAL_ONLY", "REDACTION_REQUIRED"],
        }.items():
            schema.setdefault("allOf", []).append(
                {
                    "if": {
                        "required": ["evidence"],
                        "properties": {
                            "evidence": {
                                "contains": {"properties": {"privacy": {"const": source_privacy}}}
                            }
                        },
                    },
                    "then": {"properties": {"privacy_scope": {"enum": permitted}}},
                }
            )
    if title == "VerifierResult":
        schema.setdefault("allOf", []).append(
            {
                "if": {"properties": {"status": {"const": "VERIFIED"}}},
                "then": {
                    "required": ["evidence"],
                    "properties": {
                        "evidence": {
                            "minItems": 1,
                            "contains": {"properties": {"authority": {"const": "AUTHORITATIVE"}}},
                        }
                    },
                },
            }
        )
    if title == "CaseCandidate":
        schema.setdefault("allOf", []).append(
            {"properties": {"verification": {"properties": {"status": {"const": "VERIFIED"}}}}}
        )
    if title == "HandoffTarget":
        targets = ("feature", "project_id", "chapter_id", "task_id", "session_id")
        schema["allOf"] = []
        for action, field in {
            "OPEN_FEATURE": "feature",
            "OPEN_PROJECT": "project_id",
            "OPEN_TASK": "task_id",
            "OPEN_CHAPTER": "chapter_id",
            "OPEN_SESSION": "session_id",
        }.items():
            allowed = {field} | (
                {"project_id"} if action in ("OPEN_TASK", "OPEN_CHAPTER") else set()
            )
            required = [field]
            properties = {key: {"type": "null"} for key in targets if key not in allowed}
            properties[field] = {"type": "string"}
            if action in ("OPEN_PROJECT", "OPEN_TASK", "OPEN_CHAPTER"):
                required.append("source_version")
                properties["source_version"] = {"type": "string"}
            schema["allOf"].append(
                {
                    "if": {"properties": {"action": {"const": action}}},
                    "then": {"required": required, "properties": properties},
                }
            )
    if title == "HandoffResult":
        schema["allOf"] = [
            {
                "if": {"properties": {"status": {"const": "REJECTED"}}},
                "then": {
                    "required": ["error_code"],
                    "properties": {"error_code": {"type": "string"}},
                },
                "else": {"properties": {"error_code": {"type": "null"}}},
            }
        ]
    if title == "VerificationCondition":
        schema["allOf"] = []
        for field, value_type in {
            "runtime_status": {"enum": list(models.RuntimeStatus.__args__)},
            "task_status": {"enum": list(models.TaskStatus.__args__)},
            "project_version": {"type": "string"},
            "chapter_version": {"type": "integer"},
        }.items():
            properties = {"expected_value": value_type}
            if field != "chapter_version":
                properties["operator"] = {"enum": ["EQ", "NE"]}
            schema["allOf"].append(
                {
                    "if": {"properties": {"field": {"const": field}}},
                    "then": {"properties": properties},
                }
            )
    if title == "InteropEvent":
        schema["allOf"] = [
            {
                "properties": {
                    "context": {
                        "properties": {"content": {"properties": {"level": {"const": "NONE"}}}}
                    }
                }
            }
        ]
    if title in ("TransportRequest", "TransportResponse"):
        mapping = {
            "TransportRequest": {
                "HELLO": "HandshakeHello",
                "CAPABILITY_NEGOTIATION": "CapabilityNegotiation",
                "SESSION": "SessionOpenRequest",
                "TUTOR": "TutorRequest",
                "DIAGNOSTICS": "DiagnosticCapsule",
                "VERIFY": "VerifierRequest",
                "HANDOFF": "HandoffRequest",
                "HEARTBEAT": "Heartbeat",
                "CANCEL": "CancelRequest",
            },
            "TransportResponse": {
                "HELLO": "HelloResult",
                "CAPABILITY_NEGOTIATION": "CapabilityNegotiation",
                "SESSION": "SessionOpenResult",
                "TUTOR": "TutorGuidance",
                "DIAGNOSTICS": "TutorGuidance",
                "VERIFY": "VerifierResult",
                "HANDOFF": "HandoffResult",
                "HEARTBEAT": "Heartbeat",
                "CANCEL": "CancelResult",
            },
        }[title]
        schema["allOf"] = [
            {
                "if": {"properties": {"operation": {"const": operation}}},
                "then": {
                    "properties": {
                        "payload": (
                            {
                                "anyOf": [
                                    {"$ref": f"#/$defs/{dto}"},
                                    {"$ref": "#/$defs/InteropError"},
                                ]
                            }
                            if title == "TransportResponse"
                            else {"$ref": f"#/$defs/{dto}"}
                        )
                    }
                },
            }
            for operation, dto in mapping.items()
        ]
    if "properties" in schema and "protocol_name" in schema["properties"]:
        schema["required"] = sorted(
            set(schema.get("required", [])) | {"protocol_name", "protocol_version"}
        )
    for definition in schema.get("$defs", {}).values():
        _constraints(definition)


def _ts_type(node: dict) -> str:
    if "$ref" in node:
        return node["$ref"].split("/")[-1]
    if "const" in node:
        return json.dumps(node["const"])
    if "enum" in node:
        return " | ".join(json.dumps(value) for value in node["enum"])
    if "anyOf" in node:
        return " | ".join(dict.fromkeys(_ts_type(value) for value in node["anyOf"]))
    kind = node.get("type")
    if kind == "array":
        return f"ReadonlyArray<{_ts_type(node['items'])}>"
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "null": "null",
    }.get(kind, "never")


def _pascal(name: str) -> str:
    return "".join(word[:1].upper() + word[1:] for word in re.split(r"[^A-Za-z0-9]+", name))


def _rust_types(definitions: dict[str, dict]) -> str:
    extras: dict[str, str] = {}

    def ty(node: dict, name: str) -> str:
        if "$ref" in node:
            return node["$ref"].split("/")[-1]
        if "const" in node:
            if isinstance(node["const"], bool):
                return "bool"
            vals = [node["const"]]
        else:
            vals = node.get("enum")
        if vals is not None:
            variants = "\n".join(
                f"    #[serde(rename = {json.dumps(v)})]\n    V{i}," for i, v in enumerate(vals)
            )
            extras[name] = (
                "#[derive(Debug, Clone, Serialize, Deserialize)]\n"
                f"pub enum {name} {{\n{variants}\n}}\n"
            )
            return name
        if "anyOf" in node:
            nonnull = [part for part in node["anyOf"] if part.get("type") != "null"]
            if len(nonnull) == 1 and len(nonnull) != len(node["anyOf"]):
                return f"Option<{ty(nonnull[0], name)}>"
            variant_types = [ty(part, f"{name}V{i}") for i, part in enumerate(nonnull)]
            variant_types = list(dict.fromkeys(variant_types))
            if len(variant_types) == 1:
                return variant_types[0]
            variants = "\n".join(f"    V{i}({item})," for i, item in enumerate(variant_types))
            extras[name] = (
                "#[derive(Debug, Clone, Serialize, Deserialize)]\n#[serde(untagged)]\n"
                f"pub enum {name} {{\n{variants}\n}}\n"
            )
            return name
        if node.get("type") == "array":
            return f"Vec<{ty(node['items'], name + 'Item')}>"
        return {"string": "String", "integer": "u64", "number": "f64", "boolean": "bool"}[
            node["type"]
        ]

    structs = []
    for name, definition in sorted(definitions.items()):
        lines = []
        required = definition.get("required", [])
        for field, node in definition["properties"].items():
            field_type = ty(node, name + _pascal(field))
            if field not in required and not field_type.startswith("Option<"):
                field_type = f"Option<{field_type}>"
            lines.append(f"    pub {field}: {field_type},")
        structs.append(
            "#[derive(Debug, Clone, Serialize, Deserialize)]\n#[serde(deny_unknown_fields)]\n"
            f"pub struct {name} {{\n" + "\n".join(lines) + "\n}\n"
        )
    return (
        "// GENERATED INTERFACE DRAFT. Requires serde derive. No Desktop runtime claim.\n"
        "// Validate all values against the accompanying JSON Schema before use.\n"
        "// Serde alone does not enforce bounds, hashes, timestamps, privacy or provenance.\n"
        "// Optional defaults must be hydrated per the schema before canonical hashing.\n"
        "use serde::{Deserialize, Serialize};\n\n"
        + "\n".join(extras.values())
        + "\n"
        + "\n".join(structs)
    )


def generate(root: Path | None = None) -> None:
    root = root or Path(__file__).resolve().parents[1]
    destination = root / "contracts/local-interop/v1"
    destination.mkdir(parents=True, exist_ok=True)
    definitions: dict[str, dict] = {}
    for slug, model in SCHEMAS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://schemas.poemseed.dev/local-interop/v1/{slug}.schema.json"
        _constraints(schema)
        (destination / f"{slug}.schema.json").write_text(
            json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        )
        definitions.update(schema.get("$defs", {}))
        definitions[model.__name__] = {
            key: value for key, value in schema.items() if key not in ("$schema", "$id", "$defs")
        }
    common = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://schemas.poemseed.dev/local-interop/v1/common.schema.json",
        "$defs": definitions,
    }
    (destination / "common.schema.json").write_text(
        json.dumps(common, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    lines = [
        "// Generated public Local Interop 1.0 DTOs. Validate Schema + semantics at ingress.",
        "// Advice never grants authority, navigation, model execution or project writes.",
        "",
    ]
    for name, definition in sorted(definitions.items()):
        lines.append(f"export interface {name} {{")
        for key, node in definition["properties"].items():
            required = "" if key in definition.get("required", []) else "?"
            lines.append(f"  readonly {key}{required}: {_ts_type(node)};")
        lines.extend(["}", ""])
    (destination / "protocol.ts").write_text("\n".join(lines))
    (destination / "protocol.rs").write_text(_rust_types(definitions))
    paths = sorted(
        list((root / "local_interop_protocol").glob("*.py"))
        + [
            path
            for path in destination.iterdir()
            if path.is_file() and path.name != "parity-manifest.json"
        ]
    )
    manifest = {
        "protocol_name": models.PROTOCOL_NAME,
        "protocol_version": models.PROTOCOL_VERSION,
        "hash_algorithm": "sha256",
        "files": {
            str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest() for path in paths
        },
    }
    (destination / "parity-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    generate()
