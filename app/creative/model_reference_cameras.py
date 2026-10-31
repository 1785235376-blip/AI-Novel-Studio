"""Source-authored rigid static cameras and canonical camera-only glTF exchange.

No DCC import, projection approximation, rendering, external resources or store.
Convention source: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#cameras
"""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy

from .model_reference_scene import IDENTITY, multiply, scene_tree

CONTRACT = "studio-static-glb-cameras/1"
EXPORT_CONTRACT = "studio-static-glb-camera-export/1"
PROFILE = "GLTF_2_CAMERA_ONLY"
COORDINATES = "GLTF_RH_Y_UP_METERS"
MAX_CAMERAS = 64
MAX_EXPORT_BYTES = 65536
RIGID_TOLERANCE = 1e-5


def fail(code="MODEL_REFERENCE_GLB_CAMERA_INVALID"):
    raise ValueError(code)


def _number(value, *, zero=False):
    if (type(value) not in (int, float)
            or not (0 <= value <= 1e9 if zero else 0 < value <= 1e9) or not math.isfinite(value)):
        fail()
    return float(value)


def _name(value):
    if (not isinstance(value, str) or len(value) > 240
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        fail("MODEL_REFERENCE_GLB_CAMERA_NAME_INVALID")
    return value


def _projection(camera):
    if not isinstance(camera, dict):
        fail()
    if camera.get("extensions"):
        fail("MODEL_REFERENCE_GLB_CAMERA_EXTENSION_UNSUPPORTED")
    kind = camera.get("type")
    other = "orthographic" if kind == "perspective" else "perspective"
    if kind not in ("perspective", "orthographic") or other in camera:
        fail()
    value = camera.get(kind)
    if not isinstance(value, dict):
        fail()
    if value.get("extensions"):
        fail("MODEL_REFERENCE_GLB_CAMERA_EXTENSION_UNSUPPORTED")
    near = _number(value.get("znear"), zero=kind == "orthographic")
    if kind == "perspective":
        yfov = _number(value.get("yfov"))
        if yfov >= math.pi:
            fail()
        # Missing values remain missing in the exported glTF. Null is only the
        # explicit absence marker in our closed inspection receipt.
        far = _number(value["zfar"]) if "zfar" in value else None
        aspect = _number(value["aspectRatio"]) if "aspectRatio" in value else None
        result = {"type": kind, "yfov": yfov, "znear": near, "aspectRatio": aspect, "zfar": far}
    else:
        far = _number(value.get("zfar"))
        result = {"type": kind, "xmag": _number(value.get("xmag")),
                  "ymag": _number(value.get("ymag")), "znear": near, "zfar": far}
    if far is not None and far <= near:
        fail()
    return result


def _rigid(matrix):
    columns = [matrix[i:i + 3] for i in (0, 4, 8)]
    for i in range(3):
        for j in range(3):
            dot = sum(a * b for a, b in zip(columns[i], columns[j]))
            if abs(dot - (1 if i == j else 0)) > RIGID_TOLERANCE:
                return False
    a, b, c = columns
    determinant = (a[0] * (b[1] * c[2] - b[2] * c[1])
                   - b[0] * (a[1] * c[2] - a[2] * c[1])
                   + c[0] * (a[1] * b[2] - a[2] * b[1]))
    return abs(determinant - 1) <= RIGID_TOLERANCE


def inspect_cameras(document):
    if document.get("extensions"):
        fail("MODEL_REFERENCE_GLB_CAMERA_EXTENSION_UNSUPPORTED")
    cameras = document.get("cameras", [])
    if not isinstance(cameras, list) or len(cameras) > MAX_CAMERAS:
        fail("MODEL_REFERENCE_GLB_CAMERA_LIMIT")
    projections = [_projection(camera) for camera in cameras]
    names = [_name(camera.get("name", "")) for camera in cameras]
    nodes, children, transforms, roots, selected = scene_tree(document)
    for node in nodes:
        if "camera" in node and (type(node["camera"]) is not int or not 0 <= node["camera"] < len(cameras)):
            fail("MODEL_REFERENCE_GLB_CAMERA_INDEX_INVALID")
    stack = [(root, IDENTITY, True) for root in reversed(roots)]
    instances = []
    while stack:
        node_index, parent, parent_rigid = stack.pop()
        node, local = nodes[node_index], transforms[node_index]
        world = multiply(parent, local)
        # Reject authored scale even if a descendant cancels it. Matrix-only
        # inputs must independently be proper rigid transforms at every level.
        rigid = parent_rigid and node.get("scale", [1, 1, 1]) == [1, 1, 1] and _rigid(local)
        for child in reversed(children[node_index]):
            stack.append((child, world, rigid))
        if "camera" not in node:
            continue
        if not rigid or not _rigid(world):
            fail("MODEL_REFERENCE_GLB_CAMERA_NONRIGID_UNSUPPORTED")
        if len(instances) >= MAX_CAMERAS:
            fail("MODEL_REFERENCE_GLB_CAMERA_LIMIT")
        camera_index = node["camera"]
        instances.append({"node_index": node_index, "camera_index": camera_index,
                          "node_name": _name(node.get("name", "")), "camera_name": names[camera_index],
                          "world_matrix": world, "projection": deepcopy(projections[camera_index])})
    return {"contract": CONTRACT, "space": "SCENE_WORLD_STATIC", "coordinate_system": COORDINATES,
            "matrix_layout": "COLUMN_MAJOR", "scene_index": selected,
            "scene_selection": "DECLARED_DEFAULT" if "scene" in document else "SOLE_SCENE",
            "camera_definition_count": len(cameras), "instances": instances,
            "rigid_transforms_only": True, "animation_applied": False, "model_called": False}


def export_camera(inspection, source, *, scene_index, node_index, camera_index):
    if inspection["scene_index"] != scene_index:
        fail("MODEL_REFERENCE_GLB_CAMERA_SELECTION_CHANGED")
    camera = next((row for row in inspection["instances"]
                   if (row["node_index"], row["camera_index"]) == (node_index, camera_index)), None)
    if camera is None:
        fail("MODEL_REFERENCE_GLB_CAMERA_SELECTION_INVALID")
    projection = camera["projection"]
    kind = projection["type"]
    camera_data = {"type": kind, "name": camera["camera_name"],
                   kind: {key: value for key, value in projection.items() if key != "type" and value is not None}}
    origin = {"contract": "studio-static-glb-camera-source/1", "asset_id": source["id"],
              "version": source["version"], "sha256": source["digest"], "scene_index": scene_index,
              "scene_selection": inspection["scene_selection"], "node_index": node_index, "camera_index": camera_index}
    document = {"asset": {"version": "2.0", "generator": "Studio static camera exchange/1"},
                "scene": 0, "scenes": [{"nodes": [0]}],
                "nodes": [{"camera": 0, "matrix": camera["world_matrix"], "name": camera["node_name"]}],
                "cameras": [camera_data], "extras": {"studio_camera_source": origin}}
    data = (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    if len(data) > MAX_EXPORT_BYTES:
        fail("MODEL_REFERENCE_GLB_CAMERA_EXPORT_LIMIT")
    proof = {"contract": EXPORT_CONTRACT, "profile": PROFILE, "scene_index": scene_index,
             "scene_selection": inspection["scene_selection"], "camera": deepcopy(camera),
             "coordinate_system": COORDINATES, "matrix_layout": "COLUMN_MAJOR", "byte_count": len(data),
             "sha256": hashlib.sha256(data).hexdigest(), "animation_applied": False, "model_called": False,
             "asset_created": False, "blender_import_acceptance": "NOT_RUN", "unreal_import_acceptance": "NOT_RUN"}
    return data, proof
