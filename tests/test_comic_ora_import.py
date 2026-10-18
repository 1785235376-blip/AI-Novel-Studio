"""Pure, adversarial ORA inspection. No import adoption or application compatibility claim."""
import copy
import io
import struct
import zipfile
import zlib
from xml.etree.ElementTree import Element, SubElement, tostring

from PIL import Image
import pytest
from app.experimental.comic_ora_import import preview_ora, _png, _Budget
from app.experimental.comic_ora import encode_ora
from app.experimental.comic_layouts import LayoutIn, compose
from test_comic_layers import blank, layered


def png(size=(80, 80), color='red', mode='RGBA'):
    stream = io.BytesIO(); Image.new(mode, size, color).save(stream, 'PNG'); return stream.getvalue()


def archive(*, xml=None, changes=None, additions=(), compression=zipfile.ZIP_STORED):
    if xml is None:
        xml = b'<image w="320" h="320" name="External raster"><stack><layer name="Red" src="data/red.png" x="10" y="20" opacity="0.5"/></stack></image>'
    files = {'mimetype': b'image/openraster', 'stack.xml': xml, 'data/red.png': png(),
             'mergedimage.png': png((320, 320), (0, 0, 0, 0)), 'Thumbnails/thumbnail.png': png((256, 256), (0, 0, 0, 0))}
    files.update(changes or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as out:
        for name, data in [*files.items(), *additions]:
            if data is not None: out.writestr(name, data, compress_type=zipfile.ZIP_STORED if name == 'mimetype' else compression)
    return stream.getvalue()


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)


