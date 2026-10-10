"""R2 regression contracts over actual loopback HTTP/SSE.

The production ASGI app, session/membership/role stack and File/marked real PG
repositories are exercised. A controlled producer appends synthetic text to a
real JobManager; no model, remote provider, production database or paid API is
used. Blocking barriers expose wake and iterator-to-ASGI-send race boundaries.
These tests deliberately do not substitute TestClient's buffered SSE response
or direct body_iterator consumption for a live network subscription.
"""
from __future__ import annotations

import copy
import http.client
import json
import queue
import socket
import threading
import time
from dataclasses import replace
from uuid import uuid4

import pytest
import uvicorn

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.collaboration import Storyline
from app.identity import IdentityStatus
from app.jobs import mark_generation_origin
from app.services.generation_service import GenerationService
from test_r3_mounted_contracts import mounted, prefix, scoped


BEFORE = "SYNTHETIC_BEFORE_REVOCATION"
AFTER = "_SYNTHETIC_PRIVATE_AFTER_REVOCATION"
DEADLINE = 5


class LiveSSE:
    """An HTTP/1.1 streaming client, with observable clean EOF and disconnect."""

    def __init__(self, port, path, headers):
        self.connection = http.client.HTTPConnection("127.0.0.1", port, timeout=DEADLINE)
        self.connection.request("GET", path, headers=headers)
        self.socket = self.connection.sock
        self.response = self.connection.getresponse()
        assert self.response.status == 200, self.response.read().decode()
        assert self.response.getheader("Content-Type").startswith("text/event-stream")
        self.events = queue.Queue()
        self.received = []
        self.raw = bytearray()
        self.errors = []
        self.closed = threading.Event()
        self.disconnected = False
        self.worker = threading.Thread(target=self._read, daemon=True)
        self.worker.start()

    def _read(self):
        try:
            for line in iter(self.response.readline, b""):
                self.raw.extend(line)
                if line.startswith(b"data: "):
                    item = json.loads(line[6:])
                    self.received.append(item)
                    self.events.put(item)
        except Exception as exc:
            if not self.disconnected:
                self.errors.append(exc)
        finally:
            self.closed.set()

    def next_event(self):
        try:
            result = self.events.get(timeout=DEADLINE)
        except queue.Empty:
            pytest.fail(f"SSE event did not arrive; closed={self.closed.is_set()}, errors={self.errors!r}")
        assert not self.errors
        return result

    def assert_clean_close(self, *, timeout=DEADLINE):
        assert self.closed.wait(timeout), "Revoked subscriber did not close within its bounded authority poll"
        self.worker.join(DEADLINE)
        assert not self.worker.is_alive()
        assert not self.errors, f"SSE must end cleanly, rather than fail its HTTP body: {self.errors!r}"

    def disconnect(self):
        self.disconnected = True
        if self.socket is not None:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.worker.join(DEADLINE)
        self.response.close()
        self.connection.close()
        assert not self.worker.is_alive(), "Synthetic SSE reader escaped cleanup"


