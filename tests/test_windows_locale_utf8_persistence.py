"""Windows/CJK-locale persistence regression: UTF-8 JSON must be read explicitly.

Chinese Windows uses the cp936 (GBK) locale encoding for default text I/O. Product files are
written as UTF-8 by app.storage.atomic_write; reading them with Path.read_text() (no encoding)
fails or corrupts non-ASCII content. These tests pin the explicit-encoding contract and add a
static guard for the product tree.

Defect: reading image-job / video-assembly JSON without encoding='utf-8' (fixed in the same
change). The functional round-trip catches data corruption on any locale; the spy assertion makes
the missing-encoding contract deterministic even on a UTF-8 CI runner.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from app.storage import atomic_write

ROOT = Path(__file__).resolve().parents[1]
CHINESE = "中文任务标题与提示词"
SCOPE = ["小说项目", "分支-甲"]


def _spy_read_text(monkeypatch, marker: str) -> list[object]:
    recorded: list[object] = []
    original = Path.read_text

    def spy(self, *args, **kwargs):
        if marker in str(self):
            recorded.append(kwargs.get("encoding"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)
    return recorded


def test_image_job_rows_read_utf8_and_keep_chinese(tmp_path, monkeypatch):
    service = ImageJobService(tmp_path)
    atomic_write(
        service._path("novel-cn", None),
        json.dumps([{"id": "job-cn", "title": CHINESE, "status": "QUEUED"}], ensure_ascii=False),
    )
    encodings = _spy_read_text(monkeypatch, "image-jobs")
    rows = service.list("novel-cn", None)
    assert rows and rows[0]["title"] == CHINESE
    assert encodings == ["utf-8"], encodings


def test_video_assembly_rows_read_utf8_and_keep_chinese(tmp_path, monkeypatch):
    assets = object()
    service = VideoAssemblyService(tmp_path, assets)
    scope_dir = service._scope_dir(*SCOPE, "actor-cn")
    scope_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(
        scope_dir / "job-cn.json",
        json.dumps(
            {
                "id": "job-cn",
                "title": CHINESE,
                "status": "COMPLETED",
                "created_at": "2026-10-19T00:00:00Z",
            },
            ensure_ascii=False,
        ),
    )
    encodings = _spy_read_text(monkeypatch, "video-assemblies")
    rows = service.list(*SCOPE, "actor-cn")
    assert rows and rows[0]["title"] == CHINESE
    assert encodings == ["utf-8"], encodings


def _text_io_calls_without_encoding(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"read_text", "write_text"}:
            continue
        if any(keyword.arg == "encoding" for keyword in node.keywords):
            continue
        problems.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return problems


def test_product_text_io_always_declares_utf8_encoding():
    problems: list[str] = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        problems.extend(_text_io_calls_without_encoding(path))
    assert not problems, "Path.read_text/write_text without encoding='utf-8': " + ", ".join(problems)


@pytest.mark.parametrize("chapter_text", [CHINESE, "普通 ASCII 之外的内容"])
def test_cjk_locale_roundtrip_sample(chapter_text: str, tmp_path: Path) -> None:
    # Guard the shared atomic_write contract the product relies on: bytes are UTF-8 and a
    # strict UTF-8 reader recovers the exact text (no locale dependency).
    target = tmp_path / "probe.txt"
    atomic_write(target, chapter_text)
    assert target.read_text(encoding="utf-8") == chapter_text