def test_pure_preview_recomposes_pixels_and_distrusts_sidecars(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = list(tmp_path.rglob('*'))
    result = preview_ora(archive(changes={'comic-loss-receipt.json': b'{"approved":true,"asset_id":"trusted"}'}))
    assert list(tmp_path.rglob('*')) == before
    assert result.report['writes_performed'] is False and len(result.layers) == 1
    layer = result.layers[0]
    assert (layer.name, layer.x, layer.y, layer.opacity_percent) == ('Red', 10, 20, 50)
    assert not hasattr(layer, 'asset_id')
    image = Image.open(io.BytesIO(result.preview_png))
    assert image.getpixel((10, 20)) == (255, 0, 0, 128)
    assert image.getpixel((0, 0)) == (0, 0, 0, 0)
    assert not result.report['merged_preview_matches']
    assert 'IGNORED_UNTRUSTED_SIDECAR:comic-loss-receipt.json' in result.report['losses']
    assert result.report['sidecar_trust'] == 'NONE' and result.report['approval_imported'] is False
    assert result.report['origin_verified'] is False and result.report['unsupported_semantics_policy'] == 'REJECT'
    assert result.report['ignored_metadata'] == ['IGNORED_UNTRUSTED_SIDECAR:comic-loss-receipt.json']


def test_real_export_parse_retains_raster_layers_and_native_source():
    document = LayoutIn.model_validate(layered(blank())).model_dump(); before = copy.deepcopy(document)
    report = {**compose(document, {})[0], 'review_digest': 'a' * 64}
    exported = encode_ora(document, {}, report, 1)
    result = preview_ora(exported)
    assert result.report['merged_preview_matches'] and len(result.layers) == 3
    assert [x.name for x in result.layers] == ['Paper', 'PANEL_ART', 'PANEL_FRAME']
    assert document == before
    assert 'RASTER_LAYERS_ONLY_NO_EDITABLE_DIALOGUE_RECOVERY' in result.report['losses']
    # Pure output can be re-edited by a caller, but no Comic page is attached.
    assert result.layers[2].member == 'data/layer-002.png'


@pytest.mark.parametrize('x,y', [(-20, -20), (12000, 12000)])
def test_bounded_negative_and_offcanvas_offsets_keep_original_layer(x, y):
    xml = f'<image w="320" h="320"><stack><layer src="data/red.png" x="{x}" y="{y}"/></stack></image>'.encode()
    result = preview_ora(archive(xml=xml))
    assert (result.layers[0].x, result.layers[0].y) == (x, y)
    assert Image.open(io.BytesIO(result.layers[0].png)).size == (80, 80)
    assert any('CLIPPED' in issue for issue in result.report['losses'])


def test_xml_order_visibility_and_opacity():
    xml = b'<image w="320" h="320"><stack><layer src="data/blue.png" visibility="hidden"/><layer src="data/red.png" opacity="0.37"/></stack></image>'
    result = preview_ora(archive(xml=xml, changes={'data/blue.png': png(color='blue')}))
    assert [x.member for x in result.layers] == ['data/red.png', 'data/blue.png']
    assert Image.open(io.BytesIO(result.preview_png)).getpixel((0, 0)) == (255, 0, 0, 94)


@pytest.mark.parametrize('xml,code', [
    (b'<!DOCTYPE image [<!ENTITY x "hello">]><image w="320" h="320"><stack/></image>', 'DECLARATIONS'),
    (b'<image w="320" h="320"><stack><stack><layer src="data/red.png"/></stack></stack></image>', 'STRUCTURE'),
    (b'<image w="320" h="320"><stack><text>Hi</text></stack></image>', 'CONTENT'),
    (b'<image w="320" h="320"><stack><layer src="https://evil/image.png"/></stack></image>', 'PATH'),
    (b'<image w="320" h="320"><stack><layer src="data/../red.png"/></stack></image>', 'PATH'),
    (b'<image w="320" h="320"><stack><layer src="data/red.png" composite-op="svg:multiply"/></stack></image>', 'BLEND'),
    (b'<image w="320" h="320"><stack><layer src="data/red.png" opacity="0.333"/></stack></image>', 'PRECISION'),
    (b'<image w="320" h="320"><stack><layer src="data/red.png" opacity="NaN"/></stack></image>', 'OPACITY'),
    (b'<image w="320" h="320"><stack><layer src="data/red.png" x="12001"/></stack></image>', 'INTEGER'),
    (b'<image w="319" h="320"><stack><layer src="data/red.png"/></stack></image>', 'INTEGER'),
    (b'<image w="320" h="320" name="&#0;"><stack><layer src="data/red.png"/></stack></image>', 'XML_INVALID'),
    (b'<image w="320" h="320"><stack><layer src="data/red.png"/><layer src="data/red.png"/></stack></image>', 'SOURCE'),
    (b'<image w="320" h="320"><stack><layer src="data/red.png"><xi:include xmlns:xi="http://www.w3.org/2001/XInclude" href="file:///etc/passwd"/></layer></stack></image>', 'STRUCTURE'),
])
def test_xml_rejects_unsupported_or_unsafe_content(xml, code):
    with pytest.raises(ValueError, match=code): preview_ora(archive(xml=xml))


@pytest.mark.parametrize('change,code', [
    ({'mimetype': b'image/openraster\n'}, 'MEMBER_SIZE'),
    ({'mergedimage.png': None}, 'REQUIRED_MEMBER'),
    ({'data/red.png': None}, 'LAYER_MEMBER'),
    ({'data/red.png': b'<svg/>'}, 'IHDR'),
    ({'unreferenced.bin': b'bad'}, 'UNREFERENCED'),
    ({'mergedimage.png': png((321, 320))}, 'MERGED_IMAGE_DIMENSIONS'),
    ({'Thumbnails/thumbnail.png': png((257, 1))}, 'THUMBNAIL_DIMENSIONS'),
])
def test_zip_members_and_required_images(change, code):
    with pytest.raises(ValueError, match=code): preview_ora(archive(changes=change))


@pytest.mark.parametrize('name', ['data/red.png', 'DATA/RED.PNG', '../bad', '/bad', 'data\\bad.png'])
def test_duplicate_colliding_or_traversal_members(name):
    with pytest.raises(ValueError, match='ZIP_'): preview_ora(archive(additions=[(name, b'bad')]))


def test_symlink_member_rejected():
    name = zipfile.ZipInfo('link'); name.create_system = 3; name.external_attr = (0o120777 << 16)
    with pytest.raises(ValueError, match='MEMBER'): preview_ora(archive(additions=[(name, b'data/red.png')]))


def test_central_entry_count_bound_precedes_zipfile(monkeypatch):
    raw = bytearray(archive()); offset = raw.rfind(b'PK\x05\x06')
    struct.pack_into('<HH', raw, offset + 8, 65535, 65535)
    monkeypatch.setattr(zipfile, 'ZipFile', lambda *a, **kw: pytest.fail('ZipFile must not allocate entries'))
    with pytest.raises(ValueError, match='DIRECTORY'): preview_ora(bytes(raw))


def test_forged_small_count_with_large_directory_rejected_before_zipfile(monkeypatch):
    raw = bytearray(archive()); offset = raw.rfind(b'PK\x05\x06')
    struct.pack_into('<HH', raw, offset + 8, 4, 4)
    monkeypatch.setattr(zipfile, 'ZipFile', lambda *a, **kw: pytest.fail('directory must be scanned first'))
    with pytest.raises(ValueError, match='DIRECTORY'): preview_ora(bytes(raw))


def test_zip_crc_corruption():
    raw = bytearray(archive()); offset = raw.find(png()); raw[offset + 40] ^= 1
    with pytest.raises(ValueError, match='ZIP_INVALID'): preview_ora(bytes(raw))


def test_trailing_zip_payload_and_compression_ratio():
    with pytest.raises(ValueError, match='DIRECTORY'): preview_ora(archive() + b'junk')
    with pytest.raises(ValueError, match='MEMBER'): preview_ora(archive(changes={'OFL.txt': b'A' * 60000}, compression=zipfile.ZIP_DEFLATED))


@pytest.mark.parametrize('kind,value,code', [(b'acTL', b'\0' * 8, 'EFFECT'), (b'iCCP', b'x', 'COLOR_PROFILE'), (b'ABCD', b'x', 'CRITICAL'), (b'tRNS', b'\0' * 6, 'TRANSPARENCY')])
def test_png_effect_and_color_profile_rejected(kind, value, code):
    data = png(); data = data[:33] + chunk(kind, value) + data[33:]
    with pytest.raises(ValueError, match=code): preview_ora(archive(changes={'data/red.png': data}))


def test_png_compressed_metadata_is_stripped_before_pillow():
    data = png(); data = data[:33] + chunk(b'zTXt', b'name\0\0' + zlib.compress(b'A' * 2_000_000)) + data[33:]
    result = preview_ora(archive(changes={'data/red.png': data}))
    assert 'PNG_METADATA_NOT_IMPORTED:data/red.png' in result.report['losses']
    assert not Image.open(io.BytesIO(result.layers[0].png)).info


def test_png_zlib_overrun_is_rejected_before_pillow(monkeypatch):
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(b'\0' * 100000)) + chunk(b'IEND', b'')
    monkeypatch.setattr(Image, 'open', lambda *a, **kw: pytest.fail('Pillow must not see overflow stream'))
    with pytest.raises(ValueError, match='DECOMPRESSED_SIZE'): _png(data, _Budget())