@pytest.fixture
def stream_app(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    e.manager = e.api.jobs
    for name, value in (("jobs", {}), ("chapters", e.chapters),
                        ("persistence", GenerationService(e.bundle.generations))):
        monkeypatch.setattr(e.manager, name, value)
    e.token = "synthetic-stream-observer-" + uuid4().hex
    e.other_token = "synthetic-stream-independent-" + uuid4().hex
    for token in (e.token, e.other_token):
        e.sessions.register(token, SessionContext("session-" + uuid4().hex,
            "client-" + uuid4().hex, e.lead, e.workspace))
    e.headers = {"X-Session-Token": e.token}
    e.other_headers = {"X-Session-Token": e.other_token}
    e.project_deleted = False
    e.observers = []
    e.iterator_exits = []
    original_events = e.manager.events

    def tracked_events(*args, **kwargs):
        stopped = threading.Event()
        e.iterator_exits.append(stopped)
        try:
            yield from original_events(*args, **kwargs)
        finally:
            stopped.set()

    monkeypatch.setattr(e.manager, "events", tracked_events)

    def prepare(*, feature=False, output=BEFORE):
        scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
        job = e.manager.prepare_job("continue", {"novel_id": e.nid,
            "chapter_id": e.chapter["id"], "profile": "LOCAL_ONLY"},
            actor=e.sessions.resolve(e.token), scope=scope)
        job.status = "GENERATING"
        job.output = output
        if feature:
            mark_generation_origin(job, "author_context")
        e.manager.jobs[job.id] = job
        e.manager._persist(job)
        return job

    e.prepare = prepare
    yield e
    for observer in e.observers:
        observer.disconnect()
    for job in e.manager.jobs.values():
        with job.condition:
            job.status = "COMPLETED"
            job.condition.notify_all()
    # The reused mounted fixture owns PG cleanup and expects its project to
    # exist. Recreate only an empty synthetic placeholder after the deletion
    # assertion and after all subscriptions have finished; cleanup deletes it.
    if e.project_deleted and e.backend == "postgres":
        e.novels.create({"id": e.nid, "title": "Synthetic cleanup placeholder"})


@pytest.fixture
def wire(stream_app):
    e = stream_app
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(64)
    except PermissionError:
        listener.close()
        pytest.fail("Actual loopback HTTP/SSE bind denied; no in-process fallback is permitted")
    e.port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(e.main.app, host="127.0.0.1", port=e.port,
        lifespan="off", access_log=False, log_level="error", timeout_graceful_shutdown=2))
    failures = []

    def run():
        try:
            server.run(sockets=[listener])
        except BaseException as exc:
            failures.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    deadline = time.monotonic() + DEADLINE
    while not server.started and worker.is_alive() and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started and not failures, f"Loopback server did not start: {failures!r}"

    def subscribe(job, *, headers=None):
        observer = LiveSSE(e.port, e.prefix + "/generation/" + job.id + "/events",
                           headers=e.headers if headers is None else headers)
        e.observers.append(observer)
        return observer

    e.subscribe = subscribe
    try:
        yield e
    finally:
        for observer in e.observers:
            observer.disconnect()
        # Ensure a failed assertion cannot leave a synthetic producer running
        # through fixture teardown. This is after, not part of, every cleanup
        # assertion above and is never a substitute for disconnect handling.
        for job in e.manager.jobs.values():
            with job.condition:
                job.status = "COMPLETED"
                job.condition.notify_all()
        server.should_exit = True
        worker.join(DEADLINE)
        listener.close()
        assert not worker.is_alive(), "Loopback ASGI server escaped cleanup"
        assert not failures


def set_mode(monkeypatch, mode):
    if mode == "OFF":
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    elif mode == "V1":
        monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")


