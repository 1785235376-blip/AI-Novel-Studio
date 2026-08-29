from __future__ import annotations

import os
import sys
from dataclasses import fields
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from sample_novel_fixture import sample_novel_source as _sample_novel_source

_PROVIDER_AND_DATABASE_ENV = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "XAI_API_KEY",
    "DASHSCOPE_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "DATABASE_URL",
    "TEST_POSTGRES_DATABASE_URL",
    "E2E_DATABASE_URL",
)


@pytest.fixture
def sample_novel_source() -> Path:
    return _sample_novel_source()


@pytest.fixture(autouse=True)
def restore_global_settings():
    """Snapshot/restore settings, listed env vars, runtime attributes, and FastAPI overrides.

    Does not force CREDENTIAL_VAULT_BACKEND=memory and does not replace vault
    private state. Tests that need a process-local credential store inject an
    explicit memory vault in a narrow fixture.
    """
    from app.config import settings
    from app.main import app
    from app.packaging.control_pipe import credential_store
    from app.runtime import runtime

    original_settings = {field.name: getattr(settings, field.name) for field in fields(settings)}
    original_overrides = app.dependency_overrides.copy()
    original_runtime = {
        key: (value.copy() if isinstance(value, dict) else value)
        for key, value in runtime.__dict__.items()
    }
    original_store = dict(credential_store._values)
    removed_env: dict[str, str] = {}
    try:
        for key in _PROVIDER_AND_DATABASE_ENV:
            if key in os.environ:
                removed_env[key] = os.environ.pop(key)
        yield
    finally:
        for key in _PROVIDER_AND_DATABASE_ENV:
            os.environ.pop(key, None)
        os.environ.update(removed_env)
        for name, value in original_settings.items():
            object.__setattr__(settings, name, value)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        runtime.__dict__.clear()
        runtime.__dict__.update(original_runtime)
        credential_store._values.clear()
        credential_store._values.update(original_store)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    postgres = os.getenv("STORAGE_BACKEND", "file").strip().lower() == "postgres"
    for item in items:
        file_only = bool(item.get_closest_marker("file_backend_only"))
        postgres_only = bool(item.get_closest_marker("postgres_backend_only"))
        if file_only and postgres_only:
            raise pytest.UsageError(f"contradictory backend-only markers: {item.nodeid}")
        if postgres and file_only:
            item.add_marker(pytest.mark.skip(reason="File-backend implementation contract; covered by the default/File full suite"))
        if not postgres and postgres_only:
            item.add_marker(pytest.mark.skip(reason="PostgreSQL implementation contract; covered by the real PostgreSQL full suite"))
