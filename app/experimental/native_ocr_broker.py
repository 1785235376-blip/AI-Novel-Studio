"""Private native OCR route inventory over original host registries.

No public Research dispatch is enabled here. Only exact pinned native providers
are eligible; a VISION capability declaration or arbitrary adapter cannot qualify.
"""
from __future__ import annotations
import os
from .planning import digest
from ..model_runtime import Modality

PROFILE = 'LOCAL_NATIVE_OCR_ONLY_V1'


def candidates(runtime):
    from ..local_tesseract_ocr import LocalTesseractOCRProvider
    from ..local_pdf_ocr import LocalPDFOCRProvider
    from ..local_pdf_raster import LocalPDFPageRasterizer
    from ..vision_ocr_runtime import VisionOCRModelNode
    from .model_broker import implementation_hash
    node = runtime.generation_runtime.vision_ocr_node
    if (type(node) is not VisionOCRModelNode or node.providers is not runtime.provider_registry
            or node.models is not runtime.model_registry):
        return []
    items = []
    for model in runtime.model_registry.descriptors():
        if model.modality is not Modality.VISION or 'OCR' not in model.capabilities:
            continue
        try:
            provider = runtime.provider_registry.resolve(model.provider_id)
            pdf = type(provider) is LocalPDFOCRProvider
            if pdf:
                if (type(provider.image_provider) is not LocalTesseractOCRProvider
                        or type(provider.rasterizer) is not LocalPDFPageRasterizer
                        or not os.access(provider.image_provider.executable, os.X_OK)
                        or not os.access(provider.rasterizer.executable, os.X_OK)):
                    continue
            elif type(provider) is not LocalTesseractOCRProvider or not os.access(provider.executable, os.X_OK):
                continue
            binding = node.binding(model.provider_id, model.model_id)
            if binding['route']['schema'] != ('local-vision-ocr-pdf-native-admission/1' if pdf else 'local-vision-ocr-native-admission/1'):
                continue
            identity = {'native_ocr_binding': binding,
                'adapter_hash': implementation_hash(LocalTesseractOCRProvider),
                'executor': 'original.job_manager.research_ocr', 'contract': 1}
            if pdf:
                identity.update(pdf_adapter_hash=implementation_hash(LocalPDFOCRProvider),
                    raster_adapter_hash=implementation_hash(LocalPDFPageRasterizer), source_kind='PDF')
            items.append({'route_id': digest(['native-ocr', model.provider_id, model.model_id]),
                'provider_id': model.provider_id, 'model_id': model.model_id,
                'display_name': model.display_name, 'capability': 'VISION', 'context_window': None,
                'cloud': False, 'synthetic': False, 'available': True, 'reasons': [],
                'fingerprint': digest(identity), 'binding_hash': digest([id(provider), digest(identity)]),
                'identity': identity, 'verification': 'PINNED_NATIVE_RUNTIME_ONLY',
                'executor': 'original.job_manager.research_ocr', 'candidate_profile': PROFILE})
        except (ValueError, RuntimeError, OSError, TypeError, AttributeError):
            continue
    return items
