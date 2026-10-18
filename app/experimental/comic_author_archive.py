"""Private, assetless PAGE author interchange, through the original Comic owner.

This is editable author content, never a reading/publication copy. The transport
carries no source IDs, approvals, histories, actors, or authority. Persistence is
one original raw scope transaction, including a bounded durable replay receipt.
"""
from __future__ import annotations
import copy
import hashlib
import io
import json
import re
import stat
import struct
import zipfile
from pydantic import Field, ValidationError
from .media import StrictModel, digest
from .common import new_id, new_row, check_version, StaleSourceError
from .comic_collections import ComicBookIn
from .store import canonical

CONTRACT = 'comic-author-assetless-page/1'
RECEIPTS = 'comic_author_archive_receipts_v1'
MAX_ARCHIVE = 2_000_000
MAX_JSON = 180_000
MAX_PAGES = 10
MAX_TOTAL_JSON = 1_800_000
DISCLOSURE = 'PRIVATE_AUTHOR_CONTENT_INCLUDES_HIDDEN_TEXT_AND_IMAGE_BRIEFS_NOT_A_PUBLIC_READING_COPY'

class ExportPreviewIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)

class ExportIn(ExportPreviewIn):
    export_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    acknowledge_author_content: bool = Field(strict=True)

class ArchiveIn(StrictModel):
    archive_base64: str = Field(max_length=4 * ((MAX_ARCHIVE + 2) // 3))
    archive_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

class RestoreIn(ArchiveIn):
    inspection_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    request_key: str = Field(pattern=r'^[a-f0-9]{32}$')
    acknowledge_restore_drafts: bool = Field(strict=True)


def _fail():
    raise ValueError('COMIC_AUTHOR_ARCHIVE_INVALID_OR_UNSUPPORTED')


def _json(raw):
    if not 1 <= len(raw) <= MAX_JSON: _fail()
    # Bound depth before the JSON decoder recurses, including malicious inputs.
    depth = 0; quoted = False; escaped = False
    for c in raw:
        if quoted:
            if escaped: escaped = False
            elif c == 92: escaped = True
            elif c == 34: quoted = False
        elif c == 34: quoted = True
        elif c in (91, 123):
            depth += 1
            if depth > 12: _fail()
        elif c in (93, 125): depth -= 1
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: _fail()
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=lambda _: _fail())
        pending = [value]; nodes = 0
        while pending:
            item = pending.pop(); nodes += 1
            if nodes > 12000: _fail()
            if isinstance(item, dict): pending.extend(item.values())
            elif isinstance(item, list): pending.extend(item)
        return value
    except (UnicodeError, ValueError, RecursionError):
        _fail()


def _document(value):
    from .comic_layouts import LayoutIn
    try: body = LayoutIn.model_validate(value, strict=True)
    except ValidationError: _fail()
    if (body.source_mode != 'INDEPENDENT' or body.preset != 'PAGE'
            or body.screenplay_id is not None or body.expected_screenplay_version is not None): _fail()
    for panel in body.panels:
        if (panel.shot_id is not None or panel.asset_id is not None or panel.expected_asset_version is not None
                or panel.character_ids or panel.appearance_references
                or any(b.character_id is not None for b in panel.bubbles)): _fail()
    if body.layer_stack and any(item.kind == 'RASTER' for item in body.layer_stack.items): _fail()
    document = body.model_dump()
    if document != value: _fail()
    if len(canonical(document).encode()) > MAX_JSON: _fail()
    return document


def _remap(document, portable):
    document = copy.deepcopy(document); refs = {}
    for pindex, panel in enumerate(document['panels']):
        pid = f'panel_{pindex:03}' if portable else new_id()
        refs['PANEL', panel['id']] = pid; panel['id'] = pid
        for bindex, bubble in enumerate(panel['bubbles']):
            bid = f'bubble_{pindex:03}_{bindex:03}' if portable else new_id()
            refs['BUBBLE', bubble['id']] = bid; bubble['id'] = bid
    for index, layer in enumerate(document.get('layer_stack', {}).get('items', [])):
        layer['id'] = f'layer_{index:03}' if portable else 'layer_' + new_id()
        layer['target_id'] = refs[layer['kind'].split('_')[0], layer['target_id']]
    return document


def _portable(book, pages):
    aliases = {row['id']: f'page_{index:03}' for index, row in enumerate(pages)}
    entries = []; blobs = {}
    for index, row in enumerate(pages):
        document = _remap(_document(row['document']), True)
        name = f'pages/{index:03}.json'; raw = canonical(document).encode()
        blobs[name] = raw
        entries.append({'alias': aliases[row['id']], 'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    chapters = [{'id': f'chapter_{i:03}', 'title': c['title'], 'pages': [aliases[p] for p in c['pages']]}
                for i, c in enumerate(book['document']['chapters'])]
    manifest = {'contract': CONTRACT, 'book': {'title': book['document']['title'], 'chapters': chapters}, 'pages': entries}
    blobs['manifest.json'] = canonical(manifest).encode()
    if sum(map(len, blobs.values())) > MAX_TOTAL_JSON: _fail()
    return blobs


def decode(raw):
    """Strict closed-world ZIP_STORED manifest; no extraction or external reads."""
    if not isinstance(raw, bytes) or not 22 <= len(raw) <= MAX_ARCHIVE: _fail()
    try:
        if raw[-22:-18] != b'PK\x05\x06': _fail()
        end = struct.unpack('<4s4H2LH', raw[-22:])
        if (end[1] or end[2] or end[3] != end[4] or end[7]
                or not 2 <= end[4] <= MAX_PAGES + 1 or not 92 <= end[5] <= (MAX_PAGES + 1) * (46 + 14)
                or end[5] + end[6] != len(raw) - 22): _fail()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if not 2 <= len(infos) <= MAX_PAGES + 1 or archive.comment: _fail()
            names = [i.filename for i in infos]
            if len(set(names)) != len(names) or 'manifest.json' not in names: _fail()
            total = 0; offset = 0
            for item in infos:
                mode = item.external_attr >> 16
                if (item.filename != 'manifest.json' and not re.fullmatch(r'pages/[0-9]{3}\.json', item.filename)
                        or item.is_dir() or item.flag_bits not in (0, 2048) or item.external_attr & 0x10 or item.compress_type != zipfile.ZIP_STORED
                        or item.file_size != item.compress_size or not 1 <= item.file_size <= MAX_JSON
                        or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)) or item.extra or item.comment): _fail()
                if item.header_offset != offset or raw[offset:offset+4] != b'PK\x03\x04': _fail()
                local = struct.unpack('<4s5H3L2H', raw[offset:offset+30])
                if (local[2] != item.flag_bits or local[3] != item.compress_type or local[6] != item.CRC
                        or local[7] != item.compress_size or local[8] != item.file_size or local[10]): _fail()
                name = raw[offset+30:offset+30+local[9]]
                if name != item.filename.encode('ascii'): _fail()
                offset += 30 + local[9] + item.compress_size
                total += item.file_size
            if offset != archive.start_dir or offset != end[6] or len(infos) != end[4]: _fail()
            if total > MAX_TOTAL_JSON: _fail()
            manifest = _json(archive.read('manifest.json'))
            if not isinstance(manifest, dict) or set(manifest) != {'contract', 'book', 'pages'} or manifest['contract'] != CONTRACT: _fail()
            entries = manifest['pages']
            if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_PAGES: _fail()
            if set(names) != {'manifest.json', *(f'pages/{i:03}.json' for i in range(len(entries)))}: _fail()
            book = ComicBookIn.model_validate(manifest['book'], strict=True)
            if 'expected_page_versions' in manifest['book']: _fail()
            book = book.model_dump(exclude={'expected_page_versions'})
            if book != manifest['book']: _fail()
            if any(c['id'] != f'chapter_{i:03}' for i,c in enumerate(book['chapters'])): _fail()
            aliases = [f'page_{i:03}' for i in range(len(entries))]
            if [p for c in book['chapters'] for p in c['pages']] != aliases: _fail()
            documents = []
            for index, entry in enumerate(entries):
                if (not isinstance(entry, dict) or set(entry) != {'alias', 'path', 'bytes', 'sha256'}
                        or entry['alias'] != aliases[index] or entry['path'] != f'pages/{index:03}.json'
                        or type(entry['bytes']) is not int): _fail()
                content = archive.read(entry['path'])
                if len(content) != entry['bytes'] or hashlib.sha256(content).hexdigest() != entry['sha256']: _fail()
                document = _document(_json(content))
                if _remap(document, True) != document: _fail()
                documents.append(document)
            return book, documents
    except (zipfile.BadZipFile, RuntimeError, KeyError, TypeError, OverflowError, struct.error, UnicodeError, ValidationError):
        _fail()


