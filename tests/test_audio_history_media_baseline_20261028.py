"""Synthetic real-media import/read baseline; not audio-version-history acceptance."""
import hashlib
import io
import json
import shutil
import struct
import subprocess
import wave

import pytest

from test_studio_canvas_audio_return import rig, import_asset, reopened


def _run(*args):
    return subprocess.run(args, capture_output=True, check=True, timeout=30).stdout


def test_synthetic_pcm_wav_and_flac_import_and_reopen(rig, tmp_path):
    if rig.backend != "file":
        pytest.skip("this baseline validates the File project and File asset owners only")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("installed ffmpeg and ffprobe are required")
    frames = b"".join(struct.pack("<hh", (i % 100 - 50) * 400, (50 - i % 100) * 300)
                      for i in range(24000))
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(frames)
    source = tmp_path / "synthetic.wav"
    flac = tmp_path / "synthetic.flac"
    source.write_bytes(output.getvalue())
    _run(ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(source), "-c:a", "flac", str(flac))

    for path, codec, media_type in ((source, "pcm_s16le", "audio/wav"), (flac, "flac", "audio/flac")):
        original = path.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        info = json.loads(_run(ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries",
                               "stream=codec_name,sample_rate,channels,duration:format=duration", "-of", "json", str(path)))
        stream = info["streams"][0]
        assert (stream["codec_name"], int(stream["sample_rate"]), stream["channels"]) == (codec, 48000, 2)
        assert abs(float(stream.get("duration") or info["format"]["duration"]) - 0.5) < 0.001
        decoded = _run(ffmpeg, "-nostdin", "-v", "error", "-i", str(path), "-f", "s16le", "-acodec", "pcm_s16le", "-")
        assert decoded == frames
        row = import_asset(rig, data=original, filename=path.name, kind="audio", key="media-baseline-" + codec)
        assert (row["kind"], row["media_type"], row["size"], row["sha256"]) == ("audio", media_type, len(original), digest)
        again = reopened(rig)
        metadata, actual = again.download(rig.nid, rig.scope, row["id"])
        assert actual == original and hashlib.sha256(actual).hexdigest() == digest
        assert (metadata["id"], metadata["version"], metadata["sha256"], metadata["media_type"]) == (
            row["id"], row["version"], digest, media_type)
        print(json.dumps({"format": codec, "bytes": len(original), "sha256": digest,
                          "sample_rate": 48000, "channels": 2, "duration_seconds": 0.5,
                          "decoded_pcm_sha256": hashlib.sha256(decoded).hexdigest()}, sort_keys=True))
