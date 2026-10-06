"""Temporal relations and fictional knowledge over the existing world authority.

No character copies, model calls, manuscript writes, or background scans. All
extension records use WorldService's versioned review transaction. Character
projections are built from explicit approved knowledge events before serialization.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import Field, model_validator

from .common import StaleSourceError, change_row
from .planning import StrictModel, collection, digest, entity_sources, require_row, scoped_sources
from .world import WorldService

GRAPH_KINDS = frozenset({'STORY_CONCEPT', 'STORY_RELATION', 'KNOWLEDGE_EVENT'})


class GraphNode(StrictModel):
    kind: Literal['CHARACTER', 'LOCATION', 'CHAPTER', 'SCENE', 'ORGANIZATION', 'EVENT', 'RULE', 'ITEM', 'OBJECT', 'SECRET', 'FORESHADOWING']
    id: str = Field(min_length=1, max_length=160)


class Evidence(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=160)
    quote: str = Field(min_length=1, max_length=4000)
    start: int = Field(ge=0)


class TemporalData(StrictModel):
    # Existing planning Scene identity, never a duplicate scene store.
    scene_id: str | None = Field(default=None, min_length=1, max_length=160)
    world_time: int | None = None
    valid_from: int | None = None
    valid_to: int | None = None
    calendar: str = Field(default='story', min_length=1, max_length=80)
    until_chapter_id: str | None = Field(default=None, max_length=160)
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def interval(self):
        if self.valid_to is not None and self.valid_from is not None and self.valid_to <= self.valid_from:
            raise ValueError('valid_to must be later than valid_from (exclusive end)')
        return self


class ConceptData(TemporalData):
    concept_type: Literal['ITEM', 'OBJECT', 'SECRET', 'FORESHADOWING']
    description: str = Field(default='', max_length=8000)


class RelationData(TemporalData):
    subject: GraphNode
    object: GraphNode
    relation: Literal['LOCATED_AT', 'MEMBER_OF', 'OWNS', 'ALLIED_WITH', 'OPPOSES', 'CAUSES', 'PRECEDES', 'REVEALS', 'FORESHADOWS', 'CONTRADICTS', 'ABOUT', 'KNOWS', 'BELIEVES', 'BELONGS_TO', 'HATES', 'TRUSTS', 'RELATED_TO', 'APPEARS_IN']
    layer: Literal['WORLD_FACT', 'CHARACTER_BELIEF', 'RESEARCH', 'SPECULATION']
    statement: str = Field(min_length=1, max_length=8000)
    observer_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode='after')
    def observer(self):
        if self.layer == 'CHARACTER_BELIEF' and not self.observer_id:
            raise ValueError('character belief requires an observer')
        return self


class KnowledgeData(TemporalData):
    character_id: str = Field(min_length=1, max_length=160)
    operation: Literal['LEARN', 'HEARSAY', 'FORGET', 'MISUNDERSTAND', 'CORRECT', 'GOAL_CHANGE', 'SET_STATE']
    category: Literal['KNOWN_FACT', 'BELIEF', 'FALSE_BELIEF', 'SECRET', 'GOAL', 'FEAR', 'VALUE', 'EMOTION', 'INTENT', 'RELATIONSHIP_STATE']
    relation_id: str | None = Field(default=None, max_length=160)
    psychology_id: str | None = Field(default=None, max_length=160)
    value: str = Field(default='', max_length=8000)
    state_key: str = Field(default='current', min_length=1, max_length=160)
    evidence_status: Literal['EXPLICIT', 'HYPOTHESIS'] = 'HYPOTHESIS'

    @model_validator(mode='after')
    def operation_shape(self):
        if self.category in {'KNOWN_FACT', 'BELIEF', 'FALSE_BELIEF', 'SECRET'} and not self.relation_id:
            raise ValueError('knowledge requires a reviewed relation')
        if self.operation in {'MISUNDERSTAND', 'HEARSAY'} and self.category not in {'BELIEF', 'FALSE_BELIEF'}:
            raise ValueError('hearsay and misunderstanding are beliefs, never facts')
        if self.operation == 'MISUNDERSTAND' and self.category != 'FALSE_BELIEF':
            raise ValueError('misunderstanding requires FALSE_BELIEF')
        if self.category in {'BELIEF', 'FALSE_BELIEF', 'GOAL', 'FEAR', 'VALUE', 'EMOTION', 'INTENT', 'RELATIONSHIP_STATE'} and not self.value and self.operation != 'FORGET':
            raise ValueError('this knowledge change needs its own explicit value')
        if self.category == 'RELATIONSHIP_STATE' and not self.relation_id:
            raise ValueError('relationship state requires a reviewed relation')
        if self.operation == 'GOAL_CHANGE' and self.category != 'GOAL':
            raise ValueError('goal change requires GOAL')
        return self


MODELS = {'STORY_CONCEPT': ConceptData, 'STORY_RELATION': RelationData, 'KNOWLEDGE_EVENT': KnowledgeData}


class StoryRecordIn(StrictModel):
    kind: Literal['STORY_CONCEPT', 'STORY_RELATION', 'KNOWLEDGE_EVENT']
    title: str = Field(min_length=1, max_length=240)
    chapter_id: str = Field(min_length=1, max_length=160)
    event_order: int = Field(default=0, ge=0, le=1000000)
    data: dict

    @model_validator(mode='after')
    def typed(self):
        self.data = MODELS[self.kind].model_validate(self.data).model_dump()
        return self


class StoryRecordEditIn(StoryRecordIn):
    expected_version: int = Field(ge=1)


def scene_boundary(service, nid, scope, scene_id, chapter_id, state):
    """Resolve the original Scene's fresh identity and unambiguous sibling order."""
    if not scene_id: return None
    row = require_row(state, 'planning_nodes', scene_id)
    graph = require_row(state, 'planning_graphs', row['graph_id'])
    if row['level'] != 'SCENE' or row['status'] == 'ARCHIVED' or graph['status'] != 'ACTIVE':
        raise StaleSourceError('scene is unavailable')
    if row['links']['chapter_ids'] != [chapter_id]:
        raise ValueError('scene must belong to the selected chapter')
    from .planning import PlanningService
    ancestors = PlanningService(service.store, service.novels, service.chapters)._ancestors(state, row)
    sources = scoped_sources(service, nid, scope, list(row.get('sources', {})))
    if sources != row.get('sources', {}): raise StaleSourceError('scene sources changed')
    siblings = [item for item in collection(state, 'planning_nodes').values()
                if item['parent_id'] == row['parent_id'] and item['status'] != 'ARCHIVED']
    positions = [item['position'] for item in siblings]
    if len(positions) != len(set(positions)):
        raise ValueError('scene order is ambiguous; assign distinct original planning positions')
    stamps = {item['id']: digest({k: v for k, v in item.items() if k != 'history'})
              for item in [row, graph, *ancestors]}
    return {'id': scene_id, 'chapter_id': chapter_id, 'parent_id': row['parent_id'],
            'position': row['position'], 'version': row['version'], 'digest': digest(stamps)}


