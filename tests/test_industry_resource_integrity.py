"""Pure-builder regression coverage; no filesystem-backed resource loader."""
import hashlib
import io
import json
import stat
from pathlib import PurePosixPath
from zipfile import ZipFile

import pytest

from app import industry_export_formats as exports


CONTENT = b"captured resource"
DIGEST = hashlib.sha256(CONTENT).hexdigest()


class Loader:
    def __init__(self, *, metadata=None, content=CONTENT):
        self.metadata = metadata or {"id": "asset-1", "novel_id": "novel-1", "sha256": DIGEST}
        self.value = content
        self.calls = []

    def get(self, asset_id):
        self.calls.append(("get", asset_id))
        if isinstance(self.metadata, Exception):
            raise self.metadata
        return self.metadata

    def content(self, asset_id):
        self.calls.append(("content", asset_id))
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def manifest(**updates):
    return {"available": [{"id": "asset-1", "filename": "image.png", "media_type": "image/png", "sha256": DIGEST, **updates}]}


def resolve(loader, *, policy="allow_missing", snapshot=None, novel_id="novel-1"):
    return exports.resolve_resources(snapshot or manifest(), references=["asset-1"], loader=loader, novel_id=novel_id, resource_policy=policy)


@pytest.mark.parametrize("policy", ["allow_missing", "require_all"])
@pytest.mark.parametrize("fault", ["wrong_owner", "blank_owner", "missing_owner", "wrong_id", "missing_id", "substituted", "missing", "no_digest", "malformed_digest", "duplicate"])
def test_untrusted_or_changed_resources_fail_closed(fault, policy):
    loader = Loader()
    snapshot = manifest()
    if fault == "wrong_owner":
        loader.metadata["novel_id"] = "someone-else"
    elif fault == "blank_owner":
        loader.metadata["novel_id"] = ""
    elif fault == "missing_owner":
        del loader.metadata["novel_id"]
    elif fault == "wrong_id":
        loader.metadata["id"] = "asset-2"
    elif fault == "missing_id":
        del loader.metadata["id"]
    elif fault == "substituted":
        loader.value = b"replacement"
        loader.metadata["sha256"] = hashlib.sha256(loader.value).hexdigest()
    elif fault == "missing":
        loader.value = FileNotFoundError("gone")
    elif fault == "no_digest":
        snapshot["available"][0].pop("sha256")
    elif fault == "malformed_digest":
        snapshot["available"][0]["sha256"] = "garbage"
    elif fault == "duplicate":
        snapshot["available"].append(dict(snapshot["available"][0]))
    if policy == "require_all":
        with pytest.raises(exports.IndustryExportResourceError):
            resolve(loader, policy=policy, snapshot=snapshot)
    else:
        result = resolve(loader, policy=policy, snapshot=snapshot)
        assert result["binaries"] == {}
        assert result["available"] == []
        assert result["missing_count"] == 1
        assert result["missing"][0]["packaged"] is False


def test_snapshot_digest_wins_even_when_current_metadata_digest_is_stale():
    loader = Loader()
    loader.metadata["sha256"] = "0" * 64
    assert resolve(loader)["binaries"] == {"asset-1": CONTENT}


@pytest.mark.parametrize("asset_id", ["../secret", "/etc/passwd", r"..\secret", "..", "x\x00y", "asset:stream"])
def test_unsafe_ids_never_reach_loader(asset_id):
    loader = Loader()
    result = exports.resolve_resources(manifest(id=asset_id), references=[asset_id], loader=loader, novel_id="novel-1")
    assert not loader.calls
    assert result["missing_count"] == 1
    assert result["binaries"] == {}


@pytest.mark.parametrize("novel_id", ["", None, "other"])
def test_explicit_project_identity_required(novel_id):
    assert resolve(Loader(), novel_id=novel_id)["missing_count"] == 1


@pytest.mark.parametrize("builder", [exports.storyboard_to_package, exports.screenplay_to_package, exports.shot_list_to_package])
def test_every_packaged_resource_has_safe_unique_member_and_matching_digest(builder):
    class MultiLoader:
        def get(self, asset_id):
            return {"id": asset_id, "novel_id": "novel-1", "filename": "../../same.png"}
        def content(self, asset_id):
            return CONTENT + asset_id.encode()

    rows = [{"id": asset_id, "filename": "../../same.png", "sha256": hashlib.sha256(CONTENT + asset_id.encode()).hexdigest()} for asset_id in ["asset-1", "asset-2"]]
    screenplay = {"scenes": [{"id": "scene-1", "action": "A scene", "asset_ids": ["asset-1", "asset-2"]}]}
    binary = builder(screenplay, novel_id="novel-1", resource_manifest={"available": rows}, resource_loader=MultiLoader(), resource_policy="require_all")
    with ZipFile(io.BytesIO(binary)) as archive:
        package = json.loads(archive.read("manifest.json"))
        assert sorted(archive.namelist()) == package["files"]
        assert len(archive.namelist()) == len(set(archive.namelist()))
        packaged = package["resources"]["available"]
        assert len(packaged) == 2
        for row in packaged:
            assert row["packaged"] is True
            path = row["package_path"]
            assert path.startswith("resources/")
            assert ".." not in PurePosixPath(path).parts
            assert not PurePosixPath(path).is_absolute()
            assert "\\" not in path
            assert not stat.S_ISLNK(archive.getinfo(path).external_attr >> 16)
            data = archive.read(path)
            assert hashlib.sha256(data).hexdigest() == row["sha256"]
            assert len(data) == row["size"]
        assert package["resources"]["missing_count"] == 0


