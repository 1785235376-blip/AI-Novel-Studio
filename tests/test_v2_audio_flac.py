"""Original audio owner, real CPU FLAC and bounded actual PCM proof.

All inputs are tiny synthetic waveforms. No model or final native Host runs.
"""
import hashlib
from pathlib import Path
import shutil
import sys
import time

import pytest
from pydantic import ValidationError

from app.creative.graph_models import MediaNodeParameters
from app.creative.production_execution_models import MediaCommand
from app.media_files import MediaValidationError
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_execution import _body, trim_output_profile
from app.services.studio_audio_trim_profiles import FIELDS, VALIDATION, prove_flac, streaminfo
from test_v2_audio_wav_controls import (audio, command, snapshot, production, preview, queue, action, run, get, review)
from test_v2_independent_workspace import rig, reopened


def explicit(e, **parameters):
    return command(snapshot(e.source), output_format="FLAC", gain_db=-6.020599913279624, sample_rate=22050,
                   channels=1, **parameters)


def decoded(data, tmp_path):
    from app.services.studio_timeline_export import run_guarded_process
    source, target = tmp_path / "observed.flac", tmp_path / "observed.pcm"
    source.write_bytes(data)
    run_guarded_process([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-xerror", "-threads", "1",
        "-protocol_whitelist", "file,pipe", "-i", str(source), "-map", "0:a:0", "-c:a", "pcm_s16le", "-f", "s16le", str(target)],
        cwd=tmp_path, guard=lambda: None, timeout=30)
    return target.read_bytes()


def test_actual_flac_original_private_review_reopen_and_pcm_proof(audio, tmp_path):
    e = audio; e.command = explicit(e)
    inspected = preview(e)
    assert inspected["execution_recipe"]["output_profile"] == "FLAC_S16_22050_MONO_COMPRESSION5"
    queued = queue(e); assert queue(e) == queued
    result = run(e, queued); assert result["status"] == "AWAITING_REVIEW", result
    meta, data = e.production.candidate(e.nid, e.scope, e.actor, "audio", result["id"], lambda: None)
    assert meta["media_type"] == "audio/flac" and data[:4] == b"fLaC"
    measured, pcm, info = result["media_measurement"], decoded(data, tmp_path), streaminfo(data)
    assert set(measured) == FIELDS and measured["profile_validation"] == VALIDATION
    assert measured["container"] == "flac" and measured["audio_codec"] == "flac" and measured["sample_width"] == 2
    assert measured["sample_rate"] == 22050 and measured["channels"] == 1 and measured["duration_ms"] == 700
    assert measured["total_samples"] == 15435 and measured["decoded_pcm_bytes"] == len(pcm) == 30870
    assert measured["streaminfo_md5"] == info["streaminfo_md5"] == hashlib.md5(pcm, usedforsecurity=False).hexdigest()
    assert measured["decoded_pcm_sha256"] == hashlib.sha256(pcm).hexdigest()
    assert measured["output_sha256"] == hashlib.sha256(data).hexdigest() == result["output_candidate"]["digest"]
    samples = [int.from_bytes(pcm[i:i+2], "little", signed=True) for i in range(200, len(pcm)-200, 2)]
    assert max(abs(sample - 1000) for sample in samples) <= 1
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, meta["id"])
    e.production = production(e, reopened(e)); assert get(e, queued) == result
    approved = review(e, result); assert approved["status"] == "APPROVED" and approved["media_measurement"] == measured
    assert e.production.workspace.asset(e.nid, e.scope, meta["id"])["media_type"] == "audio/flac"
    e.production = production(e, reopened(e)); assert get(e, queued) == approved


@pytest.mark.parametrize("format", ["WAV", "flac", "MP3", True, 1, {}, []])
def test_format_is_closed_in_original_command_and_audio_body(format):
    value = command(output_format=format)
    with pytest.raises(ValidationError): MediaCommand.model_validate(value)
    body = {key: value[key] for key in ("operation_id", "provider_id", "model_id", "prompt", "parameters", "source_snapshots")}
    with pytest.raises(AudiobookError): _body(body)


