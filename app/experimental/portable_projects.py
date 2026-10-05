"""U14 bounded portable copies, exact relinking and conservative cache cleanup.

This format is an explicitly bounded manuscript/media subset of the existing
backup contract. Original repository, revision and asset services remain the
only content writers. No archive is ever extracted and no grant is imported.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import re
import stat
import tempfile
import zipfile
from typing import Literal
from uuid import uuid4

from pydantic import Field
from ..backup_restore import _has_credential
from ..media_files import inspect_image, inspect_media
from ..services.export_resource_snapshot import capture_asset
from ..services.novel_service import NovelService
from ..source_privacy import source_privacy_status
from .common import DomainService, StaleSourceError, change_row, check_version, new_row
from .planning import StrictModel, digest
from .reader_sources import authorized_chapter_rows
from .store import canonical

FEATURE = 'portable_projects_v2'
MAX_ARCHIVE = 40 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_MEMBER = 8 * 1024 * 1024
MAX_MANIFEST = 4 * 1024 * 1024
MAX_MEMBERS = 101
MAX_CHAPTERS = 100
SAFE_ID = r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,239}$'
SHA = r'^[a-f0-9]{64}$'
LIMITS = ['CURRENT_SELECTED_MANUSCRIPT_AND_REFERENCED_MEDIA_ONLY', 'HISTORY_TRASH_CANON_WORKFLOWS_NOT_COPIED_USE_OFFLINE_BACKUP',
          'NO_CREDENTIALS_PROVIDER_CONFIG_MODELS_OR_PERMISSION_GRANTS', 'RESTORE_LOCAL_NEW_PROJECT_ONLY']


class SelectionIn(StrictModel):
    chapter_ids: list[str] = Field(min_length=1, max_length=MAX_CHAPTERS)


class UploadIn(StrictModel):
    filename: str = Field(min_length=1, max_length=240)
    content_base64: str = Field(min_length=1, max_length=4 * ((MAX_ARCHIVE + 2) // 3))


class ConfirmIn(StrictModel):
    expected_version: int = Field(ge=1)
    snapshot_digest: str = Field(pattern=SHA)
    confirmed: Literal[True]


class RelinkIn(UploadIn):
    missing_id: str = Field(pattern=SAFE_ID)
    chapter_ids: list[str] = Field(min_length=1, max_length=MAX_CHAPTERS)
    kind: Literal['image', 'audio', 'video']


class RelinkConfirmIn(ConfirmIn):
    accept_different_digest: bool = False


class CleanupIn(StrictModel):
    record_ids: list[str] = Field(min_length=1, max_length=100)
    preview_digest: str = Field(pattern=SHA)
    confirmed: Literal[True]


class PortableChapter(StrictModel):
    ref: str = Field(pattern=r'^c[0-9]{4}$')
    title: str = Field(min_length=1, max_length=200)
    document: dict


class PortableMedia(StrictModel):
    ref: str = Field(pattern=r'^a[0-9]{4}$')
    state: Literal['AVAILABLE', 'MISSING']
    kind: Literal['image', 'audio', 'video'] | None = None
    path: str | None = Field(default=None, max_length=80)
    sha256: str | None = Field(default=None, pattern=SHA)
    size: int | None = Field(default=None, ge=1, le=MAX_MEMBER)
    media_type: str | None = Field(default=None, max_length=80)


class Manifest(StrictModel):
    format: Literal['AI_NOVEL_PORTABLE_1']
    title: str = Field(min_length=1, max_length=200)
    privacy_level: Literal['LOCAL_ONLY']
    chapters: list[PortableChapter] = Field(min_length=1, max_length=MAX_CHAPTERS)
    media: list[PortableMedia] = Field(default_factory=list, max_length=100)
    limitations: list[str]


def atomic_bytes(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode(encoded, maximum=MAX_ARCHIVE):
    if not isinstance(encoded, str) or len(encoded) > 4 * ((maximum + 2) // 3):
        raise ValueError('PORTABLE_SIZE_LIMIT')
    try: result = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError): raise ValueError('PORTABLE_INVALID_BASE64') from None
    if not result or len(result) > maximum: raise ValueError('PORTABLE_SIZE_LIMIT')
    return result


def safe_document(document, refs=None, depth=0, budget=None):
    """Whitelisted TipTap nodes; no HTML, URL, script or path-valued attributes."""
    if budget is None: budget = [0]
    budget[0] += 1
    if budget[0] > 100000 or depth > 30 or not isinstance(document, dict): raise ValueError('PORTABLE_DOCUMENT_LIMIT')
    kind = document.get('type')
    if kind not in {'doc', 'paragraph', 'heading', 'text', 'hardBreak', 'blockquote', 'bulletList', 'orderedList', 'listItem', 'codeBlock', 'horizontalRule', 'image', 'audio', 'video'}:
        raise ValueError('PORTABLE_UNSUPPORTED_DOCUMENT_NODE')
    if set(document) - {'type', 'content', 'attrs', 'text', 'marks'}: raise ValueError('PORTABLE_DOCUMENT_FIELDS')
    result = {'type': kind}
    if 'text' in document:
        if kind != 'text' or not isinstance(document['text'], str): raise ValueError('PORTABLE_TEXT_INVALID')
        result['text'] = document['text']
    attrs = document.get('attrs') or {}
    allowed = {'heading': {'level'}, 'orderedList': {'start'}, 'codeBlock': {'language'},
               'image': {'asset_id', 'alt', 'title'}, 'audio': {'asset_id', 'title'}, 'video': {'asset_id', 'title'}}.get(kind, set())
    if not isinstance(attrs, dict) or set(attrs) - allowed: raise ValueError('PORTABLE_UNSUPPORTED_DOCUMENT_ATTRIBUTES')
    if attrs:
        result['attrs'] = deepcopy(attrs)
        for key, value in attrs.items():
            if key == 'asset_id':
                if not isinstance(value, str) or not re.fullmatch(SAFE_ID, value): raise ValueError('PORTABLE_ASSET_REFERENCE_INVALID')
                if refs is not None:
                    if value not in refs: raise ValueError('PORTABLE_UNDECLARED_MEDIA')
                    result['attrs'][key] = refs[value]
            elif key == 'level':
                if type(value) is not int or not 1 <= value <= 6: raise ValueError('PORTABLE_HEADING_INVALID')
            elif key == 'start':
                if type(value) is not int or not 1 <= value <= 100000: raise ValueError('PORTABLE_LIST_INVALID')
            elif value is not None and (not isinstance(value, str) or len(value) > 200): raise ValueError('PORTABLE_ATTRIBUTE_INVALID')
    if kind in {'image', 'audio', 'video'} and not attrs.get('asset_id'): raise ValueError('PORTABLE_MEDIA_REFERENCE_REQUIRED')
    if 'marks' in document:
        marks = document['marks']
        if not isinstance(marks, list) or len(marks) > 8 or any(not isinstance(m, dict) or set(m) != {'type'} or m['type'] not in {'bold', 'italic', 'strike', 'underline', 'code', 'subscript', 'superscript'} for m in marks):
            raise ValueError('PORTABLE_UNSUPPORTED_MARK')
        result['marks'] = deepcopy(marks)
    if 'content' in document:
        if not isinstance(document['content'], list): raise ValueError('PORTABLE_CONTENT_INVALID')
        result['content'] = [safe_document(n, refs, depth + 1, budget) for n in document['content']]
    if depth == 0 and (kind != 'doc' or len(canonical(result).encode()) > MAX_MANIFEST): raise ValueError('PORTABLE_DOCUMENT_LIMIT')
    return result


def inspect_payload(data, kind):
    if len(data) > MAX_MEMBER: raise ValueError('PORTABLE_MEDIA_LIMIT')
    # Original bounded media decoders allow local file/pipe only. XML/HTML/SVG,
    # playlists, archives, scripts and model binaries cannot be media members.
    return inspect_image(data) if kind == 'image' else inspect_media(data, kind)


def _json(data):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out: raise ValueError('PORTABLE_DUPLICATE_JSON_KEY')
            out[key] = value
        return out
    try: return json.loads(data, object_pairs_hook=unique, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('PORTABLE_NONFINITE')))
    except (UnicodeError, RecursionError, json.JSONDecodeError): raise ValueError('PORTABLE_MANIFEST_INVALID') from None


def read_archive(raw):
    if not raw or len(raw) > MAX_ARCHIVE: raise ValueError('PORTABLE_ARCHIVE_LIMIT')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= MAX_MEMBERS: raise ValueError('PORTABLE_MEMBER_LIMIT')
            names, total = set(), 0
            for item in infos:
                path = PurePosixPath(item.filename)
                if (item.filename in names or '\\' in item.filename or '\x00' in item.filename or path.is_absolute()
                    or any(p in {'', '.', '..'} for p in item.filename.split('/'))
                    or not re.fullmatch(r'(manifest\.json|media/a[0-9]{4}\.(png|jpg|webp|wav|mp3|mp4|webm|ogg|flac))', item.filename)
                    or item.is_dir() or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1
                    or item.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}):
                    raise ValueError('PORTABLE_UNSAFE_MEMBER')
                maximum = MAX_MANIFEST if item.filename == 'manifest.json' else MAX_MEMBER
                if item.file_size > maximum or item.file_size > max(1, item.compress_size) * 100: raise ValueError('PORTABLE_COMPRESSION_LIMIT')
                total += item.file_size
                if total > MAX_TOTAL: raise ValueError('PORTABLE_EXPANDED_LIMIT')
                names.add(item.filename)
            if 'manifest.json' not in names: raise ValueError('PORTABLE_MANIFEST_MISSING')
            doc = _json(archive.read('manifest.json'))
            if _has_credential(doc): raise ValueError('PORTABLE_CREDENTIAL_FIELD')
            manifest = Manifest.model_validate(doc).model_dump()
            if manifest['limitations'] != LIMITS: raise ValueError('PORTABLE_SCOPE_DECLARATION_INVALID')
            if len({c['ref'] for c in manifest['chapters']}) != len(manifest['chapters']) or len({m['ref'] for m in manifest['media']}) != len(manifest['media']):
                raise ValueError('PORTABLE_DUPLICATE_REFERENCE')
            refs = {m['ref']: m['ref'] for m in manifest['media']}; expected = {'manifest.json'}; payloads = {}
            for chapter in manifest['chapters']: chapter['document'] = safe_document(chapter['document'], refs)
            for media in manifest['media']:
                if media['state'] == 'MISSING':
                    if media['path'] is not None or media['size'] is not None: raise ValueError('PORTABLE_MISSING_MEMBER_INVALID')
                    continue
                path = media['path']
                if not path or path not in names or not path.startswith('media/' + media['ref'] + '.') or path in expected or not media['kind']:
                    raise ValueError('PORTABLE_MEMBER_MISMATCH')
                data = archive.read(path)
                if len(data) != media['size'] or sha(data) != media['sha256']: raise ValueError('PORTABLE_DIGEST_MISMATCH')
                measured = inspect_payload(data, media['kind'])
                if measured['media_type'] != media['media_type'] or path != 'media/' + media['ref'] + '.' + measured['extension']:
                    raise ValueError('PORTABLE_MEDIA_TYPE_MISMATCH')
                payloads[media['ref']] = data; expected.add(path)
            if names != expected: raise ValueError('PORTABLE_UNDECLARED_MEMBER')
            return manifest, payloads
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError): raise ValueError('PORTABLE_ARCHIVE_INVALID') from None


class PortableProjectsService(DomainService):
    RECORDS = 'portable_projects_v2'

    def __init__(self, store, novels, chapters, *, sources, assets):
        super().__init__(store, novels, chapters)
        self.sources, self.assets = sources, assets
        self.cache_root = store.root / 'portable_cache_v2'

    def _rows(self, ctx, selected=None):
        rows = authorized_chapter_rows(ctx, self.sources, self.chapters)
        if selected is not None:
            if len(set(selected)) != len(selected): raise ValueError('PORTABLE_DUPLICATE_SELECTION')
            by_id = {r['id']: r for r in rows}
            if any(cid not in by_id for cid in selected): raise FileNotFoundError('source unavailable')
            rows = [by_id[cid] for cid in selected]
        if len(rows) > MAX_CHAPTERS or sum(len(canonical(r)) for r in rows) > MAX_MANIFEST: raise ValueError('PORTABLE_SOURCE_LIMIT')
        return [{**r, "portable_source_privacy": source_privacy_status(r, ctx.scope.get("branch_id"), self.store.root)} for r in rows]

    def _sources(self, rows): return {r['id']: digest(r) for r in rows}

    def _assert_sources(self, ctx, sources):
        if self._sources(self._rows(ctx, list(sources))) != sources: raise StaleSourceError('PORTABLE_SOURCE_CHANGED')

    def _owned(self, ctx, rid):
        row = self.get(ctx.novel_id, ctx.scope, self.RECORDS, rid)
        if row['created_by'] != ctx.actor: raise FileNotFoundError('record unavailable')
        if row.get('sources'):
            rows = self._rows(ctx, list(row['sources']))
            if row['kind'] == 'EXPORT':
                for alias, aid in enumerate(NovelService._asset_references(rows), 1):
                    old = next((m for m in row['manifest']['media'] if m['ref'] == f'a{alias:04d}'), None)
                    if old is None or old['state'] != 'AVAILABLE': continue
                    asset = self.assets.get(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
                    if asset.get('novel_id') != ctx.novel_id or asset.get('branch_id') != ctx.scope.get('branch_id') or asset.get('hidden') or asset.get('secret'):
                        raise FileNotFoundError('record unavailable')
        return row

    def _file(self, ctx, rid, extension='zip'):
        if not re.fullmatch(r'[a-f0-9-]{36}', rid): raise ValueError('PORTABLE_RECORD_INVALID')
        root = self.cache_root
        if root.is_symlink() or any(p.is_symlink() for p in root.parents): raise ValueError('PORTABLE_CACHE_LINK')
        root.mkdir(parents=True, exist_ok=True)
        path = root / (digest([ctx.scope, ctx.actor, rid]) + '.' + extension)
        if path.is_symlink(): raise ValueError('PORTABLE_CACHE_LINK')
        return path

    def _read_file(self, ctx, row, extension='zip'):
        path = self._file(ctx, row['id'], extension)
        if path.stat().st_size > MAX_ARCHIVE: raise ValueError('PORTABLE_CACHE_LIMIT')
        data = path.read_bytes()
        if sha(data) != row['artifact_digest']: raise ValueError('PORTABLE_CACHE_CHANGED')
        return data

    def _summary(self, row):
        result = {k: deepcopy(row[k]) for k in ('id', 'version', 'status', 'kind', 'snapshot_digest', 'created_at', 'error_code', 'target_id', 'id_map', 'digest_matches') if k in row}
        manifest = row.get('manifest')
        if manifest:
            result['title'] = manifest['title']; result['chapter_count'] = len(manifest['chapters'])
            result['media'] = [{k: v for k, v in m.items() if k != 'path'} for m in manifest['media']]
            result['limitations'] = LIMITS
        return result

    def catalog(self, ctx):
        rows = self._rows(ctx)
        missing = []
        for aid in NovelService._asset_references(rows):
            if not re.fullmatch(SAFE_ID, aid): continue
            meta = None
            try:
                meta = self.assets.get(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
                if meta.get('novel_id') != ctx.novel_id or meta.get('branch_id') != ctx.scope.get('branch_id') or meta.get('hidden') or meta.get('secret'): continue
                self.assets.content(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor); continue
            except FileNotFoundError:
                if meta is None and not aid.startswith('missing-'): continue
            except (OSError, ValueError): pass
            # ID occurs in an authorized chapter. Never expose inaccessible
            # external asset metadata, names, paths or content.
            missing.append({'id': aid, 'expected_sha256': meta.get('sha256') if meta else None,
                            'chapter_ids': [r['id'] for r in rows if aid in NovelService._asset_references(r)]})
        return {'chapters': [{'id': r['id'], 'title': r['title'], 'version': r['version']} for r in rows],
                'missing': missing, 'restore_available': ctx.scope['mode'] == 'local', 'limitations': LIMITS,
                'max_archive_bytes': MAX_ARCHIVE, 'max_member_bytes': MAX_MEMBER}

    def records(self, ctx):
        visible = []
        for row in self.list(ctx.novel_id, ctx.scope, self.RECORDS):
            if row['created_by'] != ctx.actor: continue
            try: self._owned(ctx, row['id'])
            except FileNotFoundError: continue
            visible.append(self._summary(row))
        return {'items': visible[-100:]}

    def _build(self, ctx, selected):
        rows = self._rows(ctx, selected); refs = NovelService._asset_references(rows)
        if len(refs) > 100: raise ValueError('PORTABLE_MEDIA_LIMIT')
        mapping = {rid: f'a{i:04d}' for i, rid in enumerate(refs, 1)}; media, payloads = [], {}; total = 0
        for aid, alias in mapping.items():
            meta = None
            try:
                meta = self.assets.get(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
                if meta.get('novel_id') != ctx.novel_id or meta.get('branch_id') != ctx.scope.get('branch_id') or meta.get('hidden') or meta.get('secret'):
                    meta = None; raise FileNotFoundError()
                if type(meta.get('size')) is not int or meta['size'] > MAX_MEMBER: raise ValueError('limit')
                data = self.assets.content(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
                capture_asset(meta, data, asset_id=aid, novel_id=ctx.novel_id, branch_id=ctx.scope.get('branch_id'))
                kind = meta.get('kind'); measured = inspect_payload(data, kind) if kind in {'image', 'audio', 'video'} else None
                if not measured: raise ValueError('unsupported media')
                total += len(data)
                if total > MAX_TOTAL - MAX_MANIFEST: raise ValueError('PORTABLE_TOTAL_LIMIT')
                path = f"media/{alias}.{measured['extension']}"; payloads[path] = data
                media.append({'ref': alias, 'state': 'AVAILABLE', 'kind': kind, 'path': path, 'sha256': sha(data), 'size': len(data), 'media_type': measured['media_type']})
            except (OSError, ValueError):
                media.append({'ref': alias, 'state': 'MISSING', 'kind': meta.get('kind') if meta and meta.get('kind') in {'image', 'audio', 'video'} else None,
                              'path': None, 'size': None, 'media_type': None, 'sha256': meta.get('sha256') if meta else None})
        manifest = Manifest.model_validate({'format': 'AI_NOVEL_PORTABLE_1', 'title': str(self.novels.get(ctx.novel_id)['title'])[:200], 'privacy_level': 'LOCAL_ONLY',
            'chapters': [{'ref': f'c{i:04d}', 'title': r['title'][:200], 'document': safe_document(r['document'], mapping)} for i, r in enumerate(rows, 1)], 'media': media, 'limitations': LIMITS}).model_dump()
        encoded = canonical(manifest).encode()
        if len(encoded) > MAX_MANIFEST or len(encoded) + sum(map(len, payloads.values())) > MAX_TOTAL: raise ValueError('PORTABLE_TOTAL_LIMIT')
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(zipfile.ZipInfo('manifest.json'), encoded)
            for path, data in payloads.items(): archive.writestr(zipfile.ZipInfo(path), data)
        self._assert_sources(ctx, self._sources(rows))
        return manifest, out.getvalue(), self._sources(rows)

    def export(self, ctx, body, reauthorize=lambda: None):
        selected = SelectionIn.model_validate(body)
        manifest, raw, sources = self._build(ctx, selected.chapter_ids); reauthorize()
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'kind': 'EXPORT', 'status': 'READY', 'manifest': manifest, 'sources': sources,
            'artifact_digest': sha(raw), 'snapshot_digest': digest([manifest, sources])})
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            reauthorize(); self._assert_sources(ctx, sources)
            atomic_bytes(self._file(ctx, row['id']), raw)
            state['collections'].setdefault(self.RECORDS, {})[row['id']] = row
        return self._summary(row)

    def download(self, ctx, rid, version, reauthorize=lambda: None):
        row = self._owned(ctx, rid); check_version(row, version)
        if row['kind'] != 'EXPORT': raise ValueError('PORTABLE_EXPORT_REQUIRED')
        self._assert_sources(ctx, row['sources']); reauthorize()
        current_manifest, _, _ = self._build(ctx, list(row['sources']))
        if current_manifest != row['manifest']: raise StaleSourceError('PORTABLE_MEDIA_OR_PROJECT_CHANGED')
        with self.store.transaction(ctx.novel_id, ctx.scope):
            try: raw = self._read_file(ctx, row)
            except FileNotFoundError:
                manifest, raw, sources = self._build(ctx, list(row['sources']))
                if digest([manifest, sources]) != row['snapshot_digest']: raise StaleSourceError('PORTABLE_MEDIA_CHANGED')
                if sha(raw) != row['artifact_digest']: raise StaleSourceError('PORTABLE_CACHE_REGENERATION_CHANGED')
                reauthorize(); atomic_bytes(self._file(ctx, rid), raw)
            reauthorize(); self._assert_sources(ctx, row['sources'])
            return raw

    def preflight_import(self, ctx, body, reauthorize=lambda: None):
        value = UploadIn.model_validate(body)
        if not value.filename.lower().endswith('.zip'): raise ValueError('PORTABLE_ZIP_REQUIRED')
        raw = decode(value.content_base64); manifest, _ = read_archive(raw); reauthorize()
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'kind': 'IMPORT', 'status': 'PREFLIGHT', 'manifest': manifest,
            'artifact_digest': sha(raw), 'snapshot_digest': sha(raw)})
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            reauthorize(); atomic_bytes(self._file(ctx, row['id']), raw); state['collections'].setdefault(self.RECORDS, {})[row['id']] = row
        return self._summary(row)

    def restore(self, ctx, rid, body, reauthorize=lambda: None):
        value = ConfirmIn.model_validate(body)
        if ctx.scope['mode'] != 'local': raise ValueError('PORTABLE_NEW_PROJECT_SCOPE_ADAPTER_REQUIRED')
        row = self._owned(ctx, rid); check_version(row, value.expected_version)
        if row['kind'] != 'IMPORT' or row['status'] != 'PREFLIGHT' or row['snapshot_digest'] != value.snapshot_digest: raise ValueError('PORTABLE_CONFIRMATION_CHANGED')
        manifest, payloads = read_archive(self._read_file(ctx, row)); target = 'portable-' + uuid4().hex
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.RECORDS][rid]
            change_row(current, ctx.actor, value.expected_version, lambda r: r.update(status='RESTORING', target_id=target, id_map={'chapters': {}, 'media': {}})); reauthorize()
        # Cross-domain writes are checkpointed, not misrepresented as atomic.
        # An interrupted restore is never automatically replayed or overwritten.
        try:
            reauthorize(); self.novels.create({'id': target, 'title': manifest['title'] + ' (portable)', 'genre': 'Portable copy'})
            mapping = {}
            for media in manifest['media']:
                reauthorize()
                if media['state'] == 'AVAILABLE':
                    asset = self.assets.create(target, media['path'].split('/')[-1], base64.b64encode(payloads[media['ref']]).decode(), media['media_type'], media['kind'], 'portable:' + rid + ':' + media['ref'], required_features=(FEATURE,), owner_actor_id=ctx.actor)
                    mapping[media['ref']] = asset['id']
                else: mapping[media['ref']] = 'missing-' + uuid4().hex
                self._checkpoint(ctx, rid, 'media', media['ref'], mapping[media['ref']])
            for i, chapter in enumerate(manifest['chapters'], 1):
                reauthorize(); created = self.chapters.create(target, {'number': i, 'title': chapter['title'], 'content': ''})
                document = safe_document(chapter['document'], mapping)
                reauthorize(); self.chapters.save(created['id'], {'version': self.chapters.get(created['id'])['version'], 'document': document, 'source': 'PORTABLE_IMPORT'})
                self._checkpoint(ctx, rid, 'chapters', chapter['ref'], created['id'])
            reauthorize()
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                current = state['collections'][self.RECORDS][rid]
                for media in manifest['media']:
                    if media['state'] != 'AVAILABLE': continue
                    reauthorize(); aid = mapping[media['ref']]
                    stored = self.assets.get(aid, actor_id=ctx.actor)
                    self.assets.promote_owned(aid, actor_id=ctx.actor, branch_id=None, expected_version=stored['version'], provenance={'portable_record_id': rid, 'operation': 'RESTORE_NEW_PROJECT'}, guard=reauthorize)
                change_row(current, ctx.actor, current['version'], lambda r: r.update(status='RESTORED'))
            return self._summary(self._owned(ctx, rid))
        except Exception:
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                current = state['collections'][self.RECORDS][rid]
                change_row(current, ctx.actor, current['version'], lambda r: r.update(status='RECOVERY_REQUIRED', error_code='PORTABLE_PARTIAL_NEW_PROJECT_NO_AUTOMATIC_RETRY'))
            raise

    def _checkpoint(self, ctx, rid, category, old, new):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = state['collections'][self.RECORDS][rid]
            change_row(row, ctx.actor, row['version'], lambda r: r['id_map'][category].update({old: new}))

    def preflight_relink(self, ctx, body, reauthorize=lambda: None):
        value = RelinkIn.model_validate(body); rows = self._rows(ctx, value.chapter_ids)
        if not all(value.missing_id in NovelService._asset_references(row) for row in rows): raise FileNotFoundError('reference unavailable')
        missing = next((r for r in self.catalog(ctx)['missing'] if r['id'] == value.missing_id), None)
        if missing is None: raise FileNotFoundError('missing reference unavailable')
        raw = decode(value.content_base64, MAX_MEMBER); measured = inspect_payload(raw, value.kind); reauthorize()
        sources = self._sources(rows)
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'kind': 'RELINK', 'status': 'PREFLIGHT', 'sources': sources, 'missing_id': value.missing_id,
            'media_kind': value.kind, 'media_type': measured['media_type'], 'extension': measured['extension'], 'artifact_digest': sha(raw),
            'digest_matches': missing['expected_sha256'] == sha(raw), 'snapshot_digest': digest([sources, value.missing_id, sha(raw)])})
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            reauthorize(); self._assert_sources(ctx, sources); atomic_bytes(self._file(ctx, row['id'], 'bin'), raw); state['collections'].setdefault(self.RECORDS, {})[row['id']] = row
        return self._summary(row)

    def relink(self, ctx, rid, body, reauthorize=lambda: None):
        value = RelinkConfirmIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version)
        if ctx.scope['mode'] != 'local': raise ValueError('PORTABLE_BRANCH_WRITE_ADAPTER_REQUIRED')
        if row['kind'] != 'RELINK' or row['status'] != 'PREFLIGHT' or row['snapshot_digest'] != value.snapshot_digest: raise ValueError('PORTABLE_CONFIRMATION_CHANGED')
        if not row['digest_matches'] and not value.accept_different_digest: raise ValueError('PORTABLE_EXPLICIT_REPLACEMENT_REQUIRED')
        self._assert_sources(ctx, row['sources']); raw = self._read_file(ctx, row, 'bin'); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.RECORDS][rid]
            change_row(current, ctx.actor, value.expected_version, lambda r: r.update(status='RELINKING', id_map={'chapters': {}, 'media': {}})); reauthorize()
        try:
            reauthorize(); self._assert_sources(ctx, row['sources'])
            asset = self.assets.create(ctx.novel_id, 'relinked.' + row['extension'], base64.b64encode(raw).decode(), row['media_type'], row['media_kind'], 'portable-relink:' + rid, required_features=(FEATURE,), owner_actor_id=ctx.actor)
            self._checkpoint(ctx, rid, 'media', row['missing_id'], asset['id'])
            for chapter in self._rows(ctx, list(row['sources'])):
                if digest(chapter) != row['sources'][chapter['id']]: raise StaleSourceError('PORTABLE_SOURCE_CHANGED')
                mapping = {ref: asset['id'] if ref == row['missing_id'] else ref for ref in NovelService._asset_references(chapter)}
                document = safe_document(chapter['document'], mapping); reauthorize()
                self.chapters.save(chapter['id'], {'version': chapter['version'], 'document': document, 'source': 'PORTABLE_RELINK'})
                self._checkpoint(ctx, rid, 'chapters', chapter['id'], chapter['id'])
            reauthorize()
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                current = state['collections'][self.RECORDS][rid]
                reauthorize(); stored = self.assets.get(asset['id'], actor_id=ctx.actor)
                self.assets.promote_owned(asset['id'], actor_id=ctx.actor, branch_id=None, expected_version=stored['version'], provenance={'portable_record_id': rid, 'operation': 'CONFIRMED_RELINK'}, guard=reauthorize)
                change_row(current, ctx.actor, current['version'], lambda r: r.update(status='RELINKED'))
            return self._summary(self._owned(ctx, rid))
        except Exception:
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                current = state['collections'][self.RECORDS][rid]; change_row(current, ctx.actor, current['version'], lambda r: r.update(status='RECOVERY_REQUIRED', error_code='PORTABLE_PARTIAL_RELINK_NO_AUTOMATIC_RETRY'))
            raise

    def storage(self, ctx):
        rows = self._rows(ctx); assets = [a for a in self.assets.list(ctx.novel_id, branch_id=ctx.scope.get('branch_id'), include_deleted=True, actor_id=ctx.actor)
            if a.get('branch_id') == ctx.scope.get('branch_id') and not a.get('hidden') and not a.get('secret')]
        cache = []
        for row in self.list(ctx.novel_id, ctx.scope, self.RECORDS):
            if row['created_by'] != ctx.actor or row['kind'] != 'EXPORT' or row['status'] != 'READY': continue
            try:
                self._assert_sources(ctx, row['sources']); raw = self._read_file(ctx, row)
                manifest, _, _ = self._build(ctx, list(row['sources']))
                if manifest != row['manifest']: continue
                cache.append({'id': row['id'], 'version': row['version'], 'bytes': len(raw), 'sha256': sha(raw), 'reproducible': True, 'in_use': False})
            except (FileNotFoundError, ValueError, OSError): continue
        categories = [
            {'kind': 'MANUSCRIPT', 'bytes': sum(len(canonical(r['document']).encode()) for r in rows), 'measurement': 'AUTHORIZED_CONTENT_BYTES', 'cleanable': False},
            {'kind': 'ACCEPTED_ASSETS', 'bytes': sum(a['size'] for a in assets if not a.get('deleted_at') and not a.get('_owner_actor_id')), 'measurement': 'AUTHORIZED_RECORDED_BYTES', 'cleanable': False},
            {'kind': 'HISTORY', 'bytes': None, 'measurement': 'ORIGINAL_REVISION_AUTHORITY_NOT_ENUMERATED', 'cleanable': False},
            {'kind': 'TRASH', 'bytes': sum(a['size'] for a in assets if a.get('deleted_at')), 'measurement': 'AUTHORIZED_RECORDED_BYTES', 'cleanable': False},
            {'kind': 'REPRODUCIBLE_CACHE', 'bytes': sum(c['bytes'] for c in cache), 'measurement': 'VERIFIED_PORTABLE_EXPORT_CACHE_ONLY', 'cleanable': True},
            {'kind': 'TEMPORARY_FAILED_FILES', 'bytes': None, 'measurement': 'RECOVERY_INPUTS_PRESERVED_NOT_ENUMERATED', 'cleanable': False}]
        return {'categories': categories, 'eligible': cache, 'preview_digest': digest([ctx.scope, ctx.actor, cache]), 'default_policy': 'ONLY_VERIFIED_UNUSED_REPRODUCIBLE_CACHE'}

    def cleanup(self, ctx, body, reauthorize=lambda: None):
        value = CleanupIn.model_validate(body)
        with self.store.transaction(ctx.novel_id, ctx.scope):
            preview = self.storage(ctx)
            if value.preview_digest != preview['preview_digest']: raise StaleSourceError('PORTABLE_CLEANUP_PREVIEW_CHANGED')
            allowed = {r['id']: r for r in preview['eligible']}
            if len(set(value.record_ids)) != len(value.record_ids) or any(rid not in allowed for rid in value.record_ids): raise ValueError('PORTABLE_CACHE_NOT_ELIGIBLE')
            reauthorize()
            for rid in value.record_ids:
                reauthorize(); self._file(ctx, rid).unlink()
            return {'removed_cache_count': len(value.record_ids), 'preserved': ['MANUSCRIPT', 'ACCEPTED_ASSETS', 'HISTORY', 'TRASH', 'RECOVERY_INPUTS']}
