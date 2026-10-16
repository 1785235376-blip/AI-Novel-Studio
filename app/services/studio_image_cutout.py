"""Bounded CPU cutouts from a strict PNG source and a canonical manual mask.

This is pixel compositing only: no segmentation, image library, provider,
network access, or native process. White mask pixels retain all source RGBA
bytes; black mask pixels become zero RGBA, including their hidden RGB bytes.
"""
from __future__ import annotations

import hashlib
import struct
import zlib

from app.services.studio_image_mask_authoring import SIGNATURE, _read_png, verify_mask

CONTRACT = 'cpu-binary-mask-cutout/1'
MAX_OUTPUT_BYTES = 4195716
_BLOCK_BYTES = 65535


def _sha256(data, checkpoint):
    digest = hashlib.sha256()
    for offset in range(0, len(data), _BLOCK_BYTES):
        checkpoint()
        digest.update(data[offset:offset + _BLOCK_BYTES])
    return digest.hexdigest()


def _chunk(kind, data, checkpoint):
    checksum = zlib.crc32(kind)
    for offset in range(0, len(data), _BLOCK_BYTES):
        checkpoint()
        checksum = zlib.crc32(data[offset:offset + _BLOCK_BYTES], checksum)
    checkpoint()
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', checksum & 0xffffffff)


def _rgba_png(raw, width, height, checkpoint):
    # Use our own fixed stored-DEFLATE encoder. The mask encoder's versioned
    # bytes and grayscale contract remain completely unchanged.
    output_size = len(raw) + 5 * ((len(raw) + _BLOCK_BYTES - 1) // _BLOCK_BYTES) + 63
    if output_size > MAX_OUTPUT_BYTES:
        raise ValueError('IMAGE_CUTOUT_OUTPUT_LIMIT')
    parts = [b'\x78\x01']
    checksum = 1
    for offset in range(0, len(raw), _BLOCK_BYTES):
        checkpoint()
        block = raw[offset:offset + _BLOCK_BYTES]
        parts.append(bytes([int(offset + len(block) == len(raw))])
                     + struct.pack('<HH', len(block), len(block) ^ 0xffff) + block)
        checksum = zlib.adler32(block, checksum)
    parts.append(struct.pack('>I', checksum & 0xffffffff))
    checkpoint()
    data = (SIGNATURE
            + _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0), checkpoint)
            + _chunk(b'IDAT', b''.join(parts), checkpoint)
            + _chunk(b'IEND', b'', checkpoint))
    if len(data) != output_size or len(data) > MAX_OUTPUT_BYTES:
        raise ValueError('IMAGE_CUTOUT_OUTPUT_LIMIT')
    checkpoint()
    return data


def _unfilter(row, previous, channels, filter_kind):
    if filter_kind == 0:
        return row
    for index in range(len(row)):
        left = row[index - channels] if index >= channels else 0
        above = previous[index]
        if filter_kind == 1:
            predictor = left
        elif filter_kind == 2:
            predictor = above
        elif filter_kind == 3:
            predictor = (left + above) // 2
        else:
            upper_left = previous[index - channels] if index >= channels else 0
            value = left + above - upper_left
            left_distance, above_distance, corner_distance = (
                abs(value - left), abs(value - above), abs(value - upper_left))
            predictor = (left if left_distance <= above_distance and left_distance <= corner_distance
                         else above if above_distance <= corner_distance else upper_left)
        row[index] = (row[index] + predictor) & 0xff
    return row


def render_cutout(source_data, mask_data, *, checkpoint=lambda: None):
    """Return deterministic RGBA PNG bytes and their exact, source-bound proof.

    Existing mask/source validators enforce the closed PNG contract and bound
    decompression. Cancellation exceptions propagate unchanged. Remaining
    pixel work checks once per row (at most 4,096 source bytes), and encoding
    and hashing check at most every 65,535 bytes.
    """
    checkpoint()
    mask_proof = verify_mask(mask_data, checkpoint=checkpoint)
    width, height = mask_proof['width'], mask_proof['height']
    color, source_raw = _read_png(source_data, width, height, checkpoint)
    _, mask_raw = _read_png(mask_data, width, height, checkpoint)
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    source_stride, output_stride = width * channels + 1, width * 4 + 1
    previous = bytearray(width * channels)
    # Preallocate zero RGBA and zero row filters. Removed pixels stay zero;
    # kept alpha-zero pixels are deliberately copied with their original RGB.
    output_raw = bytearray(output_stride * height)
    for y in range(height):
        checkpoint()
        start = y * source_stride
        row = _unfilter(bytearray(source_raw[start + 1:start + source_stride]),
                        previous, channels, source_raw[start])
        mask_start, output_start = y * (width + 1) + 1, y * output_stride + 1
        for x in range(width):
            if mask_raw[mask_start + x] == 255:
                source_offset, target = x * channels, output_start + x * 4
                if color in {0, 4}:
                    value = row[source_offset]
                    alpha = row[source_offset + 1] if color == 4 else 255
                    output_raw[target:target + 4] = bytes((value, value, value, alpha))
                elif color == 2:
                    output_raw[target:target + 4] = row[source_offset:source_offset + 3] + b'\xff'
                else:
                    output_raw[target:target + 4] = row[source_offset:source_offset + 4]
        previous = row
    checkpoint()
    output = _rgba_png(bytes(output_raw), width, height, checkpoint)
    proof = {'contract': CONTRACT, 'width': width, 'height': height,
             'source_sha256': _sha256(source_data, checkpoint),
             'mask_sha256': mask_proof['mask_sha256'],
             'output_sha256': _sha256(output, checkpoint), 'output_bytes': len(output),
             'keep_pixels': mask_proof['keep_pixels'], 'remove_pixels': mask_proof['remove_pixels']}
    checkpoint()
    return output, proof
