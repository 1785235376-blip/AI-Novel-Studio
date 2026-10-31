"""Explicit PDF adapter over the pinned raster and original image OCR owners.

No host registration, Research dispatch, queue or public route is enabled here.
"""
from hashlib import sha256
from threading import Lock
from .audio_processing_runtime import audio_digest
from .local_pdf_raster import LocalPDFPageRasterizer
from .local_tesseract_ocr import LocalTesseractOCRProvider
from .model_runtime import ModelRuntimeError, RuntimeErrorCode
from .vision_ocr_runtime import PDFPageOCRRequest, VisionOCRRequest, VisionOCRResponse


class LocalPDFOCRProvider:
    supports_dispatch_guard = True

    def __init__(self, *, image_provider, rasterizer):
        if type(image_provider) is not LocalTesseractOCRProvider or type(rasterizer) is not LocalPDFPageRasterizer:
            raise ValueError('PDF_OCR_EXPLICIT_NATIVE_OWNERS_REQUIRED')
        self.image_provider, self.rasterizer = image_provider, rasterizer
        self.provider_id, self.model_id = image_provider.provider_id, image_provider.model_id
        self._lock = Lock()
        self.route_snapshot()

    def route_snapshot(self):
        image = self.image_provider.route_snapshot()
        raster = self.rasterizer.route_snapshot()
        if image['provider_id'] != self.provider_id or image['model_id'] != self.model_id:
            raise ValueError('PDF_OCR_OWNER_IDENTITY_CHANGED')
        value = {**image, 'schema': 'local-vision-ocr-pdf-native-admission/1',
            'adapter_version': 'poppler-tesseract-fixed-page/1',
            'renderer_sha256': raster['executable_sha256'], 'renderer_digest': raster['admission_digest']}
        value['admission_digest'] = audio_digest({'image': image, 'raster': raster, 'adapter_version': value['adapter_version']})
        return value

    def recognize_pdf_page(self, request):
        if (type(request) is not PDFPageOCRRequest or request.provider_id != self.provider_id
                or request.model_id != self.model_id or request.language != self.image_provider.language):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'PDF OCR 请求与明确模型不一致')
        if not self._lock.acquire(blocking=False):
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, '本地 PDF OCR 正在执行其他任务', retryable=True)
        try:
            return self._recognize(request)
        finally:
            self._lock.release()

    def _recognize(self, request):
        request.dispatch_guard()
        captured = self.route_snapshot()
        image_owner, raster_owner = self.image_provider, self.rasterizer
        def guard():
            request.dispatch_guard()
            if request.cancellation is not None and request.cancellation.is_set():
                raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, 'PDF OCR 已停止')
            if (self.image_provider is not image_owner or self.rasterizer is not raster_owner
                    or self.route_snapshot() != captured):
                raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, 'PDF OCR 原生工具准入已变化')
        guard()
        page = raster_owner.render(request.content, source_digest=request.source_digest, page=request.page,
            expected_route_digest=captured['renderer_digest'], guard=guard, cancellation=request.cancellation)
        guard()
        image_request = VisionOCRRequest(provider_id=request.provider_id, model_id=request.model_id,
            content=page.content, media_type='image/png', language=request.language,
            source_digest=page.image_digest, route_digest=request.route_digest,
            request_id=request.request_id, dispatch_guard=guard, cancellation=request.cancellation)
        response = image_owner.recognize_image(image_request)
        guard()
        expected = {'model_called': True, 'source_digest': page.image_digest,
            'input_sha256': page.image_digest, 'route_digest': request.route_digest,
            'language': request.language, 'text_sha256': sha256(response.text.encode('utf-8')).hexdigest()}
        if (response.provider_id != request.provider_id or response.model_id != request.model_id
                or response.receipt != expected):
            raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, 'PDF OCR 图片阶段完成回执不一致')
        return VisionOCRResponse(request.provider_id, request.model_id, response.text,
            {**expected, 'source_digest': request.source_digest, 'input_sha256': request.source_digest,
             'source_page': request.page, 'rendered_image_sha256': page.image_digest,
             'renderer_digest': page.renderer_digest})
