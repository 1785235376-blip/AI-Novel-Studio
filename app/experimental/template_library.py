"""B01 local declarative catalog, CAS install/diff/copy/update/revert.

Packages are bounded JSON data, never archives, downloads or executable plugins.
Built-ins reuse original planning/Workflow recipes. Project copies are independent
versioned data; uninstall never traverses into instances or user work.
"""
from __future__ import annotations

from copy import deepcopy
import difflib
import json
from typing import Literal

from pydantic import Field, model_validator

from .common import DomainService, StaleSourceError, change_row, check_version, new_row
from .declarative_agents import Strict, WorkflowAuthoring, default_definition
from .planning import BUILTIN_TEMPLATES, PlanningTemplateIn, collection, digest, require_row
from .store import canonical
from .safe_batch_contracts import BatchPreset
from ..services.v1_capability_service import CapabilityVersionConflict

FEATURE = 'template_library_v2'
LIMIT = 128000
TYPES = ('planning', 'character', 'screenplay', 'storyboard', 'review', 'workflow', 'safe_batch')
EXTENDED_TYPES = ('novel', 'genre', 'world', 'agent', 'story_structure')


class Compatibility(Strict):
    # Versioned data protocol, not an application-version or runtime claim.
    protocol: Literal['LOCAL_BOUNDED_JSON_V1'] = 'LOCAL_BOUNDED_JSON_V1'
    schema_versions: list[Literal[1]] = Field(default_factory=lambda: [1], min_length=1, max_length=1)
    import_mode: Literal['READ_ONLY_DECLARATION'] = 'READ_ONLY_DECLARATION'


class Permissions(Strict):
    execute: Literal[False] = False
    network: Literal[False] = False
    manuscript_write: Literal[False] = False
    grant_capabilities: Literal[False] = False
    executable_plugins: Literal['DENY_ALL'] = 'DENY_ALL'


class Manifest(Strict):
    id: str = Field(pattern=r'^[a-z][a-z0-9-]{1,79}$')
    version: str = Field(pattern=r'^[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}$')
    type: Literal['planning', 'character', 'screenplay', 'storyboard', 'review', 'workflow', 'safe_batch', 'novel', 'genre', 'world', 'agent', 'story_structure']
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=2000)
    author: str = Field(min_length=1, max_length=160)
    license: str = Field(min_length=1, max_length=160)
    dependencies: list[Literal['advanced_planning_v2', 'declarative_agents_v2', 'safe_batches_v2']] = Field(default_factory=list, max_length=3)
    provenance: str = Field(default='USER_SUPPLIED_DECLARATION', max_length=1000)
    compatibility: Compatibility = Field(default_factory=Compatibility)
    permissions: Permissions = Field(default_factory=Permissions)


class Section(Strict):
    key: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(max_length=8000)


class Brief(Strict):
    sections: list[Section] = Field(min_length=1, max_length=20)
    @model_validator(mode='after')
    def unique(self):
        if len({s.key for s in self.sections}) != len(self.sections): raise ValueError('duplicate section key')
        return self


class TemplatePackage(Strict):
    schema_version: Literal[1] = 1
    manifest: Manifest
    content: dict
    @model_validator(mode='after')
    def content_contract(self):
        typ = self.manifest.type
        model = PlanningTemplateIn if typ == 'planning' else WorkflowAuthoring if typ in {'workflow', 'agent'} else BatchPreset if typ == 'safe_batch' else Brief
        self.content = model.model_validate(self.content).model_dump()
        # Reject contradictory dependency claims; templates cannot enable them.
        dependency = {'planning': 'advanced_planning_v2', 'workflow': 'declarative_agents_v2', 'agent': 'declarative_agents_v2', 'safe_batch': 'safe_batches_v2'}.get(typ)
        if dependency and dependency not in self.manifest.dependencies:
            raise ValueError('missing declared template dependency: ' + dependency)
        if len(canonical(self.model_dump()).encode()) > LIMIT: raise ValueError('template exceeds 128000 bytes')
        return self


def parse_package(raw):
    if isinstance(raw, str):
        if len(raw.encode()) > LIMIT: raise ValueError('template exceeds 128000 bytes')
        # No decompression, HTML, SVG, path resolution, or remote fetch occurs.
        if not raw.lstrip().startswith('{'): raise ValueError('only bounded UTF-8 JSON catalog packages are supported; archives denied')
        try: raw = json.loads(raw)
        except (ValueError, RecursionError) as exc: raise ValueError('invalid template JSON') from exc
    def depth(value, level=0):
        if level > 15: raise ValueError('template nesting exceeds limit')
        if isinstance(value, dict):
            if len(value) > 150: raise ValueError('template object exceeds limit')
            for v in value.values(): depth(v, level + 1)
        elif isinstance(value, list):
            if len(value) > 150: raise ValueError('template list exceeds limit')
            for v in value: depth(v, level + 1)
    depth(raw)
    return TemplatePackage.model_validate(raw).model_dump()


