from __future__ import annotations

import shutil
from pathlib import Path

SAMPLE_NOVEL_ID = "sample_novel"


def sample_novel_data_root() -> Path:
    """Return the test-owned data root that contains novels/sample_novel."""
    return Path(__file__).resolve().parent / "fixtures"


def sample_novel_source() -> Path:
    return sample_novel_data_root() / "novels" / SAMPLE_NOVEL_ID


def install_sample_novel(data_root: Path) -> Path:
    """Copy the synthetic sample novel into a run-scoped data root."""
    target = Path(data_root) / "novels" / SAMPLE_NOVEL_ID
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(sample_novel_source(), target)
    return target
