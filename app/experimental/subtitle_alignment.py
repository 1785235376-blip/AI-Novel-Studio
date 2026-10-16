"""Real MFA word alignment inside the original subtitle processing owner.

The administrator pins an entire local MFA 3.3.7 runtime, pronunciation
dictionary and acoustic model. HTTP cannot provide paths, hashes, parameters or
commands. Construction/catalog perform only file checks. Only an explicit
original caption task invokes FFmpeg and MFA, and its output still needs review.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
from fractions import Fraction
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import threading
import time
import unicodedata
import wave
import zipfile

from .media import digest
from .subtitle_alignment_native import run_alignment_process
from .subtitle_burn_in import _executable, _file_identity, _fingerprint
from .subtitle_processing import MAX_MEDIA_BYTES, ProcessingDefinition, ProcessingRequest, ProcessingResult
from ..model_center.discovery_types import safe_local_path

ENGINE_VERSION = '3.3.7'
MAX_RUNTIME_FILES = 20_000
MAX_RUNTIME_BYTES = 8 * 1024 * 1024 * 1024
MAX_DICTIONARY_BYTES = 128 * 1024 * 1024
MAX_ACOUSTIC_BYTES = 512 * 1024 * 1024
MAX_TRANSCRIPT_BYTES = 32_000
MAX_WORDS = 500
MAX_DURATION_MS = 600_000
MAX_ALIGNMENT_BYTES = 1_048_576
SHA256 = re.compile(r'^[a-f0-9]{64}$')
NUMBER = r'(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,18})?(?:[eE][+-]?[0-9]{1,3})?'
PARAMETERS = {'command': 'align_one', 'output_format': 'long_textgrid',
    'tokenization': 'EXPLICIT_WHITESPACE_DICTIONARY_WORDS', 'num_jobs': 1,
    'multiprocessing': False, 'threading': False, 'postgres': False,
    'cleanup_textgrids': False, 'g2p': False, 'sample_rate': 16000,
    'channels': 1, 'sample_format': 'PCM_S16LE'}


def _plain_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('PROCESSING_ALIGNMENT_DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('PROCESSING_ALIGNMENT_INVALID_JSON_NUMBER')))


def _relative(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 1024 or '\\' in value or ':' in value
            or any(ord(character) < 32 for character in value)):
        raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_PATH_INVALID')
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(part in {'', '.', '..'} for part in path.parts) or len(path.parts) > 32:
        raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_PATH_INVALID')
    return path


def _bounded_file(value, limit, suffix=None):
    path = Path(safe_local_path(str(value))).resolve(strict=True)
    if not path.is_file() or not 0 < path.stat().st_size <= limit or suffix and path.suffix.lower() != suffix:
        raise ValueError('PROCESSING_ALIGNMENT_PINNED_LOCAL_FILE_REQUIRED')
    return path


def _hash_value(value):
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError('PROCESSING_ALIGNMENT_HOST_SHA256_REQUIRED')
    return value


def _digest_file(path, guard=None):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            if guard is not None:
                guard()
            result.update(block)
    return result.hexdigest()


def _runtime_files(root):
    result, directories, total, pending = {}, {}, 0, [root]
    while pending:
        directory = pending.pop()
        directories[directory] = _file_identity(directory)
        if len(directories) > 40_000:
            raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_LIMIT')
        with os.scandir(directory) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_LINK_REJECTED')
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if len(path.relative_to(root).parts) > 32:
                        raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_LIMIT')
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    relative = path.relative_to(root).as_posix()
                    _relative(relative)
                    total += info.st_size
                    if len(result) >= MAX_RUNTIME_FILES or total > MAX_RUNTIME_BYTES:
                        raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_LIMIT')
                    result[relative] = (path, (info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino))
                else:
                    raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_REGULAR_FILES_REQUIRED')
    return result, directories


def _validate_acoustic_archive(path):
    # MFA extracts its model. Verify the pinned archive cannot write outside
    # the isolated job directory or explode into an unbounded package.
    names, total = set(), 0
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if not 1 <= len(members) <= 2000:
                raise ValueError()
            for member in members:
                name = member.filename.rstrip('/')
                _relative(name)
                folded = name.casefold()
                if (folded in names or member.flag_bits & 1
                        or (member.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError()
                names.add(folded)
                total += member.file_size
                if (member.file_size > MAX_ACOUSTIC_BYTES or total > MAX_ACOUSTIC_BYTES
                        or member.file_size > max(1, member.compress_size) * 1000):
                    raise ValueError()
            files = [member.filename for member in members if not member.is_dir()]
            if not any(name.endswith('/final.mdl') or name == 'final.mdl' for name in files):
                raise ValueError()
            if not any(name.endswith('/meta.json') or name.endswith('/meta.yaml')
                    or name in {'meta.json', 'meta.yaml'} for name in files):
                raise ValueError()
    except (ValueError, OSError, zipfile.BadZipFile):
        raise ValueError('PROCESSING_ALIGNMENT_ACOUSTIC_ARCHIVE_INVALID') from None


def _tokens(transcript):
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError('PROCESSING_ALIGNMENT_TRANSCRIPT_REQUIRED')
    try:
        encoded = transcript.encode('utf-8', errors='strict')
    except UnicodeError:
        raise ValueError('PROCESSING_ALIGNMENT_TRANSCRIPT_UTF8_REQUIRED') from None
    tokens = transcript.split()
    if (not 0 < len(encoded) <= MAX_TRANSCRIPT_BYTES or not 1 <= len(tokens) <= MAX_WORDS
            or any(len(token) > 240 for token in tokens)
            or any(ord(character) < 32 and character not in '\t\n\r'
                or ord(character) == 127 or character in '<>\x00' for character in transcript)):
        raise ValueError('PROCESSING_ALIGNMENT_TRANSCRIPT_LIMIT')
    lexical = []
    for token in tokens:
        word = token
        # Edge punctuation has no acoustic interval. Preserve it in the cue
        # while aligning the exact dictionary word; never invent a timestamp.
        while word and unicodedata.category(word[0]).startswith('P'):
            word = word[1:]
        while word and unicodedata.category(word[-1]).startswith('P'):
            word = word[:-1]
        word = word.lower()
        if not word or any(character.isspace() for character in word):
            raise ValueError('PROCESSING_ALIGNMENT_DICTIONARY_WORD_REQUIRED')
        lexical.append(word)
    return tokens, lexical


def _textgrid(data, *, duration_seconds, lexical):
    """Parse the bounded long TextGrid generated by the pinned MFA CLI only."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_ALIGNMENT_BYTES:
        raise ValueError('PROCESSING_ALIGNMENT_TEXTGRID_LIMIT')
    try:
        lines = [line.strip() for line in data.decode('utf-8-sig', errors='strict').splitlines() if line.strip()]
    except UnicodeError:
        raise ValueError('PROCESSING_ALIGNMENT_TEXTGRID_UTF8_REQUIRED') from None
    cursor = 0
    def take(pattern):
        nonlocal cursor
        if cursor >= len(lines) or not (match := re.fullmatch(pattern, lines[cursor])):
            raise ValueError('PROCESSING_ALIGNMENT_TEXTGRID_INVALID')
        cursor += 1
        return match
    def numeric(label):
        return Fraction(take(re.escape(label) + r' = (' + NUMBER + r')').group(1))
    def string(label):
        return take(re.escape(label) + r' = "((?:[^"\x00-\x1f]|"")*)"').group(1).replace('""', '"')
    take(r'File type = "ooTextFile"')
    take(r'Object class = "TextGrid"')
    minimum, maximum = numeric('xmin'), numeric('xmax')
    if minimum != 0 or not 0 < maximum <= Fraction(MAX_DURATION_MS, 1000) or abs(maximum - duration_seconds) > Fraction(1, 1000):
        raise ValueError('PROCESSING_ALIGNMENT_TEXTGRID_DURATION_CHANGED')
    take(r'tiers\? <exists>')
    count = int(take(r'size = ([1-4])').group(1))
    take(r'item \[\]:')
    tiers = {}
    for tier_index in range(1, count + 1):
        take(r'item \[' + str(tier_index) + r'\]:')
        if string('class') != 'IntervalTier':
            raise ValueError('PROCESSING_ALIGNMENT_INTERVAL_TIERS_REQUIRED')
        name = string('name')
        if name not in {'words', 'phones'} or name in tiers or numeric('xmin') != 0 or numeric('xmax') != maximum:
            raise ValueError('PROCESSING_ALIGNMENT_WORD_PHONE_TIERS_REQUIRED')
        intervals = int(take(r'intervals: size = ([0-9]{1,5})').group(1))
        if not 1 <= intervals <= 15_000:
            raise ValueError('PROCESSING_ALIGNMENT_INTERVAL_LIMIT')
        values, previous = [], Fraction(0)
        for interval_index in range(1, intervals + 1):
            take(r'intervals \[' + str(interval_index) + r'\]:')
            start, end, text = numeric('xmin'), numeric('xmax'), string('text')
            if not previous <= start < end <= maximum or len(text) > 240 or text in {'<unk>', 'spn', '<oov>'}:
                raise ValueError('PROCESSING_ALIGNMENT_INTERVAL_INVALID')
            previous = end
            if text and text != '<eps>':
                values.append((start, end, text))
        tiers[name] = values
    if cursor != len(lines) or set(tiers) != {'words', 'phones'} or not tiers['phones']:
        raise ValueError('PROCESSING_ALIGNMENT_WORD_PHONE_TIERS_REQUIRED')
    words, phones = tiers['words'], tiers['phones']
    if len(words) != len(lexical) or [item[2] for item in words] != lexical:
        raise ValueError('PROCESSING_ALIGNMENT_TRANSCRIPT_WORDS_CHANGED')
    for start, end, _ in words:
        if not any(phone_start < end and phone_end > start and label not in {'sil', 'SIL'}
                for phone_start, phone_end, label in phones):
            raise ValueError('PROCESSING_ALIGNMENT_PHONE_EVIDENCE_REQUIRED')
    return words, len(phones)