def builtin_packages():
    result = []
    for key, value in BUILTIN_TEMPLATES.items():
        result.append({'schema_version': 1, 'manifest': {'id': 'planning-' + key, 'version': '1.0.0', 'type': 'planning',
            'title': value['title'], 'description': value['description'], 'author': 'AI-Novel-Studio synthetic examples',
            'license': 'CC0-1.0', 'dependencies': ['advanced_planning_v2'], 'provenance': 'ORIGINAL_SYNTHETIC_OFFLINE'}, 'content': deepcopy(value)})
    workflow = default_definition()
    result.append({'schema_version': 1, 'manifest': {'id': 'local-review-workflow', 'version': '1.0.0', 'type': 'workflow',
        'title': '本地草稿 → 人工审核 → 材料', 'description': '复用原 Workflow 的确定性节点。提示词不授予工具权限。',
        'author': 'AI-Novel-Studio synthetic examples', 'license': 'CC0-1.0', 'dependencies': ['declarative_agents_v2'],
        'provenance': 'ORIGINAL_SYNTHETIC_OFFLINE'}, 'content': workflow})
    for typ, title, sections in [
        ('character', '合成人物档案', [('goal', '目标', '林舟寻找失落的潮汐地图。'), ('boundary', '知识边界', '林舟不知道钟楼的秘密。')]),
        ('screenplay', '雨港剧本', [('scene', '场景', '外景 · 雨港 · 夜'), ('dialogue', '对白', '林舟：等潮落，我们再出发。')]),
        ('storyboard', '雨港三镜头', [('wide', '远景', '雨港与钟楼同框。'), ('close', '近景', '林舟握紧合成地图。'), ('reverse', '反打', '同伴望向潮水。')]),
        ('review', '原创审核清单', [('source', '来源', '确认所选来源版本仍然有效。'), ('knowledge', '知识', '核对人物当时已知的事实。'), ('accept', '接受', '仅接受明确批准的草稿区块。')]),
    ]:
        result.append({'schema_version': 1, 'manifest': {'id': 'synthetic-' + typ, 'version': '1.0.0', 'type': typ, 'title': title,
            'author': 'AI-Novel-Studio synthetic examples', 'license': 'CC0-1.0', 'dependencies': [], 'provenance': 'ORIGINAL_SYNTHETIC_OFFLINE'},
            'content': {'sections': [{'key': key, 'title': label, 'text': text} for key, label, text in sections]}})
    result.append({'schema_version': 1, 'manifest': {'id': 'synthetic-safe-batch', 'version': '1.0.0', 'type': 'safe_batch', 'title': '校对与正文导出参数', 'author': 'AI-Novel-Studio synthetic examples', 'license': 'CC0-1.0', 'dependencies': ['safe_batches_v2'], 'provenance': 'ORIGINAL_SYNTHETIC_OFFLINE'}, 'content': {'proof': True, 'export_format': 'txt', 'skip_satisfied': True}})
    return [parse_package(p) for p in result]


def extended_builtin_packages():
    """Additive starters; preserve the original catalog's nine-item projection."""
    result = []
    for typ, title, sections in [
        ('novel', '原创小说起步', [('premise', '故事前提', '潮汐港的制图师决定寻找失落的航道。'), ('scope', '作品范围', '先建立卷、章节与人物草案；人工确认后再写正文。')]),
        ('genre', '悬疑类型约定', [('promise', '读者约定', '谜题的线索在揭晓前可见，误导应有合理解释。'), ('boundaries', '创作边界', '记录题材、语气与读者预期；类型约定不是事实。')]),
        ('world', '潮汐港世界简报', [('rules', '世界规则', '每次潮落会露出一条不同的旧路。'), ('institutions', '组织与地点', '灯塔会保管航线记录，雨港钟楼发布潮汐时刻。')]),
        ('story_structure', '三幕故事结构', [('setup', '第一幕', '建立人物目标、阻碍与选择。'), ('confrontation', '第二幕', '代价逐步升高，并检验人物的信念。'), ('resolution', '第三幕', '人物作出有代价的选择，回收已建立的伏笔。')]),
    ]:
        result.append({'manifest': {'id': 'synthetic-' + typ.replace('_', '-'), 'version': '1.0.0', 'type': typ,
            'title': title, 'author': 'AI-Novel-Studio synthetic examples', 'license': 'CC0-1.0',
            'provenance': 'ORIGINAL_SYNTHETIC_OFFLINE'}, 'content': {'sections': [
                {'key': key, 'title': label, 'text': text} for key, label, text in sections]}})
    definition = default_definition()
    definition['agent'].update(title='人工审核的创作整理 Agent', purpose='整理明确选取的文字，产出待审材料。',
        role_prompt='只整理当前输入；不得把未知内容写成 Canon。', capability_requirements=['LOCAL_RULES'],
        runtime_requirement='TRUSTED_IN_PROCESS_LOCAL')
    result.append({'manifest': {'id': 'synthetic-agent', 'version': '1.0.0', 'type': 'agent',
        'title': '人工审核的创作整理 Agent', 'author': 'AI-Novel-Studio synthetic examples', 'license': 'CC0-1.0',
        'dependencies': ['declarative_agents_v2'], 'provenance': 'ORIGINAL_SYNTHETIC_OFFLINE'}, 'content': definition})
    return [parse_package(p) for p in result]