def http_get(e, job, *, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", e.port, timeout=DEADLINE)
    try:
        connection.request("GET", e.prefix + "/generation/" + job.id,
                           headers=e.headers if headers is None else headers)
        response = connection.getresponse()
        return response.status, response.read().decode()
    finally:
        connection.close()


def finish(e, job, *, persist=True):
    with job.condition:
        job.output += AFTER
        job.status = "COMPLETED"
        if persist:
            e.manager._persist(job)
        job.condition.notify_all()


def assert_no_disclosure(observer):
    observer.assert_clean_close()
    assert len(observer.received) == 1
    assert observer.received[0]["chunk"] == BEFORE
    assert AFTER.encode() not in observer.raw


def change_branch_parent(e):
    """Mutate the real branch record, without stubbing an authorization verdict."""
    repository = e.scopes.repository
    row = repository.get("branches", e.branch)
    new_parent = "replacement-synthetic-storyline-" + uuid4().hex
    e.scopes.create_storyline(Storyline(new_parent, e.workspace, e.nid, "Changed branch parent"))
    row["storyline_id"] = new_parent
    if e.backend == "file":
        data = repository._read()
        data["branches"] = [row if item["id"] == e.branch else item for item in data["branches"]]
        repository._write(data)
    else:
        with repository.connection_factory() as connection:
            connection.execute("UPDATE storyline_branches SET payload=%s::jsonb WHERE id=%s",
                               (json.dumps(row), e.branch))
            connection.commit()


@pytest.mark.parametrize("mode", ["OFF", "ON", "V1"])
@pytest.mark.parametrize("revocation", ["session", "membership", "role", "branch_link", "project_deleted"])
def test_live_sse_revalidates_current_authority_before_new_output(wire, monkeypatch, mode, revocation):
    e = wire
    set_mode(monkeypatch, mode)
    job = e.prepare()
    observer = e.subscribe(job)
    assert observer.next_event()["chunk"] == BEFORE
    if revocation == "session":
        e.sessions.revoke(e.token)
    elif revocation == "membership":
        e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
    elif revocation == "role":
        e.authorization.revoke_role(e.role, e.lead)
    elif revocation == "branch_link":
        change_branch_parent(e)
    else:
        e.novels.delete(e.nid)
        e.project_deleted = True
        with pytest.raises((FileNotFoundError, KeyError)):
            e.novels.get(e.nid)
    status, body = http_get(e, job)
    assert status == (401 if revocation == "session" else 403), body
    assert BEFORE not in body and AFTER not in body
    finish(e, job, persist=not e.project_deleted)
    assert_no_disclosure(observer)
    assert not job.cancelled.is_set(), "Revoking a subscriber must not cancel shared work"
    assert job.output == BEFORE + AFTER and job.status == "COMPLETED"


@pytest.mark.parametrize("mode", ["OFF", "ON", "V1"])
def test_two_independent_sessions_revoking_one_does_not_cancel_job_or_legal_observer(wire, monkeypatch, mode):
    e = wire
    set_mode(monkeypatch, mode)
    first_actor, second_actor = e.sessions.resolve(e.token), e.sessions.resolve(e.other_token)
    assert first_actor.actor_id == second_actor.actor_id
    assert first_actor.session_id != second_actor.session_id
    job = e.prepare()
    revoked = e.subscribe(job)
    legal = e.subscribe(job, headers=e.other_headers)
    assert revoked.next_event()["chunk"] == legal.next_event()["chunk"] == BEFORE
    e.sessions.revoke(e.token)
    assert http_get(e, job)[0] == 401
    assert http_get(e, job, headers=e.other_headers)[0] == 200
    finish(e, job)
    assert_no_disclosure(revoked)
    last = legal.next_event()
    assert last["chunk"] == AFTER and last["status"] == "COMPLETED"
    legal.assert_clean_close()
    assert "".join(row["chunk"] for row in legal.received) == BEFORE + AFTER
    stored = e.manager.persistence.get(job.id)
    assert stored["status"] == job.status == "COMPLETED"
    assert stored["output"] == job.output == BEFORE + AFTER
    assert not job.cancelled.is_set()
    for token in (e.token, e.other_token):
        assert token not in json.dumps(stored)
        assert token not in json.dumps(job.public())


def test_idle_revocation_closes_without_provider_wake_or_job_cancellation(wire):
    e = wire
    job = e.prepare()
    observer = e.subscribe(job)
    assert observer.next_event()["chunk"] == BEFORE
    before = copy.deepcopy(e.manager.persistence.get(job.id))
    e.sessions.revoke(e.token)
    observer.assert_clean_close(timeout=2)
    assert e.iterator_exits[0].wait(2), "Idle authorization polling must release the worker"
    assert observer.received[0]["chunk"] == BEFORE and len(observer.received) == 1
    assert e.manager.persistence.get(job.id) == before
    assert job.status == "GENERATING" and not job.cancelled.is_set()


def test_revocation_before_first_output_closes_empty_stream_without_any_private_event(wire):
    e = wire
    job = e.prepare(output="")
    observer = e.subscribe(job)
    e.sessions.revoke(e.token)
    observer.assert_clean_close(timeout=2)
    assert not observer.raw and not observer.received
    assert e.iterator_exits[0].wait(2)
    assert job.output == "" and job.status == "GENERATING" and not job.cancelled.is_set()


def test_idle_client_disconnect_releases_only_its_iterator(wire):
    e = wire
    job = e.prepare()
    departing = e.subscribe(job)
    assert departing.next_event()["chunk"] == BEFORE
    legal = e.subscribe(job, headers=e.other_headers)
    assert legal.next_event()["chunk"] == BEFORE
    departing.disconnect()
    assert e.iterator_exits[0].wait(2), "Client disconnect must release its waiting worker"
    assert not e.iterator_exits[1].is_set()
    assert job.status == "GENERATING" and not job.cancelled.is_set()
    finish(e, job)
    assert legal.next_event()["chunk"] == AFTER
    legal.assert_clean_close()


@pytest.mark.parametrize("disable", ["OFF", "V1"])
def test_feature_revocation_closes_existing_experimental_stream_without_cancelling(wire, monkeypatch, disable):
    e = wire
    job = e.prepare(feature=True)
    observer = e.subscribe(job)
    assert observer.next_event()["chunk"] == BEFORE
    set_mode(monkeypatch, disable)
    status, body = http_get(e, job)
    assert status == 404 and "GENERATION_FEATURE_DISABLED" in body
    finish(e, job)
    assert_no_disclosure(observer)
    assert not job.cancelled.is_set()


def test_disabling_collaboration_cannot_downgrade_existing_subscriber_authority(wire, monkeypatch):
    e = wire
    job = e.prepare()
    observer = e.subscribe(job)
    assert observer.next_event()["chunk"] == BEFORE
    local = replace(e.api.settings, enable_collaboration_runtime=False)
    monkeypatch.setattr(e.api, "settings", local)
    monkeypatch.setattr(e.main, "settings", local)
    e.sessions.revoke(e.token)
    finish(e, job)
    assert_no_disclosure(observer)
    assert not job.cancelled.is_set()


def test_rebinding_same_token_to_new_session_cannot_inherit_an_open_stream(wire):
    e = wire
    job = e.prepare()
    observer = e.subscribe(job)
    assert observer.next_event()["chunk"] == BEFORE
    old = e.sessions.resolve(e.token)
    e.sessions.register(e.token, SessionContext("replacement-session-" + uuid4().hex,
        old.client_id, old.actor_id, old.workspace_id))
    assert http_get(e, job)[0] == 200  # The new session is independently legal.
    finish(e, job)
    assert_no_disclosure(observer)  # It is not the admitted subscription identity.
    assert not job.cancelled.is_set()


def test_rebinding_job_to_another_permitted_branch_closes_admitted_scope(wire):
    e = wire
    job = e.prepare()
    observer = e.subscribe(job)
    assert observer.next_event()["chunk"] == BEFORE
    target = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.other_branch)
    e.authorization.assign_permission(PermissionAssignment("second-branch-" + uuid4().hex,
        e.lead, "domain.read", ModalityDomain.NOVEL, target, e.lead))
    job.scope = {**job.scope, "branch_id": e.other_branch}
    assert http_get(e, job)[0] == 200
    finish(e, job)
    assert_no_disclosure(observer)
    assert not job.cancelled.is_set()