def test_multiple_png_images_and_animated_control_are_rejected():
    with pytest.raises(ValueError, match='PNG_STRUCTURE'): preview_ora(archive(changes={'data/red.png': png() + png()}))
    data = png(); data = data[:33] + chunk(b'acTL', struct.pack('>II', 2, 0)) + data[33:]
    with pytest.raises(ValueError, match='EFFECT'): preview_ora(archive(changes={'data/red.png': data}))


def test_member_and_canonical_output_sizes_are_bounded(monkeypatch):
    monkeypatch.setattr('app.experimental.comic_ora_import.MAX_PNG', 64)
    with pytest.raises(ValueError, match='MEMBER_SIZE'): preview_ora(archive())


def test_xml_byte_and_node_limits(monkeypatch):
    monkeypatch.setattr('app.experimental.comic_ora_import.MAX_XML', 10)
    with pytest.raises(ValueError, match='MEMBER_SIZE'): preview_ora(archive())
    monkeypatch.setattr('app.experimental.comic_ora_import.MAX_XML', 512 * 1024)
    xml = ('<image w="320" h="320"><stack>' + '<layer src="data/red.png"/>' * 257 + '</stack></image>').encode()
    with pytest.raises(ValueError, match='STRUCTURE'): preview_ora(archive(xml=xml))


def test_aggregate_source_and_work_limits(monkeypatch):
    monkeypatch.setattr('app.experimental.comic_ora_import.MAX_LAYER_PIXELS', 1)
    with pytest.raises(ValueError, match='LAYER_PIXEL'): preview_ora(archive())
    monkeypatch.setattr('app.experimental.comic_ora_import.MAX_LAYER_PIXELS', 64_000_000)
    monkeypatch.setattr('app.experimental.comic_ora_import.MAX_DECODE_WORK', 100)
    with pytest.raises(ValueError, match='DECODE_WORK'): preview_ora(archive())


def test_renderer_gate_preserved(monkeypatch):
    monkeypatch.setattr('app.experimental.comic_layouts.renderer_status', lambda: {'available': False})
    with pytest.raises(ValueError, match='PINNED_RENDERER'): preview_ora(archive())


def test_operation_budget_counts_composition_and_restarts(monkeypatch):
    expected = 3 * 80 * 80 + 2 * 320 * 320 + 2 * 256 * 256
    assert preview_ora(archive()).report['decoded_work_pixels'] == expected
    monkeypatch.setattr('app.experimental.comic_ora_import.MAX_DECODE_WORK', expected - 1)
    with pytest.raises(ValueError, match='DECODE_WORK'):
        preview_ora(archive())
    monkeypatch.setattr('app.experimental.comic_ora_import.MAX_DECODE_WORK', expected)
    assert preview_ora(archive()).report['decoded_work_pixels'] == expected


@pytest.mark.parametrize('payload', [b'', b'aa', b'x' * 771])
def test_invalid_optional_palette_rejected(payload):
    original = png()
    changed = original[:33] + chunk(b'PLTE', payload) + original[33:]
    with pytest.raises(ValueError, match='PNG_STRUCTURE'):
        preview_ora(archive(changes={'data/red.png': changed}))
