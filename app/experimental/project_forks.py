"""B09 reviewed local project forks over the original chapter and asset owners.

Only baselines/checkpoints/claims live here. They are evidence, never a second
editable manuscript. Cross-store writes have durable intent and uncertain-state
recovery, not an exactly-once or cross-project atomicity claim.
"""
from __future__ import annotations

import base64
import re
from copy import deepcopy
from contextlib import nullcontext
from dataclasses import replace
from difflib import SequenceMatcher
from typing import Literal
from uuid import uuid4

from pydantic import Field
from fastapi import HTTPException
from ..document import markdown_to_document, document_to_markdown
from ..repository import read_json
from ..file_project_lifecycle import project_operation
from ..repositories.file.chapter import FileChapterRepository
from ..revision_constraints import LOCK_ATTRIBUTE, assert_ai_locks, lock_nodes
from ..services.export_resource_snapshot import capture_asset
from ..services.novel_service import NovelService
from ..source_privacy import source_privacy_status
from .common import DomainService, StaleSourceError, check_version, new_row, now
from .planning import StrictModel, digest
from .portable_projects import safe_document, inspect_payload, MAX_MEMBER
from .reader_sources import authorized_chapter_rows
from .store import canonical

FEATURE = 'project_forks_v2'
LIMITS = ['LOCAL_NEW_PROJECT_FORK_NOT_COLLABORATION_BRANCH', 'SELECTED_CURRENT_CHAPTERS_ONLY',
          'RICH_BLOCK_MERGE_NO_TEXT_FLATTENING', 'CHAPTER_DELETION_IS_RECOVERABLE_ARCHIVE',
          'STRUCTURED_RECORDS_USE_REVIEWED_ORIGINAL_OWNER_ATTACHMENT',
          'NO_CANON_ARBITRARY_GRAPH_WORKFLOWS_HISTORY_OR_PERMISSION_COPY',
          'NO_NEW_OR_CHANGED_FORK_ASSET_REFERENCES_WITHOUT_MAPPING',
          'AUTHOR_LICENSE_DECLARATION_NOT_LEGAL_VERIFICATION',
          'CROSS_STORE_JOURNAL_NOT_GLOBAL_ATOMICITY']
MAX_CHAPTERS = 40
MAX_SNAPSHOT = 4 * 1024 * 1024
MAX_ASSETS_TOTAL = 32 * 1024 * 1024
MAX_BLOCKS = 1000


def advance(row, actor, expected_version, callback):
    """Bounded state history: manuscript evidence is already frozen once."""
    check_version(row, expected_version)
    previous = {k: row.get(k) for k in ('version', 'status', 'updated_at')}
    callback(row)
    row.update(version=expected_version + 1, updated_by=actor, updated_at=now(), history=(row.get('history', []) + [previous])[-100:])


class AssetPermission(StrictModel):
    asset_id: str = Field(min_length=1, max_length=240)
    version: int = Field(ge=1)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    license: str = Field(min_length=1, max_length=240)
    allow_local_copy: Literal[True]


class ForkIn(StrictModel):
    chapter_ids: list[str] = Field(min_length=1, max_length=MAX_CHAPTERS)
    title: str = Field(min_length=1, max_length=160)
    asset_permissions: list[AssetPermission] = Field(default_factory=list, max_length=100)


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1)


