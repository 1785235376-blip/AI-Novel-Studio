"""Opt-in original incarnation observations never provision missing identity."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.creative.project_store import CreativeProjectStore


@pytest.fixture
def store(tmp_path):
    (tmp_path / "novels" / "project").mkdir(parents=True)
    return CreativeProjectStore(SimpleNamespace(root=tmp_path, backend="file"))


def marker(store):
    return store.root / "novels" / "project" / "creative_project_v2.json"


def test_missing_identity_read_never_provisions_and_default_is_unchanged(store):
    with store.existing_owner_only():
        with pytest.raises(FileNotFoundError): store.incarnation("project")
        assert not marker(store).exists()
    actual = store.incarnation("project")
    assert marker(store).is_file()
    with store.existing_owner_only():
        assert store.incarnation("project") == actual


def test_nested_context_and_exception_restore_previous_policy(store):
    with store.existing_owner_only():
        with pytest.raises(RuntimeError):
            with store.existing_owner_only():
                raise RuntimeError("cancelled observation")
        with pytest.raises(FileNotFoundError): store.incarnation("project")
        assert not marker(store).exists()
    assert store.incarnation("project").startswith("file:")


def test_exception_restores_default_policy(store):
    with pytest.raises(FileNotFoundError):
        with store.existing_owner_only():
            store.incarnation("project")
    assert not marker(store).exists()
    assert store.incarnation("project").startswith("file:")


def test_policy_isolated_to_selected_store_instance(store, tmp_path):
    second_root = tmp_path / "second"
    (second_root / "novels" / "project").mkdir(parents=True)
    second = CreativeProjectStore(SimpleNamespace(root=second_root, backend="file"))
    with store.existing_owner_only():
        assert second.incarnation("project").startswith("file:")
        with pytest.raises(FileNotFoundError): store.incarnation("project")
    assert not marker(store).exists()


def test_policy_isolated_from_other_threads(store):
    with store.existing_owner_only():
        with pytest.raises(FileNotFoundError): store.incarnation("project")
        with ThreadPoolExecutor(max_workers=1) as pool:
            actual = pool.submit(store.incarnation, "project").result(timeout=5)
        assert store.incarnation("project") == actual


def test_existing_only_does_not_repair_corrupt_marker(store):
    marker(store).write_bytes(b"not-json")
    before = marker(store).read_bytes()
    with store.existing_owner_only():
        with pytest.raises(ValueError, match="CREATIVE_PROJECT_IDENTITY_INVALID"):
            store.incarnation("project")
    assert marker(store).read_bytes() == before
