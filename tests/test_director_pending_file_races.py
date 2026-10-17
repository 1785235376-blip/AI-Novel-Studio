"""Real original File process coordination for pending publication versus clearing."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Event
import json
import os
import subprocess
import sys

import pytest

from creative_director_execution_fixture import lifecycle, raw_proposal
from test_v2_independent_director_adoption import board, raw_bytes
from test_director_durable_pending_review import publish, prepare, read, DENIALS
from test_director_private_publication_races import _DiskEvent, _stop_children
from app.creative.director_terminal_evidence import FIELD, PENDING_FIELD

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize("first", ["writer", "pending"])
def test_original_file_writer_clear_and_pending_publication_have_one_order(lifecycle, monkeypatch, first):
    import app.experimental.store as store
    e = board(lifecycle); job, body = publish(e)
    saved = e.persistence.get(job.id)
    changed = deepcopy(saved); changed.pop(FIELD); changed.update(status="FAILED", output="")
    controls = e.root / "clear-process"; controls.mkdir()
    (controls / "item.json").write_text(json.dumps(changed), encoding="utf-8")
    attempted, acquired, release, wrote = [_DiskEvent(controls / name)
        for name in ("attempted", "acquired", "release", "wrote")]
    child_source = Path(__file__).with_name("test_director_private_publication_races.py")
    root = child_source.parents[1]
    assert Path(os.environ["PROJECT_ROOT"]).resolve() == root
    assert os.environ["PYTHONDONTWRITEBYTECODE"] == "1"
    bootstrap = ("import runpy,sys;sys.path.insert(0,sys.argv[1]);"
        "scope=runpy.run_path(sys.argv[2]);scope['_file_writer_main'](sys.argv[3],sys.argv[4])")
    paused, proceed = Event(), Event()
    original_write = store.atomic_write
    def delayed_write(path, value, *args, **kwargs):
        paused.set()
        assert proceed.wait(10), "pending commit was not released"
        return original_write(path, value, *args, **kwargs)
    processes = []
    log = (controls / "child.log").open("w", encoding="utf-8")
    def start_writer():
        process = subprocess.Popen([sys.executable, "-B", "-c", bootstrap,
            str(child_source.parent), str(child_source), str(e.root), str(controls)],
            cwd=root, env=os.environ.copy(), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        processes.append(process)
        return process
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            if first == "writer":
                child = start_writer()
                assert attempted.wait(10), (controls / "child.log").read_text()
                assert acquired.wait(10)
                future = pool.submit(prepare, e, body)
                assert not future.done()
                release.set()
                with pytest.raises(DENIALS): future.result(timeout=10)
                assert PENDING_FIELD not in raw_proposal(e)
            else:
                monkeypatch.setattr(store, "atomic_write", delayed_write)
                before = raw_bytes(e)
                future = pool.submit(prepare, e, body)
                assert paused.wait(5)
                child = start_writer()
                # A bound File save must wait at the held original owner or
                # leaf. Neither may escape before the scope atomic replacement.
                assert not acquired.wait(.3) and not wrote.is_set()
                assert raw_bytes(e) == before
                proceed.set()
                candidate = future.result(timeout=10)
                assert attempted.wait(10) and acquired.wait(10)
                release.set()
            child.wait(timeout=10)
            assert child.returncode == 0, (controls / "child.log").read_text()
            outcome = json.loads((controls / "outcome.json").read_text())
            assert outcome["outcome"] == "saved" and outcome["pid"] == child.pid != os.getpid()
        assert e.persistence.get(job.id)["output"] == ""
        assert e.persistence.get(job.id)[FIELD] == saved[FIELD]
        if first == "pending":
            assert read(e) == candidate
        assert len(e.requests) == len(e.broker.ledger(e.nid, e.scope, e.actor)) == 1
    finally:
        proceed.set()
        _stop_children(processes, [release])
        log.close()
