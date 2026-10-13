"""Independent PNG/pixel checks for the bounded, deterministic CPU cutout."""
import base64
import hashlib
import struct
import zlib

import pytest

from app.services import studio_image_cutout as cutout
from app.services.studio_image_mask_authoring import encode_mask


SIGNATURE = b'\x89PNG\r\n\x1a\n'
CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def chunk(kind, value):
    return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value) & 0xffffffff)


def png(raw, width=64, height=64, color=6, *, depth=8, compression=0, filtering=0,
        interlace=0, extra=b'', compressed=None):
    header = struct.pack('>IIBBBBB', width, height, depth, color, compression, filtering, interlace)
    compressed = zlib.compress(raw) if compressed is None else compressed
    return SIGNATURE + chunk(b'IHDR', header) + extra + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')


def mask(width=64, height=64):
    # Keep alternating pixels so every row exercises both retained/removed
    # colors, including alpha zero, partial alpha, and fully opaque pixels.
    plane = b'\xaa' * (width * height // 8)
    return encode_mask(width, height, base64.b64encode(plane).decode('ascii'))[0]


def rows_for_color(color, width=64, height=64):
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            red, green, blue = (x * 29 + y * 7 + 17) % 256, (x * 3 + y * 53 + 31) % 256, (x * 79 + y * 11 + 43) % 256
            alpha = (0, 255, 93, 127, 255, 4)[x % 6]
            row.extend({0: (red,), 2: (red, green, blue), 4: (red, alpha), 6: (red, green, blue, alpha)}[color])
        rows.append(bytes(row))
    return rows


def filtered_raw(rows, color, filter_kind):
    """Independently apply PNG filters to known bytes for the source fixture."""
    raw = bytearray()
    previous = bytes(len(rows[0]))
    for y, row in enumerate(rows):
        kind = y % 5 if filter_kind == 'mixed' else filter_kind
        raw.append(kind)
        for i, value in enumerate(row):
            left = row[i - CHANNELS[color]] if i >= CHANNELS[color] else 0
            above = previous[i]
            corner = previous[i - CHANNELS[color]] if i >= CHANNELS[color] else 0
            if kind == 0:
                prediction = 0
            elif kind == 1:
                prediction = left
            elif kind == 2:
                prediction = above
            elif kind == 3:
                prediction = (left + above) // 2
            else:
                p = left + above - corner
                prediction = min((left, above, corner), key=lambda n: abs(p - n))
            raw.append((value - prediction) % 256)
        previous = row
    return bytes(raw)


def expected_rgba(rows, color):
    result = bytearray()
    for row in rows:
        result.append(0)
        for x in range(len(row) // CHANNELS[color]):
            pixel = row[x * CHANNELS[color]:(x + 1) * CHANNELS[color]]
            if x % 2:
                result.extend(b'\0' * 4)
            elif color == 0:
                result.extend(pixel * 3 + b'\xff')
            elif color == 2:
                result.extend(pixel + b'\xff')
            elif color == 4:
                result.extend(pixel[:1] * 3 + pixel[1:])
            else:
                result.extend(pixel)
    return bytes(result)


def unpack_output(data, width=64, height=64):
    assert data[:8] == SIGNATURE
    chunks = []
    position = 8
    while position < len(data):
        size = struct.unpack('>I', data[position:position + 4])[0]
        kind, value = data[position + 4:position + 8], data[position + 8:position + 8 + size]
        crc = struct.unpack('>I', data[position + 8 + size:position + 12 + size])[0]
        assert zlib.crc32(kind + value) & 0xffffffff == crc
        chunks.append((kind, value))
        position += size + 12
    assert position == len(data)
    assert [kind for kind, _ in chunks] == [b'IHDR', b'IDAT', b'IEND']
    assert struct.unpack('>IIBBBBB', chunks[0][1]) == (width, height, 8, 6, 0, 0, 0)
    assert chunks[2][1] == b''
    stream = chunks[1][1]
    assert stream[:2] == b'\x78\x01'
    position = 2
    stored = bytearray()
    blocks = 0
    while True:
        final, length, inverted = struct.unpack('<BHH', stream[position:position + 5])
        assert final in (0, 1) and inverted == length ^ 0xffff
        assert length == min(65535, (width * 4 + 1) * height - len(stored))
        stored.extend(stream[position + 5:position + 5 + length])
        position += 5 + length
        blocks += 1
        if final:
            break
    assert position + 4 == len(stream)
    assert struct.unpack('>I', stream[-4:])[0] == zlib.adler32(stored) & 0xffffffff
    assert zlib.decompress(stream) == stored
    assert len(stored) == (width * 4 + 1) * height
    assert all(stored[y * (width * 4 + 1)] == 0 for y in range(height))
    return bytes(stored), blocks


@pytest.mark.parametrize('color', [0, 2, 4, 6])
@pytest.mark.parametrize('filter_kind', [0, 1, 2, 3, 4, 'mixed'])
def test_all_color_types_and_real_png_filters_preserve_exact_pixels(color, filter_kind):
    rows = rows_for_color(color)
    source = png(filtered_raw(rows, color, filter_kind), color=color)
    authored = mask()
    output, proof = cutout.render_cutout(source, authored)
    raw, _ = unpack_output(output)
    assert raw == expected_rgba(rows, color)
    assert proof == {'contract': 'cpu-binary-mask-cutout/1', 'width': 64, 'height': 64,
                     'source_sha256': hashlib.sha256(source).hexdigest(),
                     'mask_sha256': hashlib.sha256(authored).hexdigest(),
                     'output_sha256': hashlib.sha256(output).hexdigest(),
                     'output_bytes': len(output), 'keep_pixels': 2048, 'remove_pixels': 2048}
    if color in (4, 6):
        assert raw[1:4] != b'\0' * 3 and raw[4] == 0
        assert raw[5:9] == b'\0' * 4


def test_filter_and_idat_framing_do_not_change_deterministic_output():
    rows = rows_for_color(6)
    source = png(filtered_raw(rows, 6, 0))
    filtered = png(filtered_raw(rows, 6, 'mixed'))
    compressed = zlib.compress(filtered_raw(rows, 6, 0))
    split = (source[:33] + chunk(b'IDAT', compressed[:7]) + chunk(b'IDAT', b'')
             + chunk(b'IDAT', compressed[7:]) + chunk(b'IEND', b''))
    output, proof = cutout.render_cutout(source, mask())
    assert cutout.render_cutout(source, mask()) == (output, proof)
    for equivalent_source in (filtered, split):
        equivalent, equivalent_proof = cutout.render_cutout(equivalent_source, mask())
        assert equivalent == output
        assert equivalent_proof['source_sha256'] != proof['source_sha256']
        assert {key: value for key, value in equivalent_proof.items() if key != 'source_sha256'} == {
            key: value for key, value in proof.items() if key != 'source_sha256'}


def test_rectangular_dimensions_and_maximum_exact_output_bound():
    assert cutout.MAX_OUTPUT_BYTES == 4195716
    for width, height in ((72, 80), (1024, 1024)):
        raw = (b'\0' + b'\x35\x62\x91\0' * width) * height
        output, proof = cutout.render_cutout(png(raw, width, height), mask(width, height))
        decoded, blocks = unpack_output(output, width, height)
        assert decoded == (b'\0' + b'\x35\x62\x91\0\0\0\0\0' * (width // 2)) * height
        assert proof['keep_pixels'] == proof['remove_pixels'] == width * height // 2
        assert proof['output_bytes'] == len(output) <= cutout.MAX_OUTPUT_BYTES
        if width == 1024:
            assert len(output) == cutout.MAX_OUTPUT_BYTES and blocks == 65


@pytest.mark.parametrize('damage', ['crc', 'truncated', 'tail', 'signature', 'short_pixels', 'long_pixels',
    'filter', 'animation', 'exif', 'transparency', 'unknown_chunk', 'duplicate_header', 'second_stream',
    'no_stream', 'no_end', 'oversized_chunk', 'too_many_chunks', 'byte_limit', 'type', 'depth', 'palette',
    'compression', 'filtering', 'interlace', 'dimensions', 'oversized_dimensions'])
def test_invalid_or_ambiguous_source_png_fails_closed(damage):
    raw = (b'\0' + b'\x31\x32\x33\x34' * 64) * 64
    source = png(raw)
    if damage == 'crc': source = source[:-1] + bytes([source[-1] ^ 1])
    elif damage == 'truncated': source = source[:-4]
    elif damage == 'tail': source += b'private-canary'
    elif damage == 'signature': source = b'not PNG!' + source[8:]
    elif damage == 'short_pixels': source = png(raw[:-1])
    elif damage == 'long_pixels': source = png(raw + b'\0' * (1024 * 1024))
    elif damage == 'filter': source = png((b'\5' + b'\0' * 256) * 64)
    elif damage == 'animation': source = png(raw, extra=chunk(b'acTL', b'\0' * 8))
    elif damage == 'exif': source = png(raw, extra=chunk(b'eXIf', b'private-canary'))
    elif damage == 'transparency': source = png(raw, extra=chunk(b'tRNS', b'\0' * 6))
    elif damage == 'unknown_chunk': source = png(raw, extra=chunk(b'ABCD', b''))
    elif damage == 'duplicate_header': source = source[:33] + source[8:33] + source[33:]
    elif damage == 'second_stream': source = png(raw, compressed=zlib.compress(raw) + zlib.compress(b'private-canary'))
    elif damage == 'no_stream': source = png(raw, compressed=b'')
    elif damage == 'no_end': source = source[:-12]
    elif damage == 'oversized_chunk': source = source[:33] + struct.pack('>I', 0xffffffff) + source[37:]
    elif damage == 'too_many_chunks': source = source[:33] + chunk(b'IDAT', b'') * 1024 + source[33:]
    elif damage == 'byte_limit': source += b'\0' * (8 * 1024 * 1024)
    elif damage == 'type': source = bytearray(source)
    elif damage == 'depth': source = png(raw, depth=16)
    elif damage == 'palette': source = png(raw, color=3)
    elif damage == 'compression': source = png(raw, compression=1)
    elif damage == 'filtering': source = png(raw, filtering=1)
    elif damage == 'interlace': source = png(raw, interlace=1)
    elif damage == 'dimensions': source = png(raw, width=72)
    elif damage == 'oversized_dimensions': source = png(raw, width=0xffffffff, height=0xffffffff)
    with pytest.raises(ValueError, match='^IMAGE_MASK_SOURCE_PNG_INVALID$'):
        cutout.render_cutout(source, mask())


@pytest.mark.parametrize('damage', ['recompressed', 'nonbinary', 'all_keep', 'all_remove', 'filtered',
    'rgba', 'crc', 'tail', 'dimensions', 'too_large', 'type'])
def test_mask_requires_exact_authored_canonical_binary_png(damage):
    source = png(filtered_raw(rows_for_color(6), 6, 0))
    authored = mask()
    raw = (b'\0' + b'\xff\0' * 32) * 64
    if damage == 'recompressed': authored = png(raw, color=0)
    elif damage == 'nonbinary': authored = png((b'\0' + b'\x7f\0' * 32) * 64, color=0)
    elif damage == 'all_keep': authored = png((b'\0' + b'\xff' * 64) * 64, color=0)
    elif damage == 'all_remove': authored = png(b'\0' * (65 * 64), color=0)
    elif damage == 'filtered': authored = png(filtered_raw([b'\xff\0' * 32] * 64, 0, 1), color=0)
    elif damage == 'rgba': authored = source
    elif damage == 'crc': authored = authored[:-1] + bytes([authored[-1] ^ 1])
    elif damage == 'tail': authored += b'private-canary'
    elif damage == 'dimensions': authored = png(raw, width=65, color=0)
    elif damage == 'too_large': authored += b'\0' * (1024 * 1025)
    elif damage == 'type': authored = None
    with pytest.raises(ValueError, match='^IMAGE_MASK_'):
        cutout.render_cutout(source, authored)


def test_canonical_mask_with_different_dimensions_is_rejected():
    with pytest.raises(ValueError, match='^IMAGE_MASK_SOURCE_PNG_INVALID$'):
        cutout.render_cutout(png((b'\0' + b'\x7f' * 256) * 64), mask(72, 64))


def test_output_ceiling_fails_before_encoding_if_invariant_is_broken(monkeypatch):
    monkeypatch.setattr(cutout, 'MAX_OUTPUT_BYTES', 100)
    with pytest.raises(ValueError, match='^IMAGE_CUTOUT_OUTPUT_LIMIT$'):
        cutout.render_cutout(png((b'\0' + b'\x7f' * 256) * 64), mask())


def test_cancellation_is_checked_through_validation_pixels_encoding_and_hashing():
    source = png(filtered_raw(rows_for_color(6), 6, 'mixed'))
    authored = mask()
    checkpoints = []
    cutout.render_cutout(source, authored, checkpoint=lambda: checkpoints.append(None))
    # Both validators, mask canonicalization, rendering, encoding and hashing
    # contribute checkpoints. Test cancellation across the whole operation.
    assert len(checkpoints) >= 6 * 64
    for stop in (1, 2, 70, 140, len(checkpoints) // 2, len(checkpoints) - 50,
                 len(checkpoints) - 10, len(checkpoints) - 2, len(checkpoints)):
        calls = 0
        sentinel = RuntimeError('cancelled-cutout')
        def cancelled():
            nonlocal calls
            calls += 1
            if calls == stop:
                raise sentinel
        with pytest.raises(RuntimeError) as raised:
            cutout.render_cutout(source, authored, checkpoint=cancelled)
        assert raised.value is sentinel and calls == stop


@pytest.mark.parametrize('stage', ['_unfilter', '_rgba_png', '_sha256'])
def test_cancellation_propagates_from_each_rendering_stage(monkeypatch, stage):
    source = png(filtered_raw(rows_for_color(6), 6, 'mixed'))
    authored = mask()
    original = getattr(cutout, stage)
    entered = False
    sentinel = RuntimeError('cancelled-during-' + stage)

    def enter(*args, **kwargs):
        nonlocal entered
        entered = True
        return original(*args, **kwargs)

    def checkpoint():
        if entered:
            raise sentinel

    monkeypatch.setattr(cutout, stage, enter)
    with pytest.raises(RuntimeError) as raised:
        cutout.render_cutout(source, authored, checkpoint=checkpoint)
    assert entered and raised.value is sentinel
