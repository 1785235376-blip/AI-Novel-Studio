"""Measurement regression: Word line-break elements are manuscript text boundaries.

The hand-built packages are independent of the product DOCX generator. The
second group proves the frozen producer and original importer preserve LF before
checking the shared A43 test extractor. No PostgreSQL execution is emulated.
"""
from copy import deepcopy
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from app.document import plain_text
from app.export_formats import novel_to_docx
from app.import_parsers import docx_to_text
from test_a43_rich_document import export_text

WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def independent_docx(body):
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml',
            '<w:document xmlns:w="' + WORD_NS + '"><w:body>' + body + '</w:body></w:document>')
    return output.getvalue()


@pytest.mark.parametrize('body,expected', [
    pytest.param('<w:p><w:r><w:t>FIRST</w:t></w:r><w:r><w:br/></w:r><w:r><w:t>SECOND</w:t></w:r></w:p>',
                 'FIRST\nSECOND', id='break-between-runs'),
    pytest.param('<w:p><w:r><w:t>中文🙂FIRST</w:t><w:br/><w:t>SECOND</w:t></w:r></w:p>',
                 '中文🙂FIRST\nSECOND', id='break-inside-run'),
    pytest.param('<w:p><w:r><w:t>FIRST</w:t><w:br/><w:br/><w:t>SECOND</w:t></w:r></w:p><w:p/><w:p><w:r><w:t>END</w:t></w:r></w:p>',
                 'FIRST\n\nSECOND\n\nEND', id='repeated-breaks-and-empty-paragraph'),
    pytest.param('<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>FIRST</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>SECOND</w:t></w:r></w:p>',
                 'FIRST\tSECOND', id='tab-and-marked-runs'),
])
def test_docx_measurement_preserves_structural_breaks_and_tabs(body, expected):
    raw = independent_docx(body)
    assert export_text(raw, 'docx') == expected


@pytest.mark.parametrize('kind', ['literal-lf', 'literal-crlf', 'split-marks-lf', 'run-ends-with-lf'])
def test_pg_shaped_multiline_title_is_intact_in_product_docx_and_measurement(kind):
    first, last = '中文🙂FIRST', 'SECONDLINESECRET'
    if kind == 'literal-crlf':
        runs = [{'type': 'text', 'text': first + '\r\n' + last}]
    elif kind == 'split-marks-lf':
        runs = [{'type': 'text', 'text': '中文', 'marks': [{'type': 'bold'}]},
                {'type': 'text', 'text': '🙂FIRST\n' + last, 'marks': [{'type': 'italic'}]}]
    elif kind == 'run-ends-with-lf':
        runs = [{'type': 'text', 'text': first + '\n'}, {'type': 'text', 'text': last}]
    else:
        runs = [{'type': 'text', 'text': first + '\n' + last}]
    document = {'type': 'doc', 'content': [
        {'type': 'heading', 'attrs': {'level': 1}, 'content': runs},
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'BODY-MUST-STAY'}]},
    ]}
    original = deepcopy(document)
    # This is the unchanged PG metadata rule applied to a synthetic snapshot,
    # not a database fixture and not evidence of a new PostgreSQL run.
    chapter = {'title': ''.join(node['text'] for node in runs), 'document': document}
    expected = 'Book\n' + plain_text(document).replace('\r\n', '\n')
    raw = novel_to_docx('Book', [chapter])
    with ZipFile(BytesIO(raw)) as archive:
        xml = ET.fromstring(archive.read('word/document.xml'))
    assert len(list(xml.iter('{' + WORD_NS + '}br'))) == 1
    assert [node.text for node in xml.iter('{' + WORD_NS + '}t')] == ['Book', first, last, 'BODY-MUST-STAY']
    assert docx_to_text(raw) == expected  # Original product importer already succeeds.
    assert export_text(raw, 'docx') == expected
    assert document == original
