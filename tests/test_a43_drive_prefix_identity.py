"""A43 namespace guard regressions on synthetic paths only.

PureWindowsPath cases prove lexical path semantics on any host. They are not
native Windows filesystem, application or device verification.
"""
from contextlib import contextmanager
from pathlib import PureWindowsPath

import pytest

from app.file_project_lifecycle import project_operation

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize("novel_id", ["C:", "c:", "C:foo", "c:foo", "D:foo", "d:foo"])
def test_drive_qualified_project_rejected_before_path_or_lock(novel_id, monkeypatch):
    calls = []

    class NoPathOperations:
        def __truediv__(self, part):
            calls.append(("path", part))
            raise AssertionError("Rejected project ID reached path derivation")

    @contextmanager
    def forbidden_lock(*args, **kwargs):
        calls.append(("lock", args))
        raise AssertionError("Rejected project ID reached a lock operation")
        yield  # pragma: no cover

    monkeypatch.setattr("app.repositories.file.mutation_coordinator.workspace_mutation", forbidden_lock)
    with pytest.raises(FileNotFoundError):
        with project_operation(NoPathOperations(), novel_id, require_exists=False):
            pytest.fail("Drive-qualified project ID was accepted")
    assert calls == []


@pytest.mark.parametrize("novel_id,expected", [
    ("C:", "C:/synthetic/data/novels"),
    ("C:foo", "C:/synthetic/data/novels/foo"),
    ("D:foo", "D:foo"),
])
def test_non_native_windows_lexical_join_exposes_drive_alias(novel_id, expected):
    # Pure path calculation only: no Windows filesystem operation is executed.
    base = PureWindowsPath("C:/synthetic/data/novels")
    assert PureWindowsPath(novel_id).drive
    assert base / novel_id == PureWindowsPath(expected)
    assert not PureWindowsPath(novel_id).is_absolute()


@pytest.mark.parametrize("novel_id", ["normal-project", ".legacy-hidden"])
def test_normal_and_dot_legacy_project_components_stay_supported(tmp_path, novel_id):
    root = tmp_path / "novels" / novel_id
    root.mkdir(parents=True)
    sentinel = root / "preserved.txt"
    sentinel.write_bytes(b"synthetic legacy bytes")
    with project_operation(tmp_path, novel_id):
        assert sentinel.read_bytes() == b"synthetic legacy bytes"
    assert sentinel.read_bytes() == b"synthetic legacy bytes"
