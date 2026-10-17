"""Pure PCM16 envelope measurement shared with the original subtitle owner.

The compatibility path intentionally retains the subtitle algorithm, including
its malformed-input behavior. Strict callers opt into bounded full-data reads.
No file paths, media probes, native tools or persistence are used here.
"""
from __future__ import annotations

import array
import sys


def _samples(data):
    samples = array.array("h", data)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _peak(samples):
    return max((abs(value) for value in samples), default=0) / 32768


def pcm16_envelope(wav, *, frame_start=0, frame_end=None, strict=False, guard=lambda: None):
    frames, channels = wav.getnframes(), wav.getnchannels()
    if not strict:
        # Preserve the original B04 read, stride, slicing and exception behavior.
        samples = _samples(wav.readframes(frames))
        stride = max(1, (frames + 511) // 512)
        peaks = [_peak(samples[i * channels:min(frames, i + stride) * channels])
                 for i in range(0, frames, stride)]
        return {"samples_per_bucket": stride, "peaks": peaks}

    end = frames if frame_end is None else frame_end
    if (type(frames) is not int or type(channels) is not int or channels not in (1, 2)
            or not 0 < frames * channels <= 4194304
            or type(frame_start) is not int or type(end) is not int
            or not 0 <= frame_start < end <= frames):
        raise ValueError("STUDIO_WAVEFORM_CLIP_RANGE_INVALID")
    stride = max(1, (end - frame_start + 511) // 512)
    peaks = [0.0] * ((end - frame_start + stride - 1) // stride)
    wav.rewind()
    # Validate ALL declared PCM frames, even for an early selected interval.
    chunk_frames = 32768 // channels
    for position in range(0, frames, chunk_frames):
        guard()
        count = min(chunk_frames, frames - position)
        block = wav.readframes(count)
        if len(block) != count * channels * 2:
            raise ValueError("STUDIO_WAVEFORM_INVALID")
        samples = _samples(block)
        cursor, stop = max(position, frame_start), min(position + count, end)
        while cursor < stop:
            index = (cursor - frame_start) // stride
            boundary = min(stop, frame_start + (index + 1) * stride)
            peak = _peak(samples[(cursor - position) * channels:(boundary - position) * channels])
            peaks[index] = max(peaks[index], peak)
            cursor = boundary
        guard()
    # wave's frame count floors partial frames. Reject any residual PCM bytes.
    guard()
    if wav.readframes(1):
        raise ValueError("STUDIO_WAVEFORM_INVALID")
    guard()
    return {"samples_per_bucket": stride, "peaks": peaks}
