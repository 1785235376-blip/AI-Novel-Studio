"""Request-local publication work limits; inert outside a publication request."""
from contextlib import contextmanager
from contextvars import ContextVar
import io

MAX_PAGE_PIXELS = 64_000_000
MAX_DECODE_PIXELS = 256_000_000
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_RENDER_PIXELS = 256_000_000
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_PDF_WORK_BYTES = 512 * 1024 * 1024
MAX_BUFFER_WRITE_BYTES = 192 * 1024 * 1024
_remaining = ContextVar('comic_publication_work', default=None)


@contextmanager
def publication_budget():
    token = _remaining.set({'decode': MAX_DECODE_PIXELS, 'source': MAX_SOURCE_BYTES, 'render': MAX_RENDER_PIXELS, 'encoded': MAX_BUFFER_WRITE_BYTES, 'pdf': MAX_PDF_WORK_BYTES})
    try:
        yield
    finally:
        _remaining.reset(token)


def consume(kind, amount):
    budget = _remaining.get()
    if budget is not None:
        if amount < 0 or amount > budget[kind]:
            raise ValueError('COMIC_PUBLICATION_' + kind.upper() + '_LIMIT')
        budget[kind] -= amount


def source_work(data_bytes, pixels):
    consume('source', data_bytes)
    consume('decode', pixels)


def source_read_limit(asset, original_limit=None):
    budget = _remaining.get()
    if budget is None:
        return original_limit
    size = asset.get('size')
    if type(size) is not int or size <= 0 or size > budget['source']:
        raise ValueError('COMIC_PUBLICATION_SOURCE_LIMIT')
    return min(budget['source'], original_limit or 25 * 1024 * 1024)


class PublicationBuffer(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_ARCHIVE_BYTES:
            raise ValueError('COMIC_PUBLICATION_ARCHIVE_LIMIT')
        consume('encoded', len(data))
        return super().write(data)


def segment_buffer():
    return io.BytesIO() if _remaining.get() is None else PublicationBuffer()


def publication_active():
    return _remaining.get() is not None


def lineage_read_work(asset):
    if publication_active():
        source_read_limit(asset)
        # The existing lineage integrity reader verifies fstat size against this
        # metadata before reading; the original asset lock protects the snapshot.
        consume('source', asset['size'])