def test_absent_null_wav_and_graph_default_identities_are_unchanged():
    original = MediaCommand.model_validate(command()).model_dump()
    assert MediaCommand.model_validate(command(output_format=None)).model_dump() == original
    assert "output_format" not in original["parameters"]
    assert trim_output_profile(command()["parameters"]) == "PCM_S16LE_WAV_48000_STEREO"
    with pytest.raises(ValidationError):
        MediaNodeParameters.model_validate({"operation_id": "m8.audio.trim", "parameters": {"in_ms": 0, "out_ms": 10, "output_format": "FLAC"}})
    value = command(output_format="FLAC"); value.update(operation_id="m8.audio.music", provider_id="p", model_id="m")
    with pytest.raises(ValidationError): MediaCommand.model_validate(value)


def test_original_internal_graph_binding_cannot_enable_flac(audio):
    e = audio; e.command = explicit(e)
    binding = {"contract": "creative-graph-media-binding/1", "run_id": "run", "node_id": "trim", "graph_id": "graph",
        "graph_version": 1, "graph_digest": "a" * 64, "run_request_digest": "b" * 64,
        "actor": e.actor, "scope_key": e.production.store.key(e.nid, e.scope), "incarnation": e.production.store.incarnation(e.nid)}
    with pytest.raises(ValueError, match="STANDALONE_ONLY"):
        preview(e, graph_binding=binding)


@pytest.mark.parametrize("rate,channels,milliseconds", [(8000, 1, 17), (11025, 2, 713), (44100, 1, 713), (96000, 2, 100)])
def test_actual_fractional_sample_intervals_are_proven_not_duration_guesses(audio, rate, channels, milliseconds):
    e = audio; e.command = command(snapshot(e.source), output_format="FLAC", sample_rate=rate, channels=channels,
                                    in_ms=100, out_ms=100 + milliseconds)
    result = run(e, queue(e)); assert result["status"] == "AWAITING_REVIEW", result
    measured = result["media_measurement"]
    assert abs(measured["total_samples"] * 1000 - milliseconds * rate) <= 1000
    assert measured["decoded_pcm_bytes"] == measured["total_samples"] * channels * 2


@pytest.mark.parametrize("fault", ["md5", "total", "bits", "duplicate", "truncated"])
def test_bad_flac_metadata_or_actual_pcm_is_rejected(audio, tmp_path, fault):
    e = audio; e.command = explicit(e); result = run(e, queue(e))
    _, data = e.production.candidate(e.nid, e.scope, e.actor, "audio", result["id"], lambda: None)
    changed = bytearray(data)
    if fault == "md5": changed[26] ^= 1
    elif fault == "total": changed[25] ^= 1
    elif fault == "bits": changed[20] ^= 1
    elif fault == "duplicate": changed[4] &= 127; changed[42:42] = bytes([128, 0, 0, 34]) + data[8:42]
    else: changed = changed[:42]
    target = tmp_path / "damaged.flac"; target.write_bytes(changed)
    with pytest.raises(MediaValidationError):
        prove_flac(target, bytes(changed), e.command["parameters"], guard=lambda: None, max_bytes=e.assets.MAX_BYTES)


def test_flac_proof_never_accepts_a_different_private_file(audio, tmp_path):
    e = audio; e.command = explicit(e); result = run(e, queue(e))
    _, data = e.production.candidate(e.nid, e.scope, e.actor, "audio", result["id"], lambda: None)
    target = tmp_path / "different.flac"; target.write_bytes(data + b"changed")
    with pytest.raises(MediaValidationError):
        prove_flac(target, data, e.command["parameters"], guard=lambda: None, max_bytes=e.assets.MAX_BYTES)


