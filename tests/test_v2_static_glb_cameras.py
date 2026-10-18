"""Real synthetic GLB CPU camera data; no DCC, viewport or model acceptance."""
from copy import deepcopy
import hashlib
import json
import math

import pytest

from app.creative.model_reference_cameras import export_camera
from app.creative.model_reference_glb import inspect_static_glb
from test_v2_static_glb_inspection import glb, triangle_document


def camera_document():
    value = triangle_document()
    value["nodes"].append({"camera": 0, "translation": [0, 0, 5], "name": "Source camera node"})
    value["scenes"][0]["nodes"].append(1)
    value["cameras"] = [{"name": "Perspective camera", "type": "perspective",
                         "perspective": {"yfov": math.pi / 3, "znear": .1, "zfar": 100, "aspectRatio": 4 / 3}}]
    return value


def inspect(document):
    return inspect_static_glb(glb(document), include_cameras=True)


def exported(document):
    value = inspect(document)
    source = {"id": "fixture-model", "version": 3, "digest": value["inspection"]["sha256"]}
    camera = value["camera_inspection"]["instances"][0]
    data, proof = export_camera(value["camera_inspection"], source, scene_index=value["camera_inspection"]["scene_index"],
                               node_index=camera["node_index"], camera_index=camera["camera_index"])
    return value, source, data, proof


def test_actual_source_camera_not_diagnostic_view_and_metadata_unchanged(monkeypatch):
    document = camera_document()
    original = deepcopy(document)
    data = glb(document)
    def forbidden(*args, **kwargs):
        raise AssertionError("camera inspection must not open resources")
    monkeypatch.setattr("builtins.open", forbidden)
    result = inspect_static_glb(data, include_cameras=True)
    assert result["inspection"] == inspect_static_glb(data)
    view = result["camera_inspection"]
    assert view["coordinate_system"] == "GLTF_RH_Y_UP_METERS"
    assert view["matrix_layout"] == "COLUMN_MAJOR" and view["scene_selection"] == "DECLARED_DEFAULT"
    assert view["camera_definition_count"] == 1 and len(view["instances"]) == 1
    camera = view["instances"][0]
    assert (camera["node_index"], camera["camera_index"]) == (1, 0)
    assert camera["world_matrix"] == [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 5, 1]
    assert camera["projection"] == {"type": "perspective", **document["cameras"][0]["perspective"]}
    assert document == original and view["rigid_transforms_only"]
    assert not view["model_called"] and not view["animation_applied"]


def test_nested_rotation_translation_and_equivalent_column_major_matrix():
    document = camera_document()
    document["nodes"] = [{"mesh": 0}, {"translation": [10, 0, 0], "rotation": [0, 0, math.sqrt(.5), math.sqrt(.5)], "children": [2]},
                         {"camera": 0, "translation": [0, 3, 0]}]
    a = inspect(document)["camera_inspection"]["instances"][0]["world_matrix"]
    assert a[12:15] == pytest.approx([7, 0, 0], abs=1e-8)
    assert a[:12] == pytest.approx([0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0], abs=1e-8)
    document["nodes"][1] = {"matrix": [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 10, 0, 0, 1], "children": [2]}
    b = inspect(document)["camera_inspection"]["instances"][0]["world_matrix"]
    assert b == pytest.approx(a, abs=1e-8)


def test_instances_not_definitions_are_selected_and_unreachable_camera_is_excluded():
    document = camera_document()
    document["nodes"].extend([{"camera": 0, "translation": [1, 2, 3]}, {"camera": 0}])
    document["scenes"][0]["nodes"].append(2)
    del document["scene"]
    value = inspect(document)["camera_inspection"]
    assert value["scene_selection"] == "SOLE_SCENE"
    assert [row["node_index"] for row in value["instances"]] == [1, 2]
    assert value["camera_definition_count"] == 1
    source = {"id": "fixture-model", "version": 1, "digest": "0" * 64}
    with pytest.raises(ValueError, match="SELECTION_INVALID"):
        export_camera(value, source, scene_index=0, node_index=3, camera_index=0)
    with pytest.raises(ValueError, match="SELECTION_CHANGED"):
        export_camera(value, source, scene_index=1, node_index=1, camera_index=0)