def _snapshot(service, nid, scope, actor, rid, version, guard):
    guard()
    with service._independent_transaction(nid, scope) as state:
        guard(); book = service._book_row(nid, scope, actor, rid, state); check_version(book, version)
        ids = service._book_pages(book['document'])
        if not 1 <= len(ids) <= MAX_PAGES: _fail()
        pages = [service._book_page(nid, scope, actor, pid, state) for pid in ids]
        blobs = _portable(book, pages)
        # Includes original pins only in private preview digest; never in archive.
        pin = digest({'contract': CONTRACT, 'actor': actor, 'scope': scope,
                      'incarnation': service._independent_identity(nid),
                      'book': {k:book[k] for k in ('id','version','document')},
                      'pages': [{k:p[k] for k in ('id','version','document')} for p in pages]})
        report = {'contract': CONTRACT, 'export_digest': pin, 'book_version': book['version'],
                  'page_count': len(pages), 'disclosure': DISCLOSURE,
                  'pages': [{'id': p['id'], 'version': p['version']} for p in pages],
                  'coverage': 'ASSETLESS_INDEPENDENT_PAGE_ONLY', 'conveys_approval': False}
        guard()
    return blobs, report


def export_preview(service, nid, scope, actor, rid, body, guard):
    return _snapshot(service,nid,scope,actor,rid,body.expected_version,guard)[1]


