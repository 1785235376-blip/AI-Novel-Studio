"""Pure bounded OpenRaster inspection. No files, assets, grants or projects written.

This accepts an explicit flat, 8-bit RGB/RGBA, normal-blend subset. Returned
pixels are raster candidates, never editable dialogue or trusted provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import io
import re
import stat
import struct
import zipfile
import zlib
from xml.etree.ElementTree import XMLPullParser, ParseError

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_PNG = 25 * 1024 * 1024
MAX_XML = 512 * 1024
MAX_MEMBERS = 262
MAX_LAYERS = 256
MAX_LAYER_PIXELS = 64_000_000
MAX_DECODE_WORK = 192_000_000
PROFILE = 'COMIC_ORA_FLAT_RASTER_PREVIEW_V1'
IGNORED = {'comic-loss-receipt.json': 256 * 1024, 'OFL.txt': 64 * 1024}
LOSSES = (
    'RASTER_LAYERS_ONLY_NO_EDITABLE_DIALOGUE_RECOVERY',
    'ARCHIVE_IDS_APPROVALS_AND_SIDECARS_ARE_UNTRUSTED',
    'EXTERNAL_ARTWORK_ORIGIN_AND_LICENSE_NOT_VERIFIED',
    'NO_ASSET_STAGING_REVIEW_OR_PAGE_ATTACHMENT',
)


@dataclass(frozen=True)
class RasterLayer:
    name: str
    x: int
    y: int
    opacity_percent: int
    visible: bool
    width: int
    height: int
    member: str
    member_sha256: str
    png: bytes


@dataclass(frozen=True)
class OraPreview:
    report: dict
    layers: tuple[RasterLayer, ...]  # bottom first; no archived native identifiers
    preview_png: bytes


def _fail(code):
    raise ValueError('COMIC_ORA_' + code)


def _name(value, maximum):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or any(
            ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value):
        _fail('NAME_INVALID')
    return value


def _zip_directory(raw):
    # Bound the central-directory entry count BEFORE ZipFile creates ZipInfo
    # objects. ZIP64, split archives, trailing payloads and oversized comments
    # are outside this small profile.
    if not isinstance(raw, bytes) or not 22 <= len(raw) <= MAX_ARCHIVE:
        _fail('ARCHIVE_SIZE_LIMIT')
    end = raw.rfind(b'PK\x05\x06', max(0, len(raw) - 22 - 4096))
    if end < 0 or end + 22 > len(raw): _fail('ZIP_DIRECTORY_INVALID')
    _, disk, directory_disk, count_disk, count, size, offset, comment = struct.unpack_from('<4s4H2IH', raw, end)
    if (disk or directory_disk or count != count_disk or not 4 <= count <= MAX_MEMBERS
            or comment > 4096 or end + 22 + comment != len(raw)
            or offset + size != end or not count * 46 <= size <= count * (46 + 240 + 2048) or offset < 30):
        _fail('ZIP_DIRECTORY_INVALID')
    cursor = offset
    for _ in range(count):
        if cursor + 46 > end or raw[cursor:cursor + 4] != b'PK\x01\x02': _fail('ZIP_DIRECTORY_INVALID')
        name, extra, note = struct.unpack_from('<HHH', raw, cursor + 28)
        if not 1 <= name <= 240 or extra > 1024 or note > 1024: _fail('ZIP_DIRECTORY_INVALID')
        cursor += 46 + name + extra + note
        if cursor > end: _fail('ZIP_DIRECTORY_INVALID')
    if cursor != end: _fail('ZIP_DIRECTORY_INVALID')
    return count


def _path(name):
    if (not isinstance(name, str) or len(name) > 240 or '\\' in name
            or not re.fullmatch(r'[A-Za-z0-9_./-]+', name)
            or len(name.split('/')) > 5 or any(p in ('', '.', '..') for p in name.split('/'))):
        _fail('ZIP_PATH_INVALID')
    return name


def _read(archive, info, maximum):
    if info.file_size > maximum: _fail('MEMBER_SIZE_LIMIT')
    output = io.BytesIO()
    with archive.open(info) as member:
        while True:
            block = member.read(min(65536, maximum + 1 - output.tell()))
            if not block: break
            output.write(block)
            if output.tell() > maximum: _fail('MEMBER_SIZE_LIMIT')
    value = output.getvalue()
    if len(value) != info.file_size: _fail('MEMBER_SIZE_MISMATCH')
    return value


def _integer(value, low, high):
    if not isinstance(value, str) or not re.fullmatch(r'[+-]?[0-9]{1,6}', value): _fail('INTEGER_INVALID')
    result = int(value)
    if not low <= result <= high: _fail('INTEGER_LIMIT')
    return result


def _xml(data):
    if len(data) > MAX_XML: _fail('XML_SIZE_LIMIT')
    try: text = data.decode('utf-8-sig')
    except UnicodeError: _fail('XML_UTF8_REQUIRED')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper(): _fail('XML_DECLARATIONS_FORBIDDEN')
    declaration = re.match(r'\s*<\?xml\s+([^?]+)\?>', text)
    if declaration:
        encoding = re.search(r'encoding\s*=\s*[\'"]([^\'"]+)', declaration.group(1), re.I)
        if encoding and encoding.group(1).lower() not in ('utf-8', 'utf8'): _fail('XML_UTF8_REQUIRED')
    parser = XMLPullParser(events=('start', 'end'))
    depth = nodes = 0; root = None
    try:
        for start in range(0, len(text), 4096):
            parser.feed(text[start:start + 4096])
            for event, element in parser.read_events():
                if event == 'start':
                    depth += 1; nodes += 1
                    if root is None: root = element
                    if depth > 3 or nodes > MAX_LAYERS + 2 or len(element.attrib) > 8:
                        _fail('XML_STRUCTURE_LIMIT')
                    if len(element.tag) > 32 or any(len(k) > 32 or len(v) > 240 for k, v in element.attrib.items()):
                        _fail('XML_ATTRIBUTE_LIMIT')
                else: depth -= 1
        parser.close()
    except (ParseError, UnicodeError): _fail('XML_INVALID')
    if root is None or root.tag != 'image' or set(root.attrib) - {'version', 'w', 'h', 'name'}:
        _fail('IMAGE_PROFILE_UNSUPPORTED')
    if root.get('version', '0.0.6') not in {f'0.0.{i}' for i in range(1, 7)}: _fail('VERSION_UNSUPPORTED')
    width, height = _integer(root.get('w'), 320, 1600), _integer(root.get('h'), 320, 12000)
    if width * height > 16_000_000: _fail('PAGE_PIXEL_LIMIT')
    title = _name(root.get('name', 'Imported raster page'), 240)
    if len(root) != 1 or root[0].tag != 'stack' or root[0].attrib: _fail('FLAT_STACK_REQUIRED')
    stack = root[0]
    if not 1 <= len(stack) <= MAX_LAYERS: _fail('LAYER_COUNT_LIMIT')
    for element in root.iter():
        if (element.text and element.text.strip()) or (element.tail and element.tail.strip()): _fail('XML_CONTENT_UNSUPPORTED')
    layers = []; sources = set()
    for index, element in enumerate(stack):
        if element.tag != 'layer' or len(element) or set(element.attrib) - {'src', 'name', 'x', 'y', 'opacity', 'visibility', 'composite-op'}:
            _fail('FLAT_RASTER_LAYER_REQUIRED')
        src = _path(element.get('src'))
        if not src.startswith('data/') or not src.endswith('.png') or src in sources: _fail('LAYER_SOURCE_UNSUPPORTED')
        sources.add(src)
        if element.get('composite-op', 'svg:src-over') != 'svg:src-over': _fail('BLEND_UNSUPPORTED')
        visibility = element.get('visibility', 'visible')
        if visibility not in ('visible', 'hidden'): _fail('VISIBILITY_INVALID')
        opacity = element.get('opacity', '1')
        if not re.fullmatch(r'(?:0|1)(?:\.[0-9]{1,12})?', opacity): _fail('OPACITY_UNSUPPORTED')
        opacity = Decimal(opacity) * 100
        if not 0 <= opacity <= 100 or opacity != opacity.to_integral_value(): _fail('OPACITY_PRECISION_UNSUPPORTED')
        layers.append({'name': _name(element.get('name', f'Layer {index + 1}'), 120), 'member': src,
                       'x': _integer(element.get('x', '0'), -12000, 12000), 'y': _integer(element.get('y', '0'), -12000, 12000),
                       'visible': visibility == 'visible', 'opacity_percent': int(opacity)})
    return title, width, height, layers


class _Budget:
    def __init__(self): self.remaining = MAX_DECODE_WORK
    def consume(self, pixels):
        if pixels > self.remaining: _fail('DECODE_WORK_LIMIT')
        self.remaining -= pixels


def _png(data, budget, *, maximum_pixels=20_000_000):
    """Validate PNG structure/CRC and bound zlib work before invoking Pillow.

    Strip ancillary metadata before Pillow sees it, avoiding compressed text or
    profile expansion. Unsupported color-management and animation are rejected.
    """
    from PIL import Image
    if not data.startswith(b'\x89PNG\r\n\x1a\n'): _fail('PNG_REQUIRED')
    position = 8; chunks = []; ids = []; width = height = color = None
    ended = seen_data = ended_data = seen_palette = False; metadata = False
    while position < len(data):
        if position + 12 > len(data) or len(chunks) >= 4096: _fail('PNG_STRUCTURE_INVALID')
        length = struct.unpack_from('>I', data, position)[0]
        stop = position + 12 + length
        if stop > len(data): _fail('PNG_STRUCTURE_INVALID')
        kind = data[position + 4:position + 8]; value = data[position + 8:stop - 4]
        if not re.fullmatch(b'[A-Za-z]{4}', kind) or kind[2] & 32 or zlib.crc32(kind + value) & 0xFFFFFFFF != struct.unpack_from('>I', data, stop - 4)[0]:
            _fail('PNG_CRC_INVALID')
        if width is None:
            if kind != b'IHDR' or length != 13: _fail('PNG_IHDR_REQUIRED')
            width, height, bits, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', value)
            if (not 1 <= width <= 16000 or not 1 <= height <= 16000 or width * height > maximum_pixels
                    or bits != 8 or color not in (2, 6) or compression or filtering or interlace):
                _fail('PNG_PROFILE_UNSUPPORTED')
            budget.consume(width * height)  # bounded zlib scan below
        elif kind == b'IHDR': _fail('PNG_STRUCTURE_INVALID')
        if kind in (b'acTL', b'fcTL', b'fdAT', b'iCCP', b'gAMA', b'cHRM', b'cICP'):
            _fail('PNG_EFFECT_OR_COLOR_PROFILE_UNSUPPORTED')
        if kind == b'IDAT':
            if ended_data or len(ids) >= 2048: _fail('PNG_STRUCTURE_INVALID')
            seen_data = True; ids.append(value)
        elif seen_data: ended_data = True
        if kind == b'IEND':
            if length or not seen_data or stop != len(data): _fail('PNG_STRUCTURE_INVALID')
            ended = True
        if kind == b'tRNS': _fail('PNG_TRANSPARENCY_PROFILE_UNSUPPORTED')
        if kind == b'PLTE':
            if seen_palette or seen_data or not 3 <= length <= 768 or length % 3:
                _fail('PNG_STRUCTURE_INVALID')
            seen_palette = True
        if kind not in (b'IHDR', b'IDAT', b'IEND'):
            if not kind[0] & 32 and kind != b'PLTE': _fail('PNG_CRITICAL_CHUNK_UNSUPPORTED')
            metadata = True
        chunks.append((kind, data[position:stop])); position = stop
    if not ended: _fail('PNG_STRUCTURE_INVALID')
    expected = height * (width * (3 if color == 2 else 4) + 1)
    decoder = zlib.decompressobj(); count = 0
    try:
        for compressed in ids:
            pending = compressed
            while pending:
                decoded = decoder.decompress(pending, min(65536, expected + 1 - count))
                count += len(decoded)
                if count > expected or decoder.unused_data: _fail('PNG_DECOMPRESSED_SIZE_INVALID')
                pending = decoder.unconsumed_tail
        if not decoder.eof or count != expected: _fail('PNG_DECOMPRESSED_SIZE_INVALID')
    except zlib.error: _fail('PNG_DECOMPRESSION_INVALID')
    clean = b'\x89PNG\r\n\x1a\n' + b''.join(chunk for kind, chunk in chunks if kind in (b'IHDR', b'IDAT', b'IEND'))
    budget.consume(width * height)  # actual Pillow pixel decode
    try:
        with Image.open(io.BytesIO(clean)) as image:
            image.load(); result = image.convert('RGBA')
    except (OSError, ValueError, Image.DecompressionBombError): _fail('PNG_INVALID')
    result.info.clear()
    return result, metadata


def preview_ora(raw: bytes) -> OraPreview:
    """Decode/recompose a supported archive without any persistence or trust grant."""
    from PIL import Image
    from .comic_layouts import renderer_status
    from .comic_ora import _png as encode_png
    from .comic_layers import composite_layer
    if not renderer_status()['available']: _fail('PINNED_RENDERER_REQUIRED')
    count = _zip_directory(raw)
    budget = _Budget(); losses = list(LOSSES)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist(); members = {}; folded = set(); total = 0
            if len(infos) != count: _fail('ZIP_DIRECTORY_INVALID')
            for info in infos:
                name = _path(info.filename); folded_name = name.casefold()
                mode = info.external_attr >> 16
                if (folded_name in folded or info.is_dir() or stat.S_ISLNK(mode)
                        or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)) or info.external_attr & 0x10
                        or info.flag_bits & ~(0x800 | 0x8 | 0x6)
                        or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or info.file_size < 0 or info.file_size > MAX_TOTAL
                        or info.file_size > max(info.compress_size, 1) * 200):
                    _fail('ZIP_MEMBER_UNSUPPORTED')
                total += info.file_size
                if total > MAX_TOTAL: _fail('UNCOMPRESSED_SIZE_LIMIT')
                folded.add(folded_name); members[name] = info
            if infos[0].header_offset != 0 or infos[0].filename != 'mimetype' or infos[0].compress_type != zipfile.ZIP_STORED or _read(archive, infos[0], 16) != b'image/openraster':
                _fail('MIMETYPE_INVALID')
            if not {'stack.xml', 'mergedimage.png', 'Thumbnails/thumbnail.png'}.issubset(members): _fail('REQUIRED_MEMBER_MISSING')
            title, width, height, specs = _xml(_read(archive, members['stack.xml'], MAX_XML))
            references = {s['member'] for s in specs}
            if not references.issubset(members): _fail('LAYER_MEMBER_MISSING')
            allowed = references | {'mimetype', 'stack.xml', 'mergedimage.png', 'Thumbnails/thumbnail.png'} | set(IGNORED)
            if set(members) - allowed: _fail('UNREFERENCED_MEMBER_UNSUPPORTED')
            for name, limit in IGNORED.items():
                if name in members:
                    _read(archive, members[name], limit)  # CRC/size only; NEVER parse/trust
                    losses.append('IGNORED_UNTRUSTED_SIDECAR:' + name)
            canvas = Image.new('RGBA', (width, height))
            layers = []; layer_pixels = canonical_bytes = 0
            for spec in reversed(specs):
                source = _read(archive, members[spec['member']], MAX_PNG)
                # Header aggregate bound precedes even zlib pixel scanning.
                if len(source) < 33 or source[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR': _fail('PNG_IHDR_REQUIRED')
                w, h = struct.unpack_from('>II', source, 16)
                layer_pixels += w * h
                if layer_pixels > MAX_LAYER_PIXELS: _fail('LAYER_PIXEL_LIMIT')
                surface, metadata = _png(source, budget)
                if metadata: losses.append('PNG_METADATA_NOT_IMPORTED:' + spec['member'])
                canonical = encode_png(surface); canonical_bytes += len(canonical)
                if len(canonical) > MAX_PNG: _fail('CANONICAL_MEMBER_SIZE_LIMIT')
                if canonical_bytes > MAX_TOTAL: _fail('CANONICAL_LAYER_BYTES_LIMIT')
                layers.append(RasterLayer(**spec, width=w, height=h, member_sha256=hashlib.sha256(source).hexdigest(), png=canonical))
                if spec['x'] < 0 or spec['y'] < 0 or spec['x'] + w > width or spec['y'] + h > height:
                    losses.append('LAYER_CLIPPED_IN_PAGE_PREVIEW:' + spec['member'])
                budget.consume(w * h)  # include recomposition in the operation work cap
                composite_layer(canvas, spec, spec['x'], spec['y'], surface)
                surface.close()
            merged, metadata = _png(_read(archive, members['mergedimage.png'], MAX_TOTAL), budget, maximum_pixels=16_000_000)
            if metadata: losses.append('PNG_METADATA_NOT_IMPORTED:mergedimage.png')
            if merged.size != canvas.size: _fail('MERGED_IMAGE_DIMENSIONS_INVALID')
            merged_matches = merged.tobytes() == canvas.tobytes(); merged.close()
            if not merged_matches: losses.append('ARCHIVED_MERGED_PREVIEW_MISMATCH_RECOMPOSED_FROM_LAYERS')
            thumbnail, metadata = _png(_read(archive, members['Thumbnails/thumbnail.png'], 1024 * 1024), budget, maximum_pixels=65536)
            if metadata: losses.append('PNG_METADATA_NOT_IMPORTED:Thumbnails/thumbnail.png')
            if max(thumbnail.size) > 256: _fail('THUMBNAIL_DIMENSIONS_INVALID')
            thumbnail.close()
            preview = encode_png(canvas); canvas.close()
    except (zipfile.BadZipFile, RuntimeError, EOFError, NotImplementedError, zlib.error):
        _fail('ZIP_INVALID')
    digest = hashlib.sha256(raw).hexdigest()
    report = {'profile': PROFILE, 'archive_sha256': digest, 'title': title, 'width': width, 'height': height,
              'layer_count': len(layers), 'layer_pixels': layer_pixels, 'decoded_work_pixels': MAX_DECODE_WORK - budget.remaining,
              'merged_preview_matches': merged_matches, 'losses': losses, 'writes_performed': False,
              'composite_work_pixels': layer_pixels, 'unsupported_semantics_policy': 'REJECT',
              'sidecar_trust': 'NONE', 'approval_imported': False, 'origin_verified': False,
              'ignored_metadata': [loss for loss in losses if loss.startswith(('IGNORED_UNTRUSTED_SIDECAR:', 'PNG_METADATA_NOT_IMPORTED:'))],
              'layers': [{k: getattr(layer, k) for k in ('name', 'x', 'y', 'opacity_percent', 'visible', 'width', 'height', 'member', 'member_sha256')} |
                         {'png_sha256': hashlib.sha256(layer.png).hexdigest()} for layer in layers]}
    return OraPreview(report, tuple(layers), preview)
