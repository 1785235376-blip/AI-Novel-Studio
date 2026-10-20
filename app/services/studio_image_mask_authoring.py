"""Closed manual bitplane/PNG bytes. No image library, native process or provider.

The deliberately narrow source contract is 8-bit, noninterlaced PNG containing
only IHDR, contiguous IDAT and IEND. Ancillary/orientation/animation chunks are
not silently interpreted or copied. This is manual masking, not segmentation.
"""
from __future__ import annotations

import base64
import hashlib
import re
import struct
import zlib

CONTRACT = 'manual-binary-mask/1'
SOURCE_MAX_BYTES = 8 * 1024 * 1024
MAX_PLANE_BYTES = 1024 * 1024 // 8
MAX_PNG_BYTES = 1024 * 1025 + 17 * 5 + 63
SIGNATURE = b'\x89PNG\r\n\x1a\n'
DIGEST = re.compile(r'^[a-f0-9]{64}$')


def dimensions(width, height):
    if any(type(n) is not int or not 64 <= n <= 1024 or n % 8 for n in (width, height)):
        raise ValueError('IMAGE_MASK_DIMENSIONS_INVALID')


def _chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


def _png(raw, width, height):
    # Explicit stored-DEFLATE framing keeps the versioned output byte identity
    # independent of zlib compressor versions and has a fixed output ceiling.
    parts = [b'\x78\x01']
    for offset in range(0, len(raw), 65535):
        block = raw[offset:offset + 65535]
        parts.append(bytes([int(offset + len(block) == len(raw))])
                     + struct.pack('<HH', len(block), len(block) ^ 0xffff) + block)
    parts.append(struct.pack('>I', zlib.adler32(raw) & 0xffffffff))
    return (SIGNATURE + _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
            + _chunk(b'IDAT', b''.join(parts)) + _chunk(b'IEND', b''))


def encode_mask(width, height, bitplane_base64, *, checkpoint=lambda: None):
    dimensions(width, height)
    expected = width * height // 8
    if (not isinstance(bitplane_base64, str)
            or len(bitplane_base64) != 4 * ((expected + 2) // 3)):
        raise ValueError('IMAGE_MASK_BITPLANE_INVALID')
    try:
        plane = base64.b64decode(bitplane_base64, validate=True)
    except (ValueError, TypeError):
        raise ValueError('IMAGE_MASK_BITPLANE_INVALID') from None
    if len(plane) != expected or base64.b64encode(plane).decode('ascii') != bitplane_base64:
        raise ValueError('IMAGE_MASK_BITPLANE_INVALID')
    keep = sum(value.bit_count() for value in plane)
    if keep in {0, width * height}:
        raise ValueError('IMAGE_MASK_BOTH_COLORS_REQUIRED')
    checkpoint()
    raw = bytearray()
    for y in range(height):
        checkpoint(); raw.append(0)
        for value in plane[y * (width // 8):(y + 1) * (width // 8)]:
            raw.extend(255 if value & (128 >> bit) else 0 for bit in range(8))
    data = _png(bytes(raw), width, height)
    if len(data) > MAX_PNG_BYTES:
        raise ValueError('IMAGE_MASK_OUTPUT_LIMIT')
    checkpoint()
    return data, {'width': width, 'height': height, 'bitplane_sha256': hashlib.sha256(plane).hexdigest(),
                  'keep_pixels': keep, 'remove_pixels': width * height - keep,
                  'mask_sha256': hashlib.sha256(data).hexdigest()}


def _read_png(data, width, height, checkpoint):
    dimensions(width, height)
    if not isinstance(data, bytes) or not 57 <= len(data) <= SOURCE_MAX_BYTES or not data.startswith(SIGNATURE):
        raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
    checkpoint(); position = 8; header = None; compressed = bytearray(); ended = False; chunks = 0
    while position < len(data):
        checkpoint(); chunks += 1
        if chunks > 1024 or position + 12 > len(data):
            raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
        size = struct.unpack('>I', data[position:position + 4])[0]
        end = position + 12 + size
        if end > len(data):
            raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
        kind = data[position + 4:position + 8]; value = data[position + 8:position + 8 + size]
        crc = struct.unpack('>I', data[position + 8 + size:end])[0]
        if zlib.crc32(kind + value) & 0xffffffff != crc:
            raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
        if header is None:
            if kind != b'IHDR' or size != 13:
                raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
            w, h, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', value)
            if (w, h) != (width, height) or depth != 8 or color not in {0, 2, 4, 6} or (compression, filtering, interlace) != (0, 0, 0):
                raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
            header = color
        elif kind == b'IDAT':
            compressed.extend(value)
        elif kind == b'IEND' and size == 0 and compressed and end == len(data):
            ended = True; break
        else:
            raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
        position = end
    if not ended:
        raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[header]
    stride = width * channels + 1; expected = stride * height
    checkpoint()
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, expected + 1)
        if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
    except zlib.error:
        raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID') from None
    for offset in range(0, expected, stride):
        checkpoint()
        if raw[offset] > 4:
            raise ValueError('IMAGE_MASK_SOURCE_PNG_INVALID')
    checkpoint()
    return header, raw


def validate_source_png(data, width, height, *, checkpoint=lambda: None):
    _read_png(data, width, height, checkpoint)
    return {'width': width, 'height': height}


def verify_mask(data, *, checkpoint=lambda: None):
    if not isinstance(data, bytes) or len(data) < 33 or len(data) > MAX_PNG_BYTES:
        raise ValueError('IMAGE_MASK_OUTPUT_INVALID')
    width, height = struct.unpack('>II', data[16:24])
    color, raw = _read_png(data, width, height, checkpoint)
    if color != 0:
        raise ValueError('IMAGE_MASK_OUTPUT_INVALID')
    plane = bytearray()
    for y in range(height):
        checkpoint(); row = raw[y * (width + 1):(y + 1) * (width + 1)]
        if row[0] != 0 or any(v not in {0, 255} for v in row[1:]):
            raise ValueError('IMAGE_MASK_OUTPUT_INVALID')
        for x in range(1, width + 1, 8):
            plane.append(sum((128 >> bit) for bit, value in enumerate(row[x:x + 8]) if value == 255))
    canonical, proof = encode_mask(width, height, base64.b64encode(plane).decode('ascii'), checkpoint=checkpoint)
    if canonical != data:
        raise ValueError('IMAGE_MASK_OUTPUT_INVALID')
    return proof
