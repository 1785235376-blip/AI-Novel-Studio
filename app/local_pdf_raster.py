"""Explicit pinned one-page PDF rasterizer, not a queue or public admission.

The caller must supply the original source/host authority guard and the reviewed
renderer digest. No discovery, installation, model registration or Research
operation is enabled by importing or constructing this helper.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import io
import os
from pathlib import Path
import re
import tempfile
from threading import Event, Lock
from .audio_processing_runtime import audio_digest
from .local_tesseract_ocr import _pinned_file
from .model_runtime import ModelRuntimeError, RuntimeErrorCode

MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_SIDE = 2048


@dataclass(frozen=True)
class PDFPageRaster:
    content: bytes
    source_digest: str
    page: int
    width: int
    height: int
    image_digest: str
    renderer_digest: str


class LocalPDFPageRasterizer:
    def __init__(self, *, executable, executable_sha256):
        self.executable = Path(executable)
        self.executable_sha256 = executable_sha256
        self._lock = Lock()
        self.route_snapshot()

    def route_snapshot(self):
        _pinned_file(self.executable, self.executable_sha256, 64 * 1024 * 1024)
        value = {'contract': 'local-pdf-page-raster/1', 'executable_sha256': self.executable_sha256,
            'maximum_input_bytes': MAX_INPUT_BYTES, 'maximum_output_bytes': MAX_OUTPUT_BYTES,
            'maximum_side': MAX_SIDE, 'annotations': False, 'adapter_version': 'poppler-fixed-page/1'}
        value['admission_digest'] = audio_digest({**value, 'executable': str(self.executable)})
        return value

    def render(self, content, *, source_digest, page, expected_route_digest, guard, cancellation=None):
        if (type(content) is not bytes or not 0 < len(content) <= MAX_INPUT_BYTES or not content.startswith(b'%PDF-')
                or type(page) is not int or not 1 <= page <= 1000 or not callable(guard)
                or not isinstance(source_digest, str) or not re.fullmatch('[a-f0-9]{64}', source_digest)
                or sha256(content).hexdigest() != source_digest
                or not isinstance(expected_route_digest, str) or not re.fullmatch('[a-f0-9]{64}', expected_route_digest)
                or cancellation is not None and not isinstance(cancellation, Event)):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'PDF 页须绑定原始字节、明确页码与已核对的本地渲染器')
        if not self._lock.acquire(blocking=False):
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, '本地 PDF 渲染器正在执行其他任务', retryable=True)
        try:
            return self._render(content, source_digest, page, expected_route_digest, guard, cancellation)
        finally:
            self._lock.release()

    def _render(self, content, source_digest, page, expected_route_digest, source_guard, cancellation):
        from PIL import Image
        from .experimental.subtitle_alignment_native import run_alignment_process
        source_guard()
        try:
            captured = self.route_snapshot()
        except (OSError, ValueError) as exc:
            raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, '已核对的 PDF 渲染器文件不可用') from exc
        if captured['admission_digest'] != expected_route_digest:
            raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, 'PDF 渲染器准入已改变')
        def current():
            if cancellation is not None and cancellation.is_set():
                raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, 'PDF 页渲染已停止')
            source_guard()
            try:
                valid = self.route_snapshot() == captured
            except (OSError, ValueError):
                valid = False
            if not valid:
                raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, 'PDF 渲染器文件已变化')
        current()
        with tempfile.TemporaryDirectory(prefix='studio-pdf-page-') as temporary:
            folder = Path(temporary); source = folder / 'input.pdf'; source.write_bytes(content)
            output = folder / 'page.png'; (folder / 'cache').mkdir()
            env = {'LC_ALL': 'C', 'LANG': 'C', 'HOME': str(folder), 'XDG_CACHE_HOME': str(folder / 'cache')}
            if os.name == 'nt' and os.environ.get('SystemRoot'):
                env['SystemRoot'] = os.environ['SystemRoot']
            command = [str(self.executable), '-f', str(page), '-l', str(page), '-singlefile', '-scale-to', str(MAX_SIDE),
                '-png', '-hide-annotations', str(source), str(folder / 'page')]
            try:
                run_alignment_process(command, cwd=folder, env=env, guard=current, timeout=30)
            except OSError as exc:
                raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, '本地 PDF 渲染器不能启动') from exc
            except ValueError as exc:
                if not str(exc).startswith('PROCESSING_ALIGNMENT_'):
                    raise
                code = RuntimeErrorCode.TIMEOUT if str(exc).endswith('_TIMEOUT') else RuntimeErrorCode.GENERATION_FAILED
                raise ModelRuntimeError(code, 'PDF 页未能渲染，请检查页码和本地工具') from exc
            current()
            if output.is_symlink() or not output.is_file() or not 0 < output.stat().st_size <= MAX_OUTPUT_BYTES:
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, 'PDF 页输出超出支持范围')
            raw = output.read_bytes()
            try:
                with Image.open(io.BytesIO(raw)) as image:
                    if (image.format != 'PNG' or getattr(image, 'n_frames', 1) != 1 or image.width > MAX_SIDE
                            or image.height > MAX_SIDE or image.width * image.height > MAX_SIDE * MAX_SIDE):
                        raise ValueError('PDF_RASTER_IMAGE_LIMIT')
                    image.load(); width, height = image.size
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, 'PDF 页没有产生有效的有界 PNG') from exc
            current()
            return PDFPageRaster(raw, source_digest, page, width, height, sha256(raw).hexdigest(), captured['admission_digest'])
