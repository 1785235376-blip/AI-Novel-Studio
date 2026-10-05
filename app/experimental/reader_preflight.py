"""U11 local deterministic reading and publication checks; no manuscript writes.

All coordinates are exact editor Unicode codepoints. Author-owned annotation,
rule and ignore metadata use the existing isolated, scope-atomic store. The
original export queue continues to capture and render its own frozen snapshot.
"""
from __future__ import annotations
import re
from typing import Literal
from pydantic import Field
from .common import DomainService, StaleSourceError, change_row, new_row
from .planning import StrictModel, digest
from .ux import chapter_text
from .reader_sources import authorized_chapter_rows, chapter_revision
from ..services.novel_service import NovelService
from ..services.export_resource_snapshot import capture_asset
from ..services.v1_capability_service import CapabilityVersionConflict

MAX_CHAPTERS, MAX_TEXT, MAX_FINDINGS = 200, 2_000_000, 300


class LiteralRule(StrictModel):
    kind: Literal['naming', 'replacement'] = 'replacement'
    find: str = Field(min_length=1, max_length=80)
    suggest: str = Field(max_length=80)


class ProofRules(StrictModel):
    punctuation: bool = True
    repeated_words: bool = True
    literals: list[LiteralRule] = Field(default_factory=list, max_length=30)


class SettingsIn(StrictModel):
    expected_version: int = Field(ge=0)
    rules: ProofRules = Field(default_factory=ProofRules)
    license_declaration: str = Field(default='', max_length=2000)
    font_declaration: str = Field(default='', max_length=1000)


class AnchorIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    offset: int = Field(ge=0, le=MAX_TEXT)
    quote: str = Field(max_length=2000)


class AnnotationIn(AnchorIn):
    expected_version: int = Field(ge=0)
    note: str = Field(min_length=1, max_length=2000)


class IgnoreIn(StrictModel):
    expected_version: int = Field(ge=0)
    finding_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    reason: str = Field(min_length=1, max_length=1000)


class DraftStatus(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)
    state: Literal['SAVED', 'UNSAVED', 'LOCAL_DRAFT', 'SAVE_FAILED', 'UNKNOWN']


class PreflightIn(StrictModel):
    format: Literal['txt', 'markdown', 'docx', 'epub', 'pdf'] = 'docx'
    draft_status: list[DraftStatus] = Field(default_factory=list, max_length=MAX_CHAPTERS)


