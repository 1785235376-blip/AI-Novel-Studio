from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from tests.conftest import pytest_collection_modifyitems


@dataclass
class Item:
    markers: set[str]
    nodeid: str = "tests/test_sample.py::test_sample"
    added: list[pytest.MarkDecorator] = field(default_factory=list)

    def get_closest_marker(self, name: str):
        return name if name in self.markers else None

    def add_marker(self, marker: pytest.MarkDecorator):
        self.added.append(marker)


def skipped(item: Item) -> bool:
    return any(marker.name == "skip" for marker in item.added)


def test_default_file_collection_skips_only_postgres_contracts(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    file_item, postgres_item = Item({"file_backend_only"}), Item({"postgres_backend_only"})
    pytest_collection_modifyitems([file_item, postgres_item])
    assert not skipped(file_item)
    assert skipped(postgres_item)


def test_postgres_collection_skips_only_file_contracts(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    file_item, postgres_item = Item({"file_backend_only"}), Item({"postgres_backend_only"})
    pytest_collection_modifyitems([file_item, postgres_item])
    assert skipped(file_item)
    assert not skipped(postgres_item)


@pytest.mark.parametrize("backend", ["file", "postgres"])
def test_unmarked_cross_backend_contract_executes_in_both_matrices(monkeypatch, backend):
    monkeypatch.setenv("STORAGE_BACKEND", backend)
    item = Item(set())
    pytest_collection_modifyitems([item])
    assert not skipped(item)


def test_contradictory_backend_markers_fail_fast(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    with pytest.raises(pytest.UsageError, match="contradictory backend-only markers"):
        pytest_collection_modifyitems([Item({"file_backend_only", "postgres_backend_only"})])