def export_archive(service, nid, scope, actor, rid, body, guard):
    blobs, report = _snapshot(service,nid,scope,actor,rid,body.expected_version,guard)
    if body.acknowledge_author_content is not True or body.export_digest != report['export_digest']:
        raise StaleSourceError('COMIC_AUTHOR_EXPORT_PREVIEW_CHANGED')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, content in blobs.items():
            item = zipfile.ZipInfo(name); item.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(item, content)
    raw = stream.getvalue(); decode(raw)
    if _snapshot(service,nid,scope,actor,rid,body.expected_version,guard)[1] != report:
        raise StaleSourceError('COMIC_AUTHOR_EXPORT_PREVIEW_CHANGED')
    guard(); return raw


def _receipt(row, key, actor, scope, incarnation):
    fields = {'contract','actor','scope','incarnation','request_key','archive_sha256','book_id','page_ids'}
    if (not isinstance(row,dict) or set(row) != fields or row['contract'] != CONTRACT
            or row['actor'] != actor or row['scope'] != scope or row['incarnation'] != incarnation
            or not isinstance(row['request_key'],str) or not re.fullmatch(r'[a-f0-9]{32}',row['request_key'])
            or not isinstance(row['archive_sha256'],str) or not re.fullmatch(r'[a-f0-9]{64}',row['archive_sha256'])
            or key != digest([actor,scope,incarnation,row['request_key']])
            or not isinstance(row['book_id'],str) or not re.fullmatch(r'[a-f0-9-]{36}',row['book_id'])
            or not isinstance(row['page_ids'],list) or not 1 <= len(row['page_ids']) <= MAX_PAGES
            or any(not isinstance(p,str) or not re.fullmatch(r'[a-f0-9-]{36}',p) for p in row['page_ids'])
            or len(set(row['page_ids'])) != len(row['page_ids'])): _fail()
    return row


def inspect_archive(service, nid, scope, actor, raw, guard):
    guard(); book, documents = decode(raw)
    incarnation = service._independent_identity(nid)
    sha = hashlib.sha256(raw).hexdigest()
    token = digest({'contract': CONTRACT, 'archive_sha256': sha, 'scope': scope,
                    'actor': actor, 'incarnation': incarnation})
    rows = service.store.read(nid,scope)['collections'].get(RECEIPTS,{})
    owned = [_receipt(r,k,actor,scope,incarnation) for k,r in rows.items()
             if isinstance(r,dict) and r.get('actor') == actor and r.get('incarnation') == incarnation]
    used = len(owned)
    completed = [{'request_key':r['request_key'], 'result_state':'COMPLETED'}
                 for r in owned if r['archive_sha256'] == sha]
    guard()
    return {'completed_attempts':completed, 'receipt_capacity':20, 'receipt_remaining':max(0,20-used), 'contract': CONTRACT, 'archive_sha256': sha, 'inspection_digest': token,
            'title': book['title'], 'page_count': len(documents), 'disclosure': DISCLOSURE,
            'restore_status': 'NEW_UNAPPROVED_DRAFTS', 'coverage': 'ASSETLESS_INDEPENDENT_PAGE_ONLY'}


