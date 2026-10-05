"""Bounded manual story transitions, isolated from manuscript and Canon.

Only reviewed A04/A05 character-visible evidence is resolved. User-authored
hypotheses stay hypotheses. Saving creates an original R3 REVIEW proposal.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import StaleSourceError, check_version, change_row, new_row
from ..services.v1_capability_service import CapabilityVersionConflict
from .planning import StrictModel, PlanningProposalIn, collection, require_row, digest, entity_sources
from .style_analysis import SourceFencedService
from .character_author_context import CharacterProjection

FEATURE = 'story_simulator_v2'
METHOD = 'bounded-manual-transitions-v1'
LIMITS = {'max_steps': 32, 'max_branches': 8, 'max_expansions': 256}
Symbol = Annotated[str, Field(min_length=1, max_length=160)]
Amount = Annotated[int, Field(ge=-1_000_000, le=1_000_000)]
Quantity = Annotated[int, Field(ge=0, le=1_000_000)]


class SimulatorContextIn(StrictModel):
    chapter_id: Symbol
    expected_version: int = Field(ge=1)
    character_id: Symbol
    world_time: int | None = None
    calendar: str = Field(default='story', min_length=1, max_length=80)


class SimulationEvent(StrictModel):
    id: Symbol
    title: str = Field(min_length=1, max_length=240)
    at: int
    requires: list[Symbol] = Field(default_factory=list, max_length=32)
    adds: list[Symbol] = Field(default_factory=list, max_length=32)
    removes: list[Symbol] = Field(default_factory=list, max_length=32)
    requires_knowledge: list[Symbol] = Field(default_factory=list, max_length=32)
    resource_delta: dict[Symbol, Amount] = Field(default_factory=dict, max_length=32)
    foreshadowing_links: list[Symbol] = Field(default_factory=list, max_length=20)
    question: str = Field(default='', max_length=1000)


class SimulationRoute(StrictModel):
    id: Symbol
    title: str = Field(min_length=1, max_length=240)
    motivation_hypothesis: str = Field(default='', max_length=2000)
    events: list[SimulationEvent] = Field(min_length=1, max_length=32)

    @model_validator(mode='after')
    def unique_events(self):
        if len({e.id for e in self.events}) != len(self.events):
            raise ValueError('each event needs a unique route-local ID')
        return self


class HardConstraints(StrictModel):
    forbidden_facts: list[Symbol] = Field(default_factory=list, max_length=32)
    required_final_facts: list[Symbol] = Field(default_factory=list, max_length=32)
    resource_caps: dict[Symbol, Quantity] = Field(default_factory=dict, max_length=32)


class SimulationRunIn(StrictModel):
    chapter_ids: list[Symbol] = Field(min_length=1, max_length=20)
    expected_versions: dict[Symbol, int] = Field(min_length=1, max_length=20)
    chapter_id: Symbol
    character_id: Symbol
    world_time: int | None = None
    calendar: str = Field(default='story', min_length=1, max_length=80)
    node_id: Symbol
    expected_node_version: int = Field(ge=1)
    context_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    assumptions: list[Symbol] = Field(default_factory=list, max_length=32)
    character_goal: str = Field(default='', max_length=2000)
    motivation_hypothesis: str = Field(default='', max_length=2000)
    knowledge_ids: list[Symbol] = Field(default_factory=list, max_length=100)
    resources: dict[Symbol, Quantity] = Field(default_factory=dict, max_length=32)
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    max_steps: int = Field(default=8, ge=1, le=32)
    max_branches: int = Field(default=3, ge=1, le=8)
    model_id: str | None = Field(default=None, max_length=160)
    model_budget: int = Field(default=0, ge=0, le=0)
    routes: list[SimulationRoute] = Field(min_length=1, max_length=8)

    @model_validator(mode='after')
    def bounded(self):
        if len({r.id for r in self.routes}) != len(self.routes): raise ValueError('route IDs must be unique')
        if len(self.routes) > self.max_branches: raise ValueError('route count exceeds branch limit')
        if len(set(self.chapter_ids)) != len(self.chapter_ids) or set(self.expected_versions) != set(self.chapter_ids):
            raise ValueError('provide exactly the selected unique chapter versions')
        if self.chapter_id not in self.chapter_ids: raise ValueError('viewpoint chapter must be selected')
        if self.model_id: raise ValueError('SIMULATOR_MODEL_NOT_CONFIGURED: manual rules remain available')
        if set(self.assumptions) & set(self.hard_constraints.forbidden_facts): raise ValueError('initial assumptions violate forbidden facts')
        if any(v > self.hard_constraints.resource_caps.get(k, 1_000_000) for k, v in self.resources.items()):
            raise ValueError('initial resources exceed hard limits')
        return self


class SimulationActionIn(StrictModel):
    expected_version: int = Field(ge=1)


class SimulationSaveIn(SimulationActionIn):
    route_id: Symbol


def violation(code, message, event_id=None):
    return {'code': code, 'message': message, **({'event_id': event_id} if event_id else {})}


def change_run(row, actor, expected_version, callback):
    # Inputs are immutable and every round is replayable. Keep bounded audit
    # receipts rather than duplicating all route inputs/state on every step.
    change_row(row, actor, expected_version, callback)
    previous = row['history'][-1]
    row['history'][-1] = {key: deepcopy(previous[key]) for key in
                         ('id', 'version', 'status', 'updated_by', 'updated_at', 'request_digest', 'result_digest', 'expansions')}


def transition(state, event, knowledge_ids, graph_ids, constraints):
    """A failed event is observed but does not mutate hypothetical state."""
    after = deepcopy(state); errors = []
    if not set(event['requires']).issubset(state['facts']):
        errors.append(violation('UNMET_PREREQUISITE', '事件前提尚未满足。'))
    if state['time'] is not None and event['at'] < state['time']:
        errors.append(violation('TEMPORAL_ORDER', '事件时间早于当前路线状态。'))
    if not set(event['requires_knowledge']).issubset(knowledge_ids):
        errors.append(violation('INACCESSIBLE_KNOWLEDGE', '此事件需要角色在所选知识边界内不可用的知识。'))
    if not set(event['foreshadowing_links']).issubset(graph_ids):
        errors.append(violation('UNAVAILABLE_FORESHADOWING', '伏笔关联不在本次角色可见的已审核图谱中。'))
    facts = (set(state['facts']) - set(event['removes'])) | set(event['adds'])
    if facts & set(constraints['forbidden_facts']):
        errors.append(violation('HARD_CONSTRAINT', '事件会产生被硬约束禁止的状态。'))
    resources = deepcopy(state['resources'])
    for key, amount in event['resource_delta'].items():
        resources[key] = resources.get(key, 0) + amount
        if not 0 <= resources[key] <= constraints['resource_caps'].get(key, 1_000_000):
            errors.append(violation('RESOURCE_CONFLICT', f'资源 {key} 不足或超过上限。'))
    if not errors: after.update(facts=sorted(facts), resources=resources, time=event['at'])
    return after, errors


class StorySimulatorService(SourceFencedService):
    RUNS = 'story_simulation_runs'

    def __init__(self, store, novels, chapters, planning, story_graph):
        super().__init__(store, novels, chapters)
        self.planning, self.story_graph = planning, story_graph
        # A transient validator, never persisted credentials or authority.
        self.planning.simulation_validator = self.validate_proposal

    def catalog(self, nid, scope):
        state = self.store.read(nid, scope)
        nodes = []
        for row in collection(state, self.planning.NODES).values():
            require_row(state, self.planning.NODES, row['id'])
            if row['status'] == 'ARCHIVED' or require_row(state, self.planning.GRAPHS, row['graph_id'])['status'] != 'ACTIVE': continue
            nodes.append({'id': row['id'], 'title': row['title'], 'version': row['version'], 'chapter_ids': row['links']['chapter_ids']})
        return {'chapters': self.chapter_catalog(nid, scope), 'planning_nodes': nodes,
                'characters': [{'id': r['id'], 'name': r.get('name', r['id'])} for r in self.novels.data_set(nid, 'characters') if not r.get('branch_id') or r['branch_id'] == scope.get('branch_id')],
                'limits': deepcopy(LIMITS), 'model_configured': False}

    def _context(self, nid, scope, data):
        context = CharacterProjection.model_validate(self.story_graph.character_context(nid, scope, data['character_id'], data['chapter_id'], data['world_time'], data['calendar'])).model_dump()
        graph = self.story_graph.graph(nid, scope, data['chapter_id'], data['character_id'], data['world_time'], data['calendar'])
        entries = context['known_facts'] + context['secrets']
        visible = {'knowledge': [{'id': r['evidence']['record_id'], 'version': r['evidence']['record_version'], 'text': r['text'], 'category': r['epistemic_status']} for r in entries],
                   'goals': [{'id': r['evidence']['record_id'], 'version': r['evidence']['record_version'], 'text': r['text'], 'category': r['epistemic_status']} for r in context['goals']],
                   'graph_links': [{'id': r['id'], 'version': r['version'], 'text': r['statement']} for r in graph['edges']],
                   **{k: data[k] for k in ('chapter_id', 'character_id', 'world_time', 'calendar')}}
        # Revalidate all evidence source policies without fetching hidden facts.
        evidence_ids = {cid for section in ('known_facts', 'secrets', 'goals') for r in context[section] for cid in r['evidence']['source_versions']}
        evidence_ids.update(cid for r in graph['edges'] for cid in r['evidence']['source_versions'])
        evidence_sources, _ = self.capture(nid, scope, sorted(evidence_ids))
        visible['context_digest'] = digest([context, graph, evidence_sources, entity_sources(self, nid, scope, {'character_ids': [data['character_id']]})])
        return visible, evidence_sources

    def context(self, nid, scope, value):
        data = SimulatorContextIn.model_validate(value.model_dump() if hasattr(value, 'model_dump') else value).model_dump()
        self.capture(nid, scope, [data['chapter_id']], {data['chapter_id']: data['expected_version']})
        return self._context(nid, scope, data)[0]

    def _plan_capture(self, nid, scope, node_id, state):
        node = require_row(state, self.planning.NODES, node_id)
        if node['status'] == 'ARCHIVED' or require_row(state, self.planning.GRAPHS, node['graph_id'])['status'] != 'ACTIVE':
            raise StaleSourceError('planning target is unavailable')
        return {'version': node['version'], 'ancestors': {r['id']: r['version'] for r in self.planning._ancestors(state, node)},
                'entities': entity_sources(self, nid, scope, node['links'], state), 'links_digest': digest(node['links'])}

    def _fresh(self, nid, scope, row, state=None, proposal=None):
        self.assert_capture(nid, scope, row['sources'])
        self.assert_capture(nid, scope, row['evidence_sources'])
        context, _ = self._context(nid, scope, row['request'])
        if context['context_digest'] != row['request']['context_digest']: raise StaleSourceError('character knowledge or reviewed graph changed')
        state = state if state is not None else self.store.read(nid, scope)
        current = self._plan_capture(nid, scope, row['request']['node_id'], state)
        captured = deepcopy(row['planning_capture'])
        if proposal and proposal.get('status') == 'APPROVED':
            node = require_row(state, self.planning.NODES, row['request']['node_id'])
            if node.get('approved_proposal_id') == proposal['id']:
                captured['version'] = proposal.get('applied_node_version')
                captured['links_digest'] = digest(proposal['links'])
                captured['entities'] = entity_sources(self, nid, scope, proposal['links'], state)
        if current != captured: raise StaleSourceError('planning target or ancestor changed')
        return context

    def validate_proposal(self, nid, scope, proposal, state=None):
        from .flags import require_flag
        from fastapi import HTTPException
        try:
            for flag in (FEATURE, 'advanced_planning_v2', 'temporal_story_graph_v2', 'character_mind_v2'): require_flag(flag)
        except HTTPException as exc: raise StaleSourceError('simulation feature unavailable') from exc
        provenance = proposal.get('simulation_provenance', {})
        state = state if state is not None else self.store.read(nid, scope)
        run = require_row(state, self.RUNS, provenance.get('run_id', ''))
        self._fresh(nid, scope, run, state, proposal)
        route = next((r for r in run['routes'] if r['id'] == provenance.get('route_id')), None)
        if not route or route.get('saved_proposal_id') != proposal['id'] or run['status'] != 'COMPLETED':
            raise StaleSourceError('simulation handoff is unavailable')

    def _public(self, nid, scope, row):
        try: self._fresh(nid, scope, row)
        except (ValueError, FileNotFoundError):
            return {'id': row['id'], 'version': row['version'], 'status': row['status'], 'stale': True,
                    'routes': [], 'model_called': False, 'limitations': ['来源、规划或角色知识已变化；旧路线已隐藏，请按当前来源重新创建推演。']}
        result = {k: deepcopy(v) for k, v in row.items() if k not in {'history', 'sources', 'evidence_sources', 'planning_capture', 'request'}}
        result['routes'] = [{k: deepcopy(v) for k, v in route.items() if k not in {'state', 'seen_states'}} for route in row['routes']]
        return {**result, 'input': deepcopy(row['request']), 'stale': False}

    def runs(self, nid, scope):
        return [self._public(nid, scope, row) for row in self.list(nid, scope, self.RUNS)]

    def run(self, nid, scope, rid):
        return self._public(nid, scope, self.get(nid, scope, self.RUNS, rid))

    def create_run(self, nid, scope, actor, value, reauthorize=lambda: None):
        request = SimulationRunIn.model_validate(value.model_dump() if hasattr(value, 'model_dump') else value).model_dump()
        sources, _ = self.capture(nid, scope, request['chapter_ids'], request['expected_versions'])
        context, evidence_sources = self._context(nid, scope, request)
        if context['context_digest'] != request['context_digest']: raise StaleSourceError('character knowledge changed; refresh its preview')
        available = {r['id'] for r in context['knowledge']}
        if not set(request['knowledge_ids']).issubset(available): raise ValueError('selected knowledge is unavailable at this viewpoint')
        state = self.store.read(nid, scope); node = require_row(state, self.planning.NODES, request['node_id'])
        check_version(node, request['expected_node_version'])
        if not set(node['links']['chapter_ids']).issubset(request['chapter_ids']): raise ValueError('include all planning target chapter sources')
        planning_capture = self._plan_capture(nid, scope, node['id'], state)
        routes = []
        initial = {'facts': sorted(set(request['assumptions'])), 'resources': request['resources'], 'time': request['world_time']}
        for route in request['routes']:
            routes.append({'id': route['id'], 'title': route['title'], 'cursor': 0, 'status': 'PENDING', 'steps': [], 'violations': [], 'unresolved_questions': [],
                           'motivation_hypothesis': route['motivation_hypothesis'] or request['motivation_hypothesis'], 'character_goal': request['character_goal'],
                           'state': deepcopy(initial), 'seen_states': [digest(initial)]})
        input_digest = digest([METHOD, sources, evidence_sources, planning_capture, request])
        row = new_row(nid, scope, actor, {'status': 'READY', 'request': request, 'sources': sources, 'evidence_sources': evidence_sources, 'planning_capture': planning_capture,
                      'chapter_id': request['chapter_id'], 'source_version': sources[request['chapter_id']]['version'], 'routes': routes, 'expansions': 0,
                      'limits': {**LIMITS, 'max_steps': request['max_steps'], 'max_branches': request['max_branches']},
                      'request_digest': input_digest, 'result_digest': digest(routes), 'model_called': False, 'model_budget': 0,
                      'provenance': {'method': METHOD, 'execution': 'DETERMINISTIC_MANUAL', 'source_versions': sources, 'context_digest': context['context_digest'], 'input_digest': input_digest},
                      'limitations': ['只检查作者手工输入的事件，不推测真实未来概率。', '目标与动机是明确标注的作者假设，不是已证明的人物心理。', '未配置模型；没有模型调用、收费或 GPU 等价性声明。']})
        with self.store.transaction(nid, scope) as state:
            if len(collection(state, self.RUNS)) >= 200: raise ValueError('simulation run limit reached')
            reauthorize(); self._fresh(nid, scope, row, state)
            collection(state, self.RUNS)[row['id']] = row
        return self._public(nid, scope, row)

    def step(self, nid, scope, actor, rid, version, reauthorize=lambda: None):
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.RUNS, rid)
            current_context = self._fresh(nid, scope, row, state); reauthorize(); check_version(row, version)
            if row['status'] not in {'READY', 'RUNNING'}: raise ValueError('simulation cannot expand after completion or cancellation')
            def advance(target):
                request = target['request']; graph_ids = {r['id'] for r in current_context['graph_links']}
                for route, candidate in zip(target['routes'], request['routes']):
                    if route['status'] != 'PENDING': continue
                    reauthorize()  # Sources are fenced before the round and again before its atomic commit.
                    if route['cursor'] >= request['max_steps'] or target['expansions'] >= LIMITS['max_expansions']:
                        route['status'] = 'LIMIT_REACHED'; continue
                    event = candidate['events'][route['cursor']]
                    after, errors = transition(route['state'], event, set(request['knowledge_ids']), graph_ids, request['hard_constraints'])
                    route['cursor'] += 1; target['expansions'] += 1
                    if not errors:
                        stamp = digest(after)
                        if stamp in route['seen_states']:
                            errors.append(violation('CYCLE_STOPPED', '路线重复已有状态，已停止此路线继续扩展。')); route['status'] = 'LIMIT_REACHED'
                        else: route['seen_states'].append(stamp); route['state'] = after
                    route['steps'].append({'event_id': event['id'], 'title': event['title'], 'at': event['at'], 'applied': not errors, 'violations': errors,
                                           'question': event['question'], 'foreshadowing_links': [r for r in event['foreshadowing_links'] if r in graph_ids]})
                    route['violations'].extend([{**e, 'event_id': event['id']} for e in errors])
                    if event['question']: route['unresolved_questions'].append(event['question'])
                    if route['status'] == 'PENDING':
                        if route['cursor'] >= len(candidate['events']): route['status'] = 'COMPLETED'
                        elif route['cursor'] >= request['max_steps']: route['status'] = 'LIMIT_REACHED'
                    if route['status'] != 'PENDING':
                        if set(request['hard_constraints']['required_final_facts']) - set(route['state']['facts']):
                            route['violations'].append(violation('FINAL_GOAL_UNMET', '路线结束时尚未满足必需的终态条件。'))
                        if route['status'] == 'LIMIT_REACHED': route['unresolved_questions'].append('已到达步数或循环边界；未展开的事件没有被检查。')
                target['status'] = 'COMPLETED' if all(r['status'] != 'PENDING' for r in target['routes']) else 'RUNNING'
                target['result_digest'] = digest([{k: v for k, v in r.items() if k != 'saved_proposal_id'} for r in target['routes']])
            change_run(row, actor, version, advance)
            reauthorize(); self._fresh(nid, scope, row, state)
        return self._public(nid, scope, row)

    def cancel(self, nid, scope, actor, rid, version, reauthorize=lambda: None):
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.RUNS, rid)
            # Cancellation may stop a stale run without exposing its results.
            reauthorize()
            if row['version'] != version:
                raise CapabilityVersionConflict(self._public(nid, scope, row))
            if row['status'] not in {'READY', 'RUNNING'}: raise ValueError('only active simulations can be cancelled')
            change_run(row, actor, version, lambda r: r.update(status='CANCELLED'))
            reauthorize()
        return self._public(nid, scope, row)

    def save(self, nid, scope, actor, rid, value, reauthorize=lambda: None):
        data = SimulationSaveIn.model_validate(value.model_dump() if hasattr(value, 'model_dump') else value)
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.RUNS, rid)
            self._fresh(nid, scope, row, state); reauthorize(); check_version(row, data.expected_version)
            if row['status'] != 'COMPLETED': raise ValueError('finish bounded checking before saving a route')
            route = next((r for r in row['routes'] if r['id'] == data.route_id), None)
            if route is None: raise FileNotFoundError(data.route_id)
            if route.get('saved_proposal_id'):
                previous = require_row(state, self.planning.PROPOSALS, route['saved_proposal_id'])
                return {'proposal_id': previous['id'], 'run_id': rid, 'status': previous['status']}
            request = row['request']; node = require_row(state, self.planning.NODES, request['node_id'])
            links = {'chapter_ids': request['chapter_ids'] if node['level'] not in {'CHAPTER', 'SCENE'} else node['links']['chapter_ids']}
            # Only selected character and manual route material become planning
            # content. Never copy omniscient node fields or graph source text.
            links['character_ids'] = [request['character_id']]
            body = PlanningProposalIn(node_id=node['id'], expected_node_version=request['expected_node_version'], title=route['title'], links=links,
                fields={'goal': request['character_goal'], 'character_objectives': {request['character_id']: request['character_goal']},
                        'beats': {f"{index + 1}:{step['event_id']}": f"[{'假设通过规则检查' if step['applied'] else '违反规则，待审'}] {step['title']}" for index, step in enumerate(route['steps'])}},
                rationale=f"手工有界推演，待人工审核。动机假设：{route['motivation_hypothesis']}\n观察到的规则违反：" + '; '.join(e['code'] for e in route['violations']) + '\n未决问题：' + '; '.join(route['unresolved_questions'])).model_dump()
            proposal = self.planning._proposal_row(nid, scope, actor, body, state, 'DETERMINISTIC_MANUAL')
            proposal['simulation_provenance'] = {'run_id': rid, 'route_id': route['id'], 'input_digest': row['request_digest'], 'result_digest': row['result_digest'], 'method': METHOD}
            self._fresh(nid, scope, row, state); reauthorize()
            collection(state, self.planning.PROPOSALS)[proposal['id']] = proposal
            change_run(row, actor, data.expected_version, lambda _: route.update(saved_proposal_id=proposal['id']))
            reauthorize(); self._fresh(nid, scope, row, state)
        return {'proposal_id': proposal['id'], 'run_id': rid, 'status': 'REVIEW'}