class MfaSubtitleAlignmentAdapter:
    """Pinned single-file MFA execution, no scheduler, model install or fallback."""
    def __init__(self, *, runtime_root, manifest_path, manifest_sha256, dictionary_path,
            dictionary_sha256, acoustic_model_path, acoustic_model_sha256, ffmpeg_path, ffprobe_path):
        self._root = Path(safe_local_path(str(runtime_root))).resolve(strict=True)
        if not self._root.is_dir():
            raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_ROOT_REQUIRED')
        self._manifest = _bounded_file(manifest_path, 4 * 1024 * 1024, '.json')
        if self._manifest.is_relative_to(self._root):
            raise ValueError('PROCESSING_ALIGNMENT_MANIFEST_OUTSIDE_RUNTIME_REQUIRED')
        self._manifest_sha = _hash_value(manifest_sha256)
        manifest_bytes = self._manifest.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != self._manifest_sha:
            raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_MANIFEST_CHANGED')
        manifest = _plain_json(manifest_bytes)
        if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'engine_version', 'cli', 'python', 'files'}
                or manifest.get('schema') != 'studio-mfa-runtime/1' or manifest.get('engine_version') != ENGINE_VERSION
                or not isinstance(manifest.get('files'), list) or not 1 <= len(manifest['files']) <= MAX_RUNTIME_FILES):
            raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_MANIFEST_INVALID')
        hashes, folded = {}, set()
        for entry in manifest['files']:
            if not isinstance(entry, dict) or set(entry) != {'path', 'sha256'}:
                raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_MANIFEST_INVALID')
            name = str(_relative(entry['path']))
            if name.casefold() in folded:
                raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_DUPLICATE_PATH')
            folded.add(name.casefold())
            hashes[name] = _hash_value(entry['sha256'])
        cli, python = str(_relative(manifest['cli'])), str(_relative(manifest['python']))
        if (cli not in hashes or python not in hashes or Path(cli).name.lower() not in {'mfa', 'mfa.exe'}
                or Path(python).name.lower() not in {'python', 'python3', 'python.exe'}):
            raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_CLI_AND_PYTHON_REQUIRED')
        self._cli, self._python = self._root / cli, self._root / python
        self._runtime_hashes = hashes
        self._runtime, self._directories = _runtime_files(self._root)
        if set(self._runtime) != set(hashes):
            raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_MANIFEST_INCOMPLETE')
        # A venv launcher can delegate to an unpinned base Python elsewhere.
        # Require a self-contained Python/conda prefix and invoke the pinned
        # Python CLI module directly rather than trusting an exe shebang.
        if any(Path(name).name.lower() == 'pyvenv.cfg' for name in hashes):
            raise ValueError('PROCESSING_ALIGNMENT_SELF_CONTAINED_PYTHON_REQUIRED')
        if not any(name == 'Lib/os.py' or re.fullmatch(r'lib/python3\.[0-9]{1,2}/os\.py', name) for name in hashes):
            raise ValueError('PROCESSING_ALIGNMENT_PINNED_PYTHON_STDLIB_REQUIRED')
        self._command = [str(self._python), '-I', '-B', '-m', 'montreal_forced_aligner.command_line.mfa']
        metadata = [path for name, (path, _) in self._runtime.items()
            if '/montreal_forced_aligner-' in '/' + name.lower() and name.endswith('.dist-info/METADATA')]
        if len(metadata) != 1 or metadata[0].stat().st_size > 1_048_576:
            raise ValueError('PROCESSING_ALIGNMENT_MFA_PACKAGE_METADATA_REQUIRED')
        package = metadata[0].read_text(encoding='utf-8', errors='strict')
        if not re.search(r'^Name: montreal[-_]forced[-_]aligner\r?$', package, re.MULTILINE | re.IGNORECASE) or not re.search(
                r'^Version: ' + re.escape(ENGINE_VERSION) + r'\r?$', package, re.MULTILINE):
            raise ValueError('PROCESSING_ALIGNMENT_MFA_PACKAGE_VERSION_REQUIRED')
        if not any(name.lower().endswith(('.dll', '.pyd', '.so')) for name in hashes):
            raise ValueError('PROCESSING_ALIGNMENT_NATIVE_RUNTIME_MANIFEST_REQUIRED')
        self._dictionary = _bounded_file(dictionary_path, MAX_DICTIONARY_BYTES, '.dict')
        self._acoustic = _bounded_file(acoustic_model_path, MAX_ACOUSTIC_BYTES, '.zip')
        self._ffmpeg, self._ffprobe = _executable(ffmpeg_path), _executable(ffprobe_path)
        self._hashes = (_hash_value(dictionary_sha256), _hash_value(acoustic_model_sha256),
            _fingerprint(self._ffmpeg), _fingerprint(self._ffprobe))
        self._fixed = (self._manifest, self._dictionary, self._acoustic, self._ffmpeg, self._ffprobe)
        self._identities = tuple(_file_identity(path) for path in self._fixed)
        self._tools_current(full=True)
        _validate_acoustic_archive(self._acoustic)
        self._words = set()
        with self._dictionary.open(encoding='utf-8-sig', errors='strict') as stream:
            for line in stream:
                if len(line) > 10_000:
                    raise ValueError('PROCESSING_ALIGNMENT_DICTIONARY_LINE_LIMIT')
                fields = line.split()
                if fields and not fields[0].startswith('#'):
                    if len(fields) < 2 or len(fields[0]) > 240:
                        raise ValueError('PROCESSING_ALIGNMENT_DICTIONARY_INVALID')
                    self._words.add(fields[0].lower())
                    if len(self._words) > 1_000_000:
                        raise ValueError('PROCESSING_ALIGNMENT_DICTIONARY_LIMIT')
        if not self._words:
            raise ValueError('PROCESSING_ALIGNMENT_DICTIONARY_INVALID')
        self._execution_lock = threading.Lock()
        self._tool_digest = digest([self._manifest_sha, *self._hashes])
        self.definition = ProcessingDefinition('builtin.mfa.forced-alignment',
            '1:' + self._tool_digest, ('FORCED_ALIGNMENT',))

    def _tools_current(self, *, full=False, guard=None):
        if tuple(_file_identity(path) for path in self._fixed) != self._identities:
            raise ValueError('PROCESSING_ALIGNMENT_HOST_FILES_CHANGED')
        if any(_file_identity(path) != identity for path, identity in self._directories.items()):
            raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_CHANGED')
        for path, identity in self._runtime.values():
            if _file_identity(path) != identity:
                raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_CHANGED')
        if full:
            current, directories = _runtime_files(self._root)
            if set(current) != set(self._runtime) or directories != self._directories or any(
                    _digest_file(current[name][0], guard) != expected for name, expected in self._runtime_hashes.items()):
                raise ValueError('PROCESSING_ALIGNMENT_RUNTIME_CHANGED')
            if (_digest_file(self._manifest, guard) != self._manifest_sha
                    or tuple(_digest_file(path, guard) for path in self._fixed[1:]) != self._hashes):
                raise ValueError('PROCESSING_ALIGNMENT_HOST_FILES_CHANGED')
            self._tools_current()

    def alignment_runtime_admitted(self):
        try:
            self._tools_current()
            return True
        except (ValueError, OSError):
            return False

    def _environment(self, directory):
        # A new, narrow environment cannot inherit model credentials, Python
        # imports, user MFA profiles or downloads from another application.
        result = {key: value for key, value in os.environ.items()
            if key.upper() in {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'SYSTEMDRIVE'} }
        directories = [self._cli.parent, self._python.parent, self._root / 'Library' / 'bin', self._root / 'bin']
        result['PATH'] = os.pathsep.join(str(path) for path in directories if path.is_dir())
        for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TMP', 'TEMP', 'TMPDIR', 'MFA_ROOT_DIR'):
            result[key] = str(directory)
        result.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
            OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1',
            HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', MFA_PROFILE='studio-alignment')
        return result

    def _probe(self, source, directory, guard, env):
        target = directory / 'probe.json'
        run_alignment_process([str(self._ffprobe), '-v', 'error', '-protocol_whitelist', 'file,pipe',
            '-print_format', 'json', '-show_streams', '-show_format', str(source)],
            cwd=directory, env=env, guard=guard, timeout=20, stdout_path=target)
        result = _plain_json(target.read_bytes())
        if (not isinstance(result, dict) or not isinstance(result.get('streams'), list)
                or not isinstance(result.get('format'), dict)):
            raise ValueError('PROCESSING_ALIGNMENT_SOURCE_PROBE_INVALID')
        audios = [row for row in result['streams'] if isinstance(row, dict) and row.get('codec_type') == 'audio']
        videos = [row for row in result['streams'] if isinstance(row, dict) and row.get('codec_type') == 'video']
        if len(audios) != 1 or len(videos) > 1 or len(result['streams']) != len(audios) + len(videos):
            raise ValueError('PROCESSING_ALIGNMENT_SINGLE_AUDIO_STREAM_REQUIRED')
        try:
            duration = Fraction(result['format']['duration']) * 1000
            audio_duration = Fraction(audios[0].get('duration', result['format']['duration'])) * 1000
            channels, sample_rate = int(audios[0]['channels']), int(audios[0]['sample_rate'])
        except (ValueError, KeyError, TypeError, ZeroDivisionError, OverflowError):
            raise ValueError('PROCESSING_ALIGNMENT_SOURCE_PROBE_INVALID') from None
        if (not 0 < duration <= MAX_DURATION_MS or not 0 < audio_duration <= MAX_DURATION_MS
                or abs(audio_duration - duration) > 50 or not 1 <= channels <= 8 or not 8000 <= sample_rate <= 192000):
            raise ValueError('PROCESSING_ALIGNMENT_SOURCE_MEDIA_LIMIT')
        start = audios[0].get('start_time', result['format'].get('start_time', '0'))
        try:
            if abs(Fraction(start)) > Fraction(1, 1000):
                raise ValueError()
        except (ValueError, TypeError, ZeroDivisionError):
            raise ValueError('PROCESSING_ALIGNMENT_AUDIO_OFFSET_NORMALIZATION_REQUIRED') from None
        return duration

    def process(self, request: ProcessingRequest) -> ProcessingResult:
        if (not isinstance(request, ProcessingRequest) or request.operation != 'FORCED_ALIGNMENT'
                or not isinstance(request.media, bytes) or not 0 < len(request.media) <= MAX_MEDIA_BYTES
                or request.media_type not in {'audio/wav', 'audio/mpeg', 'audio/flac', 'audio/ogg',
                    'audio/mp4', 'video/mp4', 'video/webm'} or not callable(request.guard)):
            raise ValueError('PROCESSING_ALIGNMENT_REQUEST_INVALID')
        tokens, lexical = _tokens(request.transcript)
        if any(word not in self._words for word in lexical):
            raise ValueError('PROCESSING_ALIGNMENT_DICTIONARY_WORD_MISSING')
        duration = Fraction(**request.caption['media']['duration_seconds']) * 1000
        if not 0 < duration <= MAX_DURATION_MS or hashlib.sha256(request.media).hexdigest() != request.caption['asset_snapshot']['digest']:
            raise ValueError('PROCESSING_ALIGNMENT_SOURCE_CHANGED')
        started = time.monotonic()
        while not self._execution_lock.acquire(timeout=0.25):
            request.guard()
            self._tools_current()
            if time.monotonic() - started > 120:
                raise ValueError('PROCESSING_ALIGNMENT_BUSY_NO_AUTOMATIC_RETRY')
        try:
            return self._align(request, tokens, lexical, duration, started)
        finally:
            self._execution_lock.release()

    def _align(self, request, tokens, lexical, duration, started):
        request.guard()
        def fingerprint_guard():
            request.guard()
            if time.monotonic() - started > 310:
                raise ValueError('PROCESSING_ALIGNMENT_OPERATION_TIMEOUT')
        self._tools_current(full=True, guard=fingerprint_guard)
        next_identity_check = 0
        def guard():
            nonlocal next_identity_check
            request.guard()
            now = time.monotonic()
            if now - started > 310:
                raise ValueError('PROCESSING_ALIGNMENT_OPERATION_TIMEOUT')
            if now >= next_identity_check:
                self._tools_current()
                next_identity_check = now + 1
        with tempfile.TemporaryDirectory(prefix='novel-caption-align-') as temporary:
            directory = Path(temporary)
            env = self._environment(directory)
            source, audio, transcript, output = (directory / name for name in
                ('input.media', 'input.wav', 'input.lab', 'aligned.TextGrid'))
            source.write_bytes(request.media)
            transcript.write_bytes(' '.join(lexical).encode('utf-8'))
            configuration = directory / 'alignment.yaml'
            configuration.write_text('ignore_case: true\npunctuation: []\nclitic_markers: []\ncompound_markers: []\n'
                'brackets: []\nword_break_markers: []\n', encoding='utf-8')
            guard()
            version = directory / 'engine-version.txt'
            run_alignment_process(self._command + ['version'], cwd=directory, env=env, guard=guard,
                timeout=20, stdout_path=version)
            if version.read_text(encoding='utf-8', errors='strict').strip() != ENGINE_VERSION:
                raise ValueError('PROCESSING_ALIGNMENT_NATIVE_VERSION_CHANGED')
            measured = self._probe(source, directory, guard, env)
            if abs(measured - duration) > 1:
                raise ValueError('PROCESSING_ALIGNMENT_CAPTION_MEASURED_SOURCE_CHANGED')
            max_audio = 44 + math.ceil(duration / 1000) * 32000 + 4096
            run_alignment_process([str(self._ffmpeg), '-nostdin', '-hide_banner', '-v', 'error', '-y',
                '-protocol_whitelist', 'file,pipe', '-i', source.name, '-map', '0:a:0', '-vn', '-sn', '-dn',
                '-map_metadata', '-1', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', '-threads', '1',
                '-fs', str(max_audio + 1), audio.name], cwd=directory, env=env, guard=guard, timeout=60)
            guard()
            if not audio.is_file() or not 44 <= audio.stat().st_size <= max_audio:
                raise ValueError('PROCESSING_ALIGNMENT_DECODED_AUDIO_LIMIT')
            decoded = audio.read_bytes()
            with wave.open(io.BytesIO(decoded), 'rb') as stream:
                if (stream.getnchannels() != 1 or stream.getsampwidth() != 2 or stream.getframerate() != 16000
                        or stream.getcomptype() != 'NONE'):
                    raise ValueError('PROCESSING_ALIGNMENT_DECODED_AUDIO_INVALID')
                frames = stream.getnframes()
                if len(stream.readframes(frames)) != frames * 2:
                    raise ValueError('PROCESSING_ALIGNMENT_DECODED_AUDIO_INVALID')
            decoded_duration = Fraction(frames, 16000)
            if not 0 < decoded_duration <= 600 or abs(decoded_duration * 1000 - duration) > 50:
                raise ValueError('PROCESSING_ALIGNMENT_DECODED_DURATION_CHANGED')
            run_alignment_process(self._command + ['align_one', str(audio), str(transcript),
                str(self._dictionary), str(self._acoustic), str(output), '--output_format', 'long_textgrid',
                '--config_path', str(configuration), '--no_tokenization', '--no_cleanup_textgrids',
                '--no_use_mp', '--no_use_threading', '--no_use_postgres', '--num_jobs', '1',
                '--temporary_directory', str(directory / 'mfa-work'), '--clean', '--quiet'],
                cwd=directory, env=env, guard=guard, timeout=120)
            guard()
            if not output.is_file() or not 0 < output.stat().st_size <= MAX_ALIGNMENT_BYTES:
                raise ValueError('PROCESSING_ALIGNMENT_TEXTGRID_LIMIT')
            aligned = output.read_bytes()
            words, phone_count = _textgrid(aligned, duration_seconds=decoded_duration, lexical=lexical)
            from .subtitle_timeline import Cue
            base = request.caption['timebase']
            rate = Fraction(base['numerator'], base['denominator'])
            cues, previous_end = [], 0
            identity = digest([request.request_id, request.source_digest, self._tool_digest])[:32]
            for index, ((start, end, _), text) in enumerate(zip(words, tokens), 1):
                # Inward quantization keeps nonoverlapping native word evidence
                # within its actual interval and the unchanged caption duration.
                start_tick, end_tick = math.ceil(start * rate), math.floor(end * rate)
                if start_tick < previous_end or end_tick <= start_tick:
                    raise ValueError('PROCESSING_ALIGNMENT_TIMEBASE_RESOLUTION_REQUIRED')
                cues.append(Cue(id='align-' + identity + '-' + str(index), start_tick=start_tick,
                    end_tick=end_tick, text=text).model_dump())
                previous_end = end_tick
            guard()
            self._tools_current(full=True, guard=fingerprint_guard)
            word_evidence = [[str(start), str(end), word] for start, end, word in words]
            return ProcessingResult(cues=tuple(cues), receipt={
                'schema': 'subtitle-forced-alignment/1', 'engine': 'MONTREAL_FORCED_ALIGNER',
                'engine_version': ENGINE_VERSION, 'operation': 'FORCED_ALIGNMENT',
                'runtime_manifest_sha256': self._manifest_sha, 'dictionary_sha256': self._hashes[0],
                'acoustic_model_sha256': self._hashes[1], 'tool_digest': self._tool_digest,
                'source_digest': request.source_digest, 'input_sha256': hashlib.sha256(request.media).hexdigest(),
                'decoded_audio_sha256': hashlib.sha256(decoded).hexdigest(),
                'transcript_sha256': hashlib.sha256(request.transcript.encode('utf-8')).hexdigest(),
                'alignment_output_sha256': hashlib.sha256(aligned).hexdigest(),
                'aligned_words_digest': digest(word_evidence), 'cues_digest': digest(cues),
                'timebase': copy.deepcopy(base), 'caption_version': request.caption['version'],
                'media_snapshot': copy.deepcopy(request.caption['asset_snapshot']), 'word_count': len(words),
                'phone_count': phone_count, 'elapsed_ms': math.floor((time.monotonic() - started) * 1000),
                'local': True, 'model_called': True, 'timing_origin': 'MFA_WORD_INTERVALS',
                'quality_verification': 'NOT_RUN', 'parameters': copy.deepcopy(PARAMETERS)})


