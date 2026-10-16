"""One explicitly admitted whisper.cpp server route, never a runtime launcher.

The protocol is the upstream /inference multipart verbose_json contract. A
host-owned admission guard must prove the current local model and runtime;
loopback health or returned text alone cannot prove that model identity.
"""
from __future__ import annotations

from decimal import Decimal
from contextvars import copy_context
from fractions import Fraction
import hashlib
import http.client
import io
import json
import math
from pathlib import Path
import re
import socket
import tempfile
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4
import wave

from .audio_processing_runtime import AudioProcessingRequest, AudioProcessingResponse, audio_digest
from .model_center.discovery_types import local_endpoint
from .model_runtime import ModelDescriptor, ModelRuntimeError, Modality, ProviderDescriptor, RuntimeErrorCode
from .experimental.subtitle_burn_in import _executable, _file_identity, _fingerprint
from .services.studio_timeline_export import run_guarded_process
from .stable_identity import validate_uuid

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PCM_BYTES = 20 * 1024 * 1024
MEDIA_EXTENSIONS = {'audio/wav': 'wav', 'audio/mpeg': 'mp3', 'audio/mp4': 'mp4', 'audio/webm': 'webm',
    'audio/ogg': 'ogg', 'audio/flac': 'flac', 'video/mp4': 'mp4', 'video/webm': 'webm'}


def _invalid_number(value):
    raise ValueError('invalid JSON number')


def _seconds(value):
    # A short exponent such as 1e-999999999 must not allocate an enormous
    # Fraction denominator. Upstream emits ordinary bounded numeric seconds.
    if (type(value) not in (int, Decimal) or not 0 <= value <= 600
            or isinstance(value, Decimal) and (not value.is_finite()
                or type(value.as_tuple().exponent) is not int or value.as_tuple().exponent < -9
                or value.as_tuple().exponent > 9 or len(value.as_tuple().digits) > 20)):
        raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 时间戳须为有界秒数')
    return Fraction(value)