class ReaderPreflightService(DomainService):
    SETTINGS = 'reader_preflight_settings_v2'

    def __init__(self, store, novels, chapters, *, sources, assets=None, task_reader=None, candidate_reader=None):
        super().__init__(store, novels, chapters)
        self.sources, self.assets = sources, assets
        self.task_reader, self.candidate_reader = task_reader, candidate_reader

    def _rows(self, ctx):
        rows = authorized_chapter_rows(ctx, self.sources, self.chapters)
        if len(rows) > MAX_CHAPTERS or sum(len(chapter_text(r)) for r in rows) > MAX_TEXT or sum(chapter_text(r).count('\n') + 1 for r in rows) > 10000:
            raise ValueError('reading limit exceeded: select a smaller project (200 chapters / 2,000,000 characters / 10,000 paragraphs)')
        return rows

    def _row(self, ctx, state=None):
        self.novels.get(ctx.novel_id)
        state = state if state is not None else self.store.read(ctx.novel_id, ctx.scope)
        row = state['collections'].get(self.SETTINGS, {}).get(self.sources._owner(ctx.actor))
        if row and (row.get('created_by') != ctx.actor or row.get('scope') != ctx.scope or row.get('novel_id') != ctx.novel_id):
            raise ValueError('reader metadata scope invalid')
        return row

    def settings(self, ctx):
        row = self._row(ctx)
        return {'version': row['version'] if row else 0, 'rules': ProofRules.model_validate((row or {}).get('rules', {})).model_dump(),
                'license_declaration': (row or {}).get('license_declaration', ''), 'font_declaration': (row or {}).get('font_declaration', '')}

    def _mutate(self, ctx, version, update, reauthorize):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._row(ctx, state)
            if (row['version'] if row else 0) != version:
                raise CapabilityVersionConflict(self.settings(ctx))
            if not row:
                row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'rules': ProofRules().model_dump(), 'annotations': [], 'ignores': {}, 'status': 'ACTIVE'})
                update(row); reauthorize()
                state['collections'].setdefault(self.SETTINGS, {})[self.sources._owner(ctx.actor)] = row
            else:
                change_row(row, ctx.actor, version, update); reauthorize()
            return self.settings(ctx)

    def save_settings(self, ctx, body, reauthorize=lambda: None):
        data = SettingsIn.model_validate(body).model_dump(); version = data.pop('expected_version')
        return self._mutate(ctx, version, lambda row: row.update(data), reauthorize)

    def _anchor(self, ctx, body):
        value = AnchorIn.model_validate(body)
        row = next((r for r in self._rows(ctx) if r['id'] == value.chapter_id), None)
        if row is None: raise FileNotFoundError(value.chapter_id)
        text = chapter_text(row)
        if chapter_revision(row) != value.revision or value.offset > len(text) or text[value.offset:value.offset + len(value.quote)] != value.quote:
            raise StaleSourceError('source or quote changed; reread before opening or annotating')
        return row

    def open_anchor(self, ctx, body):
        value = AnchorIn.model_validate(body); row = self._anchor(ctx, value)
        return {'kind': 'chapter', 'id': row['id'], 'version': row['version'], 'anchor': {'offset': value.offset, 'scroll': 0},
                'coordinate': 'EDITOR_TEXT_CODEPOINT', 'stale': False}

    def annotate(self, ctx, body, reauthorize=lambda: None):
        data = AnnotationIn.model_validate(body).model_dump(); version = data.pop('expected_version')
        if not data['note'].strip(): raise ValueError('annotation required')
        def update(row):
            self._anchor(ctx, {k: data[k] for k in ('chapter_id', 'revision', 'offset', 'quote')})
            if len(row.get('annotations', [])) >= 300: raise ValueError('annotation limit reached')
            if not any(item['id'] == digest(data) for item in row.get('annotations', [])):
                row.setdefault('annotations', []).append({**data, 'id': digest(data)})
        return self._mutate(ctx, version, update, reauthorize)

    def read(self, ctx):
        rows = self._rows(ctx); metadata = self._row(ctx) or {}; chapters = []
        for row in rows:
            text, offset, paragraphs = chapter_text(row), 0, []
            for index, paragraph in enumerate(text.split('\n')):
                paragraphs.append({'index': index, 'offset': offset, 'text': paragraph}); offset += len(paragraph) + 1
            chapters.append({'id': row['id'], 'title': row.get('title', ''), 'version': row['version'], 'revision': chapter_revision(row), 'paragraphs': paragraphs})
        visible = {r['id']: r for r in rows}; annotations = []
        for item in metadata.get('annotations', []):
            source = visible.get(item['chapter_id'])
            if source is None: continue  # no deleted/private source evidence or counts
            stale = chapter_revision(source) != item['revision']
            annotations.append({**item, 'note': item['note'], 'quote': '' if stale else item['quote'], 'stale': stale})
        return {'chapters': chapters, 'annotations': annotations, 'source_digest': digest([[r['id'], chapter_revision(r)] for r in rows]),
                'branch_sources_available': ctx.scope['mode'] == 'local' or bool(self.sources.chapter_reader),
                'rendering': 'APP_LAYOUT_SIMULATION', 'target_renderer_verified': False, 'read_only': True}

    def proof(self, ctx):
        settings = self.settings(ctx); rules = settings['rules']; findings = []; more = False
        ignores = (self._row(ctx) or {}).get('ignores', {})
        for row in self._rows(ctx):
            text = chapter_text(row); revision = chapter_revision(row)
            checks = []
            if rules['punctuation']: checks.append(('punctuation', r'[，。！？,!?]{2,}', '核对连续标点是否有意使用。', None))
            if rules['repeated_words']: checks.append(('repeated_words', r'\b([A-Za-z]{2,})\s+\1\b', '核对重复词；可能是有意强调。', None))
            checks += [(item['kind'], re.escape(item['find']), f"作者规则建议：{item['suggest']}", item['suggest']) for item in rules['literals']]
            for kind, pattern, explanation, suggestion in checks:
                for match in re.finditer(pattern, text, re.IGNORECASE if kind == 'repeated_words' else 0):
                    if len(findings) >= MAX_FINDINGS: more = True; break
                    quote = match.group()[:2000]
                    data = {'chapter_id': row['id'], 'revision': revision, 'offset': match.start(), 'quote': quote,
                            'paragraph': text[:match.start()].count('\n'), 'kind': kind, 'explanation': explanation, 'suggestion': suggestion, 'severity': 'ADVICE'}
                    fid = digest(data); findings.append({**data, 'id': fid, 'ignored_reason': ignores.get(fid)})
        return {'items': findings, 'truncated': more, 'method': 'BOUNDED_LITERAL_RULES_V1', 'automatic_edits': False}

    def ignore(self, ctx, body, reauthorize=lambda: None):
        value = IgnoreIn.model_validate(body)
        if not value.reason.strip(): raise ValueError('ignore reason required')
        def update(row):
            finding = next((x for x in self.proof(ctx)['items'] if x['id'] == value.finding_id), None)
            if finding is None: raise StaleSourceError('finding changed; rerun proofreading')
            ignored = row.setdefault('ignores', {})
            if len(ignored) >= 600 and value.finding_id not in ignored: raise ValueError('ignore limit reached')
            ignored[value.finding_id] = value.reason
        return self._mutate(ctx, value.expected_version, update, reauthorize)

    def preflight(self, ctx, body):
        value = PreflightIn.model_validate(body); rows = self._rows(ctx); by_id = {r['id']: r for r in rows}
        settings = self.settings(ctx); findings = []; coverage = []
        def add(code, level, message, feature='exports', chapter_id=None):
            findings.append({'code': code, 'severity': level, 'message': message, 'feature': feature, 'chapter_id': chapter_id})
        for item in value.draft_status:
            row = by_id.get(item.chapter_id)
            if not row: raise FileNotFoundError(item.chapter_id)
            state = item.state if row['version'] == item.chapter_version else 'UNKNOWN'
            if state != 'SAVED': add('LOCAL_' + state, 'WARNING', '客户端报告有未保存、恢复草稿、保存失败或无法核实状态。', 'editor', item.chapter_id)
        coverage.append({'area': 'local_drafts', 'state': 'CLIENT_REPORTED' if value.draft_status else 'UNKNOWN'})
        for row in rows:
            document = row.get('document')
            body_row = row
            if isinstance(document, dict) and document.get('content') and document['content'][0].get('type') == 'heading':
                body_row = {**row, 'document': {**document, 'content': document['content'][1:]}}
            if not chapter_text(body_row).strip(): add('EMPTY_CHAPTER', 'WARNING', '章节正文为空。', 'editor', row['id'])
        if not rows: add('NO_CHAPTERS', 'BLOCKER', '没有可导出的已授权章节。', 'editor')
        if ctx.scope['mode'] != 'local' and not self.sources.chapter_reader:
            add('BRANCH_SOURCE_UNAVAILABLE', 'BLOCKER', '当前分支章节适配器不可用；不会借用主分支。', 'editor')
        # Reuse export reference discovery and its byte/digest validator, but
        # only over already-authorized chapters. No raw paths or bytes leave.
        refs = NovelService._asset_references(rows)
        if len(refs) > 100: raise ValueError('media validation limit exceeded (100 references)')
        media_bytes = 0; media_partial = False
        for asset_id in refs:
            try:
                if self.assets is None: raise FileNotFoundError()
                asset = self.assets.get(asset_id, branch_id=ctx.scope.get('branch_id'))
                if asset.get('novel_id') != ctx.novel_id or asset.get('branch_id') != ctx.scope.get('branch_id') or asset.get('hidden') or asset.get('secret'):
                    raise FileNotFoundError()
                if type(asset.get('size')) is not int or asset['size'] < 0:
                    raise ValueError('invalid media size')
                if media_bytes + asset['size'] > 32 * 1024 * 1024:
                    media_partial = True
                    add('MEDIA_CHECK_LIMIT', 'WARNING', '本轮媒体读取已达 32 MiB 上限；部分引用未验证，请到原资产入口核对。', 'assets')
                    continue
                media_bytes += asset['size']
                capture_asset(asset, self.assets.content(asset_id, branch_id=ctx.scope.get('branch_id')), asset_id=asset_id, novel_id=ctx.novel_id, branch_id=ctx.scope.get('branch_id'))
            except (FileNotFoundError, OSError, ValueError):
                add('MISSING_MEDIA', 'BLOCKER', '正文引用的图片或音频缺失、不可访问或完整性校验失败。', 'assets')
        coverage.append({'area': 'media', 'state': 'PARTIAL_BYTE_LIMIT' if media_partial else 'AUTHORIZED_CHAPTER_REFERENCES_ONLY'})
        if not settings['font_declaration'].strip(): add('FONT_UNDECLARED', 'WARNING', '尚未声明字体来源；实际格式字体覆盖需在原导出中心核验。')
        if not settings['license_declaration'].strip(): add('LICENSE_UNDECLARED', 'WARNING', '尚未填写正文与素材的许可声明；本检查不作法律判断。')
        if value.format == 'pdf':
            from ..pdf_export import pdf_font_status
            font = pdf_font_status()
            if not font.get('available'): add('PDF_FONT_UNAVAILABLE', 'BLOCKER', '原 PDF 导出器没有可用字体，当前无法生成完整 PDF。')
            elif not font.get('embedded'): add('PDF_FONT_NOT_EMBEDDED', 'WARNING', '原 PDF 导出器目前使用未嵌入的 CID 字体；跨设备字形、搜索和显示仍需实际文件验证。')
            coverage.append({'area': 'pdf_font', 'state': 'EMBEDDED' if font.get('embedded') else 'FALLBACK' if font.get('available') else 'UNAVAILABLE'})
        else:
            coverage.append({'area': 'target_font_rendering', 'state': 'NOT_VERIFIED'})
        add('FORMAT_LIMITS', 'INFO', f'{value.format.upper()} 使用原导出器；软件内预览不是 Word/EPUB/PDF 实际渲染验证。')
        for annotation in self.read(ctx)['annotations']:
            if annotation['stale']: add('STALE_ANNOTATION', 'WARNING', '阅读注释引用已过期，请重读当前段落。', 'editor', annotation['chapter_id'])
        if self.task_reader:
            result = self.task_reader(ctx)
            for task in result.get('items', []):
                if task.get('status') in {'FAILED', 'UNKNOWN'}: add('UNRESOLVED_TASK', 'WARNING', '原任务存在失败或未知结果，请在任务中心核对。', task['feature'])
                elif task.get('status') in {'REVIEW', 'AWAITING_REVIEW', 'PENDING_REVIEW', 'REVIEW_REQUIRED', 'RESULT_READY', 'PROPOSED'}:
                    add('UNACCEPTED_CANDIDATE', 'WARNING', '存在待审核候选；尚未成为已保存正文。', task['feature'])
                if task.get('stale'): add('STALE_REFERENCE', 'WARNING', '任务引用已过期，需回原入口复核。', task['feature'])
            coverage.append({'area': 'tasks', 'state': 'PARTIAL' if result.get('unavailable') or result.get('truncated') else 'AVAILABLE'})
        else: coverage.append({'area': 'tasks', 'state': 'UNKNOWN'})
        if self.candidate_reader:
            result = self.candidate_reader(ctx)
            for item in result.get('items', []):
                if item.get('chapter_id') not in by_id: continue
                add('UNACCEPTED_GENERATION', 'WARNING', '存在未接受的生成候选，正式导出不会包含候选正文。', 'creation', item['chapter_id'])
            coverage.append({'area': 'generation_candidates', 'state': 'PARTIAL' if result.get('truncated') else 'AVAILABLE'})
        else: coverage.append({'area': 'generation_candidates', 'state': 'UNKNOWN'})
        if digest([[r['id'], chapter_revision(r)] for r in rows]) != digest([[r['id'], chapter_revision(r)] for r in self._rows(ctx)]):
            raise StaleSourceError('manuscript changed during preflight; rerun the read-only check')
        return {'findings': findings, 'coverage': coverage, 'source_digest': digest([[r['id'], chapter_revision(r)] for r in rows]),
                'has_integrity_blockers': any(f['severity'] == 'BLOCKER' for f in findings), 'read_only': True, 'model_calls': 0,
                'export_snapshot_created': False, 'target_renderer_verified': False, 'checked_format': value.format}
