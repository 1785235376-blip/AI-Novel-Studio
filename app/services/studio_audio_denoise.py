"""One bounded, opt-in FFmpeg FFT denoise profile for the original audio job.

Measurements bind actual selected/output PCM, not an asserted quality score.
The existing trim worker still owns the process, cancellation and publication.
"""
from __future__ import annotations

import hashlib
import io
import math
import re
import struct
import wave

from .audiobook_service import AudiobookError

CONTROL = 'denoise_profile'
PROFILE = 'STATIONARY_FFT_V1'
FILTER = 'afftdn=nr=12:nf=-40:nt=w:tn=1:om=o'
CONTRACT = 'studio-audio-fft-denoise/1'


def validate_parameters(parameters):
    if (parameters.get(CONTROL) != PROFILE
            or parameters.get('out_ms', 0) - parameters.get('in_ms', 0) < 1000
            or any(key in parameters for key in ('output_format', 'target_peak_dbfs', 'target_lufs'))
            or any(parameters.get(key, 0) != 0 for key in ('gain_db', 'fade_in_ms', 'fade_out_ms'))):
        raise AudiobookError('STUDIO_AUDIO_DENOISE_PROFILE_INVALID',
            '平稳噪声降噪须为至少 1 秒的同采样率、同声道 PCM16 WAV；不能同时设置格式转换、归一化、非零增益或淡入淡出', 400)


def measure(data, parameters, guard, *, selected):
    """Read <= original asset limit, <=120s, in guarded 8192-frame chunks."""
    guard()
    try:
        with wave.open(io.BytesIO(data), 'rb') as reader:
            rate, channels = reader.getframerate(), reader.getnchannels()
            if (reader.getsampwidth() != 2 or reader.getcomptype() != 'NONE'
                    or rate != parameters.get('sample_rate', 48000) or channels != parameters.get('channels', 2)):
                raise ValueError('profile')
            start, end = parameters['in_ms'] * rate, parameters['out_ms'] * rate
            if start % 1000 or end % 1000:
                raise ValueError('alignment')
            first, frames = start // 1000, (end - start) // 1000
            if selected:
                if first + frames > reader.getnframes(): raise ValueError('range')
                reader.setpos(first)
            elif reader.getnframes() != frames:
                raise ValueError('frames')
            remaining, peak, squares, digest = frames, 0, 0, hashlib.sha256()
            while remaining:
                guard()
                count = min(8192, remaining)
                chunk = reader.readframes(count)
                if len(chunk) != count * channels * 2: raise ValueError('bytes')
                digest.update(chunk)
                for (sample,) in struct.iter_unpack('<h', chunk):
                    peak = max(peak, abs(sample)); squares += sample * sample
                remaining -= count
            guard()
            return {'first_frame': first, 'frames': frames, 'pcm_sha256': digest.hexdigest(),
                    'peak_s16': peak, 'rms_s16': math.sqrt(squares / (frames * channels))}
    except (wave.Error, EOFError, ValueError):
        raise AudiobookError('STUDIO_AUDIO_DENOISE_PCM_REQUIRED',
            '降噪仅支持已核对、同采样率同声道且起止对齐完整采样帧的 PCM16 WAV；不会自动转换来源', 400) from None


def proof(source, parameters, selected, output, data):
    value = {'contract': CONTRACT, 'profile': PROFILE,
        'source_id': source['id'], 'source_version': source['version'], 'source_sha256': source['digest'],
        'in_ms': parameters['in_ms'], 'out_ms': parameters['out_ms'],
        'sample_rate': parameters.get('sample_rate', 48000), 'channels': parameters.get('channels', 2),
        'selected_frames': selected['frames'], 'selected_pcm_sha256': selected['pcm_sha256'],
        'source_peak_s16': selected['peak_s16'], 'source_rms_s16': selected['rms_s16'],
        'output_frames': output['frames'], 'output_pcm_sha256': output['pcm_sha256'],
        'output_peak_s16': output['peak_s16'], 'output_rms_s16': output['rms_s16'],
        'output_sha256': hashlib.sha256(data).hexdigest()}
    return validate_proof(value, parameters, value['output_sha256'], source)


def validate_proof(value, parameters, output_sha256, source=None):
    fields = {'contract', 'profile', 'source_id', 'source_version', 'source_sha256', 'in_ms', 'out_ms',
        'sample_rate', 'channels', 'selected_frames', 'selected_pcm_sha256', 'source_peak_s16', 'source_rms_s16',
        'output_frames', 'output_pcm_sha256', 'output_peak_s16', 'output_rms_s16', 'output_sha256'}
    def invalid():
        raise AudiobookError('STUDIO_AUDIO_DENOISE_PROOF_INVALID', '降噪实际字节证明与原输入或输出不一致', 409)
    validate_parameters(parameters)
    if not isinstance(value, dict) or set(value) != fields: invalid()
    if value['contract'] != CONTRACT or value['profile'] != PROFILE: invalid()
    for key in ('source_version', 'in_ms', 'out_ms', 'sample_rate', 'channels', 'selected_frames', 'output_frames', 'source_peak_s16', 'output_peak_s16'):
        if type(value[key]) is not int: invalid()
    for key in ('source_rms_s16', 'output_rms_s16'):
        if type(value[key]) not in {int, float} or not math.isfinite(value[key]) or not 0 <= value[key] <= 32768: invalid()
    for key in ('source_sha256', 'selected_pcm_sha256', 'output_pcm_sha256', 'output_sha256'):
        if not isinstance(value[key], str) or not re.fullmatch('[a-f0-9]{64}', value[key]): invalid()
    if (not isinstance(value['source_id'], str) or not 1 <= len(value['source_id']) <= 240 or value['source_version'] < 1
            or value['in_ms'] != parameters['in_ms'] or value['out_ms'] != parameters['out_ms']
            or value['sample_rate'] != parameters.get('sample_rate', 48000) or value['channels'] != parameters.get('channels', 2)
            or value['in_ms'] * value['sample_rate'] % 1000 or value['out_ms'] * value['sample_rate'] % 1000
            or value['selected_frames'] != (value['out_ms'] - value['in_ms']) * value['sample_rate'] // 1000
            or value['output_frames'] != value['selected_frames'] or value['selected_frames'] < 1
            or not 0 <= value['source_peak_s16'] <= 32768 or not 0 <= value['output_peak_s16'] <= 32768
            or value['source_rms_s16'] > value['source_peak_s16'] or value['output_rms_s16'] > value['output_peak_s16']
            or value['output_sha256'] != output_sha256): invalid()
    if source is not None and (value['source_id'], value['source_version'], value['source_sha256']) != (source['id'], source['version'], source['digest']): invalid()
    return value
