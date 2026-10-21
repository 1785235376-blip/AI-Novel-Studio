"""Cold-process workers for synthetic CPU/File owner regression tests.

No database, provider, host, GPU, or HTTP acceptance is implied. Every worker
constructs new File repositories and original services from the same disk root.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import pytest


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wait(path):
    deadline = time.monotonic() + 20
    while not path.exists():
        if time.monotonic() > deadline:
            raise AssertionError("cross-process barrier did not arrive")
        time.sleep(0.01)


def open_owner(state):
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    from test_v2_independent_workspace import services
    from test_creative_canvas_views_additive import owner
    from test_v2_audio_editing_pipeline import production
    root = Path(state["data_root"])
    bundle = create_repository_bundle(Settings(storage_backend="file", database_url="", novel_data=root,
        enable_cloud=False, mock_provider=True), data_root=root)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    service = services(root, "file", "", novels, chapters)
    e = SimpleNamespace(root=root, nid=state["nid"], scope=state["scope"], actor=state["actor"],
        novels=novels, chapters=chapters, service=service, assets=service.assets,
        store=service.store, raw_store=service.store.store, backend="file", url="", bundle=bundle,
        source=state["source"], canvas=state["canvas"], command=state["command"])
    e.production = production(e)
    e.graph = owner(e)
    e.graph.configure_media(e.production)
    return e


def get(e, state):
    return e.production.get(e.nid, e.scope, e.actor, state["owner_kind"], state["candidate"]["id"], lambda: None)


def adopt_body(e, state):
    from test_creative_canvas_views_additive import reference
    formal = e.service.asset(e.nid, e.scope, state["candidate"]["output_candidate"]["id"])
    definition = deepcopy(e.canvas["definition"])
    definition["cards"][0]["asset"] = reference(formal)
    return {"expected_version": e.canvas["version"], "definition": definition,
        "expected_incarnation": state["incarnation"], "expected_definition_digest": e.canvas["definition_digest"],
        "expected_card": {"card_id": e.canvas["definition"]["cards"][0]["id"], "source": reference(e.source)}}


def cold_guards(e, mp, native_calls):
    from app.services import studio_timeline_export as native
    from app.services import studio_image_composite
    original = native.run_guarded_process
    def observed(command, *args, **kwargs):
        args_text = list(map(str, command))
        assert not any(v in args_text for v in ("-filter_complex", "-af", "-filter:a")), "cold phase re-rendered media"
        native_calls.append(Path(args_text[0]).name)
        return original(command, *args, **kwargs)
    def denied(*args, **kwargs):
        raise AssertionError("cold read/review/return phase attempted execution")
    mp.setattr(native, "run_guarded_process", observed)
    mp.setattr(studio_image_composite, "render", denied)
    mp.setattr(e.production, "execute", denied)
    mp.setattr(e.production, "canvas_video_execute", denied)


def prepare(kind, case, mp):
    from test_v2_independent_workspace import rig
    generator = rig.__wrapped__(SimpleNamespace(param="file"), case / "store", mp)
    e = next(generator)
    try:
        if kind == "audio":
            from test_studio_canvas_audio_return import audio_canvas
            from test_v2_audio_wav_controls import preview, queue, run
            e = audio_canvas.__wrapped__(e)
            captured = preview(e); queued = queue(e); candidate = run(e, queued); owner_kind = "audio"
        elif kind == "video":
            from test_studio_canvas_video_bridge import bridge, preview, queue, execute
            e = bridge.__wrapped__(e, case)
            captured = preview(e); queued = queue(e, captured=captured); candidate = execute(e, queued); owner_kind = "timeline"
        else:
            from test_studio_canvas_image_composite_return import layer_pair, card_composite
            from test_v2_cpu_cutout_owner import preview, queue, run
            e = card_composite.__wrapped__(layer_pair.__wrapped__(e, mp))
            captured = preview(e); queued = queue(e); candidate = run(e, queued); owner_kind = "image"
        assert candidate["status"] == ("SUCCEEDED" if kind == "video" else "AWAITING_REVIEW"), candidate
        with pytest.raises(FileNotFoundError):
            e.service.asset(e.nid, e.scope, candidate["output_candidate"]["id"])
        assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas["id"]) == e.canvas
        _, data = e.production.candidate(e.nid, e.scope, e.actor, owner_kind, candidate["id"], lambda: None)
        assert hashlib.sha256(data).hexdigest() == candidate["output_candidate"]["digest"]
        if kind == "audio":
            with wave.open(io.BytesIO(data), "rb") as stream:
                assert (stream.getframerate(), stream.getnchannels(), stream.getnframes()) == (48000, 2, 14400)
                samples = struct.unpack("<" + "h" * 28800, stream.readframes(14400))
                assert all(abs(v - 2121) <= 2 for v in samples[400:-400])
            measurement = {"duration_ms": 300, "sample_rate": 48000, "channels": 2, "frames": 14400, "samples_checked": True}
        elif kind == "video":
            from test_studio_canvas_video_cpu_owner_probe import _decoded_measurement
            target = case / "measured-output.mp4"; target.write_bytes(data)
            measurement = _decoded_measurement(target)
            assert (measurement["decoded_frames"], measurement["duration_ms"], measurement["width"], measurement["height"]) == (15, 600, 640, 360)
            assert measurement["codec"] == "h264" and all(v[2] > 230 and v[0] < 20 for v in measurement["center_rgb"])
        else:
            from test_studio_canvas_image_composite_return import assert_pixels
            _, measurement = assert_pixels(e, candidate)
            assert measurement["bytewise_rgba_equal"]
        state = {"kind": kind, "owner_kind": owner_kind, "data_root": str(e.root), "nid": e.nid,
            "scope": e.scope, "actor": e.actor, "incarnation": e.store.incarnation(e.nid),
            "source": e.source, "canvas": e.canvas, "command": e.command, "preview": captured,
            "queued": queued, "candidate": candidate, "measurement": measurement,
            "output_sha256": hashlib.sha256(data).hexdigest(), "prepare_pid": os.getpid()}
        write(case / "state.json", state)
        (case / ("result.wav" if kind == "audio" else "result.mp4" if kind == "video" else "result.png")).write_bytes(data)
        return {"status": "PRIVATE_CANDIDATE_ON_DISK", "candidate_id": candidate["id"], "measurement": measurement, "output_sha256": state["output_sha256"]}
    finally:
        generator.close()


def phase(name, state, case, mp, label):
    from app.experimental.common import StaleSourceError
    from test_creative_canvas_views_additive import reference
    from test_v2_audio_wav_controls import action
    e = open_owner(state); native_calls = []
    cold_guards(e, mp, native_calls)
    assert e.store.incarnation(e.nid) == state["incarnation"]
    current = get(e, state)
    assert current["id"] == state["candidate"]["id"]
    if name == "review":
        expected = deepcopy(state["candidate"])
        if state["owner_kind"] == "timeline":
            # Original GET hydrates these read-state fields after execute.
            # Compare the entire row; all pins/receipts/versions remain exact.
            expected.update(execution_state="SUCCEEDED", needs_reconciliation=False)
        assert current == expected
        assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas["id"]) == e.canvas
        approved = e.production.review(e.nid, e.scope, e.actor, state["owner_kind"], current["id"], action(current, True), lambda: None)
        assert approved["status"] == "APPROVED"
        formal = e.service.asset(e.nid, e.scope, approved["output_candidate"]["id"])
        assert formal["version"] == 2 and formal["sha256"] == state["output_sha256"]
        assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas["id"]) == e.canvas
        return {"status": "APPROVED_WITHOUT_AUTO_ADOPTION", "approved": approved, "formal": reference(formal)}
    if name in {"adopt", "adopt-race"}:
        assert current["status"] == "APPROVED"
        body = adopt_body(e, state)
        if name == "adopt-race":
            (case / (label + ".ready")).write_text("ready", encoding="ascii"); wait(case / "adopt.go")
        try:
            saved = e.graph.canvas_views.save(e.nid, e.scope, e.actor, e.canvas["id"], body)
        except (ValueError, PermissionError, StaleSourceError) as exc:
            if name != "adopt-race":raise
            return {"status": "CAS_REJECTED", "error": type(exc).__name__}
        assert saved["version"] == 2 and saved["definition"]["cards"][0]["asset"] == body["definition"]["cards"][0]["asset"]
        return {"status": "ADOPTED", "canvas": saved}
    if name == "restore":
        before = e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas["id"])
        assert before["version"] == 2
        history = e.graph.canvas_views.history(e.nid, e.scope, e.actor, e.canvas["id"])
        restored = e.graph.canvas_views.restore(e.nid, e.scope, e.actor, e.canvas["id"], {
            "expected_version": before["version"], "expected_definition_digest": before["definition_digest"],
            "expected_incarnation": history["incarnation"], "restore_version": 1,
            "restore_definition_digest": e.canvas["definition_digest"]})
        assert restored["version"] == 3 and restored["definition"] == e.canvas["definition"]
        return {"status": "RESTORED_AS_NEW_VERSION", "canvas": restored}
    if name == "verify":
        canvas = e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas["id"])
        history = e.graph.canvas_views.history(e.nid, e.scope, e.actor, e.canvas["id"])
        assert canvas["version"] == 3 and canvas["definition"] == e.canvas["definition"]
        assert [row["version"] for row in history["items"]] == [1, 2, 3]
        assert current["status"] == "APPROVED"
        formal = e.service.asset(e.nid, e.scope, current["output_candidate"]["id"])
        assert history["items"][1]["definition"]["cards"][0]["asset"] == reference(formal)
        assert formal["sha256"] == state["output_sha256"]
        _, data = e.service.download(e.nid, e.scope, formal["id"])
        assert hashlib.sha256(data).hexdigest() == state["output_sha256"]
        return {"status": "COLD_READ_HISTORY_AND_PIN_PASS", "versions": [1, 2, 3], "job_id": current["id"], "output_sha256": formal["sha256"], "binary_bytes": len(data), "native_inspection_calls": native_calls}
    if name == "change-source":
        with e.service._asset_scope(e.nid, e.scope):
            row = e.assets.update_metadata(e.source["id"], {"scene_id": "synthetic-cold-source-change"}, expected_version=e.source["version"])
        assert row["version"] == e.source["version"] + 1
        return {"status": "SOURCE_PIN_CHANGED", "version": row["version"]}
    if name == "reject-review":
        from app.experimental.common import StaleSourceError
        with pytest.raises((StaleSourceError, ValueError, PermissionError)):
            e.production.review(e.nid, e.scope, e.actor, state["owner_kind"], current["id"], action(current, True), lambda: None)
        with pytest.raises(FileNotFoundError):e.service.asset(e.nid, e.scope, current["output_candidate"]["id"])
        assert get(e, state)["status"] == state["candidate"]["status"]
        assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas["id"])["version"] == 1
        return {"status": "STALE_REVIEW_REJECTED_NO_PROMOTION", "output_sha256": state["output_sha256"]}
    if name == "rollback":
        raw = e.raw_store; before = raw.read(e.nid, e.scope)
        marker = RuntimeError("synthetic-rollback-body")
        with pytest.raises(RuntimeError) as caught:
            with raw.transaction(e.nid, e.scope) as doc:
                doc["collections"]["process_rollback_probe"] = [{"id": "must-not-survive"}]
                raise marker
        assert caught.value is marker and raw.read(e.nid, e.scope) == before
        with raw.transaction(e.nid, e.scope) as doc:
            assert doc == before  # active transaction state and lock were released
        return {"status": "BODY_EXCEPTION_ROLLBACK_AND_RELEASE_PASS", "document_sha256": hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest()}
    if name == "verify-rollback":
        assert "process_rollback_probe" not in e.raw_store.read(e.nid, e.scope)["collections"]
        assert get(e, state) == state["candidate"]
        return {"status": "COLD_ROLLBACK_READ_PASS"}
    raise AssertionError(name)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("phase"); parser.add_argument("case", type=Path); parser.add_argument("--kind", default="image"); parser.add_argument("--label", default="worker")
    args = parser.parse_args(); case = args.case.resolve()
    assert case.is_relative_to(ROOT / ".runtime")
    case.mkdir(parents=True, exist_ok=True); mp = pytest.MonkeyPatch()
    try:
        state = json.loads((case / "state.json").read_text(encoding="utf-8")) if args.phase != "prepare" else None
        result = prepare(args.kind, case, mp) if args.phase == "prepare" else phase(args.phase, state, case, mp, args.label)
        result |= {"pid": os.getpid(), "phase": args.phase, "provider_called": False, "backend": "file"}
        write(case / (args.label + ".json"), result)
        print(json.dumps({"status": result["status"], "pid": os.getpid(), "phase": args.phase}))
    finally:
        mp.undo()


if __name__ == "__main__":
    main()
