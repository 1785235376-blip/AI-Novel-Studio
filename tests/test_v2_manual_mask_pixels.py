"""Fresh reconstruction tests, not recovered historical execution evidence."""
import base64
import hashlib
import struct
import zlib

import pytest


def chunk(kind, value):
    return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value) & 0xffffffff)


def source_png(width=64, height=64, color=6, *, raw=None, extra=b''):
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    raw = raw if raw is not None else (b'\0' + b'\x7f' * width * channels) * height
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, color, 0, 0, 0))
            + extra + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def plane(width=64, height=64):
    return base64.b64encode(b'\x80' * (width * height // 8)).decode('ascii')


def test_canonical_pixels_are_real_grayscale_png_and_msb_first():
    from app.services.studio_image_mask_authoring import encode_mask, verify_mask
    data, proof = encode_mask(64, 64, plane())
    assert data.startswith(b'\x89PNG\r\n\x1a\n')
    pos = 8; chunks = []
    while pos < len(data):
        size = struct.unpack('>I', data[pos:pos + 4])[0]
        kind, value = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + size]
        assert zlib.crc32(kind + value) & 0xffffffff == struct.unpack('>I', data[pos + 8 + size:pos + 12 + size])[0]
        chunks.append((kind, value)); pos += size + 12
    assert [kind for kind, _ in chunks] == [b'IHDR', b'IDAT', b'IEND']
    assert struct.unpack('>IIBBBBB', chunks[0][1]) == (64, 64, 8, 0, 0, 0, 0)
    raw = zlib.decompress(chunks[1][1])
    assert raw == (b'\0' + (b'\xff' + b'\0' * 7) * 8) * 64
    assert proof == {'width': 64, 'height': 64, 'bitplane_sha256': hashlib.sha256(b'\x80' * 512).hexdigest(),
                     'keep_pixels': 512, 'remove_pixels': 3584, 'mask_sha256': hashlib.sha256(data).hexdigest()}
    assert verify_mask(data) == proof
    assert encode_mask(64, 64, plane()) == (data, proof)


@pytest.mark.parametrize('width,height', [(0, 64), (63, 64), (65, 64), (1032, 64), (64, 1032), (True, 64), ('64', 64), (64, 64.0)])
def test_dimensions_fail_before_bitmap_decode(width, height):
    from app.services.studio_image_mask_authoring import encode_mask
    with pytest.raises(ValueError, match='IMAGE_MASK_'):
        encode_mask(width, height, 'not base64')


@pytest.mark.parametrize('value', ['', 'AA==', plane() + '\n', plane()[:-1], plane()[:-1] + '=',
    base64.b64encode(b'\0' * 512).decode(), base64.b64encode(b'\xff' * 512).decode(), None, 10])
def test_noncanonical_wrong_size_or_single_color_plane_rejected(value):
    from app.services.studio_image_mask_authoring import encode_mask
    # The duplicate padding spelling here must not accidentally be the canonical value.
    if value == plane(): value = plane() + '='
    with pytest.raises(ValueError, match='IMAGE_MASK_'):
        encode_mask(64, 64, value)


@pytest.mark.parametrize('color', [0, 2, 4, 6])
def test_source_png_checks_complete_bounded_framing_and_pixels(color):
    from app.services.studio_image_mask_authoring import validate_source_png
    assert validate_source_png(source_png(color=color), 64, 64) == {'width': 64, 'height': 64}


@pytest.mark.parametrize('damage', ['crc', 'truncated', 'tail', 'wrong_dimensions', 'short_pixels', 'long_pixels', 'filter', 'animation', 'exif', 'second_stream'])
def test_source_png_rejects_unverified_or_ambiguous_bytes(damage):
    from app.services.studio_image_mask_authoring import validate_source_png
    data = source_png()
    if damage == 'crc': data = data[:-1] + bytes([data[-1] ^ 1])
    elif damage == 'truncated': data = data[:-4]
    elif damage == 'tail': data += b'private-canary'
    elif damage == 'wrong_dimensions': data = source_png(72, 64)
    elif damage == 'short_pixels': data = source_png(raw=b'\0')
    elif damage == 'long_pixels': data = source_png(raw=b'\0' * (64 * 257 + 1))
    elif damage == 'filter': data = source_png(raw=(b'\5' + b'\0' * 256) * 64)
    elif damage == 'animation': data = source_png(extra=chunk(b'acTL', b'\0' * 8))
    elif damage == 'exif': data = source_png(extra=chunk(b'eXIf', b'private-canary'))
    elif damage == 'second_stream':
        data = data[:33] + chunk(b'IDAT', zlib.compress((b'\0' + b'\x7f' * 256) * 64) + zlib.compress(b'private-canary')) + chunk(b'IEND', b'')
    with pytest.raises(ValueError, match='^IMAGE_MASK_SOURCE_PNG_INVALID$'):
        validate_source_png(data, 64, 64)


def test_helper_checkpoint_failure_is_not_swallowed():
    from app.services.studio_image_mask_authoring import encode_mask, validate_source_png
    def denied(): raise RuntimeError('revoked')
    with pytest.raises(RuntimeError, match='revoked'): encode_mask(64, 64, plane(), checkpoint=denied)
    with pytest.raises(RuntimeError, match='revoked'): validate_source_png(source_png(), 64, 64, checkpoint=denied)