class WakeBarrier(threading.Condition):
    def __init__(self):
        super().__init__()
        self.waiting = threading.Event()
        self.resumed = threading.Event()
        self.release = threading.Event()
        self.armed = threading.Event()

    def wait(self, timeout=None):
        self.waiting.set()
        result = super().wait(timeout)
        if self.armed.is_set():
            self.resumed.set()
            assert self.release.wait(DEADLINE), "Wake race barrier was not released"
        return result


def test_revocation_after_wait_wakes_but_before_output_snapshot_is_not_disclosed(wire):
    e = wire
    job = e.prepare()
    barrier = job.condition = WakeBarrier()
    try:
        observer = e.subscribe(job)
        assert observer.next_event()["chunk"] == BEFORE
        assert barrier.waiting.wait(DEADLINE)
        with barrier:
            barrier.armed.set()
            job.output += AFTER
            job.status = "COMPLETED"
            e.manager._persist(job)
            barrier.notify_all()
        assert barrier.resumed.wait(DEADLINE)
        e.sessions.revoke(e.token)
        barrier.release.set()
        assert_no_disclosure(observer)
        assert not job.cancelled.is_set()
    finally:
        barrier.release.set()


def test_revocation_after_generator_yield_before_asgi_send_drops_already_prepared_bytes(wire, monkeypatch):
    e = wire
    prepared = threading.Event()
    release = threading.Event()
    original_events = e.manager.events

    def held_after_iterator(*args, **kwargs):
        for event in original_events(*args, **kwargs):
            if AFTER in event:
                prepared.set()
                assert release.wait(DEADLINE), "Last-yield race barrier was not released"
            yield event

    monkeypatch.setattr(e.manager, "events", held_after_iterator)
    try:
        job = e.prepare()
        observer = e.subscribe(job)
        assert observer.next_event()["chunk"] == BEFORE
        finish(e, job)
        assert prepared.wait(DEADLINE), "Race must occur after the real generator prepared the private event"
        e.sessions.revoke(e.token)
        release.set()
        assert_no_disclosure(observer)
        assert e.manager.persistence.get(job.id)["output"] == BEFORE + AFTER
        assert not job.cancelled.is_set()
    finally:
        release.set()


