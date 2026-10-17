"""Real standalone File audio fades: synthetic sources, actual CPU codec proof.

Use the owned V2 runner and select ``not postgres_backend_only`` for File-only
acceptance. No provider, model, native desktop, or subjective-quality claim.
Envelope tolerances are chosen before execution: lossless S16 allows eight LSB
for rounding/resampler phase; MP3 allows 12% relative interior RMS-envelope error.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
import shutil
import struct
import subprocess
import wave

import pytest

from test_v2_audio_mp3 import command
from test_v2_audio_wav_controls import production, preview, queue, run, get, review, snapshot
from test_v2_independent_workspace import rig, reopened, import_asset


GAIN = -6.020599913279624
RATE = 22050
DURATION_MS = 1000
LOSSLESS_LSB_TOLERANCE = 8
MP3_RELATIVE_RMS_TOLERANCE = 0.12


@pytest.fixture(scope="module")
def native_tools():
    """Check the actual tools at test execution; never install or substitute."""
    paths = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    for name, path in paths.items():
        assert path, f"real audio-fade CPU acceptance requires installed {name}"
        checked = subprocess.run([path, "-version"], check=True, capture_output=True, text=True, timeout=20)
        assert name + " version" in checked.stdout
    encoders = subprocess.run([paths["ffmpeg"], "-hide_banner", "-encoders"],
                              check=True, capture_output=True, text=True, timeout=20)
    assert any("libmp3lame" in line.split() for line in encoders.stdout.splitlines()), \
        "real MP3 fade acceptance requires libmp3lame; no alternate encoder"
    return paths


def source_wav(channels, sine=False):
    """Distinct discarded regions prove the 200 ms source in-point, not just length."""
    rate = 16000
    values = []
    for index in range(rate * 1400 // 1000):
        milliseconds = index * 1000 / rate
        selected = 200 <= milliseconds < 1200
        if sine:
            amplitude, frequency = (12000, 1000) if selected else (2000, 250)
            sample = round(amplitude * math.sin(2 * math.pi * frequency * index / rate))
        else:
            sample = 8000 if selected else (1000 if milliseconds < 200 else -2000)
        values.extend([sample] * channels)
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(struct.pack("<" + "h" * len(values), *values))
    return output.getvalue()


def prepare(e, channels=1, sine=False):
    e.service.activate(e.nid, e.scope, e.actor)
    e.original_bytes = source_wav(channels, sine)
    e.source = import_asset(e, data=e.original_bytes, filename="owned-fade-source.wav", kind="audio")
    e.production = production(e)  # Existing NoControl collaborators fail any provider call.
    return e


def fade_command(e, format="WAV", channels=1, **fades):
    options = {} if format == "WAV" else {"output_format": format}
    return command(snapshot(e.source), in_ms=200, out_ms=1200, gain_db=GAIN,
                   sample_rate=RATE, channels=channels, **options, **fades)


def decode(e, result, tmp_path, native_tools, label):
    """Independently decode the persisted private candidate, without fake measurements."""
    from app.services.studio_timeline_export import run_guarded_process
    meta, data = e.production.candidate(e.nid, e.scope, e.actor, "audio", result["id"], lambda: None)
    measured = result["media_measurement"]
    source = tmp_path / (label + "." + measured["container"])
    pcm = tmp_path / (label + ".pcm")
    source.write_bytes(data)
    run_guarded_process([native_tools["ffmpeg"], "-nostdin", "-v", "error", "-xerror", "-threads", "1",
        "-protocol_whitelist", "file,pipe", "-i", str(source), "-map", "0:a:0", "-c:a", "pcm_s16le",
        "-f", "s16le", str(pcm)], cwd=tmp_path, guard=lambda: None, timeout=30)
    raw = pcm.read_bytes()
    samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    channels = measured["channels"]
    assert measured["sample_rate"] == RATE and measured["sample_width"] == 2
    assert measured["duration_ms"] == DURATION_MS
    assert len(samples) == RATE * channels  # Gapless decoding, no manual delay/padding removal.
    assert hashlib.sha256(data).hexdigest() == meta["sha256"] == result["output_candidate"]["digest"]
    assert measured["output_sha256"] == meta["sha256"] and measured["byte_count"] == len(data)
    if "total_samples" in measured:
        assert measured["total_samples"] == RATE and measured["decoded_pcm_bytes"] == len(raw)
        assert measured["decoded_pcm_sha256"] == hashlib.sha256(raw).hexdigest()
    evidence = {"source_sha256": e.source["sha256"], "candidate_sha256": meta["sha256"],
                "independent_decoded_pcm_sha256": hashlib.sha256(raw).hexdigest(),
                "independent_decoded_frames": len(samples) // channels, "measurement": measured}
    return [samples[channel::channels] for channel in range(channels)], raw, evidence


def envelope(index, fade_in, fade_out):
    milliseconds = index * 1000 / RATE
    entering = min(1.0, milliseconds / fade_in) if fade_in else 1.0
    leaving = min(1.0, (DURATION_MS - milliseconds) / fade_out) if fade_out else 1.0
    return max(0.0, entering * leaving)


def retain(tmp_path, evidence, label="audio-fade-observation"):
    (tmp_path / (label + ".json")).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")


def assert_source_and_review(e, result, public_before=1):
    """One explicit promotion, idempotent repeat, and durable original-owner reopen."""
    assert e.service.asset(e.nid, e.scope, e.source["id"]) == e.source
    assert e.service.download(e.nid, e.scope, e.source["id"])[1] == e.original_bytes
    assert hashlib.sha256(e.original_bytes).hexdigest() == e.source["sha256"]
    asset_id = result["output_candidate"]["id"]
    assert len(e.service.list_assets(e.nid, e.scope)["items"]) == public_before
    with pytest.raises(FileNotFoundError):
        e.service.asset(e.nid, e.scope, asset_id)
    e.production = production(e, reopened(e))
    assert get(e, result) == result
    approved = review(e, result)
    assert approved["status"] == "APPROVED" and approved["approved_asset_version"] == 2
    assert approved["media_measurement"] == result["media_measurement"]
    assert len(e.production.workspace.list_assets(e.nid, e.scope)["items"]) == public_before + 1
    assert review(e, approved) == approved
    assert len(e.production.workspace.list_assets(e.nid, e.scope)["items"]) == public_before + 1
    e.production = production(e, reopened(e))
    assert get(e, result) == approved
    assert e.production.workspace.asset(e.nid, e.scope, asset_id)["provenance"]["origin"] == "DERIVED_PROCESSING"
    assert e.chapters.list(e.nid) == []


def assert_lossless_envelope(samples, fade_in, fade_out, evidence, tmp_path):
    # Ignore only ten ms at codec boundaries, retaining both ramps and the entire
    # interior. Eight S16 units cover quantization/resampling phase, not wrong gain.
    indices = range(RATE * 10 // 1000, RATE * 990 // 1000)
    expected = [4000 * envelope(index, fade_in, fade_out) for index in indices]
    maxima = [max(abs(channel[index] - ideal) for index, ideal in zip(indices, expected)) for channel in samples]
    positions = (40, 100, 160, 400, 500, 750, 850, 950)
    evidence.update(fade_in_ms=fade_in, fade_out_ms=fade_out, absolute_lsb_tolerance=LOSSLESS_LSB_TOLERANCE,
                    maximum_absolute_error_per_channel=maxima,
                    observed_samples_by_ms={str(ms): [channel[RATE * ms // 1000] for channel in samples] for ms in positions},
                    expected_samples_by_ms={str(ms): 4000 * envelope(RATE * ms // 1000, fade_in, fade_out) for ms in positions})
    retain(tmp_path, evidence)
    assert all(error <= LOSSLESS_LSB_TOLERANCE for error in maxima), evidence


@pytest.mark.parametrize("format", ["WAV", "FLAC"])
@pytest.mark.parametrize("channels", [1, 2])
def test_actual_lossless_linear_fades_private_review_reopen(rig, native_tools, tmp_path, format, channels):
    e = prepare(rig, channels)
    e.command = fade_command(e, format, channels, fade_in_ms=200, fade_out_ms=300)
    inspected = preview(e)
    assert inspected["provider"] is None and inspected["execution_recipe"]["parameters"] == e.command["parameters"]
    queued = queue(e)
    assert queue(e) == queued and queued["media_measurement"] is None
    result = run(e, queued)
    assert result["status"] == "AWAITING_REVIEW", result
    samples, _, evidence = decode(e, result, tmp_path, native_tools, "faded")
    assert len(samples) == channels
    assert_lossless_envelope(samples, 200, 300, evidence, tmp_path)
    assert_source_and_review(e, result)


@pytest.mark.parametrize("channels", [1, 2])
def test_actual_mp3_linear_fades_gapless_rms(rig, native_tools, tmp_path, channels):
    e = prepare(rig, channels, sine=True)
    e.command = fade_command(e, "MP3", channels, fade_in_ms=200, fade_out_ms=300)
    result = run(e, queue(e))
    assert result["status"] == "AWAITING_REVIEW", result
    samples, _, evidence = decode(e, result, tmp_path, native_tools, "faded")
    assert len(samples) == channels
    assert result["media_measurement"]["profile_validation"] == "MP3_GAPLESS_PCM_VERIFIED"
    # Decoder honors MP3 skip/discard metadata; decode() requires exactly the
    # requested sample count. We neither shift windows nor remove samples to fit.
    # Twenty-ms interior windows contain 20 sine cycles, avoiding codec boundary
    # transients. Ratios cancel normal MP3 amplitude bias, while plateau amplitude
    # independently verifies gain. Expected RMS is sqrt(mean(envelope squared)),
    # NOT the midpoint or arithmetic mean of the ramp.
    windows = ((40, 60), (90, 110), (140, 160), (450, 550), (750, 770), (840, 860), (940, 960))
    observations = []
    for channel in samples:
        middle = channel[RATE * 450 // 1000:RATE * 550 // 1000]
        plateau = math.sqrt(sum(value * value for value in middle) / len(middle))
        rows = []
        for start, end in windows:
            indices = range(RATE * start // 1000, RATE * end // 1000)
            actual = math.sqrt(sum(channel[index] ** 2 for index in indices) / len(indices)) / plateau
            expected = math.sqrt(sum(envelope(index, 200, 300) ** 2 for index in indices) / len(indices))
            rows.append({"start_ms": start, "end_ms": end, "observed_rms_ratio": actual,
                         "expected_rms_ratio": expected, "relative_error": abs(actual - expected) / expected})
        observations.append({"plateau_rms": plateau, "windows": rows})
    evidence.update(relative_rms_tolerance=MP3_RELATIVE_RMS_TOLERANCE, expected_plateau_rms=6000 / math.sqrt(2),
                    channels=observations)
    retain(tmp_path, evidence)
    for observed in observations:
        assert abs(observed["plateau_rms"] / (6000 / math.sqrt(2)) - 1) <= MP3_RELATIVE_RMS_TOLERANCE, evidence
        assert all(row["relative_error"] <= MP3_RELATIVE_RMS_TOLERANCE for row in observed["windows"]), evidence
    assert_source_and_review(e, result)


@pytest.mark.parametrize("fade_in,fade_out", [(0, 300), (200, 0), (400, 600)])
def test_actual_one_sided_and_touching_fades(rig, native_tools, tmp_path, fade_in, fade_out):
    e = prepare(rig)
    e.command = fade_command(e, fade_in_ms=fade_in, fade_out_ms=fade_out)
    result = run(e, queue(e))
    assert result["status"] == "AWAITING_REVIEW", result
    samples, _, evidence = decode(e, result, tmp_path, native_tools, "faded")
    assert_lossless_envelope(samples, fade_in, fade_out, evidence, tmp_path)
    assert_source_and_review(e, result)


@pytest.mark.parametrize("format", ["WAV", "FLAC", "MP3"])
def test_explicit_zero_fades_preserve_decoded_pcm(rig, native_tools, tmp_path, format):
    e = prepare(rig, sine=True)
    e.command = fade_command(e, format)
    omitted_preview = preview(e)
    omitted = run(e, queue(e))
    assert omitted["status"] == "AWAITING_REVIEW", omitted
    _, omitted_pcm, first = decode(e, omitted, tmp_path, native_tools, "omitted")
    e.command = fade_command(e, format, fade_in_ms=0, fade_out_ms=0)
    explicit_preview = preview(e)
    assert explicit_preview["preview_digest"] != omitted_preview["preview_digest"]
    e.command["request_id"] = "explicit-zero-fades"
    explicit = run(e, queue(e))
    assert explicit["status"] == "AWAITING_REVIEW", explicit
    assert explicit["request_digest"] != omitted["request_digest"]
    _, explicit_pcm, second = decode(e, explicit, tmp_path, native_tools, "zero")
    retain(tmp_path, {"omitted": first, "explicit_zero": second, "decoded_pcm_equal": omitted_pcm == explicit_pcm})
    assert explicit_pcm == omitted_pcm
    assert_source_and_review(e, omitted)
    assert_source_and_review(e, explicit, public_before=2)


def test_fade_change_invalidates_reviewed_preview(rig, native_tools):
    e = prepare(rig)
    e.command = fade_command(e, fade_in_ms=200, fade_out_ms=300)
    captured = preview(e)
    for field in ("fade_in_ms", "fade_out_ms"):
        changed = deepcopy(e.command)
        changed["parameters"][field] += 10
        assert preview(e, changed)["preview_digest"] != captured["preview_digest"]
        with pytest.raises(ValueError):
            e.production.create(e.nid, e.scope, e.actor,
                {"command": changed, "reviewed_preview_digest": captured["preview_digest"]}, lambda: None)
    assert len(e.service.list_assets(e.nid, e.scope)["items"]) == 1
