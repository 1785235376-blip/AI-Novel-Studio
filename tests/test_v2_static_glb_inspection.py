"""Real generated GLB bytes; bounded metadata only, not viewport/renderer acceptance."""
import copy
import hashlib
import json
import struct

import pytest

from app.creative.model_reference_glb import inspect_static_glb


def triangle_document():
    return {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 42}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
                            {"buffer": 0, "byteOffset": 36, "byteLength": 6}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                          {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
            "nodes": [{"mesh": 0, "translation": [100, 0, 0]}], "scenes": [{"nodes": [0]}], "scene": 0}


def triangle_bytes():
    return struct.pack("<9f3H", -1, 0, 0, 1, 0, 0, 0, 2, 0, 0, 1, 2)


def glb(document=None, binary=None, raw_json=None):
    body = raw_json if raw_json is not None else json.dumps(document or triangle_document(), separators=(",", ":")).encode()
    binary = triangle_bytes() if binary is None else binary
    body += b" " * (-len(body) % 4)
    binary += b"\0" * (-len(binary) % 4)
    chunks = struct.pack("<II", len(body), 0x4E4F534A) + body + struct.pack("<II", len(binary), 0x004E4942) + binary
    return struct.pack("<III", 0x46546C67, 2, 12 + len(chunks)) + chunks


def test_decodes_actual_positions_indices_and_labels_untransformed_metadata(monkeypatch):
    data = glb()
    def forbidden(*args, **kwargs):
        raise AssertionError("inspection must not open resources")
    monkeypatch.setattr("builtins.open", forbidden)
    result = inspect_static_glb(data)
    assert result["triangle_count_per_primitive"] == 1
    assert result["position_count_per_primitive"] == 3
    assert result["bounds"] == {"space": "MESH_LOCAL_UNTRANSFORMED", "min": [-1, 0, 0], "max": [1, 2, 0]}
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["node_count"] == 1
    for key in ("scene_transforms_applied", "preview_available", "frame_export_available", "model_called", "full_gltf_conformance_verified", "external_resources_loaded"):
        assert result[key] is False


@pytest.mark.parametrize("change", [
    lambda d: d["buffers"][0].update(uri="https://example.invalid/private.bin"),
    lambda d: d.update(images=[{"uri": "file:///private/path"}]),
    lambda d: d.update(extensionsRequired=["KHR_draco_mesh_compression"]),
    lambda d: d.update(animations=[{}]),
    lambda d: d["accessors"][0].update(sparse={}),
    lambda d: d["accessors"][0].update(count=100_001),
    lambda d: d["accessors"][0].update(byteOffset=4),
    lambda d: d["bufferViews"][0].update(byteStride=5),
    lambda d: d["meshes"][0]["primitives"][0].update(mode=5),
    lambda d: d["meshes"][0]["primitives"][0].update(mode=4.0),
    lambda d: d["nodes"][0].update(mesh=99),
])
def test_unsupported_or_invalid_descriptors_fail_without_partial_metadata(change):
    document = triangle_document(); change(document)
    with pytest.raises(ValueError, match="MODEL_REFERENCE_GLB_"):
        inspect_static_glb(glb(document))


@pytest.mark.parametrize("change", [
    lambda b: b[:-1], lambda b: b + b"\0" * 4,
    lambda b: b[:4] + struct.pack("<I", 1) + b[8:],
    lambda b: b[:16] + struct.pack("<I", 0x004E4942) + b[20:],
])
def test_exact_container_length_version_and_chunk_order(change):
    with pytest.raises(ValueError, match="MODEL_REFERENCE_GLB_"):
        inspect_static_glb(change(glb()))


def test_index_and_float_payload_not_only_json_min_max_are_checked():
    with pytest.raises(ValueError, match="INDEX_OUT_OF_RANGE"):
        inspect_static_glb(glb(binary=triangle_bytes()[:-2] + struct.pack("<H", 3)))
    with pytest.raises(ValueError, match="POSITION_INVALID"):
        inspect_static_glb(glb(binary=struct.pack("<f", float("nan")) + triangle_bytes()[4:]))
    document = triangle_document(); document["accessors"][0].update(min=[0, 0, 0], max=[0, 0, 0])
    assert inspect_static_glb(glb(document))["bounds"]["max"] == [1, 2, 0]


def test_duplicate_keys_and_non_finite_json_are_rejected():
    for text in (b'{"asset":{},"asset":{}}', b'{"asset":{"version":"2.0"},"extra":NaN}'):
        with pytest.raises(ValueError, match="MODEL_REFERENCE_GLB_"):
            inspect_static_glb(glb(raw_json=text))


def test_non_indexed_triangle_and_strided_positions():
    document = triangle_document(); document["meshes"][0]["primitives"][0].pop("indices")
    assert inspect_static_glb(glb(document))["triangle_count_per_primitive"] == 1
    document["buffers"][0]["byteLength"] = 48
    document["bufferViews"] = [{"buffer": 0, "byteOffset": 0, "byteLength": 48, "byteStride": 16}]
    document["accessors"] = [document["accessors"][0]]
    binary = b"".join(struct.pack("<4f", *point, 99) for point in [(-1, 0, 0), (1, 0, 0), (0, 2, 0)])
    assert inspect_static_glb(glb(document, binary))["bounds"]["max"] == [1, 2, 0]
