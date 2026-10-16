"""Bounded MP3 proof for the existing standalone trim owner.

CBR is 128 kb/s for MPEG-1 rates and 64 kb/s for lower rates. The S16
measurement describes decoded PCM, never MP3 bit depth or lossless equality.
Clips must be at least 10 ms (shorter LAME outputs can decode to 47 samples).
A seekable LAME/Xing header preserves gapless timing. Container frame padding
may add up to three frames; decoded duration must match within one sample.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil

from ..media_files import MediaValidationError

SAMPLE_RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)
VALIDATION = "MP3_GAPLESS_PCM_VERIFIED"
FIELDS = {"duration_ms", "byte_count", "sample_rate", "channels", "sample_width", "container",
          "audio_codec", "profile_validation", "output_sha256", "total_samples", "decoded_pcm_bytes",
          "decoded_pcm_sha256", "bit_rate", "container_duration_ms"}


def bit_rate(rate):
    return 128000 if rate >= 32000 else 64000


def _invalid():
    raise MediaValidationError("STUDIO_AUDIO_MP3_PROFILE_INVALID")


def encoder_available(executable, directory, guard):
    from .studio_timeline_export import run_guarded_process
    if not shutil.which("ffprobe"):
        return False
    report = Path(directory) / "mp3-encoders.txt"
    run_guarded_process([executable, "-nostdin", "-hide_banner", "-encoders"], cwd=directory,
                        guard=guard, timeout=10, stdout_path=report)
    guard()
    return any(len(parts := line.split()) >= 2 and parts[1] == "libmp3lame" and parts[0].startswith("A")
               for line in report.read_text(encoding="utf-8").splitlines())


def validate_mp3_measurement(value, parameters):
    integers = FIELDS - {"container", "audio_codec", "profile_validation", "output_sha256", "decoded_pcm_sha256"}
    if (not isinstance(value, dict) or set(value) != FIELDS or parameters.get("output_format") != "MP3"
            or parameters["out_ms"] - parameters["in_ms"] < 10
            or any(type(value.get(key)) is not int for key in integers)
            or not 0 < value["byte_count"] <= 25 * 1024 * 1024
            or not 0 < value["decoded_pcm_bytes"] <= 25 * 1024 * 1024
            or value["sample_rate"] not in SAMPLE_RATES or value["channels"] not in {1, 2}
            or value["sample_rate"] != parameters.get("sample_rate", 48000)
            or value["channels"] != parameters.get("channels", 2) or value["sample_width"] != 2
            or value["bit_rate"] != bit_rate(value["sample_rate"])
            or value["container"] != "mp3" or value["audio_codec"] != "mp3" or value["profile_validation"] != VALIDATION
            or value["total_samples"] < 1
            or value["decoded_pcm_bytes"] != value["total_samples"] * value["channels"] * 2
            or value["duration_ms"] < 1
            or value["duration_ms"] != round(value["total_samples"] * 1000 / value["sample_rate"])
            or abs(value["total_samples"] * 1000 - (parameters["out_ms"] - parameters["in_ms"]) * value["sample_rate"]) > 1000):
        _invalid()
    # MP3 containers include encoder delay/frame padding. This tolerance is
    # separate from decoded gapless duration and does not hide resampling.
    frame = 1152 if value["sample_rate"] >= 32000 else 576
    if not -1 <= value["container_duration_ms"] - value["duration_ms"] <= math.ceil(3000 * frame / value["sample_rate"]) + 2:
        _invalid()
    if any(not isinstance(value[key], str) or not re.fullmatch(r"[0-9a-f]{64}", value[key])
           for key in ("output_sha256", "decoded_pcm_sha256")):
        _invalid()
    return value


def prove_mp3(path, data, parameters, *, guard, max_bytes):
    """Probe actual stream and decode capped private PCM with original guards."""
    from .studio_timeline_export import run_guarded_process
    guard()
    if (not isinstance(data, bytes) or not 0 < len(data) <= max_bytes
            or not (data[:3] == b"ID3" or len(data) > 1 and data[0] == 255 and data[1] & 224 == 224)):
        _invalid()
    probe, decoder = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not probe or not decoder:
        raise MediaValidationError("MEDIA_VALIDATOR_NOT_CONFIGURED")
    path = Path(path)
    output_sha256 = hashlib.sha256(data).hexdigest()
    def file_current():
        guard()
        if not path.is_file() or path.stat().st_size != len(data):
            _invalid()
        actual, size = hashlib.sha256(), 0
        with path.open("rb") as stream:
            while chunk := stream.read(65536):
                guard(); size += len(chunk)
                if size > max_bytes:
                    _invalid()
                actual.update(chunk)
        if size != len(data) or actual.hexdigest() != output_sha256:
            _invalid()
    file_current()
    probe_path, pcm_path = path.parent / "mp3-probe.json", path.parent / "mp3-decoded.pcm"
    run_guarded_process([probe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries",
        "stream=codec_name,codec_type,sample_rate,channels,bit_rate,duration:format=format_name", "-of", "json", str(path)],
        cwd=path.parent, guard=guard, timeout=20, stdout_path=probe_path)
    guard()
    try:
        report = json.loads(probe_path.read_text(encoding="utf-8"))
        streams = report["streams"]
        if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
            _invalid()
        actual = streams[0]
        rate, channels = parameters.get("sample_rate", 48000), parameters.get("channels", 2)
        if (report["format"]["format_name"] != "mp3" or actual.get("codec_type") != "audio"
                or actual.get("codec_name") != "mp3" or str(actual.get("sample_rate")) != str(rate)
                or type(actual.get("channels")) is not int or actual["channels"] != channels
                or str(actual.get("bit_rate")) != str(bit_rate(rate))):
            _invalid()
        duration = float(actual["duration"])
        if not math.isfinite(duration) or duration <= 0:
            _invalid()
        container_duration = round(duration * 1000)
    except (KeyError, TypeError, ValueError):
        _invalid()
    run_guarded_process([decoder, "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode+crccheck",
        "-threads", "1", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-c:a", "pcm_s16le", "-f", "s16le", "-fs", str(max_bytes + 1), str(pcm_path)],
        cwd=path.parent, guard=guard, timeout=30)
    guard()
    if not pcm_path.is_file() or not 0 < pcm_path.stat().st_size <= max_bytes or pcm_path.stat().st_size % (channels * 2):
        _invalid()
    sha, size = hashlib.sha256(), 0
    with pcm_path.open("rb") as pcm:
        while chunk := pcm.read(65536):
            guard(); size += len(chunk)
            if size > max_bytes:
                _invalid()
            sha.update(chunk)
    file_current()
    samples = size // (channels * 2)
    measured = {"duration_ms": round(samples * 1000 / rate), "byte_count": len(data), "sample_rate": rate,
        "channels": channels, "sample_width": 2, "container": "mp3", "audio_codec": "mp3",
        "profile_validation": VALIDATION, "output_sha256": output_sha256, "total_samples": samples,
        "decoded_pcm_bytes": size, "decoded_pcm_sha256": sha.hexdigest(), "bit_rate": bit_rate(rate),
        "container_duration_ms": container_duration}
    validate_mp3_measurement(measured, parameters)
    return {**measured, "media_type": "audio/mpeg", "extension": "mp3", "validation": VALIDATION}
