"""Original standalone owner: synthetic MP3, actual probe and gapless decode proof."""
from copy import deepcopy
import hashlib
import base64
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import wave

import pytest
from pydantic import ValidationError

from app.creative.production_execution_models import MediaCommand
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_execution import _body, trim_output_profile
from test_v2_audio_wav_controls import command as legacy_command, snapshot, production, preview, queue, action, run, get, review
from test_v2_independent_workspace import rig, reopened, import_asset

RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)


def command(source=None, **parameters):
    value = legacy_command(source, **parameters)
    if parameters.get("output_format") == "MP3":
        value["audio_profile"] = "studio-audio-mp3/1"
    return value


def test_mp3_is_explicit_and_keeps_omitted_wav_identity():
    value = command(output_format="MP3", sample_rate=22050, channels=1)
    assert MediaCommand.model_validate(value).parameters.output_format == "MP3"
    assert trim_output_profile(value["parameters"]) == "MP3_LIBMP3LAME_22050_MONO_CBR64"
    body = {key: value[key] for key in ("operation_id", "provider_id", "model_id", "prompt", "parameters", "source_snapshots", "audio_profile")}
    assert _body(body)["parameters"] == value["parameters"]
    assert trim_output_profile(command()["parameters"]) == "PCM_S16LE_WAV_48000_STEREO"
    assert "output_format" not in MediaCommand.model_validate(command()).model_dump()["parameters"]


@pytest.mark.parametrize("rate", [8001, 44101, 64000, 96000])
def test_mp3_rejects_unsupported_rates_without_silent_resampling(rate):
    value = command(output_format="MP3", sample_rate=rate)
    with pytest.raises(ValidationError): MediaCommand.model_validate(value)
    with pytest.raises(AudiobookError) as failure: trim_output_profile(value["parameters"])
    assert failure.value.code == "STUDIO_AUDIO_MP3_SAMPLE_RATE_INVALID"


@pytest.fixture
def mp3(rig):
    e = rig
    e.service.activate(e.nid, e.scope, e.actor)
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(48000)
        writer.writeframes(b"".join(struct.pack("<h", round(12000 * math.sin(2 * math.pi * 440 * i / 48000))) for i in range(48000)))
    e.original_bytes = output.getvalue()
    e.source = import_asset(e, data=e.original_bytes, filename="owned-440hz.wav", kind="audio")
    e.production = production(e)
    e.command = command(snapshot(e.source), output_format="MP3", sample_rate=22050, channels=1, gain_db=-6.020599913279624)
    return e


