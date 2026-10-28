"""Real child cleanup under timeline process cancellation and write failure."""
import builtins
import sys

import pytest

from app.services import studio_timeline_export as native


def observe_child(monkeypatch):
    created = []
    original = native.subprocess.Popen

    def spawn(*args, **kwargs):
        child = original(*args, **kwargs)
        created.append(child)
        return child

    monkeypatch.setattr(native.subprocess, "Popen", spawn)
    return created


def test_guard_cancellation_reaps_started_process(tmp_path, monkeypatch):
    children = observe_child(monkeypatch)

    def guard():
        if children:
            raise RuntimeError("synthetic cancellation")

    command = [sys.executable, "-u", "-c", "import time; time.sleep(30)"]
    with pytest.raises(RuntimeError, match="synthetic cancellation"):
        native.run_guarded_process(command, cwd=tmp_path, guard=guard, timeout=10)
    assert len(children) == 1 and children[0].returncode is not None


def test_probe_output_write_failure_reaps_started_process(tmp_path, monkeypatch):
    children = observe_child(monkeypatch)
    target = tmp_path / "probe-output.json"

    class BrokenOutput:
        def __init__(self, file):
            self.file = file

        def write(self, data):
            raise OSError("synthetic disk write failure")

        def close(self):
            self.file.close()

    def output_open(path, mode):
        assert path == target and mode == "wb"
        return BrokenOutput(builtins.open(path, mode))

    monkeypatch.setattr(native, "open", output_open, raising=False)
    command = [sys.executable, "-u", "-c",
               "import sys,time; sys.stdout.write('synthetic'); sys.stdout.flush(); time.sleep(30)"]
    with pytest.raises(OSError, match="synthetic disk write failure"):
        native.run_guarded_process(command, cwd=tmp_path, guard=lambda: None, timeout=10, stdout_path=target)
    assert len(children) == 1 and children[0].returncode is not None
    assert target.read_bytes() == b""
