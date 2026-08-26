from __future__ import annotations

import os
from dataclasses import fields

import pytest


@pytest.fixture(autouse=True)
def restore_global_settings():
    """Keep tests that mutate the frozen settings singleton isolated."""
    from app.config import settings

    original = {field.name: getattr(settings, field.name) for field in fields(settings)}
    yield
    for name, value in original.items():
        object.__setattr__(settings, name, value)


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