def test_lost_flac_publication_recovers_exact_proof_without_native_reexecution(audio, monkeypatch):
    e = audio; e.command = explicit(e); queued = queue(e)
    original = e.production._callbacks
    def interrupted(*args, **kwargs):
        publish, promote = original(*args, **kwargs)
        def lost(*values, **keywords):
            publish(*values, **keywords)
            raise OSError("synthetic lost publication reply")
        return lost, promote
    monkeypatch.setattr(e.production, "_callbacks", interrupted)
    uncertain = run(e, queued); assert uncertain["status"] == "UNKNOWN" and uncertain["media_measurement"]
    monkeypatch.setattr(e.production, "_callbacks", original)
    import app.services.studio_timeline_export as native
    monkeypatch.setattr(native, "run_guarded_process", lambda *a, **k: pytest.fail("Recovery may not encode or decode again"))
    recovered = e.production.reconcile(e.nid, e.scope, e.actor, "audio", queued["id"], action(uncertain), lambda: None)
    assert recovered["status"] == "AWAITING_REVIEW" and recovered["attempt"] == 1
    assert recovered["media_measurement"] == uncertain["media_measurement"]
    assert review(e, recovered)["status"] == "APPROVED"


@pytest.mark.parametrize("stage", ["probe", "decode"])
def test_revoke_during_flac_proof_propagates_original_guard_and_reaps(audio, monkeypatch, stage):
    e = audio; e.command = explicit(e); queued = queue(e)
    import app.services.studio_timeline_export as native
    original = native.run_guarded_process; seen, revoked, directories = [], [False], []
    class Revoked(ValueError): pass
    failure = Revoked("synthetic explicit guard revoked")
    def current():
        if revoked[0]: raise failure
    def observed(arguments, **kwargs):
        result = original(arguments, **kwargs)
        selected = "-show_entries" in arguments if stage == "probe" else "s16le" in arguments
        if selected: seen.append(True); directories.append(Path(kwargs["cwd"])); revoked[0] = True; kwargs["guard"]()
        return result
    monkeypatch.setattr(native, "run_guarded_process", observed)
    with pytest.raises(Revoked) as caught:
        e.production.execute(e.nid, e.scope, e.actor, "audio", queued["id"], action(queued), current)
    assert caught.value is failure and seen
    assert not any(path.exists() for path in directories)
    assert len(e.service.list_assets(e.nid, e.scope)["items"]) == 1


@pytest.mark.parametrize("stage", ["probe", "decode"])
def test_cancel_interrupts_active_flac_native_child_without_waiting_for_timeout(audio, monkeypatch, stage):
    e = audio; e.command = explicit(e); queued = queue(e)
    import app.services.studio_timeline_export as native
    original, processes, directories = native.subprocess.Popen, [], []
    def launch(arguments, *args, **kwargs):
        selected = "-show_entries" in arguments if stage == "probe" else "s16le" in arguments
        if not selected: return original(arguments, *args, **kwargs)
        child = original([sys.executable, "-c", "import time; time.sleep(60)"], *args, **kwargs)
        processes.append(child); directories.append(Path(kwargs["cwd"]))
        running = get(e, queued)
        cancelled = e.production.cancel(e.nid, e.scope, e.actor, "audio", queued["id"], action(running), lambda: None)
        assert cancelled["status"] == "CANCELLED"
        return child
    monkeypatch.setattr(native.subprocess, "Popen", launch)
    started = time.monotonic()
    try:
        result = run(e, queued)
        assert result["status"] == "CANCELLED" and result["output_candidate"] is None
        assert time.monotonic() - started < 10
        assert len(processes) == 1 and processes[0].poll() is not None
        assert processes[0].stderr.closed and (processes[0].stdout is None or processes[0].stdout.closed)
        assert not any(path.exists() for path in directories)
        assert len(e.service.list_assets(e.nid, e.scope)["items"]) == 1
    finally:
        for child in processes:
            if child.poll() is None: child.kill()
            child.wait(timeout=3)
