from __future__ import annotations

from threading import Event, Thread

from app.autosave.contracts import FlushReason, SaveError, SaveStatus
from app.autosave.coordinator import SaveCoordinator
from app.autosave.dirty_state import DirtyStateTracker
from app.autosave.scheduler import FakeScheduler


def test_dirty_tracker_uses_generation_to_reject_stale_completion():
    tracker = DirtyStateTracker()
    first = tracker.mark_dirty("doc", "one")
    second = tracker.mark_dirty("doc", "two")
    assert tracker.mark_saved("doc", first.generation) is None
    assert tracker.get("doc").generation == second.generation
    assert tracker.get("doc").dirty


def test_idle_debounce_coalesces_edits_and_saves_latest_content():
    scheduler = FakeScheduler()
    saved = []
    coordinator = SaveCoordinator(lambda *args: saved.append(args), scheduler=scheduler,
                                  idle_debounce=2, periodic_interval=None)
    coordinator.content_changed("doc", "one")
    scheduler.advance(1)
    coordinator.content_changed("doc", "two")
    scheduler.advance(1.9)
    assert saved == []
    scheduler.advance(.1)
    assert saved == [("doc", "two", 2)]
    assert coordinator.tracker.get("doc").status == SaveStatus.SAVED


def test_periodic_safety_save_and_flush_hooks():
    scheduler = FakeScheduler()
    saved = []
    coordinator = SaveCoordinator(lambda *args: saved.append(args), scheduler=scheduler,
                                  idle_debounce=100, periodic_interval=5)
    coordinator.content_changed("a", "A")
    scheduler.advance(5)
    assert saved[0][:2] == ("a", "A")
    for document_id, hook, reason in (
        ("b", coordinator.on_focus_loss, FlushReason.FOCUS_LOSS),
        ("c", coordinator.on_document_switch, FlushReason.DOCUMENT_SWITCH),
        ("d", coordinator.on_chapter_switch, FlushReason.CHAPTER_SWITCH),
    ):
        coordinator.content_changed(document_id, document_id)
        assert hook(document_id)
    coordinator.content_changed("e", "E")
    assert coordinator.on_application_close()
    assert {item[0] for item in saved} == {"a", "b", "c", "d", "e"}


def test_failure_remains_dirty_and_exposes_retryability_and_status():
    scheduler = FakeScheduler()
    observations = []
    failures = [SaveError("disk full", retryable=False)]

    def save(*_):
        if failures:
            raise failures.pop()

    coordinator = SaveCoordinator(save, scheduler=scheduler, periodic_interval=None,
                                  observer=observations.append)
    coordinator.content_changed("doc", "text")
    assert not coordinator.flush("doc")
    state = coordinator.tracker.get("doc")
    assert state.dirty and state.status == SaveStatus.FAILED
    assert state.failure and not state.failure.retryable
    assert observations[-1].status == SaveStatus.FAILED
    assert coordinator.flush("doc")
    assert coordinator.tracker.get("doc").status == SaveStatus.SAVED


def test_flush_all_attempts_every_document_after_one_failure():
    scheduler = FakeScheduler()
    attempted = []

    def save(document_id, *_):
        attempted.append(document_id)
        if document_id == "bad":
            raise SaveError("unavailable")

    coordinator = SaveCoordinator(save, scheduler=scheduler, periodic_interval=None)
    coordinator.content_changed("bad", "B")
    coordinator.content_changed("good", "G")
    assert not coordinator.flush_all()
    assert attempted == ["bad", "good"]
    assert coordinator.tracker.get("bad").dirty
    assert not coordinator.tracker.get("good").dirty


def test_per_document_serialization_and_latest_content_wins_during_save():
    scheduler = FakeScheduler()
    entered, release = Event(), Event()
    calls = []

    def save(document_id, content, generation):
        calls.append((document_id, content, generation))
        if generation == 1:
            entered.set()
            assert release.wait(2)

    coordinator = SaveCoordinator(save, scheduler=scheduler, periodic_interval=None)
    coordinator.content_changed("doc", "old")
    worker = Thread(target=lambda: coordinator.flush("doc"))
    worker.start()
    assert entered.wait(1)
    coordinator.content_changed("doc", "new")
    assert not coordinator.flush("doc")
    release.set()
    worker.join(2)
    assert not worker.is_alive()
    assert calls == [("doc", "old", 1), ("doc", "new", 2)]
    assert coordinator.tracker.get("doc").status == SaveStatus.SAVED


def test_observer_failure_cannot_strand_save_guard_and_closed_coordinator_rejects_edits():
    scheduler = FakeScheduler()
    saved = []
    coordinator = SaveCoordinator(lambda *args: saved.append(args), scheduler=scheduler,
                                  periodic_interval=None,
                                  observer=lambda *_: (_ for _ in ()).throw(RuntimeError("ui failed")))
    coordinator.content_changed("doc", "text")
    assert coordinator.flush("doc")
    coordinator.content_changed("doc", "new")
    assert coordinator.flush("doc")
    assert len(saved) == 2
    assert coordinator.on_application_close()
    import pytest
    with pytest.raises(RuntimeError, match="closed"):
        coordinator.content_changed("doc", "late")