def validate_alignment_receipt(caption, row, cues, receipt):
    """Original task result validator; native identity never comes from HTTP."""
    fields = {'schema', 'engine', 'engine_version', 'operation', 'runtime_manifest_sha256',
        'dictionary_sha256', 'acoustic_model_sha256', 'tool_digest', 'source_digest', 'input_sha256',
        'decoded_audio_sha256', 'transcript_sha256', 'alignment_output_sha256', 'aligned_words_digest',
        'cues_digest', 'timebase', 'caption_version', 'media_snapshot', 'word_count', 'phone_count',
        'elapsed_ms', 'local', 'model_called', 'timing_origin', 'quality_verification', 'parameters'}
    if (not isinstance(receipt, dict) or set(receipt) != fields
            or row.get('operation') != 'FORCED_ALIGNMENT' or row.get('verification') != 'CONTRACT_VERIFIED'
            or receipt.get('schema') != 'subtitle-forced-alignment/1' or receipt.get('engine') != 'MONTREAL_FORCED_ALIGNER'
            or receipt.get('engine_version') != ENGINE_VERSION or receipt.get('operation') != 'FORCED_ALIGNMENT'
            or receipt.get('local') is not True or receipt.get('model_called') is not True
            or receipt.get('timing_origin') != 'MFA_WORD_INTERVALS' or receipt.get('quality_verification') != 'NOT_RUN'
            or receipt.get('parameters') != PARAMETERS
            or receipt.get('source_digest') != digest([caption['version'], caption['asset_snapshot']])
            or receipt.get('input_sha256') != caption['asset_snapshot']['digest']
            or receipt.get('cues_digest') != digest(cues) or receipt.get('timebase') != caption['timebase']
            or receipt.get('caption_version') != caption['version'] or receipt.get('media_snapshot') != caption['asset_snapshot']
            or type(receipt.get('word_count')) is not int or receipt['word_count'] != len(cues) or not 1 <= len(cues) <= MAX_WORDS
            or type(receipt.get('phone_count')) is not int or not 1 <= receipt['phone_count'] <= 15_000
            or type(receipt.get('elapsed_ms')) is not int or not 0 <= receipt['elapsed_ms'] <= 310_000
            or any(not isinstance(receipt.get(key), str) or not SHA256.fullmatch(receipt[key]) for key in
                ('runtime_manifest_sha256', 'dictionary_sha256', 'acoustic_model_sha256', 'tool_digest', 'source_digest',
                 'input_sha256', 'decoded_audio_sha256', 'transcript_sha256', 'alignment_output_sha256', 'aligned_words_digest', 'cues_digest'))):
        raise ValueError('PROCESSING_ALIGNMENT_RECEIPT_INVALID')
    try:
        tokens, _ = _tokens(row['transcript'])
        transcript_digest = hashlib.sha256(row['transcript'].encode('utf-8')).hexdigest()
    except (ValueError, KeyError, UnicodeError):
        raise ValueError('PROCESSING_ALIGNMENT_RECEIPT_INVALID') from None
    if receipt['transcript_sha256'] != transcript_digest or [cue['text'] for cue in cues] != tokens:
        raise ValueError('PROCESSING_ALIGNMENT_RECEIPT_TRANSCRIPT_CHANGED')
    definition = ProcessingDefinition('builtin.mfa.forced-alignment', '1:' + receipt['tool_digest'], ('FORCED_ALIGNMENT',))
    if row.get('adapter_id') != definition.adapter_id or row.get('adapter_identity') != digest(asdict(definition)):
        raise ValueError('PROCESSING_ALIGNMENT_RECEIPT_ADAPTER_CHANGED')
    return True