@pytest.mark.parametrize("policy", ["allow_missing", "require_all"])
def test_resource_byte_limit_is_enforced(monkeypatch, policy):
    monkeypatch.setattr(exports, "MAX_RESOURCE_BYTES", len(CONTENT) - 1)
    if policy == "require_all":
        with pytest.raises(exports.IndustryExportResourceError):
            resolve(Loader(), policy=policy)
    else:
        assert resolve(Loader())["binaries"] == {}


def test_cumulative_limit_counts_uncompressed_bytes(monkeypatch):
    monkeypatch.setattr(exports, "MAX_PACKAGE_RESOURCE_BYTES", len(CONTENT))
    class MultiLoader:
        def get(self, asset_id):
            return {"id": asset_id, "novel_id": "novel-1"}
        def content(self, asset_id):
            return CONTENT
    snapshot = {"available": [manifest(id=asset_id)["available"][0] for asset_id in ["asset-1", "asset-2"]]}
    result = resolve(MultiLoader(), snapshot=snapshot)
    assert len(result["binaries"]) == 1
    assert result["missing_count"] == 1
    with pytest.raises(exports.IndustryExportResourceError):
        resolve(MultiLoader(), snapshot=snapshot, policy="require_all")


def test_path_like_loader_result_is_not_opened(tmp_path):
    secret = tmp_path / "secret"
    secret.write_bytes(CONTENT)
    symlink = tmp_path / "link"
    symlink.symlink_to(secret)
    assert resolve(Loader(content=symlink))["binaries"] == {}


@pytest.mark.parametrize("policy", ["allow_missing", "require_all"])
def test_no_loader_is_truthfully_missing(policy):
    if policy == "require_all":
        with pytest.raises(exports.IndustryExportResourceError):
            resolve(None, policy=policy)
    else:
        result = resolve(None)
        assert result["missing_count"] == 1
        assert not result["available"]
        assert not result["binaries"]


@pytest.mark.parametrize("builder", [exports.storyboard_to_package, exports.screenplay_to_package, exports.shot_list_to_package])
@pytest.mark.parametrize("policy", ["allow_missing", "require_all"])
def test_package_missing_resource_policy_matches_actual_members(builder, policy):
    screenplay = {"scenes": [{"id": "scene-1", "action": "Scene", "asset_ids": ["asset-1"]}]}
    kwargs = dict(novel_id="novel-1", resource_manifest=manifest(), resource_loader=Loader(content=FileNotFoundError("gone")), resource_policy=policy)
    if policy == "require_all":
        with pytest.raises(exports.IndustryExportResourceError):
            builder(screenplay, **kwargs)
    else:
        with ZipFile(io.BytesIO(builder(screenplay, **kwargs))) as archive:
            resources = json.loads(archive.read("manifest.json"))["resources"]
            assert not resources["available"]
            assert resources["missing_count"] == 1
            assert resources["missing"][0]["packaged"] is False
            assert all(not path.startswith("resources/") for path in archive.namelist())


def test_exact_byte_limits_are_inclusive(monkeypatch):
    monkeypatch.setattr(exports, "MAX_RESOURCE_BYTES", len(CONTENT))
    monkeypatch.setattr(exports, "MAX_PACKAGE_RESOURCE_BYTES", len(CONTENT))
    assert resolve(Loader(), policy="require_all")["binaries"] == {"asset-1": CONTENT}


def test_ambiguous_unreferenced_snapshot_resource_is_not_silently_dropped():
    snapshot = manifest()
    snapshot["available"].append(dict(snapshot["available"][0]))
    result = exports.resolve_resources(snapshot, references=[], loader=Loader(), novel_id="novel-1")
    assert result["missing_count"] == 1
    assert result["binaries"] == {}
    assert result["missing"][0]["unreferenced"] is True


def test_snapshot_metadata_is_not_mutated():
    snapshot = manifest()
    original = json.loads(json.dumps(snapshot))
    resolve(Loader(), snapshot=snapshot)
    assert snapshot == original


def test_docx_filters_xml_forbidden_characters_in_text_and_metadata():
    from xml.etree import ElementTree as ET

    invalid = "\x00\x01\x0b\x1f\ud800\udfff\ufffe\uffff"
    valid = "中文🎬"
    text = valid + invalid
    screenplay = {"title": text, "author": text, "scenes": [{"id": "scene-1", "action": text, "location": text, "dialogue": [{"character": text, "text": text, "parenthetical": text}]}]}
    binary = exports.screenplay_to_docx(screenplay, title=text, novel_id=text, snapshot_id=text, source_versions=text, resource_manifest={"available": [{"id": text, "filename": text}]})
    with ZipFile(io.BytesIO(binary)) as archive:
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                ET.fromstring(archive.read(name))
        core = ET.fromstring(archive.read("docProps/core.xml"))
        assert core.find("{http://purl.org/dc/elements/1.1/}title").text == valid
        # This exporter has a fixed creator, not an authored-by input field.
        assert core.find("{http://purl.org/dc/elements/1.1/}creator").text == "AI Novel Studio"
        document = ET.fromstring(archive.read("word/document.xml"))
        rendered = "".join(document.itertext())
        assert valid in rendered
        assert not any(char in rendered for char in invalid)


def test_xml_character_filter_preserves_valid_unicode_boundaries():
    valid = "\t\n\r \u007f\ud7ff\ue000\ufffd\U00010000\U0010ffff中文🎬"
    assert exports._clean_text(valid) == valid
    assert exports._clean_text("\x00\x08\x0b\x0c\x1f\ud800\udfff\ufffe\uffff") == ""
