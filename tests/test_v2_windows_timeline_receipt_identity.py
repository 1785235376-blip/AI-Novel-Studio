"""Real temporary-file identity checks after original atomic receipt writes.

No user files, media tools, database, runtime or model are involved. Race hooks
operate on actual opened descriptors and fixture files, not invented stat IDs.
"""
import json
import os
from pathlib import Path
import time

import pytest

from app.services.video_assembly_service import VideoAssemblyService
from app.storage import atomic_write
from test_v2_studio_receipt_bounds import receipt, load, observe_read


def test_real_atomic_rename_receipt_keeps_unicode_bytes_and_decodes(tmp_path):
    path = tmp_path / "receipt.json"
    value = {"status": "QUEUED", "label": "合成回执"}
    atomic_write(path, json.dumps(value, ensure_ascii=False))
    # Rename changes Windows descriptor change time without changing the
    # path's creation time. Both metadata families remain individually stable.
    time.sleep(0.02)
    renamed = path.with_name("renamed.json")
    path.replace(renamed)
    expected = renamed.read_bytes()
    before = renamed.stat()
    with renamed.open("rb", buffering=0) as source:
        descriptor = os.fstat(source.fileno())
    assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
        descriptor.st_dev, descriptor.st_ino, descriptor.st_size, descriptor.st_mtime_ns)
    actual = VideoAssemblyService._studio_receipt_bytes(renamed)
    assert actual == expected
    assert json.loads(actual.decode("utf-8")) == value


def test_original_atomic_owner_receipt_reopens_without_changing_digest(receipt):
    assert load(receipt) == receipt.row
    assert receipt.owner._studio_digest(receipt.row) == receipt.row["receipt_digest"]


def test_same_size_equal_mtime_path_replacement_before_open_is_rejected(receipt, monkeypatch):
    before = receipt.path.stat()
    payload = receipt.path.read_bytes()
    replacement = receipt.path.with_suffix(".replacement")
    replacement.write_bytes(payload)
    os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert replacement.stat().st_ino != before.st_ino
    events = observe_read(monkeypatch, receipt.path,
        before_open=lambda: replacement.replace(receipt.path))
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)
    assert events.sizes == [] and events.closed == [True]


def test_actual_descriptor_replacement_after_read_is_rejected(receipt, monkeypatch):
    before = receipt.path.stat()
    replacement = receipt.path.with_suffix(".descriptor-replacement")
    replacement.write_bytes(receipt.path.read_bytes())
    os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
    original_open = Path.open
    events = []

    class SwappedReader:
        def __init__(self, source):
            self.source = source

        def __enter__(self):
            self.source.__enter__()
            return self

        def __exit__(self, *args):
            result = self.source.__exit__(*args)
            events.append(self.source.closed)
            return result

        def fileno(self):
            return self.source.fileno()

        def read(self, size):
            data = self.source.read(size)
            with original_open(replacement, "rb", buffering=0) as other:
                assert os.fstat(other.fileno()).st_ino != os.fstat(self.fileno()).st_ino
                os.dup2(other.fileno(), self.fileno())
            return data

    def opened(path, mode="r", *args, **kwargs):
        source = original_open(path, mode, *args, **kwargs)
        return SwappedReader(source) if path == receipt.path and mode == "rb" else source

    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)
    assert events == [True]


def test_real_same_size_in_place_write_with_restored_mtime_is_rejected(receipt, monkeypatch):
    before = receipt.path.stat()
    payload = receipt.path.read_bytes()
    changed = payload.replace(b"QUEUED", b"FAILED")
    assert changed != payload and len(changed) == len(payload)

    def rewrite():
        # Exercise an observable metadata change, rather than assuming the
        # filesystem distinguishes writes in the same timestamp clock tick.
        time.sleep(0.02)
        receipt.path.write_bytes(changed)
        os.utime(receipt.path, ns=(before.st_atime_ns, before.st_mtime_ns))
        actual = receipt.path.stat()
        assert (actual.st_dev, actual.st_ino, actual.st_size, actual.st_mtime_ns) == (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)

    events = observe_read(monkeypatch, receipt.path, after_read=rewrite)
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)
    assert events.closed == [True]