def test_camera_only_export_is_deterministic_and_contains_only_exact_whitelisted_source():
    document = camera_document()
    document["extras"] = {"private": "MUST-NOT-EXPORT"}
    document["nodes"][1]["extras"] = {"private": "MUST-NOT-EXPORT"}
    document["cameras"][0]["extras"] = {"private": "MUST-NOT-EXPORT"}
    value, source, data, proof = exported(document)
    assert exported(document)[2:] == (data, proof)
    assert data.endswith(b"\n") and len(data) <= 65536
    assert proof["sha256"] == hashlib.sha256(data).hexdigest() and proof["byte_count"] == len(data)
    assert proof["blender_import_acceptance"] == proof["unreal_import_acceptance"] == "NOT_RUN"
    assert not proof["model_called"] and not proof["asset_created"]
    decoded = json.loads(data)
    assert set(decoded) == {"asset", "scene", "scenes", "nodes", "cameras", "extras"}
    assert decoded["scene"] == 0 and decoded["scenes"] == [{"nodes": [0]}]
    assert decoded["nodes"] == [{"camera": 0, "matrix": proof["camera"]["world_matrix"], "name": "Source camera node"}]
    assert decoded["cameras"] == [{"name": "Perspective camera", "type": "perspective",
                                    "perspective": document["cameras"][0]["perspective"]}]
    assert decoded["extras"]["studio_camera_source"] == {
        "contract": "studio-static-glb-camera-source/1", "asset_id": source["id"], "version": 3,
        "sha256": source["digest"], "scene_index": 0, "scene_selection": "DECLARED_DEFAULT", "node_index": 1, "camera_index": 0}
    assert b"MUST-NOT-EXPORT" not in data and b'"uri"' not in data


def test_missing_aspect_and_infinite_far_are_not_invented():
    document = camera_document()
    del document["cameras"][0]["perspective"]["aspectRatio"]
    del document["cameras"][0]["perspective"]["zfar"]
    _, _, data, proof = exported(document)
    assert proof["camera"]["projection"]["aspectRatio"] is None
    assert proof["camera"]["projection"]["zfar"] is None
    assert json.loads(data)["cameras"][0]["perspective"] == {"yfov": math.pi / 3, "znear": .1}


def test_orthographic_source_keeps_magnification_and_zero_near():
    document = camera_document()
    projection = {"xmag": 2, "ymag": 1.5, "znear": 0, "zfar": 100}
    document["cameras"] = [{"type": "orthographic", "orthographic": projection}]
    _, _, data, proof = exported(document)
    assert proof["camera"]["projection"] == {"type": "orthographic", **projection}
    assert json.loads(data)["cameras"] == [{"type": "orthographic", "orthographic": projection, "name": ""}]


@pytest.mark.parametrize("field,value", [("xmag", 0), ("ymag", -1), ("xmag", True),
    ("znear", -1), ("zfar", 0), ("zfar", None), ("zfar", 1e10)])
def test_invalid_orthographic_projection_is_not_approximated(field, value):
    document = camera_document()
    projection = {"xmag": 2, "ymag": 1.5, "znear": 0, "zfar": 100, field: value}
    document["cameras"] = [{"type": "orthographic", "orthographic": projection}]
    with pytest.raises(ValueError, match="^MODEL_REFERENCE_GLB_CAMERA_INVALID$"):
        inspect(document)


def test_no_authored_cameras_is_empty_and_unrelated_mesh_scale_is_not_a_camera():
    document = triangle_document()
    document["nodes"][0]["scale"] = [2, 3, 4]
    assert inspect(document)["camera_inspection"]["instances"] == []
    assert inspect(document)["camera_inspection"]["camera_definition_count"] == 0