class LocalWhisperCppProvider:
    supports_dispatch_guard = True

    def __init__(self, *, provider_id, model_id, endpoint, model_sha256, ffmpeg_path, admission_guard,
            request_authorization=None):
        if (not isinstance(provider_id, str) or not 1 <= len(provider_id) <= 240
                or not isinstance(model_id, str) or not 1 <= len(model_id) <= 240
                or not isinstance(model_sha256, str) or not re.fullmatch(r'[a-f0-9]{64}', model_sha256)
                or not callable(admission_guard)):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, '须显式指定已验证的本地 ASR 模型及其原准入 guard')
        self.provider_id, self.model_id = provider_id, model_id
        self.endpoint, self.model_sha256 = local_endpoint(endpoint), model_sha256
        self._admission_guard = admission_guard
        if request_authorization is not None and not callable(request_authorization):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'ASR 私有传输授权须由原主机 owner 持有')
        self._request_authorization = request_authorization
        self._ffmpeg = _executable(ffmpeg_path)
        self._tool_hash, self._tool_identity = _fingerprint(self._ffmpeg), _file_identity(self._ffmpeg)
        self._execution_lock = threading.Lock()

    def route_snapshot(self):
        proof = self._admission_guard()
        fields = {'schema', 'provider_id', 'model_id', 'endpoint', 'model_sha256', 'runtime_kind',
                  'management', 'enabled', 'model_locality', 'revision'}
        owned_fields = fields | {'runtime_uuid', 'process_id', 'executable_sha256', 'startup_nonce', 'ready_digest'}
        owned = isinstance(proof, dict) and proof.get('schema') == 'host-local-model-admission/2'
        if owned:
            try:
                validate_uuid(proof.get('runtime_uuid'), field='runtime_id')
            except ValueError:
                raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'ASR 原运行时持久身份无效') from None
        if (not isinstance(proof, dict) or set(proof) != (owned_fields if owned else fields)
                or proof.get('schema') not in {'host-local-model-admission/1', 'host-local-model-admission/2'}
                or proof.get('provider_id') != self.provider_id or proof.get('model_id') != self.model_id
                or proof.get('endpoint') != self.endpoint or proof.get('model_sha256') != self.model_sha256
                or proof.get('runtime_kind') != 'WHISPER_CPP' or proof.get('management') != ('MANAGED' if owned else 'EXTERNAL')
                or proof.get('enabled') is not True or proof.get('model_locality') != 'LOCAL_VERIFIED'
                or type(proof.get('revision')) is not int or not 1 <= proof['revision'] <= 2**53 - 1
                or _file_identity(self._ffmpeg) != self._tool_identity
                or owned and (self._request_authorization is None or type(proof.get('process_id')) is not int
                    or proof['process_id'] < 1 or not isinstance(proof.get('runtime_uuid'), str)
                    or any(not isinstance(proof.get(key), str) or not re.fullmatch(r'[a-f0-9]{64}', proof[key])
                           for key in ('executable_sha256', 'startup_nonce', 'ready_digest')))
                or not owned and self._request_authorization is not None):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'ASR 模型或原主机本地准入证据未验证或已变化')
        return {'schema': 'local-audio-admission/1', 'provider_id': self.provider_id, 'model_id': self.model_id,
            'endpoint': self.endpoint, 'model_sha256': self.model_sha256, 'admission_digest': audio_digest(proof),
            'operations': ['ASR'], 'adapter_version': ('studio-fixed-whisper-host/1:' if owned else 'whisper.cpp-server/1:') + self._tool_hash}

    def _pcm(self, request, guard):
        extension = MEDIA_EXTENSIONS.get(request.media_type)
        if extension is None:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'ASR 原媒体格式不受支持')
        if _fingerprint(self._ffmpeg) != self._tool_hash:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'ASR 媒体解码器已变化')
        with tempfile.TemporaryDirectory(prefix='novel-asr-input-') as temporary:
            directory = Path(temporary)
            source, destination = directory / ('source.' + extension), directory / 'input.wav'
            source.write_bytes(request.media)
            command = [str(self._ffmpeg), '-nostdin', '-hide_banner', '-v', 'error', '-y', '-protocol_whitelist',
                'file,pipe', '-i', source.name, '-map', '0:a:0', '-vn', '-map_metadata', '-1', '-ac', '1',
                '-ar', '16000', '-c:a', 'pcm_s16le', '-threads', '1', '-fs', str(MAX_PCM_BYTES + 1), destination.name]
            run_guarded_process(command, cwd=directory, guard=guard, timeout=60)
            guard()
            if not destination.is_file() or not 0 < destination.stat().st_size <= MAX_PCM_BYTES:
                raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'ASR 音频解码超出容量限制')
            content = destination.read_bytes()
            try:
                with wave.open(io.BytesIO(content), 'rb') as audio:
                    duration_ms = Fraction(audio.getnframes() * 1000, audio.getframerate())
                    if (audio.getsampwidth() != 2 or audio.getnchannels() != 1 or audio.getframerate() != 16000
                            or audio.getcomptype() != 'NONE' or not audio.getnframes()
                            or len(audio.readframes(audio.getnframes())) != audio.getnframes() * 2
                            or abs(duration_ms - request.duration_ms) > 100):
                        raise ValueError()
            except (wave.Error, EOFError, ValueError, ZeroDivisionError):
                raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'ASR 音频解码结果与原媒体时长不一致') from None
            guard()
            return content, duration_ms

    def _request(self, content, parameters, guard):
        """No DNS, proxy, redirects, retries, credentials or remote file URLs.

        A watcher closes this one original connection when its authority/source
        fence closes. Older servers may finish inference anyway; the owner
        discards that late output and never automatically replays the request.
        """
        boundary = 'novel-asr-' + uuid4().hex
        pieces = []
        for name, value in parameters.items():
            pieces.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode('utf-8'))
        pieces.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input.wav"\r\n'
                       'Content-Type: audio/wav\r\n\r\n').encode('ascii'))
        pieces += [content, (f'\r\n--{boundary}--\r\n').encode('ascii')]
        parsed = urlsplit(self.endpoint)
        cls = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
        connection = cls(parsed.hostname, parsed.port, timeout=120)
        stop, failures = threading.Event(), []
        deadline = time.monotonic() + 120
        def current():
            guard()
            if time.monotonic() >= deadline:
                raise ModelRuntimeError(RuntimeErrorCode.TIMEOUT, '本地 ASR 等待超时，未自动重发', retryable=False)
        def watch():
            while not stop.wait(0.25):
                try:
                    current()
                except Exception as exc:
                    failures.append(exc)
                    stream = connection.sock
                    if stream is None and response is not None:
                        stream = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
                    if stream is not None:
                        try: stream.shutdown(socket.SHUT_RDWR)
                        except OSError: pass
                    connection.close()
                    return
        watcher, response = None, None
        try:
            current()
            connection.connect()
            current()
            context = copy_context()
            watcher = threading.Thread(target=lambda: context.run(watch), name='original-subtitle-asr-fence', daemon=True)
            watcher.start()
            connection.putrequest('POST', (parsed.path.rstrip('/') or '') + '/inference', skip_accept_encoding=True)
            connection.putheader('Content-Type', 'multipart/form-data; boundary=' + boundary)
            connection.putheader('Content-Length', str(sum(len(part) for part in pieces)))
            connection.putheader('Accept', 'application/json')
            connection.putheader('Accept-Encoding', 'identity')
            connection.putheader('Connection', 'close')
            if self._request_authorization is not None:
                authorization = self._request_authorization()
                if (not isinstance(authorization, dict) or set(authorization) != {
                        'X-Studio-Whisper-Token', 'X-Studio-Whisper-Revision', 'X-Studio-Whisper-PID'}
                        or not isinstance(authorization.get('X-Studio-Whisper-Token'), str)
                        or not re.fullmatch(r'[a-f0-9]{64}', authorization['X-Studio-Whisper-Token'])
                        or any(not isinstance(authorization.get(key), str) or not authorization[key].isdigit()
                               for key in ('X-Studio-Whisper-Revision', 'X-Studio-Whisper-PID'))):
                    raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'ASR 私有进程授权已失效')
                for name, value in authorization.items():
                    connection.putheader(name, value)
            current()
            connection.endheaders()
            for part in pieces:
                for offset in range(0, len(part), 65536):
                    current()
                    connection.send(part[offset:offset + 65536])
            response = connection.getresponse()
            current()
            if (response.status != 200 or str(response.getheader('Content-Type', '')).split(';', 1)[0].lower() != 'application/json'
                    or response.getheader('Content-Encoding', 'identity').lower() not in ('', 'identity')):
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 未返回直接成功的 JSON 完成结果')
            size = response.getheader('Content-Length')
            if size is not None and (not size.isdigit() or int(size) > MAX_RESPONSE_BYTES):
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 结果超出容量限制')
            parts, count = [], 0
            while count <= MAX_RESPONSE_BYTES:
                current()
                part = response.read(min(65536, MAX_RESPONSE_BYTES + 1 - count))
                if not part: break
                parts.append(part); count += len(part)
            current()
            if not count or count > MAX_RESPONSE_BYTES or size is not None and count != int(size):
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 结果为空、超限或不完整')
            if failures:
                raise failures[0]
            return b''.join(parts)
        except Exception:
            if failures:
                raise failures[0]
            raise
        finally:
            stop.set()
            connection.close()
            if watcher is not None:
                watcher.join(timeout=2)

    def process_audio(self, request: AudioProcessingRequest) -> AudioProcessingResponse:
        if (not isinstance(request, AudioProcessingRequest) or request.operation != 'ASR'
                or request.provider_id != self.provider_id or request.model_id != self.model_id):
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, '该真实本地 adapter 仅执行 ASR，不支持强制对齐')
        started = time.monotonic()
        while not self._execution_lock.acquire(timeout=0.25):
            request.dispatch_guard()
            if time.monotonic() - started >= 120:
                raise ModelRuntimeError(RuntimeErrorCode.TIMEOUT, '本地 ASR 正在处理其它任务，请稍后显式重试', retryable=False)
        try:
            request.dispatch_guard()
            pcm, duration_ms = self._pcm(request, request.dispatch_guard)
            parameters = {'response_format': 'verbose_json', 'language': request.language, 'translate': 'false',
                'temperature': '0', 'temperature_inc': '0', 'diarize': 'false', 'tinydiarize': 'false',
                'no_timestamps': 'false', 'token_timestamps': 'false', 'no_language_probabilities': 'true'}
            body = self._request(pcm, parameters, request.dispatch_guard)
            request.dispatch_guard()
            try:
                payload = json.loads(body.decode('utf-8'), parse_float=Decimal, parse_constant=_invalid_number)
            except (ValueError, UnicodeError):
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 返回无效 JSON') from None
            if (not isinstance(payload, dict) or payload.get('task') != 'transcribe' or payload.get('error')
                    or not isinstance(payload.get('segments'), list) or not 1 <= len(payload['segments']) <= 2000
                    or type(payload.get('duration')) not in (int, Decimal)
                    or abs(_seconds(payload['duration']) * 1000 - duration_ms) > 100):
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 没有返回当前完整音频的段时间戳')
            segments, seen, total, previous = [], set(), 0, -1
            for raw in payload['segments']:
                if (not isinstance(raw, dict) or type(raw.get('id')) is not int or raw['id'] < 0 or raw['id'] in seen
                        or type(raw.get('start')) not in (int, Decimal) or type(raw.get('end')) not in (int, Decimal)
                        or not isinstance(raw.get('text'), str) or not raw['text'].strip() or len(raw['text']) > 10000
                        or raw.get('speaker') is not None):
                    raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 段结果无效或需要独立说话人复审')
                start, end = _seconds(raw['start']) * 1000, _seconds(raw['end']) * 1000
                if not 0 <= start < end <= request.duration_ms or start < previous:
                    raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 段时间戳越界或乱序')
                total += len(raw['text'])
                if total > 100000:
                    raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地 ASR 文本超出容量限制')
                seen.add(raw['id']); previous = start
                segments.append({'id': raw['id'], 'start_ms': start.numerator // start.denominator,
                    'end_ms': math.ceil(end), 'text': raw['text'].strip()})
            request.dispatch_guard()
            if _fingerprint(self._ffmpeg) != self._tool_hash:
                raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'ASR 媒体解码器已变化，输出已丢弃')
            return AudioProcessingResponse(self.provider_id, self.model_id, tuple(segments), {
                'schema': 'subtitle-model-execution/1',
                'adapter': 'STUDIO_FIXED_WHISPER_HOST' if self._request_authorization is not None else 'WHISPER_CPP_SERVER',
                'operation': 'ASR',
                'provider_id': self.provider_id, 'model_id': self.model_id, 'route_digest': request.route_digest,
                'source_digest': request.source_digest, 'input_sha256': hashlib.sha256(request.media).hexdigest(),
                'decoded_audio_sha256': hashlib.sha256(pcm).hexdigest(), 'provider_response_sha256': hashlib.sha256(body).hexdigest(),
                'parameters': parameters, 'elapsed_ms': int((time.monotonic() - started) * 1000),
                'model_called': True, 'local': True, 'timing_origin': 'MODEL_SEGMENT_TIMESTAMPS',
                'model_identity_verification': 'OWNED_PRIVATE_PIPE_MODEL_LOAD' if self._request_authorization is not None
                    else 'HOST_ADMISSION_REQUIRED_NO_WIRE_MODEL_ATTESTATION',
                'quality_verification': 'NOT_RUN'})
        finally:
            self._execution_lock.release()


def register_local_whisper_cpp(runtime, *, provider_id, model_id, display_name, endpoint,
        model_sha256, ffmpeg_path, admission_guard):
    """Explicit trusted host registration only; never called by HTTP discovery.

    The original registration paths mint durable identities. A live admission
    proof is mandatory before registration; no source request can install code,
    choose a model file, start the server or turn metadata into a verified model.
    """
    adapter = LocalWhisperCppProvider(provider_id=provider_id, model_id=model_id, endpoint=endpoint,
        model_sha256=model_sha256, ffmpeg_path=ffmpeg_path, admission_guard=admission_guard)
    adapter.route_snapshot()
    if runtime.provider_registry.contains(provider_id) or runtime.model_registry.contains(provider_id, model_id):
        raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, '该原模型或 Provider 标识已经注册，须由原 owner 明确停用或更新')
    runtime.provider_registry.register(ProviderDescriptor(provider_id, display_name, 'local', frozenset({Modality.AUDIO}),
        True, True, 'host_admitted_inference_not_run'), adapter)
    runtime.model_registry.register(ModelDescriptor(model_id, provider_id, display_name, Modality.AUDIO,
        frozenset({'TRANSCRIBE'}), enabled=True))
    return adapter