def test_actual_mp3_private_review_reopen_and_lossy_pcm(mp3, tmp_path):
    e = mp3
    inspected = preview(e)
    queued = queue(e); assert queue(e) == queued and queued["media_measurement"] is None
    result = run(e, queued); assert result["status"] == "AWAITING_REVIEW", result
    meta, data = e.production.candidate(e.nid, e.scope, e.actor, "audio", result["id"], lambda: None)
    measured = result["media_measurement"]
    assert meta["media_type"] == "audio/mpeg" and data[:4] != b"RIFF" and data[:4] != b"fLaC"
    assert measured["container"] == measured["audio_codec"] == "mp3"
    assert measured["profile_validation"] == "MP3_GAPLESS_PCM_VERIFIED"
    assert measured["sample_rate"] == 22050 and measured["channels"] == 1 and measured["bit_rate"] == 64000
    assert measured["duration_ms"] == 700 and measured["total_samples"] == 15435
    assert measured["decoded_pcm_bytes"] == 30870 and measured["sample_width"] == 2
    assert measured["output_sha256"] == meta["sha256"] == hashlib.sha256(data).hexdigest()
    from app.services.studio_timeline_export import run_guarded_process
    import shutil
    source, pcm, probe = tmp_path / "observed.mp3", tmp_path / "observed.pcm", tmp_path / "observed.json"
    source.write_bytes(data)
    run_guarded_process([shutil.which("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(source)], cwd=tmp_path, guard=lambda: None, timeout=20, stdout_path=probe)
    actual = json.loads(probe.read_text())["streams"][0]
    assert (actual["codec_name"], actual["sample_rate"], actual["channels"], actual["bit_rate"]) == ("mp3", "22050", 1, "64000")
    run_guarded_process([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-xerror", "-i", str(source), "-c:a", "pcm_s16le", "-f", "s16le", str(pcm)], cwd=tmp_path, guard=lambda: None, timeout=20)
    samples = struct.unpack("<" + "h" * (pcm.stat().st_size // 2), pcm.read_bytes())
    assert hashlib.sha256(pcm.read_bytes()).hexdigest() == measured["decoded_pcm_sha256"]
    # MP3 is lossy: compare interior RMS, allowing 10% amplitude loss/error,
    # not byte equality or a lossless checksum claim.
    rms = math.sqrt(sum(v * v for v in samples[1000:-1000]) / len(samples[1000:-1000]))
    assert abs(rms - 6000 / math.sqrt(2)) / (6000 / math.sqrt(2)) < 0.10
    assert e.service.asset(e.nid, e.scope, e.source["id"]) == e.source
    assert e.service.download(e.nid, e.scope, e.source["id"])[1] == e.original_bytes
    assert hashlib.sha256(e.original_bytes).hexdigest() == e.source["sha256"]
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, meta["id"])
    e.production = production(e, reopened(e)); assert get(e, queued) == result
    approved = review(e, result); assert approved["status"] == "APPROVED" and approved["media_measurement"] == measured
    assert review(e, approved) == approved
    assert e.production.workspace.asset(e.nid, e.scope, meta["id"])["media_type"] == "audio/mpeg"
    e.production = production(e, reopened(e)); assert get(e, queued) == approved
    if os.environ.get("STUDIO_CAPTURE_AUDIO_MP3"):
        Path(os.environ["STUDIO_CAPTURE_AUDIO_MP3"]).write_text(json.dumps({"command": e.command, "preview": inspected, "queued": queued, "executed": result, "approved": approved, "candidate_base64": base64.b64encode(data).decode("ascii")}, ensure_ascii=False, indent=2) + "\n")


@pytest.mark.parametrize("rate", RATES)
def test_every_supported_mp3_rate_has_real_frames_and_decoded_duration(mp3, rate):
    e = mp3
    e.command = command(snapshot(e.source), output_format="MP3", sample_rate=rate, channels=2, in_ms=100, out_ms=813)
    result = run(e, queue(e)); assert result["status"] == "AWAITING_REVIEW", result
    measured = result["media_measurement"]
    assert measured["sample_rate"] == rate and measured["channels"] == 2
    assert measured["bit_rate"] == (128000 if rate >= 32000 else 64000)
    assert abs(measured["total_samples"] * 1000 - 713 * rate) <= 1000


def test_missing_encoder_is_honest_failed_receipt_and_cleans_private_files(mp3, monkeypatch):
    e = mp3; queued = queue(e)
    import app.services.studio_timeline_export as native
    seen = []
    def absent_encoder(argv, **kwargs):
        assert "-encoders" in argv, "No substitute encoder or media execution is permitted"
        seen.append(Path(kwargs["cwd"]))
        kwargs["guard"]()
        Path(kwargs["stdout_path"]).write_text(" A..... flac FLAC encoder\n A..... libshine another MP3 encoder\n")
    monkeypatch.setattr(native, "run_guarded_process", absent_encoder)
    failed = run(e, queued)
    assert failed["status"] == "FAILED" and failed["error_code"] == "STUDIO_AUDIO_MP3_TOOL_UNAVAILABLE"
    assert failed["output_candidate"] is None and failed["media_measurement"] is None
    assert seen and all(not directory.exists() for directory in seen)
    assert e.service.download(e.nid, e.scope, e.source["id"])[1] == e.original_bytes
    assert len(e.service.list_assets(e.nid, e.scope)["items"]) == 1
    with pytest.raises(AudiobookError): run(e, failed)


def test_native_encoding_failure_does_not_publish_partial_mp3(mp3, monkeypatch):
    e = mp3; queued = queue(e)
    import app.services.studio_timeline_export as native
    original, directories = native.run_guarded_process, []
    def partial(argv, **kwargs):
        if "libmp3lame" not in argv:
            return original(argv, **kwargs)
        directories.append(Path(kwargs["cwd"]))
        Path(argv[-1]).write_bytes(b"ID3partial")
        raise OSError("synthetic encoding failure")
    monkeypatch.setattr(native, "run_guarded_process", partial)
    failed = run(e, queued)
    assert failed["status"] == "FAILED" and failed["output_candidate"] is None and failed["media_measurement"] is None
    assert directories and all(not directory.exists() for directory in directories)
    assert len(e.service.list_assets(e.nid, e.scope)["items"]) == 1


@pytest.mark.parametrize("stage", ["encode", "probe", "decode"])
def test_cancel_between_native_mp3_steps_discards_output_and_cleans(mp3, monkeypatch, stage):
    e = mp3; queued = queue(e)
    import app.services.studio_timeline_export as native
    original, directories = native.run_guarded_process, []
    def cancelled(argv, **kwargs):
        result = original(argv, **kwargs)
        selected = "libmp3lame" in argv if stage == "encode" else "-show_entries" in argv if stage == "probe" else "s16le" in argv
        if selected:
            directories.append(Path(kwargs["cwd"]))
            running = get(e, queued)
            assert e.production.cancel(e.nid, e.scope, e.actor, "audio", queued["id"], action(running), lambda: None)["status"] == "CANCELLED"
        return result
    monkeypatch.setattr(native, "run_guarded_process", cancelled)
    result = run(e, queued)
    assert result["status"] == "CANCELLED" and result["output_candidate"] is None and result["media_measurement"] is None
    assert directories and all(not directory.exists() for directory in directories)
    assert len(e.service.list_assets(e.nid, e.scope)["items"]) == 1


def test_lost_mp3_publication_recovers_original_receipt_without_encoding(mp3, monkeypatch):
    e = mp3; queued = queue(e)
    original = e.production._callbacks
    def interrupted(*args, **kwargs):
        publish, promote = original(*args, **kwargs)
        def lost(*values, **keywords):
            publish(*values, **keywords)
            raise OSError("synthetic lost publication reply")
        return lost, promote
    monkeypatch.setattr(e.production, "_callbacks", interrupted)
    uncertain = run(e, queued)
    assert uncertain["status"] == "UNKNOWN" and uncertain["media_measurement"]
    monkeypatch.setattr(e.production, "_callbacks", original)
    import app.services.studio_timeline_export as native
    monkeypatch.setattr(native, "run_guarded_process", lambda *a, **k: pytest.fail("MP3 recovery must not encode or decode again"))
    recovered = e.production.reconcile(e.nid, e.scope, e.actor, "audio", queued["id"], action(uncertain), lambda: None)
    assert recovered["status"] == "AWAITING_REVIEW" and recovered["media_measurement"] == uncertain["media_measurement"]
    assert review(e, recovered)["status"] == "APPROVED"


def test_mp3_measured_proof_is_strict_and_lossy_not_flac(mp3, tmp_path):
    from app.media_files import MediaValidationError
    from app.services.studio_audio_mp3_profile import FIELDS, prove_mp3, validate_mp3_measurement
    e = mp3; result = run(e, queue(e)); measured = result["media_measurement"]
    assert set(measured) == FIELDS
    for key, value in (("bit_rate", 128000), ("sample_rate", 48000), ("channels", 2), ("container_duration_ms", 6000),
                       ("decoded_pcm_bytes", 30868), ("decoded_pcm_sha256", "bad"), ("total_samples", 15434),
                       ("profile_validation", "FLAC_STREAMINFO_PCM_VERIFIED"), ("container", "wav"), ("sample_width", True)):
        changed = deepcopy(measured); changed[key] = value
        with pytest.raises(MediaValidationError): validate_mp3_measurement(changed, e.command["parameters"])
    for key in FIELDS:
        changed = deepcopy(measured); changed.pop(key)
        with pytest.raises(MediaValidationError): validate_mp3_measurement(changed, e.command["parameters"])
    _, data = e.production.candidate(e.nid, e.scope, e.actor, "audio", result["id"], lambda: None)
    for name, content, parameters in (("wrong-rate", data, {**e.command["parameters"], "sample_rate": 44100}),
                                      ("truncated", data[:100], e.command["parameters"]),
                                      ("extension-only", e.original_bytes, e.command["parameters"])):
        # A private directory per proof avoids overwriting another proof's files.
        directory = tmp_path / name; directory.mkdir(); path = directory / "test.mp3"; path.write_bytes(content)
        with pytest.raises((MediaValidationError, subprocess.CalledProcessError)):
            prove_mp3(path, content, parameters, guard=lambda: None, max_bytes=e.assets.MAX_BYTES)
    owner = e.production._audio(e.scope, e.actor)
    state = owner.store.load(e.nid, include_studio=True); state["jobs"][0]["measured"]["bit_rate"] = 128000
    owner.store.save(e.nid, state, include_studio=True)
    with pytest.raises(AudiobookError): get(e, result)
    with pytest.raises(AudiobookError): review(e, result)


@pytest.mark.parametrize("rate,milliseconds", [(rate, 10) for rate in RATES] + [(8000, 17), (44100, 17)])
def test_tiny_mp3_intervals_keep_original_gapless_timing(mp3, rate, milliseconds):
    e = mp3; e.command = command(snapshot(e.source), output_format="MP3", sample_rate=rate, channels=1,
                                in_ms=100, out_ms=100 + milliseconds)
    result = run(e, queue(e)); assert result["status"] == "AWAITING_REVIEW", result
    assert abs(result["media_measurement"]["total_samples"] * 1000 - milliseconds * rate) <= 1000


@pytest.mark.parametrize("milliseconds", [1, 5, 9])
def test_too_short_mp3_is_rejected_before_queue_but_wav_and_flac_unchanged(milliseconds):
    parameters = {"in_ms": 100, "out_ms": 100 + milliseconds, "sample_rate": 8000}
    with pytest.raises(ValidationError): MediaCommand.model_validate(command(**parameters, output_format="MP3"))
    with pytest.raises(AudiobookError) as failure: trim_output_profile({**parameters, "output_format": "MP3"})
    assert failure.value.code == "STUDIO_AUDIO_MP3_DURATION_INVALID"
    assert trim_output_profile(parameters) == "PCM_S16LE_WAV_8000_STEREO"
    assert trim_output_profile({**parameters, "output_format": "FLAC"}) == "FLAC_S16_8000_STEREO_COMPRESSION5"


def test_mp3_fixed_codec_arguments_and_private_process_paths(mp3, monkeypatch):
    e = mp3
    import app.services.studio_timeline_export as native
    original, observed = native.run_guarded_process, []
    def capture(argv, **kwargs):
        observed.append((argv, kwargs)); return original(argv, **kwargs)
    monkeypatch.setattr(native, "run_guarded_process", capture)
    assert run(e, queue(e))["status"] == "AWAITING_REVIEW"
    encode = [(argv, kwargs) for argv, kwargs in observed if "libmp3lame" in argv]
    assert len(encode) == 1
    argv, options = encode[0]
    for name, value in (("-c:a", "libmp3lame"), ("-sample_fmt", "s16p"), ("-b:a", "64000"), ("-abr", "0"),
                        ("-write_xing", "1"), ("-f", "mp3"), ("-ar", "22050"), ("-ac", "1"), ("-map_metadata", "-1"),
                        ("-protocol_whitelist", "file,pipe")):
        assert argv[argv.index(name) + 1] == value
    assert "-nostdin" in argv and "-xerror" in argv and options["timeout"] == 50 and callable(options["guard"])
    assert all(not Path(kwargs["cwd"]).exists() for _, kwargs in observed)