@pytest.mark.parametrize("change", [
    lambda d: d["nodes"][1].update(scale=[2, 2, 2]),
    lambda d: d["nodes"][1].update(scale=[1, 2, 1]),
    lambda d: d["nodes"][1].update(scale=[-1, -1, 1]),
    lambda d: d["nodes"][1].update(scale=[-1, 1, 1]),
    lambda d: d["nodes"][1].update(scale=[0, 1, 1]),
    lambda d: d["nodes"].__setitem__(1, {"camera": 0, "matrix": [1, 0, 0, 0, .5, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}),
    lambda d: d["nodes"].__setitem__(1, {"camera": 0, "matrix": [-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}),
])
def test_nonrigid_cameras_rejected_without_changing_old_geometry_admission(change):
    document = camera_document(); change(document)
    assert inspect_static_glb(glb(document))["mesh_count"] == 1
    with pytest.raises(ValueError, match="CAMERA_NONRIGID_UNSUPPORTED"):
        inspect(document)


def test_nonrigid_ancestry_cannot_be_cancelled_by_child_scale():
    document = camera_document()
    document["nodes"][1] = {"scale": [2, 2, 2], "children": [2]}
    document["nodes"].append({"camera": 0, "scale": [.5, .5, .5]})
    with pytest.raises(ValueError, match="CAMERA_NONRIGID_UNSUPPORTED"):
        inspect(document)


@pytest.mark.parametrize("field,value", [("yfov", 0), ("yfov", math.pi), ("yfov", True), ("yfov", "1"),
    ("znear", 0), ("znear", -1), ("znear", 10 ** 500), ("zfar", .01), ("zfar", None),
    ("aspectRatio", None), ("aspectRatio", 0), ("aspectRatio", 1e10)])
def test_invalid_perspective_numbers_fail_privately(field, value):
    document = camera_document(); document["cameras"][0]["perspective"][field] = value
    with pytest.raises(ValueError, match="^MODEL_REFERENCE_GLB_CAMERA_INVALID$"):
        inspect(document)


@pytest.mark.parametrize("change", [
    lambda d: d["nodes"][1].update(camera=True),
    lambda d: d["nodes"][1].update(camera=-1),
    lambda d: d["nodes"][1].update(camera=1),
    lambda d: d["cameras"][0].update(type="unknown"),
    lambda d: d["cameras"][0].update(orthographic={}),
    lambda d: d["cameras"][0].update(extensions={"unsupported": {}}),
    lambda d: d["cameras"][0]["perspective"].update(extensions={"unsupported": {}}),
    lambda d: d.update(extensions={"unsupported": {}}),
    lambda d: d["cameras"][0].update(name="x" * 241),
    lambda d: d["nodes"][1].update(name="private\ncontrol"),
    lambda d: d.update(cameras=d["cameras"] * 65),
    lambda d: d["nodes"][1].update(children=[1]),
    lambda d: d.update(scene=True),
])
def test_invalid_camera_structure_and_tree_are_bounded(change):
    document = camera_document(); change(document)
    with pytest.raises(ValueError, match="^MODEL_REFERENCE_GLB_"):
        inspect(document)


def test_ambiguous_scene_and_instance_limit_are_explicit():
    document = camera_document()
    document["scenes"].append({"nodes": [1]}); del document["scene"]
    with pytest.raises(ValueError, match="SCENE_SELECTION_REQUIRED"):
        inspect(document)
    document = camera_document()
    document["nodes"] = [{"camera": 0} for _ in range(65)]
    document["scenes"][0]["nodes"] = list(range(65))
    with pytest.raises(ValueError, match="CAMERA_LIMIT"):
        inspect(document)


def test_camera_inspection_does_not_expand_preview_mesh_budget():
    document = camera_document(); count = 4098
    document["buffers"][0]["byteLength"] = count * 12
    document["bufferViews"] = [{"buffer": 0, "byteLength": count * 12}]
    document["accessors"] = [{"bufferView": 0, "componentType": 5126, "count": count, "type": "VEC3"}]
    document["meshes"][0]["primitives"][0].pop("indices")
    data = glb(document, b"\0" * (count * 12))
    assert len(inspect_static_glb(data, include_cameras=True)["camera_inspection"]["instances"]) == 1
    with pytest.raises(ValueError, match="PREVIEW_LIMIT"):
        inspect_static_glb(data, include_geometry=True)


@pytest.mark.parametrize("options", [{"include_cameras": 1}, {"include_cameras": True, "include_geometry": True},
    {"include_cameras": True, "include_materials": True}, {"include_cameras": True, "include_scene": True}])
def test_camera_inspection_option_is_separate_and_closed(options):
    with pytest.raises(ValueError, match="PREVIEW_OPTION_INVALID"):
        inspect_static_glb(glb(camera_document()), **options)
