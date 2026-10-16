"""Explicitly installed FFmpeg implementation for the original caption owner.

Construction receives host-owned absolute executable paths. HTTP requests can
only select the adapter ID; they cannot supply commands, paths, font files,
filters, codec options or output destinations. Construction and catalog reads
never start native programs. Execution remains an explicit original task action.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import math
from pathlib import Path
import tempfile
import threading
import time

from .media import digest
from .subtitle_processing import MAX_MEDIA_BYTES, ProcessingDefinition, ProcessingRequest, ProcessingResult
from ..media_files import MediaValidationError
from ..model_center.discovery_types import safe_local_path
from ..services.studio_timeline_export import compiler_profile, require_encoders, run_guarded_process

MAX_DURATION_MS = 600_000
MAX_CAPTION_CHARACTERS = 32_000


def _executable(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('PROCESSING_HOST_EXECUTABLE_REQUIRED')
    path = Path(safe_local_path(str(path))).resolve(strict=True)
    if not path.is_file() or not 0 < path.stat().st_size <= 512 * 1024 * 1024:
        raise ValueError('PROCESSING_HOST_EXECUTABLE_REQUIRED')
    return path


def _fingerprint(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _file_identity(path):
    info = path.stat()
    return info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino


def _time(milliseconds):
    seconds, millis = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}'


def _captions(caption):
    from .subtitle_timeline import Cue, cue_seconds
    rows, characters, previous = [], 0, -1
    if not isinstance(caption.get('cues'), list) or not 1 <= len(caption['cues']) <= 500:
        raise ValueError('PROCESSING_BURN_IN_CAPTION_LIMIT')
    for index, raw in enumerate(caption['cues'], 1):
        cue = Cue.model_validate(raw)
        start = int(cue_seconds(cue.start_tick, caption['timebase']) * 1000)
        end = int(cue_seconds(cue.end_tick, caption['timebase']) * 1000)
        if end <= start or start < previous:
            raise ValueError('PROCESSING_BURN_IN_CAPTION_TIMING_INVALID')
        speaker = caption.get('speakers', {}).get(cue.segment_id, {}).get('name')
        text = f'[{speaker}] {cue.text}' if speaker else cue.text
        # Match the original timeline renderer's literal SRT subset. libass
        # markup and backslash directives cannot become author-supplied style.
        if (len(text) > 1000 or text.count('\n') > 7 or '-->' in text
                or any(character in text for character in '{}<>\\')
                or any(not line.strip() for line in text.split('\n'))
                or any(ord(character) < 32 and character != '\n' or ord(character) == 127
                       or 0xD800 <= ord(character) <= 0xDFFF for character in text)):
            raise ValueError('PROCESSING_BURN_IN_LITERAL_CAPTIONS_REQUIRED')
        characters += len(text)
        if characters > MAX_CAPTION_CHARACTERS:
            raise ValueError('PROCESSING_BURN_IN_CAPTION_LIMIT')
        rows.append(f'{index}\n{_time(start)} --> {_time(end)}\n{text}')
        previous = start
    return ('\n\n'.join(rows) + '\n').encode('utf-8')


class FfmpegSubtitleBurnInAdapter:
    """Original guarded task renderer; no queue, model runtime or promotion."""
    def __init__(self, *, ffmpeg_path, ffprobe_path):
        self._ffmpeg, self._ffprobe = _executable(ffmpeg_path), _executable(ffprobe_path)
        self._hashes = (_fingerprint(self._ffmpeg), _fingerprint(self._ffprobe))
        self._identities = (_file_identity(self._ffmpeg), _file_identity(self._ffprobe))
        self._execution_lock = threading.Lock()
        self.definition = ProcessingDefinition('builtin.ffmpeg.subtitle-burn-in',
            '1:' + digest(self._hashes), ('BURN_IN',))

    def _tools_current(self, *, full=False):
        if ((_file_identity(self._ffmpeg), _file_identity(self._ffprobe)) != self._identities
                or full and (_fingerprint(self._ffmpeg), _fingerprint(self._ffprobe)) != self._hashes):
            raise ValueError('PROCESSING_HOST_EXECUTABLE_CHANGED')

    def _probe(self, path, guard):
        import json
        target = path.parent / (path.name + '.probe.json')
        run_guarded_process([str(self._ffprobe), '-v', 'error', '-protocol_whitelist', 'file,pipe',
            '-print_format', 'json', '-show_streams', '-show_format', str(path)],
            cwd=path.parent, guard=guard, timeout=20, stdout_path=target)
        if target.stat().st_size > 1_048_576:
            raise MediaValidationError('PROCESSING_PROBE_OUTPUT_LIMIT')
        try:
            result = json.loads(target.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError):
            raise MediaValidationError('PROCESSING_PROBE_INVALID') from None
        if (not isinstance(result, dict) or not isinstance(result.get('streams'), list)
                or not isinstance(result.get('format'), dict)):
            raise MediaValidationError('PROCESSING_PROBE_INVALID')
        return result

    @staticmethod
    def _media(details):
        videos = [row for row in details['streams'] if isinstance(row, dict) and row.get('codec_type') == 'video']
        audios = [row for row in details['streams'] if isinstance(row, dict) and row.get('codec_type') == 'audio']
        if len(videos) != 1 or len(audios) > 1 or len(details['streams']) != len(videos) + len(audios):
            raise MediaValidationError('PROCESSING_SINGLE_VIDEO_AUDIO_STREAMS_REQUIRED')
        video = videos[0]
        try:
            if not isinstance(video.get('avg_frame_rate'), str) or len(video['avg_frame_rate']) > 40:
                raise ValueError()
            if not isinstance(details['format'].get('duration'), str) or len(details['format']['duration']) > 40:
                raise ValueError()
            fps = Fraction(video['avg_frame_rate'])
            duration = Fraction(details['format']['duration']) * 1000
            width, height = video['width'], video['height']
        except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
            raise MediaValidationError('PROCESSING_PROBE_INVALID') from None
        if (type(width) is not int or type(height) is not int or not 16 <= width <= 1920
                or not 16 <= height <= 1080 or width % 2 or height % 2
                or not 1 <= fps <= 60 or fps.numerator > 1_000_000 or fps.denominator > 1_000_000
                or not 0 < duration <= MAX_DURATION_MS):
            raise MediaValidationError('PROCESSING_BURN_IN_MEDIA_LIMIT')
        # Rotation/cropping would change the expected caption canvas. Such
        # sources must first be normalized by the original timeline renderer.
        tags = video.get('tags', {})
        if (isinstance(tags, dict) and tags.get('rotate') not in (None, '0', 0)
                or any(isinstance(item, dict) and item.get('rotation') not in (None, 0)
                       for item in video.get('side_data_list', []))):
            raise MediaValidationError('PROCESSING_ROTATED_VIDEO_NORMALIZATION_REQUIRED')
        return video, audios, fps, duration

    def process(self, request: ProcessingRequest) -> ProcessingResult:
        if not isinstance(request, ProcessingRequest) or not callable(request.guard):
            raise ValueError('PROCESSING_BURN_IN_REQUEST_INVALID')
        started = time.monotonic()
        while not self._execution_lock.acquire(timeout=0.25):
            request.guard()
            self._tools_current()
            if time.monotonic() - started >= 120:
                raise ValueError('PROCESSING_BURN_IN_BUSY_NO_AUTOMATIC_RETRY')
        try:
            return self._render(request)
        finally:
            self._execution_lock.release()

    def _render(self, request: ProcessingRequest) -> ProcessingResult:
        if (not isinstance(request, ProcessingRequest) or request.operation != 'BURN_IN'
                or request.transcript or request.media_type not in {'video/mp4', 'video/webm'}
                or not isinstance(request.media, bytes) or not 0 < len(request.media) <= MAX_MEDIA_BYTES
                or not callable(request.guard)):
            raise ValueError('PROCESSING_BURN_IN_REQUEST_INVALID')
        subtitle = _captions(request.caption)
        duration_ms = Fraction(**request.caption['media']['duration_seconds']) * 1000
        if not 0 < duration_ms <= MAX_DURATION_MS:
            raise ValueError('PROCESSING_BURN_IN_MEDIA_LIMIT')
        self._tools_current(full=True)
        def guard():
            request.guard()
            self._tools_current()
        with tempfile.TemporaryDirectory(prefix='novel-caption-render-') as temporary:
            directory = Path(temporary)
            source = directory / ('input.mp4' if request.media_type == 'video/mp4' else 'input.webm')
            destination = directory / 'output.mp4'
            source.write_bytes(request.media)
            (directory / 'captions.srt').write_bytes(subtitle)
            guard()
            original = self._probe(source, guard)
            video, audio, fps, measured = self._media(original)
            if abs(measured - duration_ms) > 1:
                raise MediaValidationError('PROCESSING_CAPTION_MEASURED_SOURCE_CHANGED')
            compiled = compiler_profile({'preset': 'REVIEW_MP4'}, duration_ms=math.ceil(duration_ms), max_bytes=MAX_MEDIA_BYTES)
            require_encoders(str(self._ffmpeg), compiled, cwd=directory, guard=guard)
            command = [str(self._ffmpeg), '-nostdin', '-hide_banner', '-v', 'error', '-y', '-noautorotate',
                '-protocol_whitelist', 'file,pipe', '-i', source.name, '-map', '0:v:0']
            if audio:
                command += ['-map', '0:a:0']
            command += ['-map_metadata', '-1', '-map_chapters', '-1', '-vf',
                'subtitles=filename=captions.srt:charenc=UTF-8', '-pix_fmt', 'yuv420p', '-threads', '1']
            command += compiled['options'] + ['-t', f'{float(duration_ms / 1000):.6f}', '-fs', str(MAX_MEDIA_BYTES + 1), destination.name]
            run_guarded_process(command, cwd=directory, guard=guard, timeout=120)
            guard()
            if not destination.is_file() or not 0 < destination.stat().st_size <= MAX_MEDIA_BYTES:
                raise MediaValidationError('PROCESSING_BURN_IN_OUTPUT_LIMIT')
            rendered = self._probe(destination, guard)
            output_video, output_audio, output_fps, output_duration = self._media(rendered)
            tolerance = max(100, math.ceil(2000 / fps))
            if (output_video['width'] != video['width'] or output_video['height'] != video['height']
                    or output_video.get('codec_name') != 'mpeg4' or output_video.get('pix_fmt') != 'yuv420p'
                    or len(output_audio) != len(audio) or abs(output_fps - fps) > Fraction(1, 1000)
                    or abs(output_duration - duration_ms) > tolerance
                    or audio and output_audio[0].get('codec_name') != 'aac'
                    or audio and any(output_audio[0].get(key) != audio[0].get(key) for key in ('sample_rate', 'channels'))
                    or 'mp4' not in str(rendered['format'].get('format_name', '')).split(',')):
                raise MediaValidationError('PROCESSING_BURN_IN_OUTPUT_PROFILE_MISMATCH')
            content = destination.read_bytes()
            guard()
            self._tools_current(full=True)
            return ProcessingResult(content=content, media_type='video/mp4', receipt={
                'schema': 'subtitle-native-render/1', 'source_digest': request.source_digest,
                'source_sha256': hashlib.sha256(request.media).hexdigest(),
                'output_sha256': hashlib.sha256(content).hexdigest(), 'width': video['width'], 'height': video['height'],
                'fps_num': fps.numerator, 'fps_den': fps.denominator, 'duration_ms': math.ceil(output_duration),
                'duration_tolerance_ms': tolerance, 'audio_streams': len(audio), 'profile': 'REVIEW_MP4',
                'tool_digest': digest(self._hashes), 'validation': 'NATIVE_FFPROBE_EXACT', 'quality_verification': 'NOT_RUN'})