class PreviewIn(Strict):
    package: str = Field(max_length=128000)


class InstallIn(PreviewIn):
    expected_version: int = Field(ge=0)
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class VersionIn(Strict):
    expected_version: int = Field(ge=1)


class FavoriteIn(Strict):
    expected_version: int = Field(ge=0)
    favorite: bool


class CopyIn(Strict):
    package_id: str = Field(pattern=r'^[a-z][a-z0-9-]{1,79}$')
    package_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')


class EditInstanceIn(VersionIn):
    content: dict


class CompareIn(VersionIn):
    package_id: str = Field(pattern=r'^[a-z][a-z0-9-]{1,79}$')


class ApplyUpdateIn(CompareIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    overwrite_edited_copy: bool = False


class RevertIn(VersionIn):
    restore_version: int = Field(ge=1)


def diff(before, after):
    lines = list(difflib.unified_diff(json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True).splitlines(),
        json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True).splitlines(), fromfile='current', tofile='proposed', lineterm=''))
    return {'lines': lines[:500], 'truncated': len(lines) > 500}


class TemplateLibraryService(DomainService):
    PACKAGES = 'template_catalog_v2'
    INSTANCES = 'template_instances_v2'
    FAVORITES = 'template_favorites_v2'
    def __init__(self, store, novels, chapters, *, planning=None, enabled_features=lambda: frozenset()):
        super().__init__(store, novels, chapters)
        self.planning = planning
        self.enabled_features = enabled_features

    def _owned(self, ctx, name, rid, state=None):
        row = require_row(state or self.store.read(ctx.novel_id, ctx.scope), name, rid)
        if row['created_by'] != ctx.actor: raise FileNotFoundError(rid)
        return row

    def _records(self, ctx, name):
        return [r for r in self.list(ctx.novel_id, ctx.scope, name) if r['created_by'] == ctx.actor]

    def _entry(self, ctx, pid, state=None):
        self.novels.get(ctx.novel_id)
        state = state or self.store.read(ctx.novel_id, ctx.scope)
        return next((r for r in collection(state, self.PACKAGES).values() if r['created_by'] == ctx.actor and r['package']['manifest']['id'] == pid), None)

    def _package(self, ctx, pid, state=None):
        entry = self._entry(ctx, pid, state)
        if entry and entry['status'] == 'INSTALLED': return parse_package(entry['package'])
        original = next((p for p in builtin_packages() + extended_builtin_packages() if p['manifest']['id'] == pid), None)
        if original: return original
        raise FileNotFoundError(pid)

    def catalog(self, ctx):
        builtins = builtin_packages() + extended_builtin_packages()
        packages = {p['manifest']['id']: p for p in builtins}
        entries = self._records(ctx, self.PACKAGES)
        for entry in entries:
            if entry['status'] == 'INSTALLED': packages[entry['package']['manifest']['id']] = parse_package(entry['package'])
        favorites = {r['package_id']: r for r in self._records(ctx, self.FAVORITES)}
        enabled = self.enabled_features()
        rows = []
        for pid, package in packages.items():
            record = next((r for r in entries if r['package']['manifest']['id'] == pid), None)
            rows.append({'id': pid, 'package': package, 'digest': digest(package), 'builtin': any(p['manifest']['id'] == pid for p in builtins),
                'installed': bool(record and record['status'] == 'INSTALLED'), 'version': record['version'] if record else 0,
                'favorite': favorites.get(pid, {}).get('favorite', False), 'favorite_version': favorites.get(pid, {}).get('version', 0),
                'missing_dependencies': [f for f in package['manifest']['dependencies'] if f not in enabled]})
        return {'items': [r for r in rows if r['package']['manifest']['type'] in TYPES], 'types': list(TYPES),
            'extended_items': [r for r in rows if r['package']['manifest']['type'] in EXTENDED_TYPES], 'extended_types': list(EXTENDED_TYPES),
            'import_mode': 'READ_ONLY_DECLARATION', 'permission_grants': [], 'remote_sync': 'DISABLED', 'executable_extensions': 'DENY_ALL',
            'protocol': 'LOCAL_BOUNDED_JSON_V1', 'license_review': 'DECLARATIONS_ONLY'}

    def preview(self, ctx, body):
        data = PreviewIn.model_validate(body); package = parse_package(data.package)
        entry = self._entry(ctx, package['manifest']['id'])
        before = entry['package'] if entry and entry['status'] == 'INSTALLED' else None
        version = entry['version'] if entry else 0
        return {'package': package, 'expected_version': version, 'diff': diff(before, package),
            'preview_digest': digest([ctx.novel_id, ctx.scope, ctx.actor, version, before, package]),
            'missing_dependencies': [f for f in package['manifest']['dependencies'] if f not in self.enabled_features()],
            'will_execute': False, 'will_grant_permissions': False}

    def install(self, ctx, body, reauthorize=lambda: None):
        data = InstallIn.model_validate(body)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            preview = self.preview(ctx, {'package': data.package})
            if preview['expected_version'] != data.expected_version: raise CapabilityVersionConflict({'version': preview['expected_version']})
            if preview['preview_digest'] != data.preview_digest: raise StaleSourceError('template preview changed')
            package = preview['package']; entry = self._entry(ctx, package['manifest']['id'], state)
            payload = {'package': package, 'package_digest': digest(package), 'status': 'INSTALLED'}
            if entry:
                if entry['package']['manifest']['type'] != package['manifest']['type']: raise ValueError('template type cannot change')
                if entry['package']['manifest']['version'] == package['manifest']['version'] and digest(parse_package(entry['package'])) != digest(package):
                    raise ValueError('changed content requires a new manifest version')
                change_row(entry, ctx.actor, data.expected_version, lambda r: r.update(payload))
            else:
                entry = new_row(ctx.novel_id, ctx.scope, ctx.actor, payload); collection(state, self.PACKAGES)[entry['id']] = entry
            reauthorize(); return deepcopy({k: v for k, v in entry.items() if k != 'history'})

    def favorite(self, ctx, pid, body, reauthorize=lambda: None):
        data = FavoriteIn.model_validate(body); self._package(ctx, pid)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = next((r for r in collection(state, self.FAVORITES).values() if r['created_by'] == ctx.actor and r['package_id'] == pid), None)
            if (row['version'] if row else 0) != data.expected_version: raise CapabilityVersionConflict({'version': row['version'] if row else 0})
            if row: change_row(row, ctx.actor, data.expected_version, lambda r: r.update(favorite=data.favorite))
            else:
                row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'package_id': pid, 'favorite': data.favorite})
                collection(state, self.FAVORITES)[row['id']] = row
            reauthorize(); return deepcopy(row)

    def uninstall(self, ctx, pid, body, reauthorize=lambda: None):
        data = VersionIn.model_validate(body)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._entry(ctx, pid, state)
            if not row: raise FileNotFoundError(pid)
            change_row(row, ctx.actor, data.expected_version, lambda r: r.update(status='UNINSTALLED'))
            reauthorize(); return {'id': pid, 'version': row['version'], 'status': row['status'], 'instances_preserved': True}

    def instances(self, ctx):
        return {'items': [{k: v for k, v in r.items() if k != 'history'} for r in self._records(ctx, self.INSTANCES)]}

    def copy(self, ctx, body, reauthorize=lambda: None):
        data = CopyIn.model_validate(body)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            package = self._package(ctx, data.package_id, state)
            if digest(package) != data.package_digest: raise StaleSourceError('template changed; reopen preview')
            if any(dep not in self.enabled_features() for dep in package['manifest']['dependencies']): raise ValueError('TEMPLATE_DEPENDENCY_MISSING')
            for existing in collection(state, self.INSTANCES).values():
                if existing['created_by'] == ctx.actor and existing.get('request_id') == data.request_id:
                    if existing['original_package_digest'] != data.package_digest: raise ValueError('request id reused for another package')
                    reauthorize(); return deepcopy({k: v for k, v in existing.items() if k != 'history'})
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'package_id': data.package_id, 'package_version': package['manifest']['version'],
                'manifest': deepcopy(package['manifest']), 'content': deepcopy(package['content']), 'base_content_digest': digest(package['content']),
                'original_package_digest': data.package_digest, 'request_id': data.request_id, 'status': 'DRAFT', 'applied': False,
                'edited': False, 'linked_target': None})
            # Planning templates remain in their original authoritative collection
            # and schema. This same scope transaction creates both metadata rows.
            if package['manifest']['type'] == 'planning':
                if self.planning is None: raise ValueError('PLANNING_SERVICE_REQUIRED')
                payload = self.planning._payload(package['content'], PlanningTemplateIn)
                target = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**payload, 'status': 'ACTIVE', 'builtin': False,
                    'template_instance_id': row['id']})
                collection(state, self.planning.TEMPLATES)[target['id']] = target
                row['linked_target'] = {'feature': 'advanced_planning_v2', 'id': target['id'], 'version': target['version']}
            elif package['manifest']['type'] in {'workflow', 'agent'}:
                from .declarative_agents import DeclarativeAgentsService
                definition = WorkflowAuthoring.model_validate(package['content']).model_dump()
                target = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'definition': definition, 'definition_digest': digest(definition),
                    'status': 'DRAFT', 'applied': False, 'template_instance_id': row['id']})
                collection(state, DeclarativeAgentsService.DEFINITIONS)[target['id']] = target
                row['linked_target'] = {'feature': 'declarative_agents_v2', 'id': target['id'], 'version': target['version']}
            collection(state, self.INSTANCES)[row['id']] = row
            reauthorize(); return deepcopy(row)

    def edit(self, ctx, rid, body, reauthorize=lambda: None):
        data = EditInstanceIn.model_validate(body)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._owned(ctx, self.INSTANCES, rid, state)
            package = parse_package({'manifest': row['manifest'], 'content': data.content})
            change_row(row, ctx.actor, data.expected_version, lambda r: r.update(content=package['content'], edited=True))
            reauthorize(); return deepcopy({k: v for k, v in row.items() if k != 'history'})

    def compare(self, ctx, rid, body):
        data = CompareIn.model_validate(body)
        row = self._owned(ctx, self.INSTANCES, rid); check_version(row, data.expected_version)
        if row['package_id'] != data.package_id: raise ValueError('compare requires the same template identity')
        package = self._package(ctx, data.package_id)
        return {'preview_digest': digest([ctx.novel_id, ctx.scope, ctx.actor, row['id'], row['version'], row['content'], package]),
            'expected_version': row['version'], 'package_id': data.package_id, 'from_version': row['package_version'], 'to_version': package['manifest']['version'],
            'edited': row['edited'], 'diff': diff(row['content'], package['content']), 'linked_target_will_change': False}

    def apply_update(self, ctx, rid, body, reauthorize=lambda: None):
        data = ApplyUpdateIn.model_validate(body)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._owned(ctx, self.INSTANCES, rid, state)
            preview = self.compare(ctx, rid, {'expected_version': data.expected_version, 'package_id': data.package_id})
            if preview['preview_digest'] != data.preview_digest: raise StaleSourceError('template or copy changed; compare again')
            if row['edited'] and not data.overwrite_edited_copy: raise ValueError('explicit overwrite of edited copy required')
            package = self._package(ctx, data.package_id, state)
            change_row(row, ctx.actor, data.expected_version, lambda r: r.update(content=deepcopy(package['content']), manifest=deepcopy(package['manifest']),
                package_version=package['manifest']['version'], base_content_digest=digest(package['content']), edited=False))
            reauthorize(); return deepcopy({k: v for k, v in row.items() if k != 'history'})

    def history(self, ctx, rid):
        row = self._owned(ctx, self.INSTANCES, rid)
        return {'items': [{'version': r['version'], 'package_version': r['package_version'], 'content': r['content']} for r in row['history']]}

    def revert(self, ctx, rid, body, reauthorize=lambda: None):
        data = RevertIn.model_validate(body)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._owned(ctx, self.INSTANCES, rid, state)
            saved = next((r for r in row['history'] if r['version'] == data.restore_version), None)
            if not saved: raise ValueError('history version unavailable')
            payload = {k: deepcopy(saved[k]) for k in ('content', 'manifest', 'package_version', 'base_content_digest', 'edited')}
            change_row(row, ctx.actor, data.expected_version, lambda r: r.update(payload))
            reauthorize(); return deepcopy({k: v for k, v in row.items() if k != 'history'})
