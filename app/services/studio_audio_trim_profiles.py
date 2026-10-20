"""Bounded proof for the original standalone trim owner's explicit FLAC.

RFC 9639 section 8.2 defines STREAMINFO and signed interleaved little-endian
PCM MD5. The checksum is format integrity only; Asset identity remains SHA256.
No queue, provider, scan or arbitrary native command is exposed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil

from ..media_files import MediaValidationError


VALIDATION = "FLAC_STREAMINFO_PCM_VERIFIED"
FIELDS = {"duration_ms", "byte_count", "sample_rate", "channels", "sample_width", "container",
          "audio_codec", "profile_validation", "output_sha256", "total_samples", "decoded_pcm_bytes",
          "streaminfo_md5", "decoded_pcm_sha256"}


def _invalid():
    raise MediaValidationError("STUDIO_AUDIO_FLAC_PROFILE_INVALID")


def streaminfo(data):
    """Validate bounded metadata framing; native decode validates audio frames."""
    if not isinstance(data, bytes) or len(data) < 43 or data[:4] != b"fLaC":
        _invalid()
    position, info = 4, None
    for _ in range(128):
        if position + 4 > len(data) or position > 1_048_576:
            _invalid()
        header = data[position]
        kind, size = header & 127, int.from_bytes(data[position + 1:position + 4], "big")
        position += 4
        if kind == 127 or size > 1_048_576 or position + size > min(len(data), 1_048_576):
            _invalid()
        if info is None:
            if kind != 0 or size != 34:
                _invalid()
            payload = data[position:position + size]
            minimum, maximum = int.from_bytes(payload[:2], "big"), int.from_bytes(payload[2:4], "big")
            packed = int.from_bytes(payload[10:18], "big")
            info = {"sample_rate": packed >> 44, "channels": ((packed >> 41) & 7) + 1,
                    "bits_per_sample": ((packed >> 36) & 31) + 1,
                    "total_samples": packed & ((1 << 36) - 1), "streaminfo_md5": payload[18:34].hex()}
            if not 16 <= minimum <= maximum <= 65535:
                _invalid()
        elif kind == 0:
            _invalid()
        position += size
        if header & 128:
            if position >= len(data) or not 8000 <= info["sample_rate"] <= 96000 or info["channels"] not in {1, 2}:
                _invalid()
            if info["bits_per_sample"] != 16 or info["total_samples"] < 1 or info["streaminfo_md5"] == "0" * 32:
                _invalid()
            return info
    _invalid()


def validate_flac_measurement(value, parameters):
    """Check the durable actual-byte proof without decoding under owner locks."""
    integers = ("duration_ms", "byte_count", "sample_rate", "channels", "sample_width", "total_samples", "decoded_pcm_bytes")
    if (not isinstance(value, dict) or set(value) != FIELDS or parameters.get("output_format") != "FLAC"
            or any(type(value.get(key)) is not int for key in integers)
            or not 0 < value["byte_count"] <= 25 * 1024 * 1024
            or not 0 < value["decoded_pcm_bytes"] <= 25 * 1024 * 1024
            or not 8000 <= value["sample_rate"] <= 96000 or value["channels"] not in {1, 2}
            or value["sample_rate"] != parameters.get("sample_rate", 48000)
            or value["channels"] != parameters.get("channels", 2) or value["sample_width"] != 2
            or value["container"] != "flac" or value["audio_codec"] != "flac" or value["profile_validation"] != VALIDATION
            or value["total_samples"] < 1
            or value["decoded_pcm_bytes"] != value["total_samples"] * value["channels"] * 2
            or value["duration_ms"] < 1
            or value["duration_ms"] != round(value["total_samples"] * 1000 / value["sample_rate"])
            # One decoded sample of rounding allowance, not a lossy-codec claim.
            or abs(value["total_samples"] * 1000 - (parameters["out_ms"] - parameters["in_ms"]) * value["sample_rate"]) > 1000):
        _invalid()
    for key, size in (("output_sha256", 64), ("decoded_pcm_sha256", 64), ("streaminfo_md5", 32)):
        if not isinstance(value[key], str) or not re.fullmatch(r"[0-9a-f]{" + str(size) + r"}", value[key]):
            _invalid()
    if value["streaminfo_md5"] == "0" * 32:
        _invalid()
    return value


def prove_flac(path, data, parameters, *, guard, max_bytes):
    """Probe/decode private local output with original process cancellation."""
    from .studio_timeline_export import run_guarded_process
    guard()
    info = streaminfo(data)
    decoded_bytes = info["total_samples"] * info["channels"] * 2
    if (not 0 < len(data) <= max_bytes or not 0 < decoded_bytes <= max_bytes
            or info["sample_rate"] != parameters.get("sample_rate", 48000)
            or info["channels"] != parameters.get("channels", 2)):
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
    # Native diagnostics retain the original finite stdout/stderr limits.
    # PCM is a capped private file, never the process owner's 1MiB stdout path.
    probe_path, pcm_path = path.parent / "flac-probe.json", path.parent / "flac-decoded.pcm"
    run_guarded_process([probe, "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "a",
        "-show_entries", "stream=codec_name,sample_rate,channels,bits_per_raw_sample", "-of", "json", str(path)],
        cwd=path.parent, guard=guard, timeout=20, stdout_path=probe_path)
    guard()
    try:
        report = json.loads(probe_path.read_text(encoding="utf-8"))
        streams = report["streams"]
        if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
            _invalid()
        actual = streams[0]
        if (actual.get("codec_name") != "flac" or str(actual.get("sample_rate")) != str(info["sample_rate"])
                or type(actual.get("channels")) is not int or actual["channels"] != info["channels"]
                or str(actual.get("bits_per_raw_sample")) != "16"):
            _invalid()
    except (KeyError, TypeError, ValueError):
        _invalid()
    guard()
    run_guarded_process([decoder, "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode+crccheck",
        "-threads", "1", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-c:a", "pcm_s16le", "-f", "s16le", "-fs", str(max_bytes + 1), str(pcm_path)],
        cwd=path.parent, guard=guard, timeout=30)
    guard()
    if not pcm_path.is_file() or pcm_path.stat().st_size != decoded_bytes:
        _invalid()
    md5, sha, size = hashlib.md5(usedforsecurity=False), hashlib.sha256(), 0
    with pcm_path.open("rb") as pcm:
        while chunk := pcm.read(65536):
            guard()
            size += len(chunk)
            if size > max_bytes:
                _invalid()
            md5.update(chunk); sha.update(chunk)
    guard()
    if size != decoded_bytes or md5.hexdigest() != info["streaminfo_md5"]:
        _invalid()
    file_current()
    measured = {"duration_ms": round(info["total_samples"] * 1000 / info["sample_rate"]), "byte_count": len(data),
        "sample_rate": info["sample_rate"], "channels": info["channels"], "sample_width": 2, "container": "flac",
        "audio_codec": "flac", "profile_validation": VALIDATION, "output_sha256": output_sha256,
        "total_samples": info["total_samples"], "decoded_pcm_bytes": size, "streaminfo_md5": info["streaminfo_md5"],
        "decoded_pcm_sha256": sha.hexdigest()}
    validate_flac_measurement(measured, parameters)
    return {**measured, "media_type": "audio/flac", "extension": "flac", "validation": VALIDATION}
