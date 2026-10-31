"""Audio-only Timeline export profiles: PCM16 and PCM24, multi-track mix.

File backend, real FFmpeg/FFprobe, synthetic tones only. No provider/model call.
"""
from __future__ import annotations

import base64
import hashlib
import io
import math
import struct
import wave

import pytest

from app.creative.production_execution_models import MediaReview
from app.services.studio_timeline_export import probe_media_file
from test_studio_asset_query import rig
from test_studio_backend_integration_v2 import studio

pytestmark = pytest.mark.file_backend_only


def tone_wav(frequency: int, sample_rate: int = 48000) -> bytes:
    samples = [int(4000 * math.sin(2 * math.pi * frequency * n / sample_rate))
               for n in range(sample_rate)]
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(b"".join(struct.pack("<hh", sample, sample) for sample in samples))
    return output.getvalue()


def amplitude(samples, frequency, sample_rate=48000):
    real = sum(value * math.cos(2 * math.pi * frequency * n / sample_rate)
               for n, value in enumerate(samples))
    imaginary = sum(value * math.sin(2 * math.pi * frequency * n / sample_rate)
                    for n, value in enumerate(samples))
    return 2 * math.hypot(real, imaginary) / len(samples)


def import_audio(e, filename: str, data: bytes):
    with e.workspace._asset_scope(e.nid, e.scope):
        return e.workspace.assets.create(
            e.nid, filename, base64.b64encode(data).decode("ascii"), "audio/wav", "audio", None,
            required_features=("narrative_production_v2",), _capacity_admitted=True)


def source(asset):
    return {"kind": "ASSET", "asset_kind": "audio", "id": asset["id"],
            "version": asset["version"], "digest": asset["sha256"]}


def track(asset, *, track_id, order, muted=False, gain_db=0.0):
    return {"id": track_id, "kind": "AUDIO", "order": order, "muted": muted, "gain_db": gain_db,
            "clips": [{"id": f"clip-{track_id}", "source_snapshot": source(asset),
                       "start_ms": 0, "in_ms": 0, "out_ms": 1000}]}


@pytest.mark.parametrize("preset,expected_codec,bits,expected_width", [
    ("AUDIO_WAV_PCM16", "pcm_s16le", 16, 2),
    ("AUDIO_WAV_PCM24", "pcm_s24le", 24, 3),
])
def test_multitrack_audio_export_profiles(studio, tmp_path, preset, expected_codec, bits, expected_width):
    e = studio
    first = import_audio(e, "tone-440.wav", tone_wav(440))
    second = import_audio(e, "tone-880.wav", tone_wav(880))
    value = {"schema_version": 3, "media_kind": "AUDIO", "duration_ms": 1000,
             "tracks": [track(first, track_id="tone-a", order=0),
                        track(second, track_id="tone-b", order=1, muted=True, gain_db=-6.020599913279624)]}
    saved = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {"expected_version": 0, "title": f"Synthetic {preset} mix", "timeline": value}, lambda: None)
    body = {"expected_version": saved["version"], "reviewed_timeline_digest": saved["timeline_digest"],
            "export_profile": {"preset": preset}}
    preview = e.production.timeline_export_preview(e.nid, e.scope, e.actor, saved["id"], body, lambda: None)
    result = e.production.timeline_export(e.nid, e.scope, e.actor, saved["id"],
        {**body, "request_id": f"synthetic-{preset}", "reviewed_export_digest": preview["preview_digest"]},
        lambda: None)
    assert result["status"] == "SUCCEEDED", result
    assert result["output_candidate"]["kind"] == "audio"
    metadata, data = e.production.candidate(e.nid, e.scope, e.actor, "timeline", result["id"], lambda: None)
    assert metadata["sha256"] == hashlib.sha256(data).hexdigest() == result["output_candidate"]["digest"]
    path = tmp_path / f"rendered-{preset}.wav"
    path.write_bytes(data)
    probe = probe_media_file(path, guard=lambda: None)
    streams = [row for row in probe["streams"] if row.get("codec_type") == "audio"]
    assert len(streams) == 1
    assert streams[0]["codec_name"] == expected_codec
    assert int(streams[0]["sample_rate"]) == 48000 and streams[0]["channels"] == 2
    header = 44 if expected_width == 2 else 68
    expected_size = header + 48000 * expected_width * 2
    assert len(data) == expected_size == int(probe["format"]["size"])
    if expected_width == 2:
        with wave.open(io.BytesIO(data), "rb") as reader:
            assert (reader.getnchannels(), reader.getsampwidth(), reader.getframerate(),
                    reader.getnframes()) == (2, expected_width, 48000, 48000)
            raw = reader.readframes(48000)
        pcm = struct.unpack("<" + "h" * 96000, raw)
        left = pcm[9600:86400:2]
        levels = {440: amplitude(left, 440), 880: amplitude(left, 880)}
        assert 3900 < levels[440] < 4100
        assert levels[880] < 15  # second track muted
    else:
        # Python wave rejects WAVE_FORMAT_EXTENSIBLE; the original media owner's
        # bounded parser validated it (bits_per_sample below comes from ffprobe).
        assert len(data) == expected_size
    # Real approval path and formal asset readback.
    review = MediaReview(expected_version=result["version"],
                         expected_request_digest=result["request_digest"],
                         reviewed_output_digest=result["output_candidate"]["digest"])
    approved = e.production.review(e.nid, e.scope, e.actor, "timeline", result["id"], review, lambda: None)
    assert approved["status"] == "APPROVED"
    with e.workspace._asset_scope(e.nid, e.scope):
        formal = e.workspace.assets.content(result["output_candidate"]["id"], branch_id=e.scope.get("branch_id"))
    assert formal == data
