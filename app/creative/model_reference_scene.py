"""Bounded static glTF scene transforms, not material/animation rendering.

Khronos glTF 2.0 uses column-major matrices and local T * R * S, with
parent-world * local composition. Strict trees are required. Only the declared
default scene (or a sole scene) is selected; ambiguous scenes fail explicitly.
"""
from __future__ import annotations
import math


def fail(code="MODEL_REFERENCE_GLB_SCENE_INVALID"):
    raise ValueError(code)


def vector(value, length):
    if (not isinstance(value, list) or len(value) != length
            or any(type(n) not in (int, float) or abs(n) > 1e9 or not math.isfinite(n) for n in value)):
        fail("MODEL_REFERENCE_GLB_TRANSFORM_INVALID")
    return [float(n) for n in value]


def multiply(a, b):
    result = [sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
              for col in range(4) for row in range(4)]
    if any(not math.isfinite(n) or abs(n) > 1e9 for n in result):
        fail("MODEL_REFERENCE_GLB_TRANSFORM_LIMIT")
    return result


IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]


def local_matrix(node):
    if "matrix" in node:
        if any(key in node for key in ("translation", "rotation", "scale")):
            fail("MODEL_REFERENCE_GLB_TRANSFORM_INVALID")
        matrix = vector(node["matrix"], 16)
        if [matrix[index] for index in (3, 7, 11, 15)] != [0, 0, 0, 1]:
            fail("MODEL_REFERENCE_GLB_TRANSFORM_INVALID")
        return matrix
    t = vector(node.get("translation", [0, 0, 0]), 3)
    scale = vector(node.get("scale", [1, 1, 1]), 3)
    rotation = vector(node.get("rotation", [0, 0, 0, 1]), 4)
    length = math.hypot(*rotation)
    if abs(length - 1) > 1e-5:
        fail("MODEL_REFERENCE_GLB_ROTATION_INVALID")
    x, y, z, w = [n / length for n in rotation]
    # Columns of the quaternion rotation, then column scaling (R * S).
    result = [1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w), 0.,
              2*(x*y-z*w), 1-2*(x*x+z*z), 2*(y*z+x*w), 0.,
              2*(x*z+y*w), 2*(y*z-x*w), 1-2*(x*x+y*y), 0.,
              *t, 1.]
    for col in range(3):
        for row in range(3): result[col*4+row] *= scale[col]
    return result


def scene_tree(document):
    """Validate the existing bounded tree without expanding mesh geometry."""
    nodes, scenes = document.get("nodes"), document.get("scenes")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 256 or not isinstance(scenes, list) or not 1 <= len(scenes) <= 64:
        fail("MODEL_REFERENCE_GLB_SCENE_REQUIRED")
    selected = document.get("scene", 0 if len(scenes) == 1 else None)
    if selected is None: fail("MODEL_REFERENCE_GLB_SCENE_SELECTION_REQUIRED")
    if type(selected) is not int or not 0 <= selected < len(scenes): fail()
    def index(value):
        if type(value) is not int or not 0 <= value < len(nodes): fail()
        return value
    children, parents, transforms = [], [0] * len(nodes), []
    for node in nodes:
        if not isinstance(node, dict): fail()
        if node.get("extensions"): fail("MODEL_REFERENCE_GLB_ANIMATION_OR_EXTENSION_UNSUPPORTED")
        values = node.get("children", [])
        if not isinstance(values, list) or len(values) > len(nodes): fail()
        values = [index(value) for value in values]
        if len(set(values)) != len(values): fail()
        for child in values:
            parents[child] += 1
            if parents[child] > 1: fail("MODEL_REFERENCE_GLB_SCENE_NOT_TREE")
        children.append(values); transforms.append(local_matrix(node))
    # Validate cycles even in unselected nodes. No recursive traversal.
    counts = parents[:]; queue = [i for i, count in enumerate(counts) if count == 0]; visited = 0
    while queue:
        current = queue.pop(); visited += 1
        for child in children[current]:
            counts[child] -= 1
            if counts[child] == 0: queue.append(child)
    if visited != len(nodes): fail("MODEL_REFERENCE_GLB_SCENE_NOT_TREE")
    scene = scenes[selected]
    if (not isinstance(scene, dict) or not isinstance(scene.get("nodes"), list)
            or len(scene["nodes"]) > len(nodes)): fail()
    if scene.get("extensions"): fail("MODEL_REFERENCE_GLB_ANIMATION_OR_EXTENSION_UNSUPPORTED")
    roots = [index(value) for value in scene["nodes"]]
    if not roots or len(set(roots)) != len(roots) or any(parents[root] for root in roots): fail()
    return nodes, children, transforms, roots, selected


def scene_geometry(document, meshes):
    nodes, children, transforms, roots, selected = scene_tree(document)
    stack = [(root, IDENTITY) for root in reversed(roots)]
    primitives, positions, triangles, instances, traversed = [], 0, 0, 0, 0
    minimum, maximum = [math.inf] * 3, [-math.inf] * 3
    while stack:
        node_id, parent = stack.pop(); traversed += 1
        world = multiply(parent, transforms[node_id]); node = nodes[node_id]
        for child in reversed(children[node_id]): stack.append((child, world))
        if "mesh" not in node: continue
        mesh_id = node["mesh"]
        if type(mesh_id) is not int or not 0 <= mesh_id < len(meshes): fail()
        instances += 1
        for primitive_id, primitive in enumerate(meshes[mesh_id]):
            positions += len(primitive["positions"]); triangles += len(primitive["triangles"])
            if positions > 4096 or triangles > 2048 or len(primitives) >= 128:
                fail("MODEL_REFERENCE_GLB_SCENE_PREVIEW_LIMIT")
            transformed = []
            for point in primitive["positions"]:
                value = [sum(world[k*4+axis]*point[k] for k in range(3))+world[12+axis] for axis in range(3)]
                if any(abs(n) > 1e9 or not math.isfinite(n) for n in value):
                    fail("MODEL_REFERENCE_GLB_TRANSFORM_LIMIT")
                transformed.append(value)
                for axis, n in enumerate(value):
                    minimum[axis] = min(minimum[axis], n); maximum[axis] = max(maximum[axis], n)
            primitives.append({"node_index": node_id, "mesh_index": mesh_id, "primitive_index": primitive_id,
                "positions": transformed, "triangles": [list(t) for t in primitive["triangles"]]})
    if not primitives: fail("MODEL_REFERENCE_GLB_SCENE_EMPTY")
    return {"contract": "studio-static-glb-scene-preview/1", "space": "SCENE_WORLD_STATIC",
        "scene_index": selected, "selection": "DECLARED_DEFAULT" if "scene" in document else "SOLE_SCENE",
        "traversed_nodes": traversed, "mesh_instances": instances, "position_count": positions,
        "triangle_count": triangles, "primitives": primitives,
        "bounds": {"min": minimum, "max": maximum}, "scene_transforms_applied": True,
        "materials_rendered": False, "animation_applied": False, "decimated": False, "model_called": False}