class ConfirmIn(VersionIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirmed: Literal[True]


class CompareIn(VersionIn):
    choices: dict[str, Literal['ORIGINAL', 'FORK']] = Field(default_factory=dict, max_length=500)


class ApplyIn(ConfirmIn):
    choices: dict[str, Literal['ORIGINAL', 'FORK']] = Field(default_factory=dict, max_length=500)


def rich_document(document, refs=None):
    """Use U14's allowlist, preserving bounded A11 locks byte-for-byte.

    Link/character/graph/custom embedded references are unsupported, not stripped.
    No mark, block or unrecognized attribute is silently flattened.
    """
    if not isinstance(document, dict) or not isinstance(document.get('content', []), list) or len(document.get('content', [])) > MAX_BLOCKS:
        raise ValueError('FORK_RICH_BLOCK_LIMIT')
    pending = [(document, 0)]; count = 0
    while pending:
        node, depth = pending.pop(); count += 1
        if not isinstance(node, dict) or depth > 30 or count > 100000:
            raise ValueError('FORK_DOCUMENT_DEPTH_OR_NODE_LIMIT')
        if not isinstance(node.get('content', []), list) or node.get('attrs') is not None and not isinstance(node['attrs'], dict):
            raise ValueError('FORK_DOCUMENT_STRUCTURE_INVALID')
        pending.extend((child, depth + 1) for child in node.get('content', []))
    clean = deepcopy(document)
    markers = lock_nodes(clean)
    for _, node, marker in markers:
        if not isinstance(marker, dict) or len(canonical(marker).encode()) > 2048:
            raise ValueError('FORK_UNSUPPORTED_REVISION_LOCK')
        node['attrs'].pop(LOCK_ATTRIBUTE)
        if not node['attrs']: node.pop('attrs')
    safe_document(clean, refs)  # validate without normalizing the saved tree
    result = deepcopy(document)
    def remap(node):
        attrs = node.get('attrs') or {}
        if refs is not None and 'asset_id' in attrs: attrs['asset_id'] = refs[attrs['asset_id']]
        for child in node.get('content', []): remap(child)
    remap(result)
    return result



def block_merge(base, original, fork):
    """Deterministic diff3 on immutable rich blocks; overlapping edits conflict.

    Insertions at an edited range boundary are deliberately conservative. Nested
    lists/quotes and all marks travel as intact subtrees, never plain text.
    """
    changes = []
    for side, value in [('ORIGINAL', original), ('FORK', fork)]:
        for tag, a, b, c, d in SequenceMatcher(a=[canonical(n) for n in base], b=[canonical(n) for n in value], autojunk=False).get_opcodes():
            if tag != 'equal': changes.append({'side': side, 'a': a, 'b': b, 'nodes': value[c:d]})
    changes.sort(key=lambda h: (h['a'], h['b'], h['side']))
    groups = []
    for change in changes:
        if not groups or change['a'] > groups[-1]['end'] or (change['a'] == groups[-1]['end'] and change['a'] != change['b'] and all(x['a'] != x['b'] for x in groups[-1]['changes'])):
            groups.append({'start': change['a'], 'end': change['b'], 'changes': [change]})
        else:
            groups[-1]['end'] = max(groups[-1]['end'], change['b']); groups[-1]['changes'].append(change)
    segments = []; position = 0
    for group in groups:
        start, end = group['start'], group['end']
        if position < start: segments.append({'kind': 'UNCHANGED', 'nodes': deepcopy(base[position:start])})
        values = {}
        for side in ['ORIGINAL', 'FORK']:
            nodes = []; cursor = start
            for change in sorted((h for h in group['changes'] if h['side'] == side), key=lambda h: h['a']):
                nodes.extend(base[cursor:change['a']]); nodes.extend(change['nodes']); cursor = change['b']
            nodes.extend(base[cursor:end]); values[side] = deepcopy(nodes)
        both = {h['side'] for h in group['changes']} == {'ORIGINAL', 'FORK'}
        kind = 'CONFLICT' if both and values['ORIGINAL'] != values['FORK'] else 'BOTH_SAME' if both else 'ORIGINAL_ONLY' if group['changes'][0]['side'] == 'ORIGINAL' else 'FORK_ONLY'
        segments.append({'kind': kind, 'start': start, 'end': end, 'base': deepcopy(base[start:end]), **values})
        position = end
    if position < len(base): segments.append({'kind': 'UNCHANGED', 'nodes': deepcopy(base[position:])})
    return segments


class ProjectForksService(DomainService):
    FORKS = 'project_forks_v2'
    MERGES = 'project_fork_merges_v2'

    def __init__(self, store, novels, chapters, *, sources, assets):
        super().__init__(store, novels, chapters)
        self.sources, self.assets = sources, assets

    @staticmethod
    def _local(ctx):
        if ctx.scope.get('mode') != 'local' or ctx.scope.get('branch_id') or ctx.branch:
            raise ValueError('FORK_COLLABORATION_BRANCH_WRITER_UNAVAILABLE')

    def _owned(self, ctx, collection, rid):
        self._local(ctx)
        row = self.get(ctx.novel_id, ctx.scope, collection, rid)
        if row.get('created_by') != ctx.actor: raise FileNotFoundError('fork unavailable')
        return row

    def _chapter(self, ctx, cid):
        if not re.fullmatch(re.escape(ctx.novel_id) + r':[1-9][0-9]{0,6}', cid):
            raise FileNotFoundError('chapter unavailable')
        try:
            repo = self.chapters.repository
            if isinstance(repo, FileChapterRepository):
                # Match U12's pure original-document projection. Preflight and
                # recovery reads must not lazily persist legacy packages.
                with project_operation(repo.backend.data, ctx.novel_id):
                    row = repo.backend.chapter(cid)
                    package = read_json(repo._paths(cid)[2], None)
                    if package is None:
                        doc, version = markdown_to_document(row['content']), 1
                    else:
                        if not isinstance(package, dict) or package.get('chapter_id') != cid or type(package.get('version')) is not int or package['version'] < 1 or not isinstance(package.get('document'), dict):
                            raise ValueError('FORK_ORIGINAL_DOCUMENT_PACKAGE_INVALID')
                        doc, version = package['document'], package['version']
                    row = {**row, 'version': version, 'document': doc, 'content': document_to_markdown(doc)}
            else: row = self.chapters.get(cid)
        except FileNotFoundError: return None
        if row.get('novel_id') != ctx.novel_id or row.get('branch_id') or row.get('hidden') or row.get('secret') or str(row.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'}:
            raise FileNotFoundError('chapter unavailable')
        return {'id': cid, 'version': row['version'], 'title': row['title'], 'archived': bool(row.get('is_archived')), 'document': rich_document(row['document']), 'privacy': source_privacy_status(row, root=self.store.root)['privacy_level']}

    def _create_chapter(self, ctx, target_id, number, title):
        repo = self.chapters.repository
        guard = project_operation(repo.backend.data, target_id) if isinstance(repo, FileChapterRepository) else nullcontext()
        with guard:
            try: self.chapters.get(f'{target_id}:{number}')
            except FileNotFoundError: pass
            else: raise StaleSourceError('FORK_NEW_TARGET_CHAPTER_ALREADY_EXISTS')
            return self.chapters.create(target_id, {'number': number, 'title': title, 'content': ''})

    def _archive_receipt_versions(self, version):
        # Original File archive tracks state separately; PostgreSQL increments
        # the chapter version. Respect both original contracts, never guess.
        return {version} if isinstance(self.chapters.repository, FileChapterRepository) else {version + 1}

    def _target_ctx(self, ctx, row):
        return replace(ctx, novel_id=row['target_id'], scope={'mode': 'local', 'novel_id': row['target_id']})

    def _asset(self, ctx, aid):
        meta = self.assets.get(aid, actor_id=ctx.actor)
        if meta.get('novel_id') != ctx.novel_id or meta.get('branch_id') or meta.get('hidden') or meta.get('secret'):
            raise FileNotFoundError('asset unavailable')
        if meta.get('size', MAX_MEMBER + 1) > MAX_MEMBER: raise ValueError('FORK_ASSET_SIZE_LIMIT')
        content = self.assets.content(aid, actor_id=ctx.actor)
        capture_asset(meta, content, asset_id=aid, novel_id=ctx.novel_id)
        if meta.get('kind') not in {'image', 'audio', 'video'}: raise ValueError('FORK_UNSUPPORTED_ASSET_KIND')
        inspect_payload(content, meta['kind'])
        return {k: deepcopy(meta.get(k)) for k in ('id', 'version', 'sha256', 'size', 'kind', 'filename', 'media_type', 'parameters', '_origin_provenance')}, content

    @staticmethod
    def _summary(row):
        keys = ('id', 'version', 'status', 'title', 'target_id', 'preview_digest', 'id_map', 'error_code', 'active_merge', 'created_at', 'fork_id', 'kind', 'checkpoint_id', 'journal', 'restored_by')
        out = {k: deepcopy(row[k]) for k in keys if k in row}
        out['limitations'] = LIMITS
        if 'baseline' in row: out['chapter_count'] = len(row['baseline'])
        if 'assets' in row: out['assets'] = [{k: a[k] for k in ('id', 'version', 'sha256', 'license')} for a in row['assets'].values()]
        return out

    def catalog(self, ctx):
        if ctx.scope.get('mode') != 'local': return {'chapters': [], 'assets': [], 'available': False, 'limitations': LIMITS}
        self._local(ctx)
        rows = authorized_chapter_rows(ctx, self.sources, self.chapters)
        chapters = []; assets = {}
        for row in rows[:MAX_CHAPTERS]:
            refs = NovelService._asset_references(row.get('document', {}))
            supported = True
            try:
                rich_document(row['document'])
                if len(refs) > 100: raise ValueError('FORK_ASSET_COUNT_LIMIT')
            except ValueError: supported = False
            chapters.append({'id': row['id'], 'title': row['title'], 'version': row['version'], 'asset_ids': refs, 'supported': supported})
            if not supported: continue
            for aid in refs:
                if aid in assets: continue
                try:
                    meta, _ = self._asset(ctx, aid)
                    assets[aid] = {**{k: meta[k] for k in ('id', 'version', 'sha256', 'filename')}, 'available': True}
                except (FileNotFoundError, OSError, ValueError):
                    # This ID occurs in authorized prose. Do not reveal whether
                    # it exists in another project, is private or is corrupt.
                    assets[aid] = {'id': aid, 'version': 0, 'sha256': '', 'filename': '不可用媒体引用', 'available': False}
        return {'chapters': chapters, 'assets': list(assets.values()), 'available': True, 'limitations': LIMITS}

    def records(self, ctx, target_authorize=lambda nid: None):
        self._local(ctx); visible = []
        for row in self.list(ctx.novel_id, ctx.scope, self.FORKS):
            if row['created_by'] != ctx.actor: continue
            try:
                for cid in row['baseline']: self._chapter(ctx, cid)
                for aid in row['assets']:
                    meta = self.assets.get(aid, actor_id=ctx.actor)
                    if meta.get('novel_id') != ctx.novel_id or meta.get('branch_id') or meta.get('hidden') or meta.get('secret'): raise FileNotFoundError()
            except FileNotFoundError: continue
            summary = self._summary(row); summary['target_available'] = True
            if row['status'] != 'PREFLIGHT':
                try: target_authorize(row['target_id'])
                except FileNotFoundError: summary['target_available'] = False
                except HTTPException as exc:
                    if exc.status_code not in {403, 404}: raise
                    summary['target_available'] = False
            # These are this actor's original-project operation receipts, not
            # target manuscript. Preserve them when a partial target is lost.
            visible.append(summary)
        ids = {row['id'] for row in visible}
        return {'items': visible[-100:],
                'merges': [self._summary(row) for row in self.list(ctx.novel_id, ctx.scope, self.MERGES)
                           if row['created_by'] == ctx.actor and row['fork_id'] in ids][-100:]}

    def preflight(self, ctx, body, reauthorize=lambda: None):
        self._local(ctx); value = ForkIn.model_validate(body)
        if len(set(value.chapter_ids)) != len(value.chapter_ids): raise ValueError('FORK_DUPLICATE_CHAPTER')
        baseline = {cid: self._chapter(ctx, cid) for cid in value.chapter_ids}
        if any(not c or c['archived'] for c in baseline.values()): raise FileNotFoundError('selected chapter unavailable')
        if len(canonical(baseline).encode()) > MAX_SNAPSHOT: raise ValueError('FORK_SNAPSHOT_SIZE_LIMIT')
        refs = NovelService._asset_references(baseline)
        if any(NovelService._asset_references(node) for chapter in baseline.values() for _, node, _ in lock_nodes(chapter['document'])):
            raise ValueError('FORK_LOCKED_ASSET_MAPPING_UNSUPPORTED')
        if len(refs) > 100: raise ValueError('FORK_ASSET_COUNT_LIMIT')
        declarations = {a.asset_id: a for a in value.asset_permissions}
        if len(declarations) != len(value.asset_permissions) or set(declarations) != set(refs): raise ValueError('FORK_EXPLICIT_ASSET_LICENSE_REQUIRED')
        assets = {}
        for aid in refs:
            meta, _ = self._asset(ctx, aid); declaration = declarations[aid]
            if meta['version'] != declaration.version or meta['sha256'] != declaration.sha256: raise StaleSourceError('FORK_ASSET_CHANGED')
            if declaration.license.upper() in {'UNKNOWN', 'UNSPECIFIED', 'NONE'}: raise ValueError('FORK_EXPLICIT_ASSET_LICENSE_REQUIRED')
            assets[aid] = {**meta, 'license': declaration.license, 'license_verification': 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION'}
            if sum(a['size'] for a in assets.values()) > MAX_ASSETS_TOTAL: raise ValueError('FORK_TOTAL_ASSET_SIZE_LIMIT')
        snapshot = digest([baseline, assets, value.title]); reauthorize()
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'status': 'PREFLIGHT', 'title': value.title, 'baseline': baseline, 'assets': assets,
            'preview_digest': snapshot, 'target_id': 'fork-' + uuid4().hex, 'id_map': {'chapters': {}, 'assets': {}}, 'journal': []})
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            reauthorize(); self._assert_baseline(ctx, row)
            if len(state['collections'].get(self.FORKS, {})) >= 100: raise ValueError('FORK_RECORD_LIMIT')
            state['collections'].setdefault(self.FORKS, {})[row['id']] = row
        return self._summary(row)

    def _assert_baseline(self, ctx, row):
        if any(self._chapter(ctx, cid) != chapter for cid, chapter in row['baseline'].items()): raise StaleSourceError('FORK_SOURCE_CHANGED')
        for aid, expected in row['assets'].items():
            actual, _ = self._asset(ctx, aid)
            if any(actual[k] != expected[k] for k in actual): raise StaleSourceError('FORK_ASSET_CHANGED')

    def _change(self, ctx, collection, rid, callback):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = state['collections'][collection][rid]
            advance(row, ctx.actor, row['version'], callback)

    def _step(self, ctx, collection, rid, kind, target, fn, reauthorize, *, expected_version=None):
        reauthorize(); index = len(self.get(ctx.novel_id, ctx.scope, collection, rid)['journal'])
        entry = {'index': index, 'kind': kind, 'target': target, 'expected_version': expected_version, 'status': 'CLAIMED'}
        self._change(ctx, collection, rid, lambda r: (r.update(status='APPLYING'), r['journal'].append(entry)))
        # The already committed CLAIMED entry survives a crash. Holding the
        # metadata owner's lock while issuing one original CAS prevents a
        # concurrent checkpoint restore from overtaking an active writer. This
        # is still not an atomic transaction across the two authorities.
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            reauthorize(); result = fn()
            receipt = {'status': 'ACKNOWLEDGED' if collection == self.MERGES else 'DONE'}
            if isinstance(result, dict):
                receipt.update(result_id=result.get('id'), result_version=result.get('version'))
            row = state['collections'][collection][rid]
            advance(row, ctx.actor, row['version'], lambda r: r['journal'][index].update(receipt))
        return result

    def create_fork(self, ctx, rid, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = ConfirmIn.model_validate(body); row = self._owned(ctx, self.FORKS, rid); check_version(row, value.expected_version)
        if row['status'] != 'PREFLIGHT' or row['preview_digest'] != value.preview_digest: raise ValueError('FORK_CONFIRMATION_CHANGED')
        self._assert_baseline(ctx, row); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.FORKS][rid]
            advance(current, ctx.actor, value.expected_version, lambda r: r.update(status='CLAIMED')); reauthorize(); self._assert_baseline(ctx, row)
        try:
            guard = lambda: (reauthorize(), self._assert_baseline(ctx, row))
            self._step(ctx, self.FORKS, rid, 'CREATE_PROJECT', row['target_id'], lambda: self.novels.create({'id': row['target_id'], 'title': row['title'], 'genre': 'Reviewed project fork'}), guard)
            target_authorize(row['target_id']); mapping = {}
            for aid, expected in row['assets'].items():
                _, content = self._asset(ctx, aid)
                created = self._step(ctx, self.FORKS, rid, 'COPY_ASSET', aid,
                    lambda: self.assets.create(row['target_id'], expected['filename'], base64.b64encode(content).decode(), expected['media_type'], expected['kind'],
                        'fork:' + rid + ':' + aid, required_features=(FEATURE,), owner_actor_id=ctx.actor), lambda: (guard(), target_authorize(row['target_id'])))
                mapping[aid] = created['id']
                self._change(ctx, self.FORKS, rid, lambda r: r['id_map']['assets'].update({aid: created['id']}))
                self._step(ctx, self.FORKS, rid, 'PROMOTE_ASSET', created['id'], lambda: self.assets.promote_owned(created['id'], actor_id=ctx.actor, branch_id=None,
                    expected_version=created['version'], provenance={'project_fork_id': rid, 'source_project_id': ctx.novel_id, 'source_asset_id': aid,
                        'source_version': expected['version'], 'source_sha256': expected['sha256'], 'license': expected['license'],
                        'license_verification': 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION'}, guard=lambda: (guard(), target_authorize(row['target_id']))), lambda: (guard(), target_authorize(row['target_id'])))
            for number, (cid, chapter) in enumerate(row['baseline'].items(), 1):
                target_cid = f"{row['target_id']}:{number}"
                self._change(ctx, self.FORKS, rid, lambda r: r['id_map']['chapters'].update({cid: target_cid}))
                self._step(ctx, self.FORKS, rid, 'CREATE_CHAPTER', target_cid, lambda: self._create_chapter(ctx, row['target_id'], number, chapter['title']), lambda: (guard(), target_authorize(row['target_id'])))
                current = self.chapters.get(target_cid); doc = rich_document(chapter['document'], mapping)
                self._step(ctx, self.FORKS, rid, 'COPY_DOCUMENT', target_cid, lambda: self.chapters.save(target_cid, {'version': current['version'], 'document': doc, 'source': 'PROJECT_FORK_COPY'}),
                    lambda: (guard(), target_authorize(row['target_id'])), expected_version=current['version'])
            guard(); target_authorize(row['target_id'])
            target_ctx = self._target_ctx(ctx, row)
            asset_versions = {old: self._asset(target_ctx, new)[0] for old, new in mapping.items()}
            self._change(ctx, self.FORKS, rid, lambda r: r.update(status='FORKED', target_assets=asset_versions))
            return self._summary(self._owned(ctx, self.FORKS, rid))
        except Exception:
            self._change(ctx, self.FORKS, rid, lambda r: r.update(status='RECOVERY_REQUIRED', error_code='FORK_PARTIAL_NEW_PROJECT_NO_AUTOMATIC_RETRY'))
            raise

    def _current(self, ctx, row, target_authorize):
        target_authorize(row['target_id']); target_ctx = self._target_ctx(ctx, row)
        self.novels.get(row['target_id'])
        for old, expected in row.get('target_assets', {}).items():
            actual, _ = self._asset(target_ctx, expected['id'])
            if actual != expected: raise StaleSourceError('FORK_TARGET_ASSET_CHANGED')
            source, _ = self._asset(ctx, old)
            if source['sha256'] != row['assets'][old]['sha256'] or source['version'] != row['assets'][old]['version']: raise StaleSourceError('FORK_SOURCE_ASSET_CHANGED')
        original = {cid: self._chapter(ctx, cid) for cid in row['baseline']}
        fork = {cid: self._chapter(target_ctx, new) for cid, new in row['id_map']['chapters'].items()}
        reverse = {new: old for old, new in row['id_map']['assets'].items()}
        for chapter in fork.values():
            if chapter: chapter['document'] = rich_document(chapter['document'], reverse)
        if len(canonical(original).encode()) > MAX_SNAPSHOT or len(canonical(fork).encode()) > MAX_SNAPSHOT: raise ValueError('FORK_SNAPSHOT_SIZE_LIMIT')
        return original, fork

    def _comparison(self, row, original, fork, choices):
        chapters = []; used = set(); desired = {}; conflicts = 0
        for cid, base in row['baseline'].items():
            left, right = original[cid], fork[cid]
            left_live = bool(left and not left['archived']); right_live = bool(right and not right['archived'])
            result = {'chapter_id': cid, 'fork_chapter_id': row['id_map']['chapters'][cid], 'title': (left or base)['title'],
                      'original_version': left['version'] if left else None, 'fork_version': right['version'] if right else None, 'segments': []}
            if not left_live or not right_live:
                # A disappeared/archived chapter is always a deliberate choice,
                # even when its opposite stayed at baseline. Never auto-delete.
                key = digest([cid, 'CHAPTER_DELETION', base, left, right]); chosen = choices.get(key); used.add(key)
                result['segments'] = [{'id': key, 'kind': 'CONFLICT', 'reason': 'CHAPTER_DELETION_OR_DELETE_MODIFY',
                    'base': base['document']['content'], 'ORIGINAL': left['document']['content'] if left_live else [],
                    'FORK': right['document']['content'] if right_live else [], 'choice': chosen}]
                if not chosen: conflicts += 1
                if chosen == 'FORK':
                    if left is None and right_live: raise ValueError('FORK_PERMANENTLY_DELETED_TARGET_RESTORE_ADAPTER_REQUIRED')
                    desired[cid] = None if not right_live else {**left, 'archived': False, 'document': right['document']}
                else: desired[cid] = left
            else:
                # Chapter title is the original repository's first heading, so
                # rename and body edits share one rich-document CAS, not two.
                segments = block_merge(base['document'].get('content', []), left['document'].get('content', []), right['document'].get('content', [])); nodes = []
                for index, segment in enumerate(segments):
                    if segment['kind'] == 'UNCHANGED': nodes.extend(segment['nodes']); continue
                    key = digest([cid, index, segment]); segment['id'] = key
                    if segment['kind'] == 'CONFLICT':
                        used.add(key); chosen = choices.get(key); segment['choice'] = chosen
                        segment['reason'] = 'RENAME_OR_HEADING' if any(n.get('type') == 'heading' for n in segment['base'] + segment['ORIGINAL'] + segment['FORK']) else 'RICH_BLOCK_OVERLAP'
                        if not chosen: conflicts += 1
                        nodes.extend(segment[chosen or 'ORIGINAL'])
                    else: nodes.extend(segment['FORK'] if segment['kind'] in {'FORK_ONLY', 'BOTH_SAME'} else segment['ORIGINAL'])
                    result['segments'].append(segment)
                document = {**deepcopy(left['document']), 'content': deepcopy(nodes)}
                rich_document(document)
                desired[cid] = {**left, 'document': document}
            chapters.append(result)
        if set(choices) - used: raise ValueError('FORK_UNKNOWN_OR_STALE_CONFLICT_CHOICE')
        return chapters, desired, conflicts

    def compare(self, ctx, rid, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = CompareIn.model_validate(body); row = self._owned(ctx, self.FORKS, rid); check_version(row, value.expected_version)
        if row['status'] != 'FORKED': raise ValueError('FORK_NOT_READY_OR_RECOVERY_REQUIRED')
        if row.get('active_merge'):
            previous = self._owned(ctx, self.MERGES, row['active_merge'])
            if previous['status'] not in {'COMPLETED', 'RESTORED'}: raise ValueError('FORK_MERGE_RECOVERY_REQUIRED')
        original, fork = self._current(ctx, row, target_authorize)
        chapters, desired, conflicts = self._comparison(row, original, fork, value.choices)
        blocked = []
        for cid, after in desired.items():
            before = original[cid]
            if before and after is None:
                try: assert_ai_locks(before['document'], {'type': 'doc', 'content': []})
                except Exception: blocked.append({'chapter_id': cid, 'code': 'FORK_LOCKED_CHAPTER_ARCHIVE'})
            elif before and after:
                try: assert_ai_locks(before['document'], after['document'])
                except Exception: blocked.append({'chapter_id': cid, 'code': 'FORK_LOCKED_PARAGRAPH_CHANGE'})
        reauthorize(); target_authorize(row['target_id'])
        return {'fork_id': rid, 'expected_version': row['version'], 'preview_digest': digest([rid, row['version'], original, fork, value.choices, desired]),
                'chapters': chapters, 'unresolved': conflicts, 'blocked': blocked, 'can_apply': not conflicts and not blocked,
                'write_count': sum(after != original[cid] for cid, after in desired.items()), 'limitations': LIMITS}

    def _plan(self, ctx, row, original, desired, kind, fork_snapshot=None, checkpoint_id=None):
        return new_row(ctx.novel_id, ctx.scope, ctx.actor, {'status': 'CLAIMED', 'kind': kind, 'fork_id': row['id'], 'target_id': row['target_id'],
            'checkpoint_id': checkpoint_id, 'checkpoint': deepcopy(original), 'expected': deepcopy(original), 'desired': deepcopy(desired),
            'fork_snapshot': deepcopy(fork_snapshot), 'journal': []})

    def _execute(self, ctx, row, plan, reauthorize, target_authorize, save_document, archive_chapter, restore_archive):
        pid = plan['id']
        def guard():
            reauthorize()
            if plan['kind'] == 'MERGE': target_authorize(row['target_id'])
            current_plan = self._owned(ctx, self.MERGES, pid)
            current_fork = self._owned(ctx, self.FORKS, row['id'])
            if current_fork.get('active_merge') != pid or current_plan['status'] not in {'CLAIMED', 'APPLYING'}: raise ValueError('FORK_WRITER_SUPERSEDED_BY_RECOVERY')
            if any(self._chapter(ctx, cid) != expected for cid, expected in current_plan['expected'].items()): raise StaleSourceError('FORK_ORIGINAL_CHANGED_DURING_APPLY')
            if plan['kind'] == 'MERGE':
                _, fork = self._current(ctx, row, target_authorize)
                if fork != plan['fork_snapshot']: raise StaleSourceError('FORK_SOURCE_CHANGED_DURING_APPLY')
        try:
            for cid, desired in plan['desired'].items():
                before = self._owned(ctx, self.MERGES, pid)['expected'][cid]
                if desired == before: continue
                if before is None: raise ValueError('FORK_MISSING_TARGET_REQUIRES_ORIGINAL_RESTORE')
                if desired is None:
                    if before['archived']: continue
                    assert_ai_locks(before['document'], {'type': 'doc', 'content': []})
                    callback, kind = lambda: archive_chapter(cid, before['version']), 'ARCHIVE'
                elif desired['document'] != before['document']:
                    assert_ai_locks(before['document'], desired['document'])
                    callback, kind = lambda: save_document(cid, deepcopy(desired['document']), before['version'], 'PROJECT_FORK_MERGE' if plan['kind'] == 'MERGE' else 'PROJECT_FORK_RESTORE'), 'SAVE_DOCUMENT'
                elif desired['archived'] != before['archived']:
                    callback, kind = (lambda: archive_chapter(cid, before['version']), 'ARCHIVE') if desired['archived'] else (lambda: restore_archive(cid, before['version']), 'RESTORE_ARCHIVE')
                else: continue
                self._step(ctx, self.MERGES, pid, kind, cid, callback, guard, expected_version=before['version'])
                actual = self._chapter(ctx, cid)
                # An acknowledgement is not proof that the intended write won.
                if not actual or actual['version'] not in ({before['version'] + 1} if kind == 'SAVE_DOCUMENT' else self._archive_receipt_versions(before['version'])): raise StaleSourceError('FORK_WRITE_RECEIPT_UNCERTAIN')
                if kind == 'SAVE_DOCUMENT' and actual['document'] != desired['document']: raise StaleSourceError('FORK_WRITE_DOCUMENT_UNCERTAIN')
                if kind in {'ARCHIVE', 'RESTORE_ARCHIVE'} and (actual['archived'] != (kind == 'ARCHIVE') or actual['document'] != before['document']): raise StaleSourceError('FORK_WRITE_STATE_UNCERTAIN')
                self._change(ctx, self.MERGES, pid, lambda p: (p['expected'].update({cid: actual}), p['journal'][-1].update(status='DONE', result_version=actual['version'], result_digest=digest(actual))))
                # Restore of an archived chapter may require a second original
                # CAS after restoring its document. Both have separate claims.
                if desired and actual['archived'] != desired['archived']:
                    before = actual
                    kind = 'ARCHIVE' if desired['archived'] else 'RESTORE_ARCHIVE'
                    self._step(ctx, self.MERGES, pid, kind, cid, lambda: (archive_chapter if desired['archived'] else restore_archive)(cid, before['version']), guard, expected_version=before['version'])
                    actual = self._chapter(ctx, cid)
                    if not actual or actual['version'] not in self._archive_receipt_versions(before['version']) or actual['archived'] != desired['archived'] or actual['document'] != before['document']: raise StaleSourceError('FORK_WRITE_STATE_UNCERTAIN')
                    self._change(ctx, self.MERGES, pid, lambda p: (p['expected'].update({cid: actual}), p['journal'][-1].update(status='DONE', result_version=actual['version'], result_digest=digest(actual))))
            guard()
            self._change(ctx, self.MERGES, pid, lambda p: p.update(status='COMPLETED' if plan['kind'] == 'MERGE' else 'RESTORED'))
            if plan.get('checkpoint_id'):
                self._change(ctx, self.MERGES, plan['checkpoint_id'], lambda p: p.update(status='RESTORED', restored_by=pid))
            return self._summary(self._owned(ctx, self.MERGES, pid))
        except Exception:
            current = self._owned(ctx, self.MERGES, pid)
            if current['status'] in {'CLAIMED', 'APPLYING'}:
                self._change(ctx, self.MERGES, pid, lambda p: p.update(status='RECOVERY_REQUIRED', error_code='FORK_PARTIAL_OR_UNKNOWN_NO_AUTOMATIC_RETRY'))
            raise

    def apply(self, ctx, rid, body, reauthorize=lambda: None, target_authorize=lambda nid: None, *, save_document=None, archive_chapter=None, restore_archive=None):
        if not all((save_document, archive_chapter, restore_archive)): raise ValueError('FORK_ORIGINAL_WRITER_REQUIRED')
        value = ApplyIn.model_validate(body)
        comparison = self.compare(ctx, rid, CompareIn(expected_version=value.expected_version, choices=value.choices), reauthorize, target_authorize)
        if comparison['preview_digest'] != value.preview_digest: raise StaleSourceError('FORK_PREVIEW_CHANGED')
        if not comparison['can_apply']: raise ValueError('FORK_CONFLICTS_OR_LOCKS_UNRESOLVED')
        row = self._owned(ctx, self.FORKS, rid); original, fork = self._current(ctx, row, target_authorize)
        _, desired, _ = self._comparison(row, original, fork, value.choices)
        if digest([rid, row['version'], original, fork, value.choices, desired]) != value.preview_digest: raise StaleSourceError('FORK_PREVIEW_CHANGED')
        plan = self._plan(ctx, row, original, desired, 'MERGE', fork)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.FORKS][rid]; check_version(current, value.expected_version)
            reauthorize(); target_authorize(row['target_id'])
            state['collections'].setdefault(self.MERGES, {})[plan['id']] = plan
            advance(current, ctx.actor, value.expected_version, lambda r: r.update(active_merge=plan['id']))
        return self._execute(ctx, row, plan, reauthorize, target_authorize, save_document, archive_chapter, restore_archive)

    def recovery(self, ctx, mid, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = VersionIn.model_validate(body); plan = self._owned(ctx, self.MERGES, mid); check_version(plan, value.expected_version)
        self._owned(ctx, self.FORKS, plan['fork_id'])
        # Recovery's source is the original project's own checkpoint. It does
        # not read fork prose and must remain possible if that fork was lost.
        current = {cid: self._chapter(ctx, cid) for cid in plan['checkpoint']}
        observed = []
        for cid, before in plan['checkpoint'].items():
            live = current[cid]; expected = plan['expected'][cid]; wanted = plan['desired'][cid]
            state = 'CHECKPOINT_UNCHANGED' if live == before else 'CONFIRMED_RECEIPT' if live == expected else 'UNKNOWN_OR_NEWER'
            if state == 'UNKNOWN_OR_NEWER' and live and wanted and live['document'] == wanted['document'] and live['archived'] == wanted['archived']: state = 'MATCHES_INTENT_UNCONFIRMED'
            observed.append({'chapter_id': cid, 'checkpoint_version': before['version'] if before else None, 'current_version': live['version'] if live else None, 'state': state})
        reauthorize()
        # Fresh explicit review can restore the checkpoint even after an unknown
        # receipt; it never retries the original merge. Permanent deletion and
        # active locks still require the original editor's recovery flow.
        blocked = []
        for cid, before in plan['checkpoint'].items():
            if before is None or current[cid] is None: blocked.append('FORK_MISSING_TARGET_REQUIRES_ORIGINAL_RESTORE'); continue
            try: assert_ai_locks(current[cid]['document'], before['document'])
            except Exception: blocked.append('FORK_LOCKED_PARAGRAPH_CHANGE')
        return {'id': mid, 'expected_version': plan['version'], 'status': plan['status'], 'observations': observed,
            'checkpoint': deepcopy(plan['checkpoint']), 'current': current, 'journal': deepcopy(plan['journal']),
            'preview_digest': digest([mid, plan['version'], current, plan['checkpoint']]), 'can_restore': not blocked and plan['status'] != 'RESTORED',
            'blocked': blocked, 'no_automatic_retry': True}

    def restore_checkpoint(self, ctx, mid, body, reauthorize=lambda: None, target_authorize=lambda nid: None, *, save_document=None, archive_chapter=None, restore_archive=None):
        if not all((save_document, archive_chapter, restore_archive)): raise ValueError('FORK_ORIGINAL_WRITER_REQUIRED')
        value = ConfirmIn.model_validate(body); preview = self.recovery(ctx, mid, VersionIn(expected_version=value.expected_version), reauthorize, target_authorize)
        if preview['preview_digest'] != value.preview_digest: raise StaleSourceError('FORK_RECOVERY_PREVIEW_CHANGED')
        if not preview['can_restore']: raise ValueError('FORK_CHECKPOINT_RESTORE_BLOCKED')
        old = self._owned(ctx, self.MERGES, mid); row = self._owned(ctx, self.FORKS, old['fork_id'])
        if row.get('active_merge') != mid: raise ValueError('FORK_ONLY_CURRENT_MERGE_CAN_RESTORE')
        desired = {cid: {**preview['current'][cid], 'document': before['document'], 'archived': before['archived']} for cid, before in old['checkpoint'].items()}
        plan = self._plan(ctx, row, preview['current'], desired, 'CHECKPOINT_RESTORE', checkpoint_id=mid)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            reauthorize(); current = state['collections'][self.MERGES][mid]; check_version(current, value.expected_version)
            current_fork = state['collections'][self.FORKS][row['id']]
            if current_fork.get('active_merge') != mid: raise ValueError('FORK_RECOVERY_ALREADY_CLAIMED')
            advance(current, ctx.actor, value.expected_version, lambda p: p.update(status='RESTORING_CHECKPOINT'))
            state['collections'][self.MERGES][plan['id']] = plan
            advance(current_fork, ctx.actor, current_fork['version'], lambda r: r.update(active_merge=plan['id']))
        return self._execute(ctx, row, plan, reauthorize, target_authorize, save_document, archive_chapter, restore_archive)
