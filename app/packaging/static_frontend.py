from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


FRONTEND_INCOMPLETE = "应用界面组件不完整，请重新安装 AI-Novel-Studio。"
_ASSET_REFERENCE = re.compile(r'(?:src|href)=["\'](/assets/[^"\']+)["\']')


def validate_frontend_dist(path: Path) -> Path:
    root = path.resolve(strict=False)
    index = root / "index.html"
    if not root.is_dir() or not index.is_file():
        raise RuntimeError(FRONTEND_INCOMPLETE)
    try:
        markup = index.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(FRONTEND_INCOMPLETE) from exc
    references = _ASSET_REFERENCE.findall(markup)
    if not references:
        raise RuntimeError(FRONTEND_INCOMPLETE)
    for reference in references:
        candidate = (root / reference.removeprefix("/")).resolve(strict=False)
        if root not in candidate.parents or not candidate.is_file() or candidate.stat().st_size == 0:
            raise RuntimeError(FRONTEND_INCOMPLETE)
    return root


def mount_packaged_frontend(app: FastAPI, path: Path) -> None:
    app.mount("/", StaticFiles(directory=validate_frontend_dist(path), html=True), name="packaged-frontend")
