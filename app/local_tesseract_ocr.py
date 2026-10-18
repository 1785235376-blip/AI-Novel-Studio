"""Explicit pinned local Tesseract adapter; no discovery, installation or queue.

This provider must be installed into the original host registries by a trusted
owner. Merely constructing it never starts a process. Research dispatch remains
closed until its original JobManager/admission integration is complete.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import re
import tempfile
import threading

from .audio_processing_runtime import audio_digest
from .model_runtime import ModelRuntimeError, RuntimeErrorCode
from .vision_ocr_runtime import VisionOCRRequest, VisionOCRResponse


def _pinned_file(path, expected, maximum):
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        raise ValueError('OCR_NATIVE_ABSOLUTE_REGULAR_FILE_REQUIRED')
    if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
        raise ValueError('OCR_NATIVE_FILE_PIN_REQUIRED')
    if not path.is_file() or not 1 <= path.stat().st_size <= maximum:
        raise ValueError('OCR_NATIVE_FILE_LIMIT')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError('OCR_NATIVE_FILE_CHANGED')


class LocalTesseractOCRProvider:
    supports_dispatch_guard = True

    def __init__(self, *, provider_id, model_id, executable, executable_sha256,
                 traineddata, model_sha256, language):
        if not isinstance(language, str) or not re.fullmatch('[A-Za-z]{2,3}', language):
            raise ValueError('OCR_NATIVE_EXPLICIT_LANGUAGE_REQUIRED')
        self.provider_id, self.model_id = provider_id, model_id
        self.executable, self.traineddata = Path(executable), Path(traineddata)
        self.executable_sha256, self.model_sha256, self.language = executable_sha256, model_sha256, language
        if self.traineddata.name != language + '.traineddata':
            raise ValueError('OCR_NATIVE_LANGUAGE_FILE_MISMATCH')
        self._lock = threading.Lock()
        self.route_snapshot()

    def route_snapshot(self):
        _pinned_file(self.executable, self.executable_sha256, 64 * 1024 * 1024)
        _pinned_file(self.traineddata, self.model_sha256, 64 * 1024 * 1024)
        route = {'schema': 'local-vision-ocr-native-admission/1',
            'provider_id': self.provider_id, 'model_id': self.model_id,
            'model_sha256': self.model_sha256, 'executable_sha256': self.executable_sha256,
            'languages': [self.language], 'adapter_version': 'tesseract-fixed-image/1'}
        # Paths participate in admission, but do not leak into returned metadata.
        route['admission_digest'] = audio_digest({**route,
            'executable': str(self.executable), 'traineddata': str(self.traineddata)})
        return route

    def recognize_image(self, request):
        if (not isinstance(request, VisionOCRRequest) or request.provider_id != self.provider_id
                or request.model_id != self.model_id or request.language != self.language):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'OCR 本地请求与已配置模型不一致')
        if not self._lock.acquire(blocking=False):
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, '本地 OCR 正在执行其他任务', retryable=True)
        try:
            return self._recognize(request)
        finally:
            self._lock.release()

    def _recognize(self, request):
        from PIL import Image
        from .experimental.subtitle_alignment_native import run_alignment_process
        request.dispatch_guard()
        captured = self.route_snapshot()
        def guard():
            if request.cancellation is not None and request.cancellation.is_set():
                raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, '已停止 OCR')
            request.dispatch_guard()
            if self.route_snapshot() != captured:
                raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, 'OCR 本地文件已变化')
        guard()
        with tempfile.TemporaryDirectory(prefix='studio-ocr-') as temporary:
            folder = Path(temporary)
            try:
                with Image.open(io.BytesIO(request.content)) as source:
                    expected = 'PNG' if request.media_type == 'image/png' else 'JPEG'
                    if (source.format != expected or getattr(source, 'n_frames', 1) != 1
                            or source.width > 8192 or source.height > 8192
                            or source.width * source.height > 16_000_000):
                        raise ValueError('OCR_NATIVE_IMAGE_LIMIT')
                    source.load()
                    # Composite transparency on paper white rather than turning
                    # transparent black pixels into a black OCR background.
                    with source.convert('RGBA') as foreground:
                        with Image.new('RGBA', foreground.size, 'white') as paper:
                            paper.alpha_composite(foreground)
                            with paper.convert('RGB') as pixels:
                                pixels.save(folder / 'input.png', format='PNG')
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'OCR 图片格式或尺寸不受支持') from exc
            guard()
            env = {'OMP_THREAD_LIMIT': '1', 'LC_ALL': 'C', 'LANG': 'C'}
            if os.name == 'nt' and os.environ.get('SystemRoot'):
                env['SystemRoot'] = os.environ['SystemRoot']
            output = folder / 'output.txt'
            command = [str(self.executable), str(folder / 'input.png'), 'stdout',
                '--tessdata-dir', str(self.traineddata.parent), '-l', self.language, '--psm', '6']
            try:
                run_alignment_process(command, cwd=folder, env=env, guard=guard, timeout=30, stdout_path=output)
            except OSError as exc:
                raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, '本地 OCR 工具不可用') from exc
            except ValueError as exc:
                if not str(exc).startswith('PROCESSING_ALIGNMENT_'):
                    raise
                code = RuntimeErrorCode.TIMEOUT if str(exc).endswith('_TIMEOUT') else RuntimeErrorCode.GENERATION_FAILED
                raise ModelRuntimeError(code, '本地 OCR 未能完成，请检查已配置的本地工具') from exc
            guard()
            if output.stat().st_size > 256 * 1024:
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, 'OCR 输出超出大小限制')
            try:
                text = output.read_bytes().decode('utf-8').strip()
            except UnicodeError as exc:
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, 'OCR 输出不是有效文本') from exc
            if not text or '\x00' in text:
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, 'OCR 没有提取到有效文字')
            return VisionOCRResponse(self.provider_id, self.model_id, text,
                {'model_called': True, 'source_digest': request.source_digest,
                 'input_sha256': hashlib.sha256(request.content).hexdigest(),
                 'route_digest': request.route_digest, 'language': request.language,
                 'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()})
