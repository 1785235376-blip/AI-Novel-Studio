"""File test helpers must not inherit the CI matrix's PostgreSQL default.

These are File fixture-selection checks, not PostgreSQL integration coverage.
No database is connected; the process-wide default is changed only after normal
application/test imports, then restored by the standard test fixtures.
"""
import pytest

from app.config import settings
from app.repositories.file import FileChapterRepository, FileGenerationRepository
from test_memory_agent_contract import runner, valid_output
from test_r2_acceptance_integrity import build_manager
from test_r2_dispatch_revalidation import agent_rig  # noqa: F401; register the actual fixture


@pytest.fixture
def postgres_default(monkeypatch):
    object.__setattr__(settings, "storage_backend", "postgres")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")


def test_acceptance_fixture_explicitly_selects_file(postgres_default, tmp_path):
    manager, bundle = build_manager(tmp_path)
    assert isinstance(bundle.chapters, FileChapterRepository)
    assert isinstance(bundle.generations, FileGenerationRepository)
    assert manager.persistence.repository.root == tmp_path / "runtime/jobs"


def test_memory_runner_explicitly_selects_file(postgres_default, tmp_path):
    agent, bundle, novel_id, chapter_id, version = runner(tmp_path, valid_output())
    assert isinstance(bundle.chapters, FileChapterRepository)
    assert isinstance(bundle.generations, FileGenerationRepository)
    assert chapter_id == "agent-test:1" and version == 2
    assert bundle.generations.root == tmp_path / "runtime/jobs"


def test_dispatch_agent_fixture_explicitly_selects_file(postgres_default, request):
    rig = request.getfixturevalue("agent_rig")
    assert isinstance(rig.bundle.chapters, FileChapterRepository)
    assert isinstance(rig.bundle.generations, FileGenerationRepository)
    assert rig.bundle.generations.get(rig.job["id"])["status"] == "QUEUED"
    assert rig.captured == []
