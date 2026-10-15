"""R3-I — deterministic concurrency, rollback and lease-boundary acceptance.

Everything here uses explicit threading synchronisation (Events/Barriers with timeouts) placed
at points that PROVE the state being asserted. No sleep orders anything, and no assertion is
satisfied by "the other thread exited".

The phase wrapper below is the key correction for C2: `GraphAssetInputs.phase()` also calls
`guard()` BEFORE the leases exist, so a first-guard signal proves nothing. The wrapper signals
only after the real phase has yielded, which is the point at which the project owner transaction
and the asset lease are both held. The production lock rules are not modified.
"""
from __future__ import annotations

import copy
import os
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative.prompt_adoption import PromptAdoptionService
from app.creative.prompt_authoring_models import PromptCreateIn

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"

TEXT_A = "线程 A 采用到镜头的正文 🙂"
TEXT_B = "线程 B 采用到镜头的正文 ✨"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    from app.config import Settings
    from app.creative.bible_workspace import BibleWorkspaceService
    from app.creative.prompt_authoring import PromptAuthoringService
    from app.creative.prompt_workspace import PromptWorkspaceService
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.experimental.world import WorldService
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.asset_library_service import AssetLibraryService

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    nid = "conc-" + uuid4().hex
    novels.create({"id": nid, "title": "并发"})
    raw = ExperimentalStore(tmp_path, "file", "")
    creative = CreativeService(raw, novels, chapters)
    assets = AssetLibraryService(tmp_path)
    ws = IndependentWorkspaceService(creative, assets, ProductionLineageService(
        raw, novels, chapters, assets, MediaService(raw, novels, chapters, assets)))
    bible = BibleWorkspaceService(ws, WorldService(raw, novels, chapters))
    library, authoring = PromptWorkspaceService(ws, bible), PromptAuthoringService(ws, bible)
    return SimpleNamespace(nid=nid, scope={"mode": "local", "novel_id": nid}, creative=creative,
                           library=library, authoring=authoring, workspace=ws, assets=assets,
                           actor="author-a",
                           adoption=PromptAdoptionService(ws, library))


