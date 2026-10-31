"""Deliberately small, fixed-effort reading-copy codecs, not a general encoder.

Admission is whole-request and happens before rendering/codec allocations. The
1 Mi-pixel ceiling admits one 1024-square page, not eight full-size pages. Eight
small pages and 2048-pixel edges are independent ceilings. No user-provided
encoder knobs, optimization searches, progressive passes or threads are exposed.
The 256 bytes/pixel + 8 MiB/page conservative work reservation covers RGB copies,
PNG decode, native scratch, verification decode and retained encoded pages; the
8 bytes/pixel + 64 KiB/page output reservation covers incompressible RGB and ZIP
framing, with 4 MiB reserved for manifest/license. These are engineering admission
limits, not a hard wall-clock timeout or a guarantee against a faulty native codec.
JPEG uses baseline single-pass, no optimizer; WebP method=0 and lossless quality=0
select lowest effort. Larger books require a separately measured admission change.
"""
import io
from PIL import Image, features
from . import comic_publication_budget as budget

MAX_CODEC_PIXELS = 1_048_576
MAX_CODEC_PAGES = 8
MAX_CODEC_SIDE = 2048
MAX_CODEC_WORK_BYTES = 512 * 1024 * 1024


def admit(dimensions, request):
    if not features.check('jpg' if request.image_format == 'JPEG' else 'webp'):
        raise ValueError('COMIC_PAGE_ARCHIVE_CODEC_UNAVAILABLE')
    pixels = sum(w * h for w, h in dimensions)
    if (not dimensions or len(dimensions) > MAX_CODEC_PAGES or pixels > MAX_CODEC_PIXELS
            or any(min(w, h) <= 0 or max(w, h) > MAX_CODEC_SIDE for w, h in dimensions)):
        raise ValueError('COMIC_PAGE_ARCHIVE_PIXEL_LIMIT')
    work = pixels * 256 + len(dimensions) * 8 * 1024 * 1024
    output = pixels * 8 + len(dimensions) * 65536 + 4 * 1024 * 1024
    if work > MAX_CODEC_WORK_BYTES:
        raise ValueError('COMIC_PAGE_ARCHIVE_WORK_LIMIT')
    if output > budget.MAX_ARCHIVE_BYTES:
        raise ValueError('COMIC_PUBLICATION_ARCHIVE_LIMIT')
    return {'max_total_page_pixels': MAX_CODEC_PIXELS, 'max_pages': MAX_CODEC_PAGES,
            'max_side_pixels': MAX_CODEC_SIDE, 'max_codec_work_bytes': MAX_CODEC_WORK_BYTES,
            'max_output_bytes': budget.MAX_ARCHIVE_BYTES, 'total_page_pixels': pixels,
            'reserved_codec_work_bytes': work, 'reserved_output_bytes': output}


def encode(png, width, height, request):
    from .comic_publication import BoundedBuffer
    # Additional decode/render accounting is cumulative with the original renderer.
    budget.consume('decode', width * height * 2)
    budget.consume('render', width * height * 2)
    with Image.open(io.BytesIO(png)) as original:
        if original.format != 'PNG' or original.mode != 'RGB' or original.size != (width, height):
            raise ValueError('COMIC_PAGE_ARCHIVE_RENDER_INVALID')
        original.load()
        # frombytes intentionally drops any source metadata/EXIF/ICC/path fields.
        with Image.frombytes('RGB', original.size, original.tobytes()) as image:
            output = BoundedBuffer()
            if request.image_format == 'JPEG':
                image.save(output, format='JPEG', quality=request.quality,
                           optimize=False, progressive=False, subsampling=0)
            else:
                image.save(output, format='WEBP', lossless=request.loss_mode == 'LOSSLESS',
                           quality=0 if request.loss_mode == 'LOSSLESS' else request.quality,
                           method=0, exact=True)
            data = output.getvalue()
            if len(data) > width * height * 8 + 65536:
                raise ValueError('COMIC_PAGE_ARCHIVE_OUTPUT_LIMIT')
            with Image.open(io.BytesIO(data)) as decoded:
                if decoded.format != request.image_format or decoded.size != image.size or decoded.mode != 'RGB':
                    raise ValueError('COMIC_PAGE_ARCHIVE_CODEC_INVALID')
                decoded.load()
                if request.loss_mode == 'LOSSLESS' and decoded.tobytes() != image.tobytes():
                    raise ValueError('COMIC_PAGE_ARCHIVE_LOSSLESS_MISMATCH')
            return data
