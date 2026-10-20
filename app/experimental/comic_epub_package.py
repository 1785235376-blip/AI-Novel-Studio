"""Bounded EPUB3 fixed-layout packaging of original flattened PNG pages.

No owner, persistence, HTML input, external resources, or publication authority.
Structural XML/ZIP tests are not EPUBCheck or reading-system certification.
"""
from datetime import datetime, timezone
import zipfile
from xml.sax.saxutils import escape

FORMAT = 'comic-epub-fixed-raster-v1'
MAX_METADATA_BYTES = 1024 * 1024
MAX_XML_BYTES = 64 * 1024
LOSSES = ['FLATTENED_RGB_PNG_PAGES', 'NO_EDITABLE_OR_SEARCHABLE_TEXT',
          'RASTER_ONLY_LIMITED_ACCESSIBILITY_NO_TEXT_ALTERNATIVE',
          'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS',
          'NO_DPI_BLEED_COLOR_PROFILE_OR_PRINT_CONFORMANCE',
          'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'LANGUAGE_UNSPECIFIED_UND',
          'EPUBCHECK_NOT_RUN', 'EXTERNAL_READER_VALIDATION_NOT_RUN']


def _text(value):
    # XML 1.0 Fifth Edition character range, including surrogate rejection.
    if any(not (c in '\t\n\r' or '\x20' <= c <= '\ud7ff' or '\ue000' <= c <= '\ufffd'
                or '\U00010000' <= c <= '\U0010ffff') for c in value):
        raise ValueError('COMIC_EPUB_XML_CHARACTER_INVALID')
    return value


def admit(book, rows, max_output):
    # Bounds precede escaping, UTF-8 encoding, XML/navigation/manifest assembly,
    # source decode and rendering. No attacker-controlled names become paths.
    titles = [book['document']['title']] + [r['document']['title'] for r in rows]
    if any(len(t) * 6 + 4096 > MAX_XML_BYTES for t in titles):
        raise ValueError('COMIC_EPUB_METADATA_LIMIT')
    for title in titles:
        _text(title)
        if not title.strip(' \t\r\n'):
            raise ValueError('COMIC_EPUB_TITLE_REQUIRED')
    metadata = 16384 + 18 * len(titles[0]) + sum(4096 + 18 * len(t) for t in titles[1:])
    # Nav is one document, with an escaped label per page.
    if 4096 + 12 * len(titles[0]) + sum(256 + 6 * len(t) for t in titles[1:]) > MAX_XML_BYTES:
        raise ValueError('COMIC_EPUB_METADATA_LIMIT')
    if 4096 + 512 * len(rows) > MAX_XML_BYTES or metadata > MAX_METADATA_BYTES:
        raise ValueError('COMIC_EPUB_METADATA_LIMIT')
    # Conservative PNG/zlib bound, plus ZIP names/headers/central directory and
    # metadata. PNG remains the original encoder, not a second raster engine.
    pixels = sum(r['document']['width'] * r['document']['height'] for r in rows)
    output = pixels * 4 + len(rows) * 65536 + metadata + 65536
    if output > max_output:
        raise ValueError('COMIC_PUBLICATION_ARCHIVE_LIMIT')
    return {'max_metadata_bytes': MAX_METADATA_BYTES, 'max_output_bytes': max_output,
            'total_page_pixels': pixels, 'reserved_metadata_bytes': metadata,
            'reserved_output_bytes': output}


class Package:
    def __init__(self, stream, book, rows, request, receipt):
        self.archive = zipfile.ZipFile(stream, 'w', allowZip64=False)
        try:
            self._metadata(book, rows, request, receipt)
        except BaseException:
            # Initialization can fail on an exhausted output budget; release the
            # ZIP handle without masking that original fail-closed exception.
            try:
                self.archive.close()
            except Exception:
                pass
            raise

    def _metadata(self, book, rows, request, receipt):
        self.remaining = receipt['epub_limits']['reserved_metadata_bytes']
        self._put('mimetype', b'application/epub+zip')
        self._xml('META-INF/container.xml', '<?xml version="1.0" encoding="UTF-8"?>'
                  '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                  '<rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/>'
                  '</rootfiles></container>')
        title = escape(book['document']['title'])
        items = []; spine = []; navigation = []
        for i, row in enumerate(rows, 1):
            stem = f'{i:04}'
            label = escape(row['document']['title'])
            width, height = row['document']['width'], row['document']['height']
            items.append(f'<item id="page-{stem}" href="pages/{stem}.xhtml" media-type="application/xhtml+xml"/>'
                         f'<item id="image-{stem}" href="images/{stem}.png" media-type="image/png"/>')
            spine.append(f'<itemref idref="page-{stem}"/>')
            navigation.append(f'<li><a href="pages/{stem}.xhtml">{i}. {label}</a></li>')
            self._xml(f'EPUB/pages/{stem}.xhtml',
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="und" lang="und"><head>'
                f'<title>{label}</title><meta name="viewport" content="width={width}, height={height}"/>'
                '<style>html,body{margin:0;padding:0;}img{display:block;}</style></head><body>'
                f'<img src="../images/{stem}.png" width="{width}" height="{height}" '
                f'alt="Raster comic page {i}; text alternative unavailable."/></body></html>')
        self._xml('EPUB/nav.xhtml', '<?xml version="1.0" encoding="UTF-8"?>'
                  '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
                  'xml:lang="und" lang="und"><head>' + f'<title>{title}</title></head><body>'
                  f'<nav epub:type="toc" id="toc"><h1>{title}</h1><ol>' + ''.join(navigation) + '</ol></nav></body></html>')
        modified = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        direction = request.reading_direction.lower()
        self._xml('EPUB/package.opf', '<?xml version="1.0" encoding="UTF-8"?>'
                  '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="publication-id" '
                  'prefix="rendition: http://www.idpf.org/vocab/rendition/#">'
                  '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                  f'<dc:identifier id="publication-id">urn:sha256:{receipt["publication_digest"]}</dc:identifier>'
                  f'<dc:title>{title}</dc:title><dc:language>und</dc:language>'
                  f'<meta property="dcterms:modified">{modified}</meta>'
                  '<meta property="rendition:layout">pre-paginated</meta>'
                  '<meta property="rendition:orientation">auto</meta><meta property="rendition:spread">none</meta>'
                  '<dc:description>Raster-only reading copy; no searchable or editable text. Limited accessibility; '
                  'text alternatives unavailable. No print fidelity guarantee. EPUBCheck and external reader validation '
                  'not run. Saved chapter then page order; direction does not reorder panels.</dc:description>'
                  '</metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
                  + ''.join(items) + f'</manifest><spine page-progression-direction="{direction}">'
                  + ''.join(spine) + '</spine></package>')

    def _put(self, name, data):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        self.archive.writestr(info, data)

    def _xml(self, name, text):
        # Conservative pre-allocation bounds are checked by admit; exact sizes
        # still fail closed if a future template outgrows those bounds.
        if len(text) > MAX_XML_BYTES:
            raise ValueError('COMIC_EPUB_METADATA_LIMIT')
        data = text.encode('utf-8')
        if len(data) > min(MAX_XML_BYTES, self.remaining):
            raise ValueError('COMIC_EPUB_METADATA_LIMIT')
        self.remaining -= len(data)
        self._put(name, data)

    def page(self, index, data):
        self._put(f'EPUB/images/{index:04}.png', data)

    def finish(self):
        self.archive.close()