def test_revocation_while_snapshotting_output_is_checked_again_before_yield(wire):
    e = wire
    job = e.prepare()
    observer = e.subscribe(job)
    assert observer.next_event()["chunk"] == BEFORE
    sliced = threading.Event()

    class RevokeOnSlice(str):
        def __getitem__(self, key):
            result = super().__getitem__(key)
            if isinstance(key, slice) and key.start == len(BEFORE):
                e.sessions.revoke(e.token)
                sliced.set()
            return result

    with job.condition:
        job.output = RevokeOnSlice(BEFORE + AFTER)
        job.status = "COMPLETED"
        e.manager._persist(job)
        job.condition.notify_all()
    assert sliced.wait(DEADLINE), "Race must revoke only after output snapshotting begins"
    assert_no_disclosure(observer)
    assert not job.cancelled.is_set()


@pytest.mark.parametrize("mode", ["OFF", "ON", "V1"])
@pytest.mark.parametrize("revocation", ["session", "host_invalidated"])
def test_packaged_issued_session_and_current_host_are_rechecked_on_live_stream(wire, monkeypatch, mode, revocation):
    from app.packaging.bootstrap_api import PackagedBootstrapRegistry
    from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
    from app.packaging.runtime_identity import RuntimeIdentity
    import app.dependencies as dependencies

    e = wire
    set_mode(monkeypatch, mode)
    config = replace(e.api.settings, enable_packaged_runtime=True,
                     frontend_origin="http://127.0.0.1:5173")
    monkeypatch.setattr(e.api, "settings", config)
    monkeypatch.setattr(e.main, "settings", config)
    registry = PackagedBootstrapRegistry()
    manager = LocalSessionBootstrap(runtime=RuntimeIdentity.create(), sessions=e.sessions,
        trusted_identity=TrustedLocalIdentity(e.lead, e.workspace), expected_origin=config.frontend_origin)
    registry.configure(manager)
    monkeypatch.setattr(e.main, "packaged_bootstrap_registry", registry)
    monkeypatch.setattr(dependencies, "packaged_bootstrap_registry", registry)
    e.token = manager.exchange(bootstrap_secret=manager.take_launcher_secret(),
        runtime_instance_id=manager.runtime.runtime_instance_id, origin=config.frontend_origin,
        remote_host="127.0.0.1").session_token
    e.headers = {"X-Session-Token": e.token}
    job = e.prepare()
    observer = e.subscribe(job)
    assert observer.next_event()["chunk"] == BEFORE
    if revocation == "session":
        e.sessions.revoke(e.token)
    else:
        manager.invalidate()
    assert http_get(e, job)[0] == 401
    finish(e, job)
    assert_no_disclosure(observer)
    assert not job.cancelled.is_set()
    assert e.token not in json.dumps(e.manager.persistence.get(job.id))
