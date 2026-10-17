"""Bounded static GLB geometry inspection, not a complete glTF validator/renderer.

Reference: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
Only embedded, uncompressed triangle POSITION/index data is decoded. No URI,
filesystem, GPU, material, animation, model provider or executable processing.
Node transforms are intentionally NOT applied; bounds are mesh-local metadata.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct

MAX_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024
MAX_VERTICES = 100_000
MAX_INDICES = 300_000
CONTRACT = "studio-static-glb-inspection/1"


def _fail(code="MODEL_REFERENCE_GLB_UNSUPPORTED"):
    raise ValueError(code)


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        _fail("MODEL_REFERENCE_GLB_RANGE_INVALID")
    return value


def _object(value):
    if not isinstance(value, dict):
        _fail("MODEL_REFERENCE_GLB_STRUCTURE_INVALID")
    return value


def _array(value, maximum, *, required=False):
    if not isinstance(value, list) or len(value) > maximum or required and not value:
        _fail("MODEL_REFERENCE_GLB_STRUCTURE_INVALID")
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail("MODEL_REFERENCE_GLB_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _inspect_json(value):
    pending = [(value, 0)]
    visited = 0
    while pending:
        item, depth = pending.pop()
        visited += 1
        if depth > 48 or visited > 40_000:
            _fail("MODEL_REFERENCE_GLB_JSON_LIMIT")
        if isinstance(item, dict):
            if "uri" in item:
                _fail("MODEL_REFERENCE_GLB_URI_UNSUPPORTED")
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, float) and not math.isfinite(item):
            _fail("MODEL_REFERENCE_GLB_NUMBER_INVALID")


def inspect_static_glb(data: bytes):
    if not isinstance(data, bytes) or not 28 <= len(data) <= MAX_BYTES:
        _fail("MODEL_REFERENCE_GLB_SIZE_INVALID")
    magic, version, length = struct.unpack_from("<III", data)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        _fail("MODEL_REFERENCE_GLB_HEADER_INVALID")
    chunks, offset = [], 12
    while offset < len(data):
        if len(chunks) >= 2 or offset + 8 > len(data):
            _fail("MODEL_REFERENCE_GLB_CHUNKS_INVALID")
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if not size or size % 4 or offset + size > len(data):
            _fail("MODEL_REFERENCE_GLB_CHUNKS_INVALID")
        chunks.append((kind, memoryview(data)[offset:offset + size]))
        offset += size
    if len(chunks) != 2 or [item[0] for item in chunks] != [0x4E4F534A, 0x004E4942]:
        _fail("MODEL_REFERENCE_GLB_EMBEDDED_BUFFER_REQUIRED")
    if len(chunks[0][1]) > MAX_JSON_BYTES:
        _fail("MODEL_REFERENCE_GLB_JSON_LIMIT")
    try:
        document = json.loads(bytes(chunks[0][1]).decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=lambda value: _fail("MODEL_REFERENCE_GLB_NUMBER_INVALID"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail("MODEL_REFERENCE_GLB_JSON_INVALID")
    except ValueError as error:
        if str(error).startswith("MODEL_REFERENCE_GLB_"):
            raise
        _fail("MODEL_REFERENCE_GLB_JSON_INVALID")
    _object(document)
    _inspect_json(document)
    asset = _object(document.get("asset"))
    if asset.get("version") != "2.0" or asset.get("minVersion", "2.0") != "2.0":
        _fail("MODEL_REFERENCE_GLB_VERSION_UNSUPPORTED")
    if any(document.get(name) for name in ("extensionsUsed", "extensionsRequired", "animations", "skins")):
        _fail("MODEL_REFERENCE_GLB_ANIMATION_OR_EXTENSION_UNSUPPORTED")
    buffers = _array(document.get("buffers"), 1, required=True)
    declared = _integer(_object(buffers[0]).get("byteLength"), 1, MAX_BYTES)
    binary = chunks[1][1]
    if not declared <= len(binary) <= declared + 3 or any(binary[declared:]):
        _fail("MODEL_REFERENCE_GLB_BUFFER_LENGTH_INVALID")
    views = _array(document.get("bufferViews"), 1024, required=True)
    for raw in views:
        view = _object(raw)
        if view.get("buffer") != 0 or type(view.get("buffer")) is not int:
            _fail("MODEL_REFERENCE_GLB_BUFFER_INVALID")
        start = _integer(view.get("byteOffset", 0), 0, declared)
        size = _integer(view.get("byteLength"), 1, declared)
        if start + size > declared:
            _fail("MODEL_REFERENCE_GLB_BUFFER_RANGE_INVALID")
        if "byteStride" in view:
            stride = _integer(view["byteStride"], 4, 252)
            if stride % 4:
                _fail("MODEL_REFERENCE_GLB_STRIDE_INVALID")
        if "target" in view and (type(view["target"]) is not int or view["target"] not in (34962, 34963)):
            _fail("MODEL_REFERENCE_GLB_TARGET_INVALID")
    accessors = _array(document.get("accessors"), 1024, required=True)
    sizes = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
    parsed = []
    for raw in accessors:
        item = _object(raw)
        if "sparse" in item or item.get("type") not in widths or type(item.get("componentType")) is not int or item["componentType"] not in sizes:
            _fail("MODEL_REFERENCE_GLB_ACCESSOR_UNSUPPORTED")
        if "normalized" in item and type(item["normalized"]) is not bool:
            _fail("MODEL_REFERENCE_GLB_ACCESSOR_UNSUPPORTED")
        view = views[_integer(item.get("bufferView"), 0, len(views) - 1)]
        code, size = sizes[item["componentType"]]
        count = _integer(item.get("count"), 1, MAX_INDICES)
        width = widths[item["type"]]
        inner = _integer(item.get("byteOffset", 0), 0, view["byteLength"])
        stride = view.get("byteStride", size * width)
        start = view.get("byteOffset", 0) + inner
        if start % size or inner % size or stride < size * width or inner + (count - 1) * stride + size * width > view["byteLength"]:
            _fail("MODEL_REFERENCE_GLB_ACCESSOR_RANGE_INVALID")
        parsed.append((item, start, stride, count, code, width))
    meshes = _array(document.get("meshes"), 64, required=True)
    vertices = indices = primitives = triangles = 0
    minimum, maximum = [math.inf] * 3, [-math.inf] * 3
    for raw in meshes:
        mesh = _object(raw)
        if mesh.get("weights"):
            _fail("MODEL_REFERENCE_GLB_MORPH_UNSUPPORTED")
        for raw_primitive in _array(mesh.get("primitives"), 128, required=True):
            primitive = _object(raw_primitive)
            primitives += 1
            if (primitives > 128 or type(primitive.get("mode", 4)) is not int or primitive.get("mode", 4) != 4
                    or primitive.get("targets") or primitive.get("extensions")):
                _fail("MODEL_REFERENCE_GLB_PRIMITIVE_UNSUPPORTED")
            attributes = _object(primitive.get("attributes"))
            for index in attributes.values():
                _integer(index, 0, len(parsed) - 1)
            position = parsed[_integer(attributes.get("POSITION"), 0, len(parsed) - 1)]
            item, start, stride, count, code, width = position
            if item["type"] != "VEC3" or item["componentType"] != 5126 or item.get("normalized", False):
                _fail("MODEL_REFERENCE_GLB_POSITION_UNSUPPORTED")
            vertices += count
            if vertices > MAX_VERTICES:
                _fail("MODEL_REFERENCE_GLB_GEOMETRY_LIMIT")
            for index in range(count):
                point = struct.unpack_from("<fff", binary, start + index * stride)
                if any(not math.isfinite(number) or abs(number) > 1e9 for number in point):
                    _fail("MODEL_REFERENCE_GLB_POSITION_INVALID")
                for axis, number in enumerate(point):
                    minimum[axis] = min(minimum[axis], number)
                    maximum[axis] = max(maximum[axis], number)
            element_count = count
            if "indices" in primitive:
                item, start, stride, element_count, code, width = parsed[_integer(primitive["indices"], 0, len(parsed) - 1)]
                if item["type"] != "SCALAR" or item["componentType"] not in (5121, 5123, 5125) or item.get("normalized", False):
                    _fail("MODEL_REFERENCE_GLB_INDICES_UNSUPPORTED")
                for index in range(element_count):
                    if struct.unpack_from("<" + code, binary, start + index * stride)[0] >= count:
                        _fail("MODEL_REFERENCE_GLB_INDEX_OUT_OF_RANGE")
            indices += element_count
            if indices > MAX_INDICES or element_count % 3:
                _fail("MODEL_REFERENCE_GLB_TRIANGLES_INVALID")
            triangles += element_count // 3
    nodes = _array(document.get("nodes", []), 256)
    for node in nodes:
        node = _object(node)
        if "skin" in node or node.get("weights"):
            _fail("MODEL_REFERENCE_GLB_ANIMATION_OR_EXTENSION_UNSUPPORTED")
        if "mesh" in node:
            _integer(node["mesh"], 0, len(meshes) - 1)
    return {"contract": CONTRACT, "format": "GLB_2_STATIC_TRIANGLE_GEOMETRY", "byte_count": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "mesh_count": len(meshes), "node_count": len(nodes),
            "primitive_count": primitives, "position_count_per_primitive": vertices, "triangle_count_per_primitive": triangles,
            "bounds": {"space": "MESH_LOCAL_UNTRANSFORMED", "min": minimum, "max": maximum},
            "scene_transforms_applied": False, "materials_rendered": False, "textures_decoded": False,
            "full_gltf_conformance_verified": False, "external_resources_loaded": False,
            "model_called": False, "preview_available": False, "frame_export_available": False}
