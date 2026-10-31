"""Original mixed ExperimentalStore File write observations, not quota approval."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import wave

import pytest

from app.experimental.store import canonical
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


def audio_candidate():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * 800)
    data = buffer.getvalue()
    return {"id": "synthetic-mix", "status": "PENDING_REVIEW", "plan_id": "synthetic-plan",
        "content_base64": base64.b64encode(data).decode("ascii"),
        "content_sha256": hashlib.sha256(data).hexdigest(),
        "media": {"media_type": "audio/wav", "duration_ms": 100, "sample_rate": 8000, "channels": 1},
        "source_asset_ids": [], "verification": "MOCK_ONLY", "asset_id": None,
        "title": "合成声音"}


def initialized(rig):
    store = rig.workspace.store.store
    mixed = {"non-audio-private": {"id": "non-audio-private", "body": "勿改动：雪☃", "version": 7}}
    with store.transaction(rig.nid, rig.scope) as doc:
        doc["collections"]["unrelated_synthetic"] = copy.deepcopy(mixed)
        doc["collections"]["audio_v2_mix_proposals"] = {}
    return store, mixed


def test_real_owner_writes_entire_mixed_document_at_atomic_peak(rig, monkeypatch):
    import app.storage as storage
    store, unrelated = initialized(rig)
    path = store.path(rig.nid, rig.scope)
    previous = path.read_bytes()
    candidate = audio_candidate()
    expected = store.read(rig.nid, rig.scope)
    expected["collections"]["audio_v2_mix_proposals"][candidate["id"]] = candidate
    encoded = canonical(expected).encode("utf-8")
    samples = []
    original_replace = os.replace
    def observe(source, target):
        if Path(target) == path:
            samples.append((path.read_bytes(), Path(source).read_bytes()))
        return original_replace(source, target)
    monkeypatch.setattr(storage.os, "replace", observe)
    with store.transaction(rig.nid, rig.scope) as doc:
        doc["collections"]["audio_v2_mix_proposals"][candidate["id"]] = candidate
    assert samples == [(previous, encoded)]
    assert len(samples[0][1]) == len(encoded) > len(candidate["content_base64"].encode("ascii"))
    assert path.read_bytes() == encoded
    reopened = store.read(rig.nid, rig.scope)
    assert reopened["collections"]["unrelated_synthetic"] == unrelated
    assert reopened["collections"]["audio_v2_mix_proposals"][candidate["id"]] == candidate
    # Observations only: they do not select which row punctuation or metadata
    # fields are charged by a future shared-document accounting contract.


_CRASH = r'''
import json, os, sys
from pathlib import Path
from app.experimental.store import ExperimentalStore
root, nid, candidate_path = sys.argv[1:]
scope = {"mode": "local", "novel_id": nid}
store = ExperimentalStore(Path(root), "file", "")
target = store.path(nid, scope)
replace = os.replace
def stop(source, dest):
    if Path(dest) == target: os._exit(73)
    return replace(source, dest)
os.replace = stop
candidate = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
with store.transaction(nid, scope) as doc:
    doc["collections"]["audio_v2_mix_proposals"][candidate["id"]] = candidate
'''


def test_process_crash_preserves_old_document_and_full_candidate_temp(rig, tmp_path):
    store, unrelated = initialized(rig)
    path = store.path(rig.nid, rig.scope)
    previous = path.read_bytes()
    candidate = audio_candidate()
    expected = store.read(rig.nid, rig.scope)
    expected["collections"]["audio_v2_mix_proposals"][candidate["id"]] = candidate
    candidate_path = tmp_path / "synthetic-mix-input.json"
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run([sys.executable, "-c", _CRASH, str(rig.root), rig.nid, str(candidate_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).resolve().parents[1]), timeout=20)
    assert result.returncode == 73, result.stdout + result.stderr
    assert path.read_bytes() == previous
    temps = list(path.parent.glob(path.name + ".*.tmp"))
    assert len(temps) == 1 and temps[0].read_bytes() == canonical(expected).encode("utf-8")
    reopened = store.read(rig.nid, rig.scope)
    assert reopened["collections"]["unrelated_synthetic"] == unrelated
    assert reopened["collections"]["audio_v2_mix_proposals"] == {}
    assert temps[0].is_file(), "unreconciled staging evidence was removed"
