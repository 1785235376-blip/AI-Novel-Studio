"""Additive bounds and stable-snapshot checks on the original receipt owner.

Race hooks change only temporary fixture files at deterministic I/O boundaries;
production path, ownership, receipt validation and mutation locks remain real.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.video_assembly_service import VideoAssemblyService
from app.services.studio_video_execution import StudioVideoExecution
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig


LIMIT = 384_000


@pytest.fixture
def receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    owner = VideoAssemblyService(tmp_path, None)
    context = {"actor": "author", "scope_key": "a" * 64, "incarnation": "file:" + str(uuid4())}
    row = owner._studio_write("project", None, "author", {
        "id": "receipt", "kind": "STUDIO_VIDEO", "contract": StudioVideoExecution.CONTRACT,
        "status": "QUEUED", "created_at": "2026-10-12T00:00:00+00:00", "context": context,
        "body": {"prompt": "Private receipt fixture: 青"},
    }, context=context)
    path = owner._studio_path("project", None, "author", row["id"], context)
    return SimpleNamespace(owner=owner, context=context, row=row, path=path)


def load(receipt):
    return receipt.owner._studio_read("project", None, "author", "receipt", context=receipt.context)


def encode(receipt, row=None):
    row = deepcopy(receipt.row if row is None else row)
    row["receipt_digest"] = receipt.owner._studio_digest(row)
    return json.dumps(row, ensure_ascii=False).encode("utf-8")


def observe_read(monkeypatch, path, *, before_open=None, before_read=None, after_read=None, read_limit=None):
    """Observe real opens/reads; never synthesize bytes, metadata or file handles."""
    original = Path.open
    events = SimpleNamespace(modes=[], sizes=[], returned=[], closed=[])

    class ObservedFile:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            result = self.handle.__exit__(*args)
            events.closed.append(self.handle.closed)
            return result

        def fileno(self):
            return self.handle.fileno()

        def read(self, size=-1):
            events.sizes.append(size)
            if before_read:
                before_read()
            value = self.handle.read(size if read_limit is None else read_limit)
            events.returned.append(len(value))
            if after_read:
                after_read()
            return value

    def observed(candidate, mode="r", *args, **kwargs):
        if candidate == path and mode in {"r", "rb"}:
            events.modes.append(mode)
            if before_open:
                before_open()
            return ObservedFile(original(candidate, mode, *args, **kwargs))
        return original(candidate, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", observed)
    return events


def test_valid_receipt_uses_one_bounded_binary_read(receipt, monkeypatch):
    events = observe_read(monkeypatch, receipt.path)
    assert load(receipt) == receipt.row
    assert events.modes == ["rb"]
    assert events.sizes == [LIMIT + 1]
    assert events.returned == [receipt.path.stat().st_size]
    assert events.closed == [True]


def test_exact_original_byte_limit_keeps_utf8_receipt(receipt):
    payload = encode(receipt)
    receipt.path.write_bytes(payload + b" " * (LIMIT - len(payload)))
    assert receipt.path.stat().st_size == LIMIT
    assert load(receipt) == receipt.row


def test_oversized_receipt_is_rejected_without_reading(receipt, monkeypatch):
    receipt.path.write_bytes(encode(receipt) + b" " * LIMIT)
    events = observe_read(monkeypatch, receipt.path)
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_LIMIT$"):
        load(receipt)
    assert events.sizes == []


@pytest.mark.parametrize("moment", ["before_open", "before_read"])
def test_growth_cannot_bypass_original_limit(receipt, monkeypatch, moment):
    payload = encode(receipt)
    def grow():
        receipt.path.write_bytes(payload + b" " * LIMIT)
    events = observe_read(monkeypatch, receipt.path, **{moment: grow})
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_LIMIT$"):
        load(receipt)
    assert all(0 <= size <= LIMIT + 1 for size in events.sizes)
    assert all(size <= LIMIT + 1 for size in events.returned)
    assert all(events.closed)


def test_actual_overflow_sentinel_rejects_growth_even_after_size_is_restored(receipt, monkeypatch):
    payload = receipt.path.read_bytes()
    events = observe_read(monkeypatch, receipt.path,
        before_read=lambda: receipt.path.write_bytes(payload + b" " * LIMIT),
        after_read=lambda: receipt.path.write_bytes(payload))
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_LIMIT$"):
        load(receipt)
    assert receipt.path.stat().st_size == len(payload)
    assert events.sizes == events.returned == [LIMIT + 1]
    assert events.closed == [True]


@pytest.mark.parametrize("change", ["grow", "truncate", "rewrite", "mtime", "replace", "remove"])
def test_changes_after_read_are_not_accepted_as_stable(receipt, monkeypatch, change):
    payload = receipt.path.read_bytes()
    before = receipt.path.stat()
    replacement = receipt.path.with_suffix(".replacement")
    replacement.write_bytes(payload)
    os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))

    def mutate():
        if change == "grow":
            receipt.path.write_bytes(payload + b" ")
        elif change == "truncate":
            receipt.path.write_bytes(payload[:-1])
        elif change == "rewrite":
            receipt.path.write_bytes(payload.replace(b"QUEUED", b"FAILED"))
            os.utime(receipt.path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        elif change == "mtime":
            os.utime(receipt.path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        elif change == "replace":
            replacement.replace(receipt.path)
        else:
            receipt.path.unlink()

    events = observe_read(monkeypatch, receipt.path, after_read=mutate)
    # Windows can deny deletion/replacement while the read handle is open.
    # That native denial must also fail closed instead of returning a row.
    errors = (ValueError, FileNotFoundError)
    if os.name == "nt" and change in {"replace", "remove"}:
        errors += (PermissionError,)
    with pytest.raises(errors):
        load(receipt)
    assert events.closed == [True]


@pytest.mark.skipif(os.name == "nt", reason="Windows ctime is creation time, not POSIX metadata change time")
def test_posix_change_time_rejects_same_size_write_with_restored_mtime(receipt, monkeypatch):
    before = receipt.path.stat()
    payload = receipt.path.read_bytes()
    def rewrite():
        receipt.path.write_bytes(payload.replace(b"QUEUED", b"FAILED"))
        os.utime(receipt.path, ns=(before.st_atime_ns, before.st_mtime_ns))
    observe_read(monkeypatch, receipt.path, after_read=rewrite)
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)


def test_same_size_replacement_between_stat_and_open_is_rejected(receipt, monkeypatch):
    before = receipt.path.stat()
    replacement = receipt.path.with_suffix(".replacement")
    replacement.write_bytes(receipt.path.read_bytes())
    os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
    events = observe_read(monkeypatch, receipt.path, before_open=lambda: replacement.replace(receipt.path))
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)
    assert events.sizes == []
    assert events.closed == [True]


def test_truncation_before_read_rejects_otherwise_valid_short_json(receipt, monkeypatch):
    payload = encode(receipt)
    receipt.path.write_bytes(payload + b" " * 100)
    observe_read(monkeypatch, receipt.path, before_read=lambda: receipt.path.write_bytes(payload))
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)


def test_short_read_rejects_valid_json_even_with_unchanged_metadata(receipt, monkeypatch):
    payload = encode(receipt)
    receipt.path.write_bytes(payload + b" " * 100)
    before = receipt.path.stat()
    events = observe_read(monkeypatch, receipt.path, read_limit=len(payload))
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)
    assert receipt.path.stat().st_mtime_ns == before.st_mtime_ns
    assert receipt.path.stat().st_size == before.st_size
    assert events.returned == [len(payload)]
    assert events.closed == [True]


@pytest.mark.parametrize("acceptance", [False, True])
def test_disabled_feature_never_opens_receipt(receipt, monkeypatch, acceptance):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2" if acceptance else "")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if acceptance else "")
    events = observe_read(monkeypatch, receipt.path)
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_FEATURE_DISABLED$"):
        load(receipt)
    assert events.modes == []


def test_denied_guard_never_opens_receipt(receipt, monkeypatch):
    events = observe_read(monkeypatch, receipt.path)
    def deny():
        raise PermissionError("Denied")
    with pytest.raises(PermissionError, match="^Denied$"):
        receipt.owner.get_studio("project", None, "author", "receipt", context=receipt.context, guard=deny)
    assert events.modes == []


@pytest.mark.parametrize("field,value", [
    ("id", "other"), ("novel_id", "other"), ("branch_id", "other"),
    ("owner_actor_id", "other"), ("scope_key", "b" * 64),
    ("incarnation", "file:00000000-0000-0000-0000-000000000000"),
    ("required_features", []), ("version", True), ("version", 0),
])
def test_existing_receipt_identity_validation_is_preserved(receipt, field, value):
    altered = {**receipt.row, field: value}
    receipt.path.write_bytes(encode(receipt, altered))
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)


def test_existing_digest_and_graph_validation_are_preserved(receipt):
    receipt.path.write_bytes(encode(receipt).replace(b"QUEUED", b"FAILED"))
    with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
        load(receipt)
    row = deepcopy(receipt.row)
    row["context"]["graph_binding"] = None
    receipt.path.write_bytes(encode(receipt, row))
    with pytest.raises(ValueError, match="^CREATIVE_GRAPH_MEDIA_BINDING_INVALID$"):
        load(receipt)


@pytest.mark.parametrize("payload", [b"{", b"\xff", b"[]"])
def test_malformed_receipts_still_fail_closed(receipt, payload):
    receipt.path.write_bytes(payload)
    with pytest.raises((ValueError, UnicodeError)):
        load(receipt)


def test_missing_receipt_retains_not_found_contract(receipt):
    receipt.path.unlink()
    with pytest.raises(FileNotFoundError):
        load(receipt)


def test_original_list_video_and_cas_paths_share_the_read_bound(receipt, monkeypatch):
    guard = lambda: None
    calls = [
        lambda: receipt.owner.get_studio("project", None, "author", "receipt", context=receipt.context, guard=guard),
        lambda: receipt.owner.list_studio("project", None, "author", context=receipt.context, guard=guard),
        lambda: StudioVideoExecution(receipt.owner).get("project", None, "author", "receipt", context=receipt.context, guard=guard),
        lambda: receipt.owner._studio_write("project", None, "author", receipt.row, context=receipt.context, expected_version=1),
        lambda: receipt.owner._studio_mutate("project", None, "author", "receipt", 1, lambda _: pytest.fail("unstable receipt reached mutation"), context=receipt.context),
    ]
    original = receipt.path.read_bytes()
    for operation in calls:
        receipt.path.write_bytes(original)
        with monkeypatch.context() as patch:
            before = receipt.path.stat()
            events = observe_read(patch, receipt.path, after_read=lambda: os.utime(
                receipt.path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000)))
            with pytest.raises(ValueError, match="^STUDIO_TIMELINE_RECEIPT_INVALID$"):
                operation()
            assert events.sizes == [LIMIT + 1]


def test_original_owner_reopen_list_and_cas_with_real_project_scope(rig):
    """JSON receipts retain original File/PostgreSQL project incarnation context."""
    owner = VideoAssemblyService(rig.root, rig.assets)
    context = {"actor": rig.actor, "scope_key": rig.service.store.key(rig.nid, rig.scope),
               "incarnation": rig.service.store.incarnation(rig.nid)}
    assert context["incarnation"].startswith(rig.backend + ":")
    row = owner._studio_write(rig.nid, None, rig.actor, {
        "id": "bounded", "kind": "STUDIO_VIDEO", "contract": StudioVideoExecution.CONTRACT,
        "status": "QUEUED", "context": context, "created_at": "2026-10-12T00:00:00+00:00",
    }, context=context)
    reopened = VideoAssemblyService(rig.root, rig.assets)
    assert StudioVideoExecution(reopened).get(rig.nid, None, rig.actor, row["id"], context=context, guard=lambda: None) == row
    listed = reopened.list_studio(rig.nid, None, rig.actor, context=context, guard=lambda: None)
    assert [item["id"] for item in listed] == [row["id"]]
    changed = reopened._studio_write(rig.nid, None, rig.actor, {**row, "status": "CANCELLED"}, context=context, expected_version=1)
    assert changed["version"] == 2 and changed["status"] == "CANCELLED"
    with pytest.raises(CapabilityVersionConflict):
        reopened._studio_write(rig.nid, None, rig.actor, row, context=context, expected_version=1)
    assert reopened.list(rig.nid, None, rig.actor) == []
