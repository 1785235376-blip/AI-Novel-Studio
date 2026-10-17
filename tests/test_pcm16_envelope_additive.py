"""Synthetic pure PCM contracts; no native decoder, provider or persistent owner."""
import array
import io
import struct
import sys
import wave

import pytest

from app.services.pcm16_envelope import pcm16_envelope


def wav_bytes(samples, channels=1, rate=1000):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels); wav.setsampwidth(2); wav.setframerate(rate)
        wav.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return output.getvalue()


def legacy_result(data):
    with wave.open(io.BytesIO(data), "rb") as wav:
        frames, channels = wav.getnframes(), wav.getnchannels()
        samples = array.array("h", wav.readframes(frames))
        if sys.byteorder != "little": samples.byteswap()
        stride = max(1, (frames + 511) // 512)
        return {"samples_per_bucket": stride,
                "peaks": [max((abs(v) for v in samples[i * channels:min(frames, i + stride) * channels]), default=0) / 32768
                          for i in range(0, frames, stride)]}


@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("frames", [0, 1, 3, 511, 512, 513, 1025])
def test_legacy_exact_peak_parity(channels, frames):
    samples = [(-32768, 0, 32767, -12345)[i % 4] for i in range(frames * channels)]
    data = wav_bytes(samples, channels)
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert pcm16_envelope(wav) == legacy_result(data)


@pytest.mark.parametrize("removed", [2, 3, 12])
def test_legacy_truncation_behavior_is_unchanged(removed):
    data = wav_bytes([1000] * 12)[:-removed]
    with wave.open(io.BytesIO(data), "rb") as wav:
        if removed % 2:
            with pytest.raises(ValueError): legacy_result(data)
            with pytest.raises(ValueError): pcm16_envelope(wav)
        else:
            assert pcm16_envelope(wav) == legacy_result(data)


def test_strict_selected_half_open_interval_excludes_outside_extrema():
    data = wav_bytes([-32768, 10, 20, 30, 32767])
    with wave.open(io.BytesIO(data), "rb") as wav:
        result = pcm16_envelope(wav, frame_start=1, frame_end=4, strict=True)
    assert result == {"samples_per_bucket": 1, "peaks": [10 / 32768, 20 / 32768, 30 / 32768]}


def test_strict_stereo_combines_channels_and_last_partial_bucket():
    samples = [0] * (1025 * 2)
    samples[1] = -32768; samples[-1] = 16384
    with wave.open(io.BytesIO(wav_bytes(samples, 2)), "rb") as wav:
        result = pcm16_envelope(wav, strict=True)
    assert result["samples_per_bucket"] == 3
    assert len(result["peaks"]) == 342
    assert result["peaks"][0] == 1 and result["peaks"][-1] == 0.5
    assert set(result["peaks"][1:-1]) == {0}


@pytest.mark.parametrize("removed", [1, 2, 3, 12])
def test_strict_validates_whole_source_after_early_selected_interval(removed):
    data = wav_bytes([1] * 100)[:-removed]
    with wave.open(io.BytesIO(data), "rb") as wav:
        with pytest.raises(ValueError, match="STUDIO_WAVEFORM_INVALID"):
            pcm16_envelope(wav, frame_start=0, frame_end=1, strict=True)


def test_strict_rejects_partial_frame_remainder():
    data = bytearray(wav_bytes([1, 2, 3]))
    data.extend(b"x")
    struct.pack_into("<I", data, 4, len(data) - 8)
    struct.pack_into("<I", data, 40, 7)
    with wave.open(io.BytesIO(data), "rb") as wav:
        with pytest.raises(ValueError, match="STUDIO_WAVEFORM_INVALID"):
            pcm16_envelope(wav, strict=True)


def test_chunk_bound_and_revocation_are_enforced():
    data = wav_bytes([100] * 40000)
    with wave.open(io.BytesIO(data), "rb") as wav:
        reads = []
        original = wav.readframes
        def read(count):
            reads.append(count)
            return original(count)
        wav.readframes = read
        calls = 0
        def guard():
            nonlocal calls
            calls += 1
            if calls == 3: raise PermissionError("revoked")
        with pytest.raises(PermissionError, match="revoked"):
            pcm16_envelope(wav, strict=True, guard=guard)
    assert reads == [32768]


@pytest.mark.parametrize("start,end", [(0, 0), (-1, 1), (1, 4), (True, 2), (0, False)])
def test_strict_range_bounds(start, end):
    with wave.open(io.BytesIO(wav_bytes([1, 2, 3])), "rb") as wav:
        with pytest.raises(ValueError, match="STUDIO_WAVEFORM_CLIP_RANGE_INVALID"):
            pcm16_envelope(wav, frame_start=start, frame_end=end, strict=True)