def restore_archive(service, nid, scope, actor, raw, body, guard):
    report = inspect_archive(service,nid,scope,actor,raw,guard)
    if (body.acknowledge_restore_drafts is not True or body.archive_sha256 != report['archive_sha256']
            or body.inspection_digest != report['inspection_digest']):
        raise StaleSourceError('COMIC_AUTHOR_IMPORT_PREVIEW_CHANGED')
    book_document, documents = decode(raw)
    # Validate original payloads before opening any write-capable transaction.
    documents = [_remap(d, False) for d in documents]
    payloads = [service._payload(nid,scope,actor,d) for d in documents]
    with service._independent_transaction(nid,scope) as state:
        guard()
        if inspect_archive(service,nid,scope,actor,raw,guard)['inspection_digest'] != report['inspection_digest']:
            raise StaleSourceError('COMIC_AUTHOR_IMPORT_PREVIEW_CHANGED')
        incarnation = service._independent_identity(nid)
        key = digest([actor, scope, incarnation, body.request_key])
        rows = state['collections'].get(RECEIPTS, {})
        if key in rows:
            receipt = _receipt(rows[key],key,actor,scope,incarnation)
            if receipt['archive_sha256'] != body.archive_sha256: raise ValueError('COMIC_AUTHOR_IMPORT_REQUEST_CONFLICT')
            try:
                book = service._book_row(nid,scope,actor,receipt['book_id'],state)
                pages = [service._book_page(nid,scope,actor,pid,state) for pid in receipt['page_ids']]
                if set(service._book_pages(book['document'])) != set(receipt['page_ids']):
                    raise FileNotFoundError('changed imported membership')
            except (FileNotFoundError, ValueError):
                raise ValueError('COMIC_AUTHOR_IMPORT_ALREADY_COMPLETED_RESULTS_CHANGED_OR_UNAVAILABLE') from None
            result = {'book': service._book_view(nid,scope,actor,book,state),
                      'pages': [service._view(nid,scope,actor,p) for p in pages], 'replayed': True,
                      'request_key': body.request_key, 'result_state':'CURRENT_EDITABLE_ROWS_FROM_COMPLETED_IMPORT'}
            guard(); return result
        owned = [r for r in rows.values() if r.get('actor') == actor and r.get('incarnation') == incarnation]
        if len(owned) >= 20: raise ValueError('COMIC_AUTHOR_IMPORT_RECEIPT_LIMIT')
        if len(service._book_owner_rows(nid,actor,state)) >= 20: raise ValueError('COMIC_BOOK_COUNT_LIMIT')
        pages = []
        for payload in payloads:
            service._current(nid,scope,actor,payload)
            page = new_row(nid,scope,actor,payload)
            state['collections'].setdefault(service.RECORDS,{})[page['id']] = page; pages.append(page)
        mapping = {f'page_{i:03}': p['id'] for i,p in enumerate(pages)}
        for chapter in book_document['chapters']:
            chapter['id'] = new_id(); chapter['pages'] = [mapping[p] for p in chapter['pages']]
        book = new_row(nid,scope,actor,{'document':book_document, 'project_incarnation':incarnation,
                                      'status':'DRAFT', 'snapshot_scope':'STRUCTURE_ONLY'})
        state['collections'].setdefault(service.BOOKS,{})[book['id']] = book
        service._book_bound(nid,actor,state)
        # Bound all current actor/incarnation imported pages and receipts, not only books.
        owned_pages = {k:v for k,v in state['collections'].get(service.RECORDS,{}).items()
                       if v.get('created_by') == actor and v.get('project_incarnation') == incarnation}
        if len(canonical(owned_pages).encode()) > 16_000_000: raise ValueError('COMIC_AUTHOR_IMPORT_STORAGE_LIMIT')
        state['collections'].setdefault(RECEIPTS,{})[key] = {
            'contract': CONTRACT, 'actor':actor, 'scope':copy.deepcopy(scope), 'incarnation':incarnation,
            'request_key':body.request_key, 'archive_sha256':body.archive_sha256,
            'book_id':book['id'], 'page_ids':[p['id'] for p in pages]}
        result = {'book':service._book_view(nid,scope,actor,book,state),
                  'pages':[service._view(nid,scope,actor,p) for p in pages], 'replayed':False,
                  'request_key':body.request_key}
        guard()
    return result
