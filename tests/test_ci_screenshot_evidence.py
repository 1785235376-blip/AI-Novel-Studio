"""Artifact transport only: original image bytes and failure history stay intact."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("ci_screenshots", Path(__file__).parents[1] / ".github/ci/screenshots.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_all_png_bytes_preserved_and_each_part_has_exact_source_receipt(tmp_path):
    root = tmp_path / "original"; root.mkdir()
    for index in range(3):
        path = root / f"journey-{index}" / "test-failed-1.png"
        path.parent.mkdir(); path.write_bytes(bytes([index]) * 12)
    (root / "trace.zip").write_bytes(b"original full trace remains")
    output = tmp_path / "bounded"
    manifests = module.collect(root, output, "exact-ci-source", limit=24)
    assert len(manifests) == 2 and sum(len(row["files"]) for row in manifests) == 3
    for part in output.iterdir():
        data = json.loads((part / "manifest.json").read_text())
        assert data["source_sha"] == "exact-ci-source" and data["png_bytes"] <= 24
        assert data["images_unmodified"] and data["full_trace_artifact_retained"]
        for row in data["files"]:
            assert (part / row["path"]).read_bytes() == (root / row["path"]).read_bytes()
    assert (root / "trace.zip").read_bytes() == b"original full trace remains"
    assert not list(output.rglob("*.zip"))


def test_capacity_error_is_explicit_and_never_drops_originals(tmp_path):
    root = tmp_path / "original"; root.mkdir()
    for index in range(5): (root / f"{index}.png").write_bytes(b"123")
    with pytest.raises(ValueError, match="four bounded groups"):
        module.collect(root, tmp_path / "bounded", "source", limit=3)
    assert len(list(root.glob("*.png"))) == 5
    assert not (tmp_path / "bounded").exists()