def capture_graph(service, nid, scope, payload, state):
    """Source capture shared with WorldService; no second review authority."""
    data, kind = payload['data'], payload['kind']
    chapters = [payload['chapter_id']]
    if data['until_chapter_id']:
        chapters.append(data['until_chapter_id'])
    chapters += [item['chapter_id'] for item in data['evidence']]
    sources = scoped_sources(service, nid, scope, chapters)
    start = service._chapter(nid, scope, payload['chapter_id'])['narrative_sequence']
    end = service._chapter(nid, scope, data['until_chapter_id'])['narrative_sequence'] if data['until_chapter_id'] else None
    if end is not None and end <= start:
        raise ValueError('end chapter must follow the originating chapter')
    for item in data['evidence']:
        content = service.chapters.get(item['chapter_id']).get('content', '')
        if content[item['start']:item['start'] + len(item['quote'])] != item['quote']:
            raise ValueError('evidence quote does not match source at the selected offset')
    links = {'character_ids': [], 'location_ids': []}
    entities, semantic = {}, {}
    scene = scene_boundary(service, nid, scope, data.get('scene_id'), payload['chapter_id'], state)
    if scene: entities['viewpoint_scene:' + scene['id']] = scene['digest']

    def world_ref(rid, allowed):
        row = require_row(state, service.RECORDS, rid)
        if row['status'] != 'APPROVED' or row['kind'] not in allowed:
            raise ValueError('reference must identify an approved record of the correct kind')
        semantic[rid] = {'version': row['version'], 'digest': digest({key: value for key, value in row.items() if key != 'history'})}
        return row

    def node(ref):
        rid, node_kind = ref['id'], ref['kind']
        if node_kind in {'CHARACTER', 'LOCATION'}:
            links['character_ids' if node_kind == 'CHARACTER' else 'location_ids'].append(rid)
        elif node_kind == 'CHAPTER':
            sources.update(scoped_sources(service, nid, scope, [rid]))
            service._chapter(nid, scope, rid)
        elif node_kind == 'SCENE':
            row = require_row(state, 'planning_nodes', rid)
            graph = require_row(state, 'planning_graphs', row['graph_id'])
            if row['level'] != 'SCENE' or row['status'] == 'ARCHIVED' or graph['status'] != 'ACTIVE':
                raise ValueError('scene is unavailable')
            from .planning import PlanningService
            for ancestor in PlanningService(service.store, service.novels, service.chapters)._ancestors(state, row):
                entities['planning_ancestor:' + ancestor['id']] = digest({key: value for key, value in ancestor.items() if key != 'history'})
            entities['scene:' + rid] = digest({key: value for key, value in row.items() if key != 'history'})
            entities['planning_graph:' + graph['id']] = digest({key: value for key, value in graph.items() if key != 'history'})
            sources.update(scoped_sources(service, nid, scope, list(row.get('sources', {}))))
            if row.get('sources', {}) != {key: sources[key] for key in row.get('sources', {})}:
                raise StaleSourceError('planning scene sources changed')
        else:
            expected = {'ORGANIZATION': 'CIVILIZATION', 'EVENT': 'HISTORY', 'RULE': 'ABILITY'}.get(node_kind, 'STORY_CONCEPT')
            row = world_ref(rid, {expected})
            if expected == 'STORY_CONCEPT' and row['data']['concept_type'] != node_kind:
                raise ValueError('concept type mismatch')

    if kind == 'STORY_RELATION':
        node(data['subject']); node(data['object'])
        if data['observer_id']: links['character_ids'].append(data['observer_id'])
    elif kind == 'KNOWLEDGE_EVENT':
        links['character_ids'].append(data['character_id'])
        if data['relation_id']:
            relation = world_ref(data['relation_id'], {'STORY_RELATION'})
            if data['category'] in {'KNOWN_FACT', 'SECRET'} and relation['data']['layer'] != 'WORLD_FACT':
                raise ValueError('research, speculation and belief cannot become known world fact')
            observer = relation['data'].get('observer_id')
            if relation['data']['layer'] == 'CHARACTER_BELIEF' and observer != data['character_id']:
                raise ValueError('another character belief must be recorded as a new hearsay claim')
        if data['psychology_id']:
            psychology = world_ref(data['psychology_id'], {'PSYCHOLOGY'})
            if psychology['data']['character_id'] != data['character_id']:
                raise ValueError('psychology belongs to another character')
    links = {key: sorted(set(value)) for key, value in links.items()}
    # Existing legacy entity references are allowed locally. A branch requires
    # genuinely branch-owned sources; unbranched manuscript is never evidence.
    entities.update(entity_sources(service, nid, scope, links, state))
    return {'sources': sources, 'effective_chapter': start, 'effective_until': end,
            'links': links, 'entity_sources': entities, 'semantic_sources': semantic,
            **({'effective_scene_position': scene['position'], 'effective_scene_parent_id': scene['parent_id']} if scene else {})}


