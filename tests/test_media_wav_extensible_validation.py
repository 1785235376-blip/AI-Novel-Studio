"""Bounded RIFF/WAVE validation, including WAVE_FORMAT_EXTENSIBLE PCM.

Python 3.11's wave module rejects WAVE_FORMAT_EXTENSIBLE, which real ffmpeg output uses for
96 kHz pcm_s16le. The product advertises 8000-96000 Hz PCM trim profiles, so the media validator
must accept extensible integer PCM while still rejecting non-PCM and truncated input.
"""
from __future__ import annotations

import struct
import wave
from io import BytesIO

import pytest

from app.media_files import MediaValidationError, _wav_pcm_metadata, inspect_media, normalize_pcm_wav


def classic_wav(rate=48000, channels=2, width=2, frames=480) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(width)
        writer.setframerate(rate)
        writer.writeframes(b"\x00" * (frames * channels * width))
    return output.getvalue()


def extensible_wav(rate=96000, channels=2, width_bytes=2, frames=67200) -> bytes:
    block = channels * width_bytes
    data = b"\x01\x00" * (frames * channels)
    fmt = struct.pack(
        "<HHIIHHHHI",
        0xFFFE, channels, rate, rate * block, block, width_bytes * 8, 22, width_bytes * 8, 3,
    ) + b"\x01\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


def test_python311_wave_rejects_extensible_but_validator_accepts_it():
    payload = extensible_wav()
    with pytest.raises(Exception):
        wave.open(BytesIO(payload), "rb")
    info = inspect_media(payload, "audio")
    assert info == {
        "media_type": "audio/wav", "extension": "wav", "duration_ms": 700,
        "sample_rate": 96000, "channels": 2, "sample_width": 2, "validation": "PCM_DECODED",
    }


def test_classic_pcm_wav_still_validates_identically():
    info = inspect_media(classic_wav(), "audio")
    assert (info["sample_rate"], info["channels"], info["sample_width"]) == (48000, 2, 2)


def test_truncated_extensible_data_is_rejected():
    payload = extensible_wav()
    with pytest.raises(MediaValidationError):
        inspect_media(payload[:-10], "audio")


def test_non_pcm_extensible_subformat_is_rejected():
    payload = bytearray(extensible_wav())
    fmt_offset = payload.index(b"fmt ")
    payload[fmt_offset + 8 + 24:fmt_offset + 8 + 26] = b"\x03\x00"  # IEEE float subformat
    with pytest.raises(MediaValidationError):
        inspect_media(bytes(payload), "audio")


def test_unknown_list_chunk_before_data_is_tolerated_but_bad_sizes_are_not():
    payload = extensible_wav()
    list_chunk = b"LIST" + struct.pack("<I", 4) + b"INFO"
    insertion = payload.index(b"data")
    patched = bytearray(payload[:insertion] + list_chunk + payload[insertion:])
    patched[4:8] = struct.pack("<I", len(patched) - 8)
    assert inspect_media(bytes(patched), "audio")["duration_ms"] == 700
    broken = bytes(patched)
    assert _wav_pcm_metadata(broken)["_frames"] == 67200
    with pytest.raises(MediaValidationError):
        inspect_media(broken[:len(broken) - 4], "audio")


def test_normalize_pcm_wav_rewrites_extensible_to_classic_and_preserves_payload():
    payload = extensible_wav()
    source = _wav_pcm_metadata(payload)
    normalized = normalize_pcm_wav(payload)
    target = _wav_pcm_metadata(normalized)
    assert target["_format_tag"] == 1
    assert (target["sample_rate"], target["channels"], target["sample_width"]) == (96000, 2, 2)
    assert target["_frames"] == source["_frames"]
    source_payload = payload[source["_payload_offset"]:source["_payload_offset"] + source["_payload_size"]]
    target_payload = normalized[target["_payload_offset"]:target["_payload_offset"] + target["_payload_size"]]
    assert target_payload == source_payload
    with wave.open(BytesIO(normalized), "rb") as decoded:
        assert decoded.getframerate() == 96000 and decoded.getnchannels() == 2


def test_normalize_pcm_wav_passes_classic_pcm_through_unchanged():
    payload = classic_wav()
    assert normalize_pcm_wav(payload) == payload

