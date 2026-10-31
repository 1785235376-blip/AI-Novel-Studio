"""V2-only explicit native adapter configuration; never starts a process.

Executable locations and hashes are administrator-owned environment values,
never HTTP inputs. Absent configuration remains NOT_CONFIGURED. Installing a
Whisper owner does not start it: original Model Center Host start must obtain
the private-pipe, actual model-load proof before the AUDIO route is admitted.
"""
from __future__ import annotations

import os
import re

from ..packaged_profile import PROFILE_ENV, V2_PROFILE


def _configuration(prefix, fields):
    values = {key: os.environ.get(prefix + key, '') for key in fields}
    if not any(values.values()):
        return None
    if not all(values.values()) or any(value != value.strip() for value in values.values()):
        raise ValueError('PROCESSING_HOST_CONFIGURATION_INCOMPLETE')
    return values


def _integer(name, default, minimum, maximum):
    value = os.environ.get(name, str(default))
    if not re.fullmatch(r'[0-9]{1,5}', value) or not minimum <= int(value) <= maximum:
        raise ValueError('PROCESSING_HOST_INTEGER_CONFIGURATION_INVALID')
    return int(value)


def configured_subtitle_adapters():
    if os.environ.get(PROFILE_ENV) != V2_PROFILE:
        return ()
    ffmpeg = os.environ.get("AI_NOVEL_STUDIO_V2_SUBTITLE_FFMPEG")
    ffprobe = os.environ.get("AI_NOVEL_STUDIO_V2_SUBTITLE_FFPROBE")
    if bool(ffmpeg) != bool(ffprobe):
        raise ValueError("PROCESSING_HOST_FFMPEG_AND_FFPROBE_PAIR_REQUIRED")
    adapters = []
    if ffmpeg:
        from .subtitle_burn_in import FfmpegSubtitleBurnInAdapter
        adapters.append(FfmpegSubtitleBurnInAdapter(ffmpeg_path=ffmpeg, ffprobe_path=ffprobe))
    alignment = _configuration('AI_NOVEL_STUDIO_V2_MFA_', ('RUNTIME_ROOT', 'MANIFEST', 'MANIFEST_SHA256',
        'DICTIONARY', 'DICTIONARY_SHA256', 'ACOUSTIC_MODEL', 'ACOUSTIC_MODEL_SHA256'))
    if alignment:
        if not ffmpeg:
            raise ValueError('PROCESSING_ALIGNMENT_MEDIA_TOOLS_REQUIRED')
        from .subtitle_alignment import MfaSubtitleAlignmentAdapter
        adapters.append(MfaSubtitleAlignmentAdapter(runtime_root=alignment['RUNTIME_ROOT'],
            manifest_path=alignment['MANIFEST'], manifest_sha256=alignment['MANIFEST_SHA256'],
            dictionary_path=alignment['DICTIONARY'], dictionary_sha256=alignment['DICTIONARY_SHA256'],
            acoustic_model_path=alignment['ACOUSTIC_MODEL'], acoustic_model_sha256=alignment['ACOUSTIC_MODEL_SHA256'],
            ffmpeg_path=ffmpeg, ffprobe_path=ffprobe))
    return tuple(adapters)


def configured_whisper_subtitle_resolver(center, runtime):
    """Install an original fixed-model lifecycle owner, with lazy ASR admission.

    Configuration/start/stop and processing tasks keep their original owners.
    Loading is explicit and requires the original trusted DesktopHost session.
    A stopped/unloaded/exited owner contributes no adapter to the current
    catalog; an old task keeps its route hash until explicit cancel/resume.
    """
    if os.environ.get(PROFILE_ENV) != V2_PROFILE:
        return None
    values = _configuration('AI_NOVEL_STUDIO_V2_WHISPER_',
        ('HOST', 'HOST_SHA256', 'MODEL', 'MODEL_SHA256', 'FFMPEG_SHA256'))
    if not values:
        return None
    ffmpeg = os.environ.get('AI_NOVEL_STUDIO_V2_SUBTITLE_FFMPEG')
    if not ffmpeg:
        raise ValueError('PROCESSING_WHISPER_MEDIA_TOOL_REQUIRED')
    gpu = os.environ.get('AI_NOVEL_STUDIO_V2_WHISPER_USE_GPU', '0')
    if gpu not in ('0', '1'):
        raise ValueError('PROCESSING_WHISPER_GPU_CONFIGURATION_INVALID')
    from ..model_center.whisper_runtime import install_fixed_whisper_host
    from ..model_runtime import ModelRuntimeError
    owner = install_fixed_whisper_host(center, runtime, executable=values['HOST'], executable_sha256=values['HOST_SHA256'],
        model_path=values['MODEL'], model_sha256=values['MODEL_SHA256'], ffmpeg_path=ffmpeg,
        ffmpeg_sha256=values['FFMPEG_SHA256'],
        port=_integer('AI_NOVEL_STUDIO_V2_WHISPER_PORT', 8178, 1024, 65535),
        threads=_integer('AI_NOVEL_STUDIO_V2_WHISPER_THREADS', 4, 1, 64), use_gpu=gpu == '1')
    def current_original_adapter():
        try:
            return (owner.subtitle_adapter(),)
        except ValueError as error:
            if str(error) != 'WHISPER_HOST_NOT_ADMITTED':
                raise
            return ()
        except ModelRuntimeError:
            # A current owner is not a grant for a disabled original route.
            return ()
    return current_original_adapter


def processing_host_required():
    return os.environ.get(PROFILE_ENV) == V2_PROFILE