class StoryGraphService(WorldService):
    supports_graph = True
    INDEX = 'story_graph_index'
    MAX_RECORDS = 5000

    def _payload(self, value):
        return StoryRecordIn.model_validate(value.model_dump() if hasattr(value, 'model_dump') else value).model_dump()

    def records(self, nid, scope):
        state, rows = self._rows(nid, scope)
        return [self._decorate(nid, scope, row, state) for row in rows.values() if row['kind'] in GRAPH_KINDS]

    def record(self, nid, scope, rid):
        row = super().record(nid, scope, rid)
        if row['kind'] not in GRAPH_KINDS: raise FileNotFoundError(rid)
        return row

    def edit_record(self, nid, scope, actor, rid, value, *, reauthorize=lambda: None):
        raw = value.model_dump() if hasattr(value, 'model_dump') else dict(value)
        self.record(nid, scope, rid)
        return super().edit_record(nid, scope, actor, rid, raw, reauthorize=reauthorize)

    def _validate_create_capacity(self, state):
        if len(collection(state, self.RECORDS)) >= self.MAX_RECORDS:
            raise ValueError('bounded graph capacity reached; partition the project')

    def catalog(self, nid, scope):
        state, _ = self._rows(nid, scope)
        result = []
        for dataset, kind in [('characters', 'CHARACTER'), ('locations', 'LOCATION')]:
            for row in self.novels.data_set(nid, dataset):
                if row.get('branch_id') and row['branch_id'] != scope.get('branch_id'): continue
                result.append({'kind': kind, 'id': row['id'], 'label': row.get('name') or row['id']})
        for row in self.chapters.list(nid):
            if scope.get('mode') == 'collaboration' and row.get('branch_id') != scope.get('branch_id'): continue
            result.append({'kind': 'CHAPTER', 'id': row['id'], 'label': row.get('title') or str(row['number'])})
        for row in collection(state, 'planning_nodes').values():
            if row['level'] == 'SCENE' and row['status'] != 'ARCHIVED':
                result.append({'kind': 'SCENE', 'id': row['id'], 'label': row['title'], 'chapter_id': row['links']['chapter_ids'][0], 'position': row['position']})
        for row in collection(state, self.RECORDS).values():
            if row['status'] != 'APPROVED': continue
            kind = {'CIVILIZATION': 'ORGANIZATION', 'HISTORY': 'EVENT', 'ABILITY': 'RULE'}.get(row['kind'])
            if row['kind'] == 'STORY_CONCEPT': kind = row['data']['concept_type']
            if kind: result.append({'kind': kind, 'id': row['id'], 'label': row['title']})
        return {'items': result, 'author_only': True}

    def _rows(self, nid, scope):
        self.novels.get(nid)
        state = self.store.read(nid, scope)
        rows = collection(state, self.RECORDS)
        for rid in rows: require_row(state, self.RECORDS, rid)
        if len(rows) > self.MAX_RECORDS: raise ValueError('graph exceeds bounded query capacity')
        return state, rows

    def _narrative_reached(self, nid, scope, row, state, chapter_number, scene):
        number = row.get('effective_chapter', 0)
        if number > chapter_number: return False
        if scene is None or number < chapter_number: return True
        if not row['data'].get('scene_id'): return False
        # Reviewed boundary, not a later edited scene order: stale forgets stay tombstones.
        return (row.get('effective_scene_parent_id') == scene['parent_id']
                and row.get('effective_scene_position', float('inf')) <= scene['position'])

    def _current(self, nid, scope, row, state, chapter_number, world_time, calendar, scene=None):
        if row['status'] != 'APPROVED' or not self._narrative_reached(nid, scope, row, state, chapter_number, scene): return False
        if row.get('effective_until') is not None and chapter_number >= row['effective_until']: return False
        data = row['data']
        if world_time is not None:
            # Unknown time stays unknown; it never becomes zero or "always".
            if data.get('calendar') != calendar or all(data.get(key) is None for key in ('world_time', 'valid_from', 'valid_to')): return False
            if data.get('world_time') is not None and data['world_time'] > world_time: return False
            if data.get('valid_from') is not None and world_time < data['valid_from']: return False
            if data.get('valid_to') is not None and world_time >= data['valid_to']: return False
        try: self._assert_fresh(nid, scope, row, state)
        except (ValueError, FileNotFoundError): return False
        return True

    @staticmethod
    def _evidence(row):
        # Never serialize quoted chapter text to a character/adapter merely
        # because it was the author evidence for a knowledge change.
        return {'record_id': row['id'], 'record_version': row['version'], 'chapter_id': row['chapter_id'],
                'source_versions': deepcopy(row['sources'])}

    def _projection(self, nid, scope, character_id, chapter_id, world_time=None, calendar='story', scene_id=None):
        entity_sources(self, nid, scope, {'character_ids': [character_id]})
        number = self._chapter(nid, scope, chapter_id)['narrative_sequence']
        state, rows = self._rows(nid, scope)
        scene = scene_boundary(self, nid, scope, scene_id, chapter_id, state)
        active = {rid: row for rid, row in rows.items() if row['kind'] in GRAPH_KINDS and self._current(nid, scope, row, state, number, world_time, calendar, scene)}
        # A stale or revoked later change must not resurrect older knowledge.
        # Candidates have no effect. An archived previously approved change is
        # retained as a tombstone for its key until explicitly corrected.
        events, uncertain = [], []
        for row in rows.values():
            if row['kind'] != 'KNOWLEDGE_EVENT' or row['data']['character_id'] != character_id or row['effective_chapter'] > number:
                continue
            if row['status'] != 'APPROVED' and not any(prior['status'] == 'APPROVED' for prior in row.get('history', [])):
                continue
            data = row['data']
            if world_time is not None:
                if data['calendar'] != calendar or all(data.get(key) is None for key in ('world_time', 'valid_from', 'valid_to')): continue
                if data['world_time'] is not None and data['world_time'] > world_time: continue
                if data['valid_from'] is not None and data['valid_from'] > world_time: continue
            if not self._narrative_reached(nid, scope, row, state, number, scene):
                if scene and row['effective_chapter'] == number and (not data.get('scene_id') or row.get('effective_scene_parent_id') != scene['parent_id']): uncertain.append(row)
                continue
            events.append(row)
        events.sort(key=lambda row: (row['effective_chapter'], row.get('effective_scene_position', float('inf')), *self._order(row)[1:]))
        knowledge, mental = {}, {}
        for event in events:
            data = event['data']; rid = data['relation_id']
            epistemic = data['category'] in {'KNOWN_FACT', 'BELIEF', 'FALSE_BELIEF', 'SECRET'}
            key = rid if epistemic else (data['category'], data['state_key'])
            target = knowledge if epistemic else mental
            if event['id'] not in active or data['operation'] == 'FORGET': target.pop(key, None); continue
            if rid and rid not in active:
                target.pop(key, None)
                continue
            target[key] = event
        for event in uncertain:
            data = event['data']
            if data['category'] in {'KNOWN_FACT', 'BELIEF', 'FALSE_BELIEF', 'SECRET'}: knowledge.pop(data['relation_id'], None)
            else: mental.pop((data['category'], data['state_key']), None)
        return active, knowledge, mental, scene

    def character_context(self, nid, scope, character_id, chapter_id, world_time=None, calendar='story', scene_id=None):
        active, knowledge, mental, scene = self._projection(nid, scope, character_id, chapter_id, world_time, calendar, scene_id)
        result = {'contract': 'CHARACTER_KNOWLEDGE_V1', 'character_id': character_id, 'chapter_id': chapter_id,
                  'world_time': world_time, 'calendar': calendar, 'known_facts': [], 'beliefs': [], 'false_beliefs': [],
                  'secrets': [], 'goals': [], 'fears': [], 'values': [], 'emotion': [], 'intent': [], 'verification': 'DETERMINISTIC_REVIEWED_EVENTS'}
        categories = {'KNOWN_FACT': 'known_facts', 'BELIEF': 'beliefs', 'FALSE_BELIEF': 'false_beliefs', 'SECRET': 'secrets',
                      'GOAL': 'goals', 'FEAR': 'fears', 'VALUE': 'values', 'EMOTION': 'emotion', 'INTENT': 'intent', 'RELATIONSHIP_STATE': 'relationships'}
        if scene_id: result.update(scene_id=scene_id, scene_boundary=scene)
        for event in [*knowledge.values(), *mental.values()]:
            data = event['data']; relation = active.get(data['relation_id'])
            text = relation['data']['statement'] if relation and data['category'] in {'KNOWN_FACT', 'SECRET'} else data['value']
            result.setdefault(categories[data['category']], []).append({'text': text, 'epistemic_status': data['category'],
                'evidence_status': data['evidence_status'], 'evidence': self._evidence(event),
                'relation_version': relation['version'] if relation else None})
        result['context_digest'] = digest(result)
        return result

    def graph(self, nid, scope, chapter_id, character_id=None, world_time=None, calendar='story', scene_id=None):
        number = self._chapter(nid, scope, chapter_id)['narrative_sequence']
        if character_id:
            active, knowledge, _, scene = self._projection(nid, scope, character_id, chapter_id, world_time, calendar, scene_id)
            # False beliefs expose their own assertion, never true endpoints,
            # labels, tooltips, source quotes, or counts of hidden relations.
            selected = [active[rid] for rid, event in knowledge.items() if event['data']['category'] in {'KNOWN_FACT', 'SECRET'}]
        else:
            state, rows = self._rows(nid, scope)
            scene = scene_boundary(self, nid, scope, scene_id, chapter_id, state)
            selected = [row for row in rows.values() if row['kind'] == 'STORY_RELATION' and self._current(nid, scope, row, state, number, world_time, calendar, scene)]
        edges, nodes = [], {}
        for row in selected:
            data = row['data']
            for ref in (data['subject'], data['object']):
                # IDs and node types suffice; full entity descriptions may hold
                # secrets unrelated to this relation and are never loaded here.
                nodes[(ref['kind'], ref['id'])] = deepcopy(ref)
            edges.append({'id': row['id'], 'version': row['version'], 'subject': data['subject'], 'object': data['object'],
                'relation': data['relation'], 'layer': data['layer'], 'statement': data['statement'], 'world_time': data['world_time'],
                'time_state': 'UNKNOWN' if data['world_time'] is None else 'KNOWN', 'valid_from': data['valid_from'], 'valid_to': data['valid_to'],
                'calendar': data['calendar'], 'evidence': self._evidence(row)})
        return {'perspective': 'CHARACTER' if character_id else 'AUTHOR', 'character_id': character_id, 'chapter_id': chapter_id,
                **({'scene_id': scene_id, 'scene_boundary': scene} if scene_id else {}), 'nodes': list(nodes.values()), 'edges': edges, 'visible_count': len(edges), 'verification': 'DETERMINISTIC_REVIEWED_RELATIONS'}

    def impact(self, nid, scope, rid):
        state, rows = self._rows(nid, scope)
        require_row(state, self.RECORDS, rid)
        impacted, frontier = set(), {rid}
        # Each record is visited at most once, with a hard scope capacity bound.
        while frontier:
            found = {key for key, row in rows.items() if key not in impacted and key != rid and set(row.get('semantic_sources', {})) & frontier}
            impacted |= found; frontier = found
        return {'source_record_id': rid, 'items': [{'id': key, 'kind': rows[key]['kind'], 'version': rows[key]['version'],
                'stale': self._decorate(nid, scope, rows[key], state)['stale']} for key in sorted(impacted)], 'affected_count': len(impacted)}

    def _refresh_index(self, nid, scope, actor, rid, state):
        from .common import new_row
        ids = [rid] + [item['id'] for item in self.impact(nid, scope, rid)['items']]
        index = collection(state, self.INDEX)
        for key in ids:
            source = require_row(state, self.RECORDS, key)
            stale = self._decorate(nid, scope, source, state)['stale']
            data = {'source_record_id': key, 'source_version': source['version'], 'stale': stale,
                    'status': 'INVALID' if source['status'] != 'APPROVED' or stale else 'CURRENT',
                    'dependency_ids': sorted(source.get('semantic_sources', {}))}
            if key in index: change_row(index[key], actor, index[key]['version'], lambda target, data=data: target.update(data))
            else: index[key] = new_row(nid, scope, actor, data)
        return ids

    def _after_record_mutation(self, state, row, actor):
        # Revoke/approve/edit and their affected index entries commit together.
        self._refresh_index(row['novel_id'], row['scope'], actor, row['id'], state)

    def recompute(self, nid, scope, actor, rid, expected_version, *, reauthorize=lambda: None):
        with self.store.transaction(nid, scope) as state:
            reauthorize()
            row = require_row(state, self.RECORDS, rid)
            from .common import check_version
            check_version(row, expected_version)
            ids = self._refresh_index(nid, scope, actor, rid, state)
            reauthorize()
            return {'recomputed_ids': ids, 'count': len(ids), 'source_version': expected_version, 'scope_only': True}

    def list_review_items(self, nid, scope):
        return [{**row, 'domain': 'story_graph', 'source': 'world_semantic_engine', 'preview': row['title'],
                 'target': {'kind': row['kind'], 'chapter_id': row['chapter_id']}, 'source_versions': row['sources'],
                 'risk': 'REVIEWED_SEMANTIC_METADATA', 'safe_batch': False,
                 'allowed_actions': ['approve', 'reject'] if row['status'] == 'REVIEW' else ['reopen'] if row['status'] in {'REJECTED', 'ARCHIVED'} else []} for row in self.records(nid, scope)]
