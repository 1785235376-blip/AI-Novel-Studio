"""One-page OpenRaster export, not a native project archive or ORA importer.

Reference layers render separately; native text remains in Comic storage.
Only the original Comic service authorizes this pure, bounded codec.
"""
from __future__ import annotations

import io
import json
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring
from .comic_layers import iter_layer_images, composite_layer

MAX_ORA_BYTES = 64 * 1024 * 1024
LOSSES = [
    'TEXT_AND_SHAPES_RASTERIZED_IN_ORA_NATIVE_COMIC_TEXT_REMAINS_EDITABLE',
    'NO_NATIVE_PANEL_CHARACTER_SOURCE_HISTORY_OR_APPROVAL_RESTORE_FROM_ORA',
    'NORMAL_SOURCE_OVER_ONLY_NO_MASKS_EFFECTS_OR_VECTOR_TEXT_EXCHANGE',
    'ORA_IMPORT_AND_TARGET_APPLICATION_ROUNDTRIP_NOT_IMPLEMENTED',
]


class _BoundedBuffer(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_ORA_BYTES:
            raise ValueError('COMIC_ORA_SIZE_LIMIT')
        return super().write(data)


def _png(image):
    output = _BoundedBuffer()
    image.save(output, format='PNG', compress_level=9)
    return output.getvalue()


def encode_ora(document, images, report, version):
    from PIL import Image
    from .comic_layouts import licensed_font
    output = _BoundedBuffer()
    root = Element('image', {'version': '0.0.6', 'w': str(document['width']), 'h': str(document['height']), 'name': document['title']})
    stack = SubElement(root, 'stack')
    canvas = Image.new('RGBA', (document['width'], document['height']), 'white')
    entries = []
    receipt = {'format': 'comic-ora-reference-layers-v1', 'layout_version': version,
               'review_digest': report['review_digest'], 'losses': LOSSES,
               'native_project_modified': False, 'automatic_publication': False,
               'privacy_level': 'LOCAL_ONLY', 'layers': []}

    def put(archive, name, data):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, data)

    with zipfile.ZipFile(output, 'w') as archive:
        put(archive, 'mimetype', b'image/openraster')
        for index, (item, x, y, surface) in enumerate(iter_layer_images(document, images, report['placements'])):
            path = f'data/layer-{index + 1:03}.png'
            put(archive, path, _png(surface))
            entries.append({'name': item['name'], 'src': path, 'x': str(x), 'y': str(y),
                            'opacity': f"{item['opacity_percent'] / 100:.2f}",
                            'visibility': 'visible' if item['visible'] else 'hidden', 'composite-op': 'svg:src-over'})
            receipt['layers'].append({'id': item['id'], 'kind': item['kind'], 'target_id': item['target_id'], 'src': path})
            composite_layer(canvas, item, x, y, surface)
        # Explicit paper layer keeps the ordinary ORA composite equal to preview.
        paper = Image.new('RGB', canvas.size, 'white')
        put(archive, 'data/paper.png', _png(paper))
        paper.close()
        for attrs in reversed(entries): SubElement(stack, 'layer', attrs)
        SubElement(stack, 'layer', {'name': 'Paper', 'src': 'data/paper.png', 'x': '0', 'y': '0',
                                    'opacity': '1.00', 'visibility': 'visible', 'composite-op': 'svg:src-over'})
        put(archive, 'stack.xml', tostring(root, encoding='utf-8', xml_declaration=True))
        put(archive, 'mergedimage.png', _png(canvas.convert('RGB')))
        thumbnail = canvas.convert('RGB'); thumbnail.thumbnail((256, 256), Image.Resampling.LANCZOS)
        put(archive, 'Thumbnails/thumbnail.png', _png(thumbnail))
        put(archive, 'comic-loss-receipt.json', json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode())
        if any(p['bubbles'] for p in document['panels']):
            put(archive, 'OFL.txt', licensed_font()[1])
    return output.getvalue()