def _storyboard(rig):
    screenplay = rig.creative.create(rig.nid, rig.scope, rig.actor, {
        "mode": "SCREENPLAY", "title": "剧本", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日", "action": "站住"}]})
    board = rig.creative.derive(rig.nid, rig.scope, rig.actor, screenplay["id"], {
        "expected_version": screenplay["version"], "mode": "STORYBOARD",
        "title": "分镜", "shot_policy": "SCENE"})
    return board, board["shots"][0]["id"]


def _prompt(rig, text):
    receipt = rig.authoring.create(rig.nid, rig.scope, rig.actor, PromptCreateIn.model_validate(
        dict(text=text, purpose="IMAGE", origin="MANUAL", request_id="r-" + uuid4().hex)))
    rig.authoring.approve(rig.nid, rig.scope, rig.actor, receipt["family_id"],
                          receipt["asset_id"], receipt["asset_version"])
    body = rig.library.revision_body(rig.nid, rig.scope, receipt["family_id"],
                                     receipt["asset_id"], rig.actor)
    return receipt, body


def _request(rig, board, receipt, body, shot_id, **over):
    base = dict(shot_id=shot_id, family_id=receipt["family_id"], asset_id=receipt["asset_id"],
                revision=receipt["revision"], expected_digest=body["digest"],
                expected_version=board["version"],
                expected_digest_target=rig.creative.document_digest(board),
                request_id="adopt-" + uuid4().hex)
    base.update(over)
    return SimpleNamespace(**base)


class _SignallingInputs:
    """Test-only wrapper: signals AFTER the real phase has yielded, i.e. with leases held."""

    def __init__(self, inner, acquired: threading.Event):
        self._inner, self._acquired = inner, acquired

    @contextmanager
    def phase(self, nid, scope, actor, guard, *, writable=False):
        with self._inner.phase(nid, scope, actor, guard, writable=writable) as state:
            self._acquired.set()
            yield state
        # Reached only if the body completed; the real phase commits after this returns.

    def in_phase(self, *args, **kwargs):
        return self._inner.in_phase(*args, **kwargs)


class _FailBeforeCommitInputs(_SignallingInputs):
    """Test-only fault injection: the body completes, then the outer commit is never reached."""

    @contextmanager
    def phase(self, nid, scope, actor, guard, *, writable=False):
        with self._inner.phase(nid, scope, actor, guard, writable=writable) as state:
            yield state
            # Raising here propagates into the real phase's body, so its `raw.clear();
            # raw.update(state)` commit is SKIPPED and the transaction rolls back.
            raise RuntimeError("INJECTED_OUTER_COMMIT_FAILURE")


def _run_both(fn_a, fn_b):
    """Run two callables concurrently from a shared barrier, returning their outcomes."""
    barrier = threading.Barrier(2, timeout=20)
    out = {}

    def wrap(key, fn):
        def run():
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass
            try:
                out[key] = ("ok", fn())
            except Exception as exc:  # noqa: BLE001
                out[key] = ("error", exc)
        return run

    ta = threading.Thread(target=wrap("a", fn_a), daemon=True)
    tb = threading.Thread(target=wrap("b", fn_b), daemon=True)
    ta.start(); tb.start()
    ta.join(timeout=30); tb.join(timeout=30)
    assert not ta.is_alive() and not tb.is_alive(), "a thread deadlocked"
    return out


# ============================================================ C2: hardened lease boundary --
def test_C2_a_delete_waits_for_the_held_lease_and_leaves_a_coherent_state(rig):
    board, shot_id = _storyboard(rig)
    receipt, body = _prompt(rig, TEXT_A)
    request = _request(rig, board, receipt, body, shot_id)

    acquired = threading.Event()          # set only once the REAL phase holds its leases
    release_adoption = threading.Event()
    delete_started = threading.Event()
    delete_done = threading.Event()
    outcome, delete_outcome = {}, {}

    def guard():
        # Block the adoption inside its transaction, after the leases are held.
        if acquired.is_set():
            release_adoption.wait(timeout=20)

    adoption = PromptAdoptionService(rig.workspace, rig.library)
    adoption._inputs = _SignallingInputs(adoption._phase_inputs(), acquired)

    def run_adoption():
        try:
            outcome["result"] = adoption.adopt_atomic(rig.nid, rig.scope, rig.actor,
                                                      board["id"], shot_id, request, guard)
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = exc

    def run_delete():
        try:
            delete_started.set()
            with rig.workspace._asset_scope(rig.nid, rig.scope):
                rig.assets.delete(receipt["asset_id"], branch_id=rig.scope.get("branch_id"))
            delete_outcome["ok"] = True
        except Exception as exc:  # noqa: BLE001
            delete_outcome["error"] = exc
        finally:
            delete_done.set()

    worker = threading.Thread(target=run_adoption, daemon=True)
    deleter = threading.Thread(target=run_delete, daemon=True)
    try:
        worker.start()
        # The signal is emitted only after the real phase yielded: leases ARE held here.
        assert acquired.wait(timeout=20), "the adoption never acquired its lease"
        deleter.start()
        assert delete_started.wait(timeout=10), "the delete never started"
        # The delete must not slip past the protected boundary while the lease is held.
        finished_while_held = delete_done.wait(timeout=1.5)
        assert not finished_while_held, "the delete crossed the held resource boundary"
    finally:
        # Always release, even if an assertion above failed, so no thread is left blocked.
        release_adoption.set()
    assert delete_done.wait(timeout=25), "the delete never finished after the lease was released"
    worker.join(timeout=25)
    assert not worker.is_alive(), "the adoption thread did not finish"

    # Real persisted state, not merely "the threads exited".
    assert "result" in outcome or "error" in outcome, "the adoption produced no outcome"
    # The delete must reach an EXPLICABLE outcome: success through the owner, or one of the
    # owner's own defined refusals. An arbitrary exception is not an acceptable result.
    assert ("ok" in delete_outcome) != ("error" in delete_outcome), \
        "the delete produced no definite outcome"
    if "error" in delete_outcome:
        assert isinstance(delete_outcome["error"], (FileNotFoundError, ValueError,
                                                   PermissionError)), \
            f"the delete failed with an unexpected error: {delete_outcome['error']!r}"
    live = rig.creative.get(rig.nid, rig.scope, board["id"])
    proofs = [p for p in (live.get("prompt_adoptions") or [])
              if p.get("request_id") == request.request_id
              and p.get("document_id") == board["id"]
              and p.get("shot_id") == shot_id]
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    if "result" in outcome:
        assert outcome["result"]["committed"] is True
        assert live["version"] == outcome["result"]["version"]
        assert shot["frame_prompt"] == TEXT_A
        assert len(proofs) == 1, "exactly one proof for this request"
    else:
        assert live["version"] == board["version"], "a failed adoption must not commit"
        assert not proofs
    assert not any("job" in name.lower()
                   for name in rig.workspace.store.read(rig.nid, rig.scope).get("collections", {}))

    # Read the persisted effect through the PRODUCT's own projection: if the source really was
    # deleted, the projection must say so rather than still offering it as readable.
    projection = rig.adoption.read(rig.nid, rig.scope, board["id"], rig.actor)
    entry = next((e for e in projection["adoptions"]
                  if e.get("request_id") == request.request_id), None)
    if "ok" in delete_outcome and entry is not None:
        assert entry["source_readable"] is False, \
            "a deleted source must not still be reported as readable"
        # History survives the deletion even though readability does not.
        assert entry["asset_id"] == receipt["asset_id"]


# ================================================================= A: two prompts, one shot --
def test_A_two_different_prompts_to_one_shot_let_exactly_one_win(rig):
    board, shot_id = _storyboard(rig)
    r1, b1 = _prompt(rig, TEXT_A)
    r2, b2 = _prompt(rig, TEXT_B)
    # Both requests are built from the SAME initial document version and digest.
    q1 = _request(rig, board, r1, b1, shot_id)
    q2 = _request(rig, board, r2, b2, shot_id)

    out = _run_both(
        lambda: rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"], shot_id, q1),
        lambda: rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"], shot_id, q2))

    winners = [k for k, v in out.items() if v[0] == "ok"]
    losers = [k for k, v in out.items() if v[0] == "error"]
    assert len(winners) == 1, f"exactly one adoption may win, got {out}"
    assert len(losers) == 1
    # The loser must fail for a DEFINED reason: a version/digest conflict or a defined
    # adoption refusal. Any other exception is a bug, not a legitimate race outcome.
    from app.services.v1_capability_service import CapabilityVersionConflict
    loser_exc = out[losers[0]][1]
    assert isinstance(loser_exc, CapabilityVersionConflict) or (
        isinstance(loser_exc, ValueError)
        and str(loser_exc).startswith("PROMPT_ADOPTION")), \
        f"the loser failed for an undefined reason: {loser_exc!r}"

    live = rig.creative.get(rig.nid, rig.scope, board["id"])
    # Exactly one new revision, and it holds the WINNER's text.
    assert live["version"] == board["version"] + 1, "the loser must not add a revision"
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    win_req = q1 if winners[0] == "a" else q2
    win_text = TEXT_A if winners[0] == "a" else TEXT_B
    assert shot["frame_prompt"] == win_text
    proofs = [p for p in (live.get("prompt_adoptions") or [])
              if p.get("request_id") == win_req.request_id]
    assert len(proofs) == 1
    lose_req = q2 if winners[0] == "a" else q1
    assert not [p for p in (live.get("prompt_adoptions") or [])
                if p.get("request_id") == lose_req.request_id], "no proof for the loser"


# ============================================== B: two identical request_ids concurrently --
def test_B_two_identical_request_ids_produce_exactly_one_revision(rig):
    board, shot_id = _storyboard(rig)
    receipt, body = _prompt(rig, TEXT_A)
    request = _request(rig, board, receipt, body, shot_id)   # the SAME request object

    out = _run_both(
        lambda: rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"], shot_id, request),
        lambda: rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"], shot_id, request))

    live = rig.creative.get(rig.nid, rig.scope, board["id"])
    assert live["version"] == board["version"] + 1, "an identical request must not add revisions"
    proofs = [p for p in (live.get("prompt_adoptions") or [])
              if p.get("request_id") == request.request_id
              and p.get("document_id") == board["id"] and p.get("shot_id") == shot_id]
    assert len(proofs) == 1, "exactly one proof may exist for one request identity"
    # At least one caller observed success; the other either replayed the SAME committed result
    # or was refused by CAS -- never a second write.
    successes = [v[1] for v in out.values() if v[0] == "ok"]
    assert successes, "at least one caller must succeed"
    for result in successes:
        assert result["version"] == live["version"], \
            "every success must describe the same committed version"
    replay_flags = [r["replayed"] for r in successes]
    if len(successes) == 2:
        assert sorted(replay_flags) == [False, True], \
            "a second identical success must be reported as a replay, not a second write"


# ================================================ E: authorization revoked before commit --
class _RevokeBeforeCommitInputs(_SignallingInputs):
    """Revoke authorization only AFTER the in-transaction revision has completed.

    Counting guard calls does NOT establish this: `phase()` itself calls guard twice before the
    adoption business logic is reached, so a "refuse from call 2" rule aborts far too early and
    proves nothing about rolling back a completed in-memory revision. This wrapper lets every
    guard call succeed until the body has finished, then revokes, so the refusal lands on the
    real phase's own post-yield guard -- i.e. after `revise_in_state` succeeded and before the
    outer commit.
    """

    def __init__(self, inner, revoked: threading.Event):
        super().__init__(inner, threading.Event())
        self._revoked = revoked

    @contextmanager
    def phase(self, nid, scope, actor, guard, *, writable=False):
        def wrapped_guard():
            if self._revoked.is_set():
                raise PermissionError("AUTHORIZATION_REVOKED")
            return guard()

        with self._inner.phase(nid, scope, actor, wrapped_guard, writable=writable) as state:
            yield state
            # The adoption body has completed, including revise_in_state.
            self._revoked.set()


def test_E_a_revoked_authorization_rolls_back_a_completed_revision(rig):
    board, shot_id = _storyboard(rig)
    receipt, body = _prompt(rig, TEXT_A)
    request = _request(rig, board, receipt, body, shot_id)

    adoption = PromptAdoptionService(rig.workspace, rig.library)
    adoption._inputs = _RevokeBeforeCommitInputs(adoption._phase_inputs(), threading.Event())

    with pytest.raises(PermissionError, match="AUTHORIZATION_REVOKED"):
        adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"], shot_id, request)

    # The revision was completed in memory and then the authorization was revoked: the real
    # persisted result must contain none of it.
    live = rig.creative.get(rig.nid, rig.scope, board["id"])
    assert live["version"] == board["version"], "a revoked request must not commit a version"
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    assert shot["frame_prompt"] == "", "the shot must be unchanged"
    assert not (live.get("prompt_adoptions") or []), "no proof for a revoked request"


# ========================================= F: outer commit failure after the revision --
def test_F_a_failed_outer_commit_persists_nothing_and_reports_nothing(rig):
    board, shot_id = _storyboard(rig)
    receipt, body = _prompt(rig, TEXT_A)
    request = _request(rig, board, receipt, body, shot_id)

    adoption = PromptAdoptionService(rig.workspace, rig.library)
    adoption._inputs = _FailBeforeCommitInputs(adoption._phase_inputs(), threading.Event())

    with pytest.raises(RuntimeError, match="INJECTED_OUTER_COMMIT_FAILURE"):
        adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"], shot_id, request)

    # Nothing persisted: no version, no proof, no shot change.
    live = rig.creative.get(rig.nid, rig.scope, board["id"])
    assert live["version"] == board["version"], "a rolled-back transaction must leave no version"
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    assert shot["frame_prompt"] == "", "a rolled-back transaction must leave the shot unchanged"
    assert not (live.get("prompt_adoptions") or []), "no proof may survive a failed commit"


# ============================== G: a real STORE commit failure, distinct from test F --
def test_G_a_real_file_atomic_write_failure_persists_nothing(rig):
    """Test F aborts BEFORE the outer commit; this fails the REAL persistence write.

    The previous version of this test was a false positive and is replaced. It wrapped
    `raw_store.transaction` with a function that called `raw_store.transaction` again -- i.e.
    itself -- and accepted RuntimeError, of which RecursionError is a subclass, so a stack
    overflow could be mistaken for a storage failure. It also never reached the real commit.

    This version injects at the actual boundary the File backend uses:
    `atomic_write(path, canonical(doc))` in app/experimental/store.py line 109. A counter proves
    the path was really reached, the failure carries a specific marker, and only this round's
    isolated scope file is targeted.
    """
    import app.experimental.store as store_mod

    board, shot_id = _storyboard(rig)
    receipt, body = _prompt(rig, TEXT_A)
    request = _request(rig, board, receipt, body, shot_id)

    scope_key = rig.workspace.store.key(rig.nid, rig.scope)
    original_atomic_write = store_mod.atomic_write
    calls = {"n": 0}

    def failing_atomic_write(path, text):
        # Only this test's own scope document; anything else goes through untouched.
        if scope_key in str(path):
            calls["n"] += 1
            raise OSError("INJECTED_FILE_ATOMIC_WRITE_FAILURE")
        return original_atomic_write(path, text)

    store_mod.atomic_write = failing_atomic_write
    raised = None
    try:
        try:
            rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"],
                                      shot_id, request)
        except BaseException as exc:  # noqa: BLE001
            raised = exc
    finally:
        # Restore unconditionally so no other test inherits the injected failure.
        store_mod.atomic_write = original_atomic_write

    # The REAL commit path must have been reached; otherwise this proves nothing.
    assert calls["n"] >= 1, "the File atomic_write commit boundary was never reached"
    assert raised is not None, "the adoption reported success despite a failed commit"
    assert isinstance(raised, OSError), f"unexpected failure type: {raised!r}"
    assert "INJECTED_FILE_ATOMIC_WRITE_FAILURE" in str(raised)

    # Reopen the real store and confirm nothing changed.
    live = rig.creative.get(rig.nid, rig.scope, board["id"])
    assert live["version"] == board["version"], "a failed commit must persist no version"
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    assert shot["frame_prompt"] == "", "a failed commit must leave the shot unchanged"
    assert not (live.get("prompt_adoptions") or []), "no proof may survive a failed commit"

    # And a retry with the injection removed must now work, proving the store was restored.
    retry = _request(rig, rig.creative.get(rig.nid, rig.scope, board["id"]),
                     receipt, body, shot_id)
    result = rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"],
                                       shot_id, retry)
    assert result["committed"] is True, "the store was not restored after the injection"
