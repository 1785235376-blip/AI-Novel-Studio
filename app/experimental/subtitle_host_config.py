"""V2-only explicit native adapter configuration; never starts a process.

Executable locations are administrator-owned environment values, not HTTP
inputs. Absent configuration keeps the original service NOT_CONFIGURED. ASR
requires original registry admission and cannot be enabled by these paths.
"""
from __future__ import annotations

import os

from ..packaged_profile import PROFILE_ENV, V2_PROFILE


def configured_subtitle_adapters():
    if os.environ.get(PROFILE_ENV) != V2_PROFILE:
        return ()
    ffmpeg = os.environ.get("AI_NOVEL_STUDIO_V2_SUBTITLE_FFMPEG")
    ffprobe = os.environ.get("AI_NOVEL_STUDIO_V2_SUBTITLE_FFPROBE")
    if not ffmpeg and not ffprobe:
        return ()
    if not ffmpeg or not ffprobe:
        raise ValueError("PROCESSING_HOST_FFMPEG_AND_FFPROBE_PAIR_REQUIRED")
    from .subtitle_burn_in import FfmpegSubtitleBurnInAdapter
    return (FfmpegSubtitleBurnInAdapter(ffmpeg_path=ffmpeg, ffprobe_path=ffprobe),)


def processing_host_required():
    return os.environ.get(PROFILE_ENV) == V2_PROFILE
