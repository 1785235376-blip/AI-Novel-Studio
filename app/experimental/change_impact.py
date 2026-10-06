"""Evidence-bound change impact and selective refresh over existing authorities.

This is a projection and a pointer checkpoint, not another graph, asset store,
executor or review authority. Unknown relationships remain unknown. Only the
existing synthetic and registered-local image adapters are executable here;
unsupported domains remain manual review items. Original inputs/results and manuscript remain untouched.
"""
from __future__ import annotations

import copy
from typing import Literal

from pydantic import Field

from ..source_privacy import source_privacy_status
from .common import DomainService, StaleSourceError, change_row, check_version, new_row, snapshot
from .media import CoverBriefIn, StoryboardBriefIn, RegisteredLocalImageWorkflowAdapter, StrictModel, digest, production_environment, supported_local_image


class SourceRef(StrictModel):
    kind: Literal['CHAPTER', 'CHARACTER', 'WORLD_RECORD', 'ASSET']
    id: str = Field(min_length=1, max_length=240)


class SelectedNode(StrictModel):
    key: str = Field(min_length=1, max_length=500)
    expected_version: int = Field(ge=0)


class ImpactRequest(StrictModel):
    source: SourceRef


class PreflightInput(ImpactRequest):
    selected: list[SelectedNode] = Field(min_length=1, max_length=20)


class LockInput(SelectedNode):
    expected_lock_version: int = Field(default=0, ge=0)
    locked: bool


class RefreshInput(StrictModel):
    expected_version: int = Field(ge=1)
    preflight_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=120)


class TaskVersion(StrictModel):
    expected_task_version: int = Field(ge=1)


def node_key(kind, rid):
    return kind + ':' + rid


