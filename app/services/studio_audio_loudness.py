"""Bounded PCM16 loudness proof for the original standalone audio job owner.

loudnorm is an input meter only: discard its output, then use the existing trim
owner's fixed volume stage. Never allow its dynamic fallback into a candidate.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import wave

from .audiobook_service import AudiobookError

CONTRACT = "studio-audio-loudness-match/1"
METHOD = "FFMPEG_LOUDNORM_INPUT/1"
CEILING = -1.0
TOLERANCE = 0.2
FIELDS = {"contract", "method", "source_id", "source_version", "source_sha256", "in_ms", "out_ms",
    "sample_rate", "channels", "target_lufs", "input_lufs", "output_lufs", "input_true_peak_dbtp",
    "output_true_peak_dbtp", "applied_gain_db", "true_peak_ceiling_dbtp", "tolerance_lu",
    "selected_pcm_sha256", "selected_frames", "source_peak_s16", "output_pcm_sha256", "output_frames",
    "output_peak_s16", "output_sha256"}


def fail(suffix, status=400):
    raise AudiobookError("STUDIO_AUDIO_LOUDNESS_" + suffix, "Loudness matching: " + suffix.lower().replace("_", " "), status)


def validate_parameters(parameters):
    target = parameters["target_lufs"]
    if type(target) not in {int, float} or not math.isfinite(target) or not -30 <= target <= -14:
        fail("TARGET_INVALID")
    if ("target_peak_dbfs" in parameters or "output_format" in parameters
            or any(parameters.get(key, 0) != 0 for key in ("gain_db", "fade_in_ms", "fade_out_ms"))):
        fail("EXCLUSIVE_PCM_WAV_REQUIRED")
    if parameters["out_ms"] - parameters["in_ms"] < 3000:
        fail("INTERVAL_TOO_SHORT")


def pcm(data, parameters, guard, *, selected):
    """Scan only bounded original PCM frames; preserve channel order and samples."""
    rate, channels = parameters.get("sample_rate", 48000), parameters.get("channels", 2)
    if parameters["in_ms"] * rate % 1000 or parameters["out_ms"] * rate % 1000:
        fail("FRAME_ALIGNMENT_REQUIRED")
    first = parameters["in_ms"] * rate // 1000 if selected else 0
    frames = (parameters["out_ms"] - parameters["in_ms"]) * rate // 1000
    digest, peak, parts = hashlib.sha256(), 0, []
    try:
        with wave.open(io.BytesIO(data), "rb") as stream:
            if (stream.getcomptype() != "NONE" or stream.getsampwidth() != 2
                    or stream.getframerate() != rate or stream.getnchannels() != channels
                    or stream.getnframes() < first + frames or not selected and stream.getnframes() != frames):
                fail("SAME_PCM16_PROFILE_REQUIRED")
            stream.setpos(first)
            remaining = frames
            while remaining:
                guard()
                count = min(8192, remaining)
                chunk = stream.readframes(count)
                if len(chunk) != count * channels * 2:
                    fail("PCM_TRUNCATED")
                peak = max(peak, max(abs(sample[0]) for sample in struct.iter_unpack("<h", chunk)))
                digest.update(chunk)
                if selected: parts.append(chunk)
                remaining -= count
    except (wave.Error, EOFError):
        fail("SAME_PCM16_PROFILE_REQUIRED")
    guard()
    if peak == 0: fail("SILENCE")
    if peak >= 32767: fail("CLIPPING_RISK")
    return {"pcm_sha256": digest.hexdigest(), "frames": frames, "peak_s16": peak}, b"".join(parts)


def measure(path, executable, directory, guard, name):
    from .studio_timeline_export import run_guarded_process
    stats = Path(directory) / (name + "-loudness.json")
    try:
        # Stats stdout is bounded/drained by the original guarded runner. The
        # null muxer consumes measured filter output; it is never a candidate.
        run_guarded_process([executable, "-nostdin", "-v", "error", "-xerror", "-threads", "1",
            "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
            "-af", "loudnorm=I=-23:TP=-1:LRA=7:dual_mono=false:print_format=json:stats_file=-",
            "-f", "null", str(Path(directory) / (name + "-discard"))],
            cwd=directory, guard=guard, timeout=50, stdout_path=stats)
    except (subprocess.CalledProcessError, FileNotFoundError):
        fail("METER_UNAVAILABLE", 501)
    guard()
    try:
        if not 0 < stats.stat().st_size <= 16384: fail("METER_UNAVAILABLE", 501)
        result = json.loads(stats.read_text(encoding="utf-8"))
        if not isinstance(result, dict): fail("METER_UNAVAILABLE", 501)
        integrated, peak = float(result["input_i"]), float(result["input_tp"])
    except (ValueError, KeyError, TypeError, OSError):
        fail("METER_UNAVAILABLE", 501)
    if not math.isfinite(integrated) or not math.isfinite(peak): fail("NONFINITE_MEASUREMENT")
    if not -70 <= integrated <= 0 or not -99 <= peak <= 3: fail("UNMEASURABLE")
    return integrated, peak


def prepare(data, parameters, source, executable, directory, guard):
    validate_parameters(parameters)
    selected, samples = pcm(data, parameters, guard, selected=True)
    path = Path(directory) / "selected-pcm.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(parameters.get("channels", 2)); output.setsampwidth(2)
        output.setframerate(parameters.get("sample_rate", 48000)); output.writeframes(samples)
    integrated, peak = measure(path, executable, directory, guard, "input")
    gain = parameters["target_lufs"] - integrated
    if not -60 <= gain <= 12: fail("GAIN_OUT_OF_RANGE")
    # Reserve 0.1 dB beyond the published -1 dBTP ceiling for metering and
    # integer quantization. Re-measure actual encoded PCM before publication.
    if peak + gain > CEILING - 0.1: fail("TRUE_PEAK_HEADROOM_REQUIRED")
    return path, {"contract": CONTRACT, "method": METHOD, "source_id": source["id"],
        "source_version": source["version"], "source_sha256": source["digest"],
        **{key: parameters[key] for key in ("in_ms", "out_ms", "target_lufs")},
        "sample_rate": parameters.get("sample_rate", 48000), "channels": parameters.get("channels", 2),
        "input_lufs": integrated, "input_true_peak_dbtp": peak, "applied_gain_db": gain,
        "true_peak_ceiling_dbtp": CEILING, "tolerance_lu": TOLERANCE,
        "selected_pcm_sha256": selected["pcm_sha256"], "selected_frames": selected["frames"],
        "source_peak_s16": selected["peak_s16"]}


def finish(path, data, prepared, parameters, executable, directory, guard):
    actual, _ = pcm(data, parameters, guard, selected=False)
    integrated, peak = measure(path, executable, directory, guard, "output")
    if peak > CEILING: fail("CLIPPING_RISK")
    if abs(integrated - parameters["target_lufs"]) > TOLERANCE: fail("TARGET_UNREACHABLE")
    result = {**prepared, "output_lufs": integrated, "output_true_peak_dbtp": peak,
        "output_pcm_sha256": actual["pcm_sha256"], "output_frames": actual["frames"],
        "output_peak_s16": actual["peak_s16"], "output_sha256": hashlib.sha256(data).hexdigest()}
    return validate_proof(result, parameters, result["output_sha256"])


def validate_proof(value, parameters, output_sha256, source=None):
    def invalid(): fail("PROOF_INVALID", 409)
    if not isinstance(value, dict) or set(value) != FIELDS: invalid()
    integers = ("source_version", "in_ms", "out_ms", "sample_rate", "channels", "selected_frames", "source_peak_s16", "output_frames", "output_peak_s16")
    numbers = ("target_lufs", "input_lufs", "output_lufs", "input_true_peak_dbtp", "output_true_peak_dbtp", "applied_gain_db", "true_peak_ceiling_dbtp", "tolerance_lu")
    if any(type(value[k]) is not int for k in integers): invalid()
    if any(type(value[k]) not in {int, float} or not math.isfinite(value[k]) for k in numbers): invalid()
    if any(not isinstance(value[k], str) or not re.fullmatch(r"[a-f0-9]{64}", value[k]) for k in ("source_sha256", "selected_pcm_sha256", "output_pcm_sha256", "output_sha256")): invalid()
    if not isinstance(value["source_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", value["source_id"]): invalid()
    rate = parameters.get("sample_rate", 48000)
    if (value["contract"] != CONTRACT or value["method"] != METHOD or value["source_version"] < 1
            or value["in_ms"] != parameters["in_ms"] or value["out_ms"] != parameters["out_ms"]
            or value["sample_rate"] != rate or value["channels"] != parameters.get("channels", 2)
            or value["in_ms"] * rate % 1000 or value["out_ms"] * rate % 1000
            or value["selected_frames"] != (value["out_ms"] - value["in_ms"]) * rate // 1000
            or value["output_frames"] != value["selected_frames"] or value["selected_frames"] < 1
            or not 0 < value["source_peak_s16"] < 32767 or not 0 < value["output_peak_s16"] < 32767
            or value["target_lufs"] != parameters["target_lufs"] or not -30 <= value["target_lufs"] <= -14
            or value["true_peak_ceiling_dbtp"] != CEILING or value["tolerance_lu"] != TOLERANCE
            or not -60 <= value["applied_gain_db"] <= 12 or not -70 <= value["input_lufs"] <= 0
            or abs(value["applied_gain_db"] - (value["target_lufs"] - value["input_lufs"])) > 1e-9
            or abs(value["output_lufs"] - value["target_lufs"]) > TOLERANCE
            or not -99 <= value["input_true_peak_dbtp"] <= 3
            or not -99 <= value["output_true_peak_dbtp"] <= CEILING
            or value["input_true_peak_dbtp"] + value["applied_gain_db"] > CEILING - 0.1
            or abs(value["output_true_peak_dbtp"] - value["input_true_peak_dbtp"] - value["applied_gain_db"]) > 0.15
            or value["output_sha256"] != output_sha256): invalid()
    if source is not None and (value["source_id"], value["source_version"], value["source_sha256"]) != (source["id"], source["version"], source["digest"]): invalid()
    return value