class ChangeImpactService(DomainService):
    LOCKS = 'change_impact_locks_v2'
    PLANS = 'change_impact_preflights_v2'
    REFRESHES = 'change_impact_refreshes_v2'
    MAX_NODES = 5000

    def __init__(self, store, novels, chapters, story_graph, production, planning, audiobook, *, enabled=None):
        super().__init__(store, novels, chapters)
        self.graph, self.production, self.planning, self.audiobook = story_graph, production, planning, audiobook
        self.media = production.media
        production.change_impact = self
        if enabled is None:
            from .flags import enabled_flags
            enabled = lambda name: name in enabled_flags()
        self.enabled = enabled

    def _active(self):
        if not all(self.enabled(f) for f in ('change_impact_v2', 'temporal_story_graph_v2', 'asset_lineage_v2')):
            raise FileNotFoundError('change impact unavailable')

    def _source(self, nid, scope, ref):
        kind, rid = ref['kind'], ref['id']
        if kind == 'CHAPTER':
            row = self.chapters.get(rid)
            if row.get('novel_id') != nid or row.get('branch_id') != scope.get('branch_id'):
                raise FileNotFoundError('source unavailable')
            return {'kind': kind, 'id': rid, 'label': row.get('title', rid), 'binding': self.sources(nid, [rid])[rid]}
        if kind in {'CHARACTER', 'LOCATION'}:
            row = next((r for r in self.novels.data_set(nid, 'characters' if kind == 'CHARACTER' else 'locations') if r['id'] == rid and r.get('branch_id') == scope.get('branch_id')), None)
            if row is None: raise FileNotFoundError('source unavailable')
            return {'kind': kind, 'id': rid, 'label': row.get('name', rid), 'binding': digest(row)}
        if kind == 'WORLD_RECORD':
            row = self.graph.get(nid, scope, self.graph.RECORDS, rid)
            if 'research_sources' in row: raise FileNotFoundError('source unavailable')
            if row['kind'] == 'KNOWLEDGE_EVENT' and not self.enabled('character_mind_v2'): raise FileNotFoundError('source unavailable')
            return {'kind': kind, 'id': rid, 'label': row['title'], 'binding': {'version': row['version'], 'digest': digest(snapshot(row))}}
        row = self.production._asset(nid, scope, rid, deleted=True)
        return {'kind': kind, 'id': rid, 'label': row['filename'], 'binding': {'version': row['version'], 'digest': row['sha256']}}

    def catalog(self, nid, scope):
        self._active(); self.novels.get(nid)
        refs = [{'kind': 'CHAPTER', 'id': r['id']} for r in self.chapters.list(nid) if r.get('branch_id') == scope.get('branch_id')]
        refs += [{'kind': 'CHARACTER', 'id': r['id']} for r in self.novels.data_set(nid, 'characters') if r.get('branch_id') == scope.get('branch_id')]
        refs += [{'kind': 'WORLD_RECORD', 'id': r['id']} for r in self.graph.list(nid, scope, self.graph.RECORDS) if 'research_sources' not in r and (r['kind'] != 'KNOWLEDGE_EVENT' or self.enabled('character_mind_v2'))]
        refs += [{'kind': 'ASSET', 'id': r['id']} for r in self.production._asset_rows(nid, scope)]
        if len(refs) > self.MAX_NODES: raise ValueError('CHANGE_IMPACT_SCOPE_LIMIT')
        nodes, _ = self._inventory(nid, scope)
        # WORLD/ASSET labels are withheld if any recorded parent is inaccessible.
        return {'items': [self._source(nid, scope, r) for r in refs
                          if r['kind'] not in {'WORLD_RECORD', 'ASSET'} or node_key(r['kind'], r['id']) in nodes],
                'rename_policy': 'STABLE_ID_DISPLAY_ONLY_NO_MANUSCRIPT_REPLACEMENT'}

    def _inventory(self, nid, scope):
        self._active()
        nodes, hidden = {}, set()
        locks = {r['node_key']: r for r in self.list(nid, scope, self.LOCKS)}

        def add(kind, row, deps, *, label=None, feature=None, stale=None, rid=None):
            key = node_key(kind, rid or row['id'])
            nodes[key] = {'key': key, 'kind': kind, 'id': rid or row['id'], 'label': label or row.get('title') or kind,
                          'version': row.get('version', row.get('edit_version', 0)), 'status': row.get('status', 'RECORDED'),
                          'deps': deps, 'fingerprint': digest(snapshot(row)), 'feature': feature,
                          'domain_stale': stale, 'raw': row, 'lock': locks.get(key)}
            if len(nodes) > self.MAX_NODES: raise ValueError('CHANGE_IMPACT_SCOPE_LIMIT')

        def references(row):
            deps = [(node_key('CHAPTER', cid), b) for cid, b in row.get('sources', {}).items()]
            deps += [(node_key('CHARACTER', cid), b) for cid, b in row.get('character_sources', {}).items()]
            deps += [(node_key('CHARACTER', cid), b) for cid, b in row.get('character_snapshots', {}).items() if isinstance(b, str)]
            deps += [(node_key('ASSET', aid), b) for aid, b in row.get('asset_sources', {}).items()]
            deps += [(node_key('WORLD_RECORD', rid), b) for rid, b in row.get('semantic_sources', {}).items()]
            if row.get('kind') == 'STORYBOARD' and row.get('screenplay_source') and row.get('shot_snapshot'):
                source = row['screenplay_source']
                deps.append((node_key('SHOT', source['id'] + '/' + row['shot_id']),
                    {'version': source['version'], 'digest': digest(snapshot({**row['shot_snapshot'], 'version': source['version']}))}))
            for key, binding in row.get('entity_sources', {}).items():
                if key.startswith('characters:'): deps.append((node_key('CHARACTER', key.split(':', 1)[1]), binding))
                elif key.startswith('locations:'): deps.append((node_key('LOCATION', key.split(':', 1)[1]), binding))
                elif key.startswith('scene:') or key.startswith('planning_ancestor:'): deps.append((node_key('PLANNING_NODE', key.split(':', 1)[1]), {'digest': binding}))
                elif key.startswith('world:'): deps.append((node_key('WORLD_RECORD', key.split(':', 1)[1]), {'digest': binding}))
            return deps

        state, world = self.graph._rows(nid, scope)
        for row in world.values():
            if 'research_sources' in row:
                hidden.add(node_key('WORLD_RECORD', row['id'])); continue
            if row['kind'] == 'KNOWLEDGE_EVENT' and not self.enabled('character_mind_v2'):
                hidden.add(node_key('WORLD_RECORD', row['id'])); continue
            add('WORLD_RECORD', row, references(row), feature='temporal_story_graph_v2' if row['kind'] in {'STORY_RELATION', 'STORY_CONCEPT', 'KNOWLEDGE_EVENT'} else 'world_character_engines_v2',
                stale=self.graph._decorate(nid, scope, row, state)['stale'])
        if self.enabled('advanced_planning_v2'):
            for row in self.planning.list(nid, scope, self.planning.NODES):
                deps = references(row)
                if row.get('parent_id'): deps.append((node_key('PLANNING_NODE', row['parent_id']), None))
                add('PLANNING_NODE', row, deps, feature='advanced_planning_v2')
            for row in self.planning.proposals(nid, scope):
                add('PLANNING_PROPOSAL', row, references(row) + [(node_key('PLANNING_NODE', row['node_id']), {'version': row['target_version']})], feature='advanced_planning_v2')
        media_on = self.enabled('cover_storyboard_generation') and self.enabled('media_adapter_registry')
        if media_on:
            for row in self.media.list(nid, scope, self.media.BRIEFS):
                add('MEDIA_BRIEF', row, references(row), feature='cover_storyboard_generation')
            for row in self.media.list(nid, scope, self.media.TASKS):
                deps = references(row['brief_snapshot']) + [(node_key('MEDIA_BRIEF', row['brief_id']), {'version': row['brief_version']})]
                add('MEDIA_TASK', row, deps, label='媒体任务 · ' + row['brief_snapshot'].get('title', row['operation']), feature='cover_storyboard_generation')
            if self.media.screenplays is not None:
                for screenplay in self.media.screenplays.list(nid, branch_id=scope.get('branch_id')):
                    if screenplay.get('branch_id') != scope.get('branch_id'): continue
                    scenes = {r['id']: r for r in screenplay.get('scenes', [])}
                    for scene in scenes.values():
                        deps = [(node_key('CHAPTER', scene['source_chapter_id']), {'version': scene['source_version']})] if scene.get('source_chapter_id') and scene.get('source_version') else []
                        add('SCREENPLAY_SCENE', {**scene, 'version': screenplay.get('edit_version', 0)}, deps,
                            rid=screenplay['id'] + '/' + scene['id'], label='剧本场景', feature='cover_storyboard_generation')
                    for shot in screenplay.get('shots', []):
                        deps = [(node_key('SCREENPLAY_SCENE', screenplay['id'] + '/' + shot['scene_id']), None)] if shot.get('scene_id') else []
                        if shot.get('source_chapter_id'):
                            scene = scenes.get(shot.get('scene_id'), {})
                            binding = {'version': scene['source_version']} if scene.get('source_chapter_id') == shot['source_chapter_id'] and scene.get('source_version') else None
                            deps.append((node_key('CHAPTER', shot['source_chapter_id']), binding))
                        for name in ('asset_id', 'frame_asset_id'):
                            if shot.get(name): deps.append((node_key('ASSET', shot[name]), None))
                        add('SHOT', {**shot, 'version': screenplay.get('edit_version', 0)}, deps, rid=screenplay['id'] + '/' + shot['id'], label='镜头 ' + str(shot.get('number', '')), feature='cover_storyboard_generation')
                    for frame in screenplay.get('storyboard', []):
                        deps = [(node_key('SHOT', screenplay['id'] + '/' + frame['shot_id']), None)] if frame.get('shot_id') else []
                        for name in ('asset_id', 'frame_asset_id'):
                            if frame.get(name): deps.append((node_key('ASSET', frame[name]), None))
                        add('STORYBOARD_FRAME', {**frame, 'version': screenplay.get('storyboard_revision', 0)}, deps,
                            rid=screenplay['id'] + '/' + frame['id'], label='分镜卡片', feature='cover_storyboard_generation')
                    for motion in screenplay.get('motion_tasks', []):
                        deps = []
                        for name in ('start_frame', 'end_frame'):
                            ref = motion.get(name) or ''
                            for prefix, kind in (('asset:', 'ASSET'), ('shot:', 'SHOT'), ('storyboard:', 'STORYBOARD_FRAME')):
                                if ref.startswith(prefix): deps.append((node_key(kind, (screenplay['id'] + '/' if kind != 'ASSET' else '') + ref[len(prefix):]), None))
                        aid = (motion.get('result') or {}).get('asset_id')
                        if aid: deps.append((node_key('ASSET', aid), None))
                        add('MOTION_TASK', {**motion, 'version': screenplay.get('motion_task_revision', 0)}, deps,
                            rid=screenplay['id'] + '/' + motion['id'], label='视频任务', feature='cover_storyboard_generation')
        for raw in self.production._asset_rows(nid, scope):
            projected = self.production._project_asset(nid, scope, raw)
            declaration = raw.get('parameters', {}).get('asset_lineage_v2', {})
            deps = [(node_key('ASSET', aid), declaration.get('parents', {}).get(aid)) for aid in raw.get('source_asset_ids', [])]
            deps += [(node_key('CHAPTER', cid), b) for cid, b in declaration.get('sources', {}).items()]
            if projected.get('generation') and media_on:
                deps.append((node_key('MEDIA_TASK', projected['generation']['task_id']), None))
            add('ASSET', raw, deps, label=raw['filename'], feature='asset_lineage_v2', stale=projected['stale'])
        if self.enabled('audiobook_v2'):
            for row in self.audiobook.plans(nid, scope):
                used_characters = {s.get('character_id') for s in row.get('segments', [])}
                deps = [(key, b) for key, b in references(row) if not key.startswith('CHARACTER:') or key.split(':', 1)[1] in used_characters]
                for segment in row.get('segments', []):
                    if segment.get('audio_asset_id'): deps.append((node_key('ASSET', segment['audio_asset_id']), segment.get('audio_source')))
                add('AUDIO_PLAN', row, deps, feature='audiobook_v2', stale=row['stale'])
                # SRT/VTT are on-demand views of this exact plan, not invented files.
                add('SUBTITLES', row, [(node_key('AUDIO_PLAN', row['id']), {'version': row['version']})], label='字幕视图 · ' + row['title'], feature='audiobook_v2')
            for row in self.audiobook.list(nid, scope, self.audiobook.MIXES):
                deps = references(row) + [(node_key('AUDIO_PLAN', row['plan_id']), {'version': row['plan_version']})]
                deps += [(node_key('ASSET', aid), None) for aid in row.get('source_asset_ids', [])]
                add('AUDIO_MIX', row, deps, label='混音候选', feature='audiobook_v2')
        if self.enabled('production_manifest_v2'):
            for row in self.production.list(nid, scope, self.production.MANIFESTS):
                deps = references(row) + [(node_key('MEDIA_TASK', row['task_id']), {'version': row['task_version']})]
                add('EXPORT', row, deps, label='生产清单导出视图', feature='asset_lineage_v2')

        def current(key):
            kind, rid = key.split(':', 1)
            if kind in {'CHAPTER', 'CHARACTER', 'LOCATION', 'WORLD_RECORD', 'ASSET'}:
                ref = self._source(nid, scope, {'kind': kind, 'id': rid})
                return ref['binding'], ref['label']
            if key not in nodes: raise FileNotFoundError('dependency unavailable')
            return {'version': nodes[key]['version'], 'digest': nodes[key]['fingerprint']}, nodes[key]['label']

        for key, node in nodes.items():
            node['evidence'] = []
            for parent, expected in dict(node['deps']).items():
                try: actual, label = current(parent)
                except (FileNotFoundError, ValueError, KeyError): hidden.add(key); continue
                same = actual == expected
                if isinstance(actual, dict) and isinstance(expected, dict): same = all(actual.get(k) == v for k, v in expected.items())
                node['evidence'].append({'key': parent, 'label': label, 'state': 'UNVERIFIED' if expected is None else 'CURRENT' if same else 'STALE',
                    'recorded_version': expected.get('version') if isinstance(expected, dict) else None,
                    'current_version': actual.get('version') if isinstance(actual, dict) else None})
        # Suppress the whole dependent node, including its title/count, when an
        # inaccessible ancestor is referenced. No hidden placeholder count leaks.
        while True:
            more = {key for key, row in nodes.items() if any(parent in hidden for parent, _ in row['deps'])} - hidden
            if not more: break
            hidden |= more
        nodes = {key: row for key, row in nodes.items() if key not in hidden}
        stale = {key for key, row in nodes.items() if row['domain_stale'] or any(e['state'] == 'STALE' for e in row['evidence'])}
        while True:
            more = {key for key, row in nodes.items() if any(parent in stale for parent, _ in row['deps'])} - stale
            if not more: break
            stale |= more
        for key, row in nodes.items(): row['stale'] = key in stale
        return nodes, current

    def _node_view(self, node):
        locked = bool(node['lock'] and node['lock']['locked'])
        supported = node['kind'] == 'MEDIA_TASK' and node['raw'].get('operation') in {'cover_generation', 'storyboard_card_generation'}
        reason = 'LOCKED_OUTCOME' if locked else 'SOURCE_CURRENT' if not node['stale'] else None
        if not supported: reason = 'ORIGINAL_DOMAIN_MANUAL_REVIEW_REQUIRED'
        elif node['status'] in {'RUNNING', 'QUEUED'}: reason = 'ORIGINAL_TASK_NOT_TERMINAL'
        return {k: copy.deepcopy(node[k]) for k in ('key', 'kind', 'id', 'label', 'version', 'status', 'feature', 'stale', 'evidence')} | {
            'evidence_type': 'EXACT_RECORDED_EDGE', 'locked': locked, 'lock_version': node['lock']['version'] if node['lock'] else 0,
            'refresh_candidate': supported and not reason, 'refresh_reason': reason,
            'knowledge_category': node['raw'].get('kind') if node['kind'] == 'WORLD_RECORD' else None}

    def impact(self, nid, scope, value):
        self._active(); body = ImpactRequest.model_validate(value)
        source = self._source(nid, scope, body.source.model_dump())
        nodes, _ = self._inventory(nid, scope)
        key = node_key(source['kind'], source['id'])
        if source['kind'] in {'WORLD_RECORD', 'ASSET'} and key not in nodes: raise FileNotFoundError('source unavailable')
        found, frontier = set(), {key}
        while frontier:
            children = {k for k, n in nodes.items() if any(parent in frontier for parent, _ in n['deps'])} - found - {key}
            found |= children; frontier = children
        return {'source': source, 'items': [self._node_view(nodes[k]) for k in sorted(found)],
                'coverage': 'EXACT_RECORDED_DEPENDENCIES_ONLY', 'inferred': [], 'unrecorded_dependencies': 'UNKNOWN',
                'chapter_reference_coverage': 'RECORDED_SOURCE_BINDINGS_ONLY_NO_TEXT_INFERENCE',
                'export_coverage': 'RECORDED_PRODUCTION_MANIFEST_AND_SUBTITLE_VIEWS_ONLY',
                'rename_policy': 'STABLE_ID_DISPLAY_ONLY_NO_MANUSCRIPT_REPLACEMENT', 'automatic_regeneration': False}

    def set_lock(self, nid, scope, actor, value, guard=lambda: None):
        body = LockInput.model_validate(value); self._active(); guard()
        with self.store.transaction(nid, scope) as doc:
            guard(); self._active()
            nodes, _ = self._inventory(nid, scope)
            if body.key not in nodes: raise FileNotFoundError('node unavailable')
            node = nodes[body.key]; check_version(node, body.expected_version)
            locks = doc['collections'].setdefault(self.LOCKS, {})
            old = node['lock']
            if old:
                check_version(old, body.expected_lock_version)
                change_row(locks[old['id']], actor, body.expected_lock_version, lambda r: r.update(locked=body.locked, outcome_fingerprint=node['fingerprint']))
            else:
                if body.expected_lock_version != 0: raise StaleSourceError('CHANGE_IMPACT_LOCK_CHANGED')
                row = new_row(nid, scope, actor, {'node_key': body.key, 'locked': body.locked, 'outcome_fingerprint': node['fingerprint']})
                locks[row['id']] = row
            guard(); self._active()
        return self._node_view(self._inventory(nid, scope)[0][body.key])

    def _prepare_brief(self, nid, scope, actor, kind, recipe):
        return (self.media.prepare_cover if kind == 'COVER' else self.media.prepare_storyboard)(nid, scope, actor, recipe)

    def manifest_origin(self, nid, scope, task, guard=lambda: None):
        """Bind A13 capture/replay to this coordinator's original current checks."""
        self._active(); guard()
        refresh = self.get(nid, scope, self.REFRESHES, task['change_impact_refresh_id'])
        if refresh['task_id'] != task['id'] or refresh['created_by'] != task['created_by']:
            raise ValueError('CHANGE_IMPACT_MANIFEST_ORIGIN_CHANGED')
        plan = self.get(nid, scope, self.PLANS, refresh['plan_id'])
        entry = next(e for e in plan['entries'] if e['key'] == refresh['node_key'])
        single = {**plan, 'selected': [e for e in plan['selected'] if e['key'] == refresh['node_key']], 'entries': [entry]}
        self._assert_plan(nid, scope, task['created_by'], single, guard)
        self.media._current_brief(nid, scope, task)
        return {'refresh_id': refresh['id'], 'plan_id': plan['id'], 'node_key': refresh['node_key'],
                'preflight_digest': plan['preflight_digest']}

    def _entry(self, nid, scope, actor, source, selected, guard):
        view = self.impact(nid, scope, {'source': source})
        public = next((r for r in view['items'] if r['key'] == selected['key']), None)
        if public is None: raise FileNotFoundError('selected node unavailable')
        check_version(public, selected['expected_version'])
        node = self._inventory(nid, scope)[0][selected['key']]
        blockers = [public['refresh_reason']] if public['refresh_reason'] else []
        result = {'key': selected['key'], 'expected_version': selected['expected_version'], 'blockers': blockers,
                  'label': public['label'], 'recipe': None, 'state': None}
        if blockers: return result
        task = node['raw']
        if not all(self.enabled(f) for f in ('cover_storyboard_generation', 'media_adapter_registry')):
            result['blockers'].append('MEDIA_FEATURE_DISABLED'); return result
        try:
            adapter = self.media.registry.resolve(task['adapter_id'], task['operation'])
        except ValueError:
            result['blockers'].append('ORIGINAL_ADAPTER_UNAVAILABLE'); return result
        try:
            if not supported_local_image(adapter):
                result['blockers'].append('REGISTERED_LOCAL_IMAGE_EXECUTOR_REQUIRED'); return result
            if type(adapter) is RegisteredLocalImageWorkflowAdapter and not self.production.broker_enabled():
                result['blockers'].append('MODEL_BROKER_FEATURE_REQUIRED'); return result
            if adapter.definition.model_dump() != task['adapter_definition']:
                result['blockers'].append('ORIGINAL_ADAPTER_CHANGED'); return result
            old = task['brief_snapshot']
            fields = CoverBriefIn.model_fields if old['kind'] == 'COVER' else StoryboardBriefIn.model_fields
            recipe = {name: copy.deepcopy(old[name]) for name in fields if name in old}
            if old['kind'] == 'STORYBOARD':
                screenplay, _ = self.media._shot(nid, scope, old['screenplay_id'], old['shot_id'])
                recipe['expected_screenplay_version'] = screenplay.get('edit_version', 0)
            brief = self._prepare_brief(nid, scope, actor, old['kind'], recipe)
            if type(adapter) is RegisteredLocalImageWorkflowAdapter: adapter.validate_request(brief, task['candidate_count'])
            self.media._assert_brief(nid, scope, brief)
            privacy = {cid: {k: v for k, v in source_privacy_status(self.chapters.get(cid), scope.get('branch_id'), self.store.root).items()
                             if k in {'privacy_level', 'reviewed', 'stale'}} for cid in brief['sources']}
            guard(); self._active()
            result.update(recipe=recipe, state={'source': view['source']['binding'], 'node_fingerprint': node['fingerprint'],
                'lock_version': public['lock_version'], 'brief_digest': digest({k: v for k, v in brief.items() if k not in {'id', 'created_at', 'updated_at', 'created_by', 'updated_by', 'history'}}),
                'kind': old['kind'], 'parameters': copy.deepcopy(task.get('parameters', {})),
                'privacy': privacy, 'adapter': adapter.definition.model_dump(), 'environment': production_environment(adapter),
                'candidate_count': task['candidate_count'], 'broker_required': bool(self.production.broker_enabled())})
        except (FileNotFoundError, ValueError, KeyError):
            result['blockers'].append('CURRENT_INPUTS_UNAVAILABLE')
        return result

    def preflight(self, nid, scope, actor, value, guard=lambda: None):
        body = PreflightInput.model_validate(value); self._active(); guard()
        selected = [r.model_dump() for r in body.selected]
        if len({r['key'] for r in selected}) != len(selected): raise ValueError('CHANGE_IMPACT_DUPLICATE_SELECTION')
        source = body.source.model_dump()
        entries = [self._entry(nid, scope, actor, source, r, guard) for r in selected]
        for entry in entries:
            entry.update(broker_decision_id=None, broker_decision_version=None, cost=None)
            if not entry['blockers'] and entry['state']['broker_required']:
                broker = self.production.broker
                if broker is None: entry['blockers'].append('MODEL_BROKER_NOT_CONFIGURED'); continue
                adapter = entry['state']['adapter']
                decision = broker.preview(nid, scope, actor, {'capability': 'IMAGE', 'policy': 'CUSTOM', 'profile': 'LOCAL_ONLY',
                    'preferred_route': digest(['media', adapter['adapter_id'], adapter.get('model_id')]),
                    'chapter_ids': entry['recipe'].get('chapter_ids', list(self.media.prepare_storyboard(nid, scope, actor, entry['recipe'])['sources']) if entry['state']['kind'] == 'STORYBOARD' else []),
                    'allow_synthetic': entry['state']['environment']['deterministic']}, guard)
                if not decision.get('chosen'): entry['blockers'].append('MODEL_BROKER_NO_LEGAL_ROUTE')
                entry.update(broker_decision_id=decision['id'], broker_decision_version=decision['version'])
                if decision.get('chosen'):
                    entry['cost'] = {'state': decision['chosen']['cost_state'], 'estimate_microusd': (decision['chosen'].get('price') or {}).get('reserve_microusd')}
            elif not entry['blockers']:
                entry['cost'] = {'state': 'KNOWN_SYNTHETIC_ZERO', 'estimate_microusd': 0}
        guard(); self._active()
        with self.store.transaction(nid, scope) as doc:
            for selected_node, entry in zip(selected, entries):
                current = self._entry(nid, scope, actor, source, selected_node, guard)
                if current['state'] != entry['state']: raise StaleSourceError('CHANGE_IMPACT_PREFLIGHT_CHANGED')
            row = new_row(nid, scope, actor, {'status': 'PREFLIGHT', 'source': source, 'source_snapshot': self._source(nid, scope, source), 'selected': selected, 'entries': entries})
            row['preflight_digest'] = digest([actor, scope, source, entries])
            doc['collections'].setdefault(self.PLANS, {})[row['id']] = row
        return self._plan_view(row)

    def _plan_view(self, row):
        ready = all(not e['blockers'] for e in row['entries'])
        amounts = [(e.get('cost') or {}).get('estimate_microusd') for e in row['entries']]
        synthetic = all((e.get('state') or {}).get('environment', {}).get('deterministic') for e in row['entries'])
        return {'id': row['id'], 'version': row['version'], 'preflight_digest': row['preflight_digest'],
                'source_snapshot': copy.deepcopy(row['source_snapshot']),
                'ready': all(not e['blockers'] for e in row['entries']),
                'items': [{'key': e['key'], 'label': e['label'], 'blockers': e['blockers']} for e in row['entries']],
                'cost': {'state': ('KNOWN_SYNTHETIC_ZERO' if synthetic else 'ESTIMATE') if ready and all(v is not None for v in amounts) else 'UNAVAILABLE',
                         'currency': 'USD', 'estimate_microusd': sum(amounts) if ready and all(v is not None for v in amounts) else None},
                'automatic_execution': False, 'maximum_candidates': sum(e['state']['candidate_count'] for e in row['entries'] if e['state']),
                'verification': 'SYNTHETIC_PROTOCOL_ONLY' if synthetic else 'REGISTERED_LOCAL_RUNTIME_NOT_RUN'}

    def _assert_plan(self, nid, scope, actor, row, guard):
        self._active(); guard()
        if row['created_by'] != actor: raise FileNotFoundError('preflight unavailable')
        for selected, entry in zip(row['selected'], row['entries']):
            current = self._entry(nid, scope, actor, row['source'], selected, guard)
            if entry['blockers'] or current['blockers'] or current['state'] != entry['state']:
                raise StaleSourceError('CHANGE_IMPACT_FRESH_PREFLIGHT_REQUIRED')
            if entry['state']['broker_required']:
                broker = self.production.broker
                if broker is None or not entry['broker_decision_id']: raise ValueError('CHANGE_IMPACT_BROKER_REQUIRED')
                decision = broker.get(nid, scope, broker.DECISIONS, entry['broker_decision_id'])
                check_version(decision, entry['broker_decision_version'])
                route = broker._assert_preview(nid, scope, actor, decision)
                if route.get('adapter_id') != entry['state']['adapter']['adapter_id'] or route.get('model_id') != entry['state']['adapter'].get('model_id'):
                    raise ValueError('CHANGE_IMPACT_BROKER_ROUTE_CHANGED')
        guard(); self._active()

    def prepare(self, nid, scope, actor, rid, value, guard=lambda: None):
        self._active(); guard()
        body = RefreshInput.model_validate(value)
        plan = self.get(nid, scope, self.PLANS, rid)
        if plan['created_by'] != actor: raise FileNotFoundError('preflight unavailable')
        check_version(plan, body.expected_version)
        if body.preflight_digest != plan['preflight_digest']: raise StaleSourceError('CHANGE_IMPACT_PREFLIGHT_MISMATCH')
        key = digest([actor, body.idempotency_key]); fingerprint = digest([rid, body.model_dump()])
        self._active(); guard()
        with self.store.transaction(nid, scope) as doc:
            rows = doc['collections'].setdefault(self.REFRESHES, {})
            old = [r for r in rows.values() if r['idempotency_digest'] == key]
            if old:
                if any(r['request_digest'] != fingerprint for r in old): raise ValueError('CHANGE_IMPACT_IDEMPOTENCY_CONFLICT')
                positions = {e['key']: i for i, e in enumerate(plan['entries'])}
                return {'items': [self._refresh_view(nid, scope, r) for r in sorted(old, key=lambda r: positions[r['node_key']])]}
            self._assert_plan(nid, scope, actor, plan, guard)
            result = []
            for entry in plan['entries']:
                brief = self._prepare_brief(nid, scope, actor, entry['state']['kind'], entry['recipe'])
                doc['collections'].setdefault(self.media.BRIEFS, {})[brief['id']] = brief
                task = self.media.prepare_task(nid, scope, actor, {'brief_id': brief['id'], 'expected_brief_version': 1,
                    'adapter_id': entry['state']['adapter']['adapter_id'], 'candidate_count': entry['state']['candidate_count'],
                    'parameters': entry['state']['parameters']})
                pointer = new_row(nid, scope, actor, {'plan_id': rid, 'node_key': entry['key'], 'task_id': task['id'],
                    'idempotency_digest': key, 'request_digest': fingerprint, 'status': 'LINKED', 'reservation_id': None})
                task['change_impact_refresh_id'] = pointer['id']
                brief['change_impact_refresh_id'] = pointer['id']
                task['brief_snapshot'] = snapshot(brief)
                task['source_digest'] = digest(snapshot(brief))
                doc['collections'].setdefault(self.media.TASKS, {})[task['id']] = task
                rows[pointer['id']] = pointer; result.append(pointer)
            self._assert_plan(nid, scope, actor, plan, guard)
            return {'items': [self._refresh_view(nid, scope, r) for r in result]}

    def _refresh_view(self, nid, scope, row):
        task = self.media.get(nid, scope, self.media.TASKS, row['task_id'])
        nodes, _ = self._inventory(nid, scope)
        # Callers filter unavailable originals; never serialize hidden old IDs.
        if row['node_key'] not in nodes: raise FileNotFoundError('refresh source unavailable')
        try: self.media._current_brief(nid, scope, task); current = True
        except (FileNotFoundError, ValueError): current = False
        return {'id': row['id'], 'version': row['version'], 'node_key': row['node_key'], 'task_id': task['id'],
                'task_version': task['version'], 'status': task['status'], 'source_current': current,
                'outputs': [{'id': pid, 'status': self.media.get(nid, scope, self.media.PROPOSALS, pid)['status']} for pid in task['proposal_ids']],
                'automatic_approval': False, 'recovery': 'FRESH_PREFLIGHT_NEW_TASK_REQUIRED' if task['status'] in {'FAILED', 'CANCELLED'} or not current else None}

    def refreshes(self, nid, scope, actor):
        self._active()
        if not self.enabled('cover_storyboard_generation') or not self.enabled('media_adapter_registry'): return {'items': []}
        rows = []
        for r in self.list(nid, scope, self.REFRESHES):
            if r['created_by'] != actor: continue
            try: rows.append(self._refresh_view(nid, scope, r))
            except (FileNotFoundError, ValueError): continue
        return {'items': rows}

    def execute(self, nid, scope, actor, rid, expected_task_version, guard=lambda: None):
        self._active(); guard()
        row = self.get(nid, scope, self.REFRESHES, rid)
        if row['created_by'] != actor: raise FileNotFoundError('refresh unavailable')
        plan = self.get(nid, scope, self.PLANS, row['plan_id'])
        entry = next(e for e in plan['entries'] if e['key'] == row['node_key'])
        # Each explicit task dispatch checks only its selected node. Another
        # selected node failing cannot invalidate a completed unrelated result.
        single = {**plan, 'selected': [next(e for e in plan['selected'] if e['key'] == row['node_key'])], 'entries': [entry]}
        def current(): self._assert_plan(nid, scope, actor, single, guard)
        current()
        task = self.media.get(nid, scope, self.media.TASKS, row['task_id']); check_version(task, expected_task_version)
        if task['status'] != 'QUEUED': raise ValueError('CHANGE_IMPACT_TASK_NOT_QUEUED')
        reservation_id = row.get('reservation_id')
        broker = self.production.broker
        if entry['state']['broker_required']:
            reservation = broker.reserve(nid, scope, actor, entry['broker_decision_id'], entry['broker_decision_version'],
                'change-impact:' + rid, task['id'], current)
            reservation_id = reservation['id']
            with self.store.transaction(nid, scope) as doc:
                current(); doc['collections'][self.REFRESHES][rid]['reservation_id'] = reservation_id
        def dispatch(actual, adapter):
            current()
            if actual['id'] != task['id'] or not supported_local_image(adapter): raise ValueError('CHANGE_IMPACT_TASK_BINDING_CHANGED')
            if reservation_id: broker.guard_dispatch(nid, scope, actor, reservation_id, task['id'], current)
            latest = self.media.get(nid, scope, self.media.TASKS, task['id'])
            if latest['status'] != 'RUNNING' or latest.get('execution_token') != actual.get('execution_token') or latest['version'] != actual['version']:
                raise ValueError('CHANGE_IMPACT_TASK_CANCELLED')
        try:
            self.media.execute(nid, scope, actor, task['id'], expected_task_version, current, change_impact_guard=dispatch)
        finally:
            if reservation_id:
                status = self.media.get(nid, scope, self.media.TASKS, task['id'])['status']
                if status not in {'QUEUED', 'RUNNING'}: broker.finalize(nid, scope, actor, reservation_id, task['id'], {'SUCCEEDED': 'COMPLETED', 'FAILED': 'FAILED', 'CANCELLED': 'CANCELLED'}.get(status, 'UNKNOWN'))
        guard(); self._active()
        return self._refresh_view(nid, scope, self.get(nid, scope, self.REFRESHES, rid))

    def cancel(self, nid, scope, actor, rid, version, guard=lambda: None):
        self._active(); guard()
        row = self.get(nid, scope, self.REFRESHES, rid)
        if row['created_by'] != actor: raise FileNotFoundError('refresh unavailable')
        self.media.transition(nid, scope, actor, row['task_id'], 'cancel', version)
        reservation_id = row.get('reservation_id')
        if self.production.broker:
            if not reservation_id:
                candidate = digest([actor, 'change-impact:' + rid])
                try:
                    entry = self.production.broker.get(nid, scope, self.production.broker.LEDGER, candidate)
                    if entry.get('job_id') == row['task_id'] and entry.get('created_by') == actor: reservation_id = candidate
                except FileNotFoundError: pass
            if reservation_id: self.production.broker.finalize(nid, scope, actor, reservation_id, row['task_id'], 'CANCELLED')
        guard(); self._active()
        return self._refresh_view(nid, scope, row)
