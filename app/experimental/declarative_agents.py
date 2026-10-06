"""B02 declarative authoring over the original Workflow DAG and executor.

This is a restricted persistence host, not a scheduler. Execution, approval,
rejection, pause/resume and timeout are inherited unchanged from V1. Only
bounded local proposal nodes and one explicitly reviewed original author job are exposed. No browser-provided name
can register executable code, a tool, a model, or an egress grant.
"""
from __future__ import annotations

from copy import deepcopy
import threading
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import DomainService, StaleSourceError, change_row, check_version, new_row, now
from .planning import collection, digest, require_row
from .store import canonical
from ..services.v1_capability_service import V1CapabilityService
from ..workflow_recipes import recipe_definition

FEATURE = 'declarative_agents_v2'
LOCAL_NODES = {'agent_task', 'draft_prepare', 'knowledge_candidates', 'shot_proposals', 'review_artifact', 'manual_approval', 'checkpoint'}
TOOLS = {'draft_prepare', 'knowledge_candidates', 'shot_proposals'}
MAX_PACKAGE_BYTES = 128000


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class SchemaField(Strict):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    type: Literal['string', 'number', 'boolean'] = 'string'
    required: bool = True
    max_length: int = Field(default=8000, ge=1, le=8000)


class ObjectSchema(Strict):
    """An explicitly supported, finite JSON object schema subset, no $ref/regex."""
    fields: list[SchemaField] = Field(min_length=1, max_length=12)
    @model_validator(mode='after')
    def unique(self):
        if len({f.name for f in self.fields}) != len(self.fields):
            raise ValueError('duplicate schema field')
        return self


def validate_object(schema, value):
    schema = ObjectSchema.model_validate(schema)
    if not isinstance(value, dict) or set(value) - {f.name for f in schema.fields}:
        raise ValueError('input/output object contains undeclared fields')
    for field in schema.fields:
        if field.name not in value:
            if field.required: raise ValueError('required schema field missing: ' + field.name)
            continue
        item = value[field.name]
        if field.type == 'string' and (not isinstance(item, str) or len(item) > field.max_length):
            raise ValueError('schema string limit exceeded: ' + field.name)
        if field.type == 'boolean' and type(item) is not bool:
            raise ValueError('schema boolean required: ' + field.name)
        if field.type == 'number' and (type(item) not in {int, float}):
            raise ValueError('schema number required: ' + field.name)
    if len(canonical(value).encode()) > 32000: raise ValueError('schema object exceeds byte limit')
    return deepcopy(value)


class AgentDefinition(Strict):
    title: str = Field(min_length=1, max_length=160)
    purpose: str = Field(default='', max_length=2000)
    role_prompt: str = Field(default='', max_length=8000)
    input_schema: ObjectSchema = Field(default_factory=lambda: ObjectSchema(fields=[SchemaField(name='source_text')]))
    output_schema: ObjectSchema = Field(default_factory=lambda: ObjectSchema(fields=[SchemaField(name='draft')]))
    allowed_tools: list[str] = Field(default_factory=lambda: ['draft_prepare'], max_length=3)
    model_route: str | None = Field(default=None, max_length=200)
    review_required: Literal[True] = True
    max_steps: int = Field(default=8, ge=3, le=16)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_output_bytes: int = Field(default=64000, ge=256, le=128000)
    max_cost_microusd: Literal[0] = 0
    @model_validator(mode='after')
    def static_authority(self):
        if not self.allowed_tools or len(self.allowed_tools) != len(set(self.allowed_tools)) or set(self.allowed_tools) - TOOLS:
            raise ValueError('unregistered tool; executable extensions are DENY_ALL')
        source = next((f for f in self.input_schema.fields if f.name == 'source_text'), None)
        if not source or source.type != 'string' or not source.required:
            raise ValueError('the local adapter requires a source_text string')
        if any(f.name not in {'draft', 'summary'} or f.type != 'string' for f in self.output_schema.fields):
            raise ValueError('local output schema supports draft/summary string fields only')
        return self


class Node(Strict):
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,39}$')
    type: Literal['agent_task', 'draft_prepare', 'knowledge_candidates', 'shot_proposals', 'manual_approval', 'review_artifact', 'checkpoint']
    name: str = Field(min_length=1, max_length=160)
    # Do not accept arbitrary node config, paths, URLs, scripts or dynamic imports.


class Edge(Strict):
    source: str = Field(min_length=1, max_length=40)
    target: str = Field(min_length=1, max_length=40)


class WorkflowAuthoring(Strict):
    agent: AgentDefinition
    nodes: list[Node] = Field(min_length=3, max_length=16)
    edges: list[Edge] = Field(min_length=2, max_length=40)
    @model_validator(mode='after')
    def graph(self):
        nodes, edges = [n.model_dump() for n in self.nodes], [e.model_dump() for e in self.edges]
        order = V1CapabilityService._workflow_order(nodes, edges)
        if len(nodes) > self.agent.max_steps: raise ValueError('graph exceeds agent step budget')
        tools = {n.type for n in self.nodes} & TOOLS
        if tools - set(self.agent.allowed_tools): raise ValueError('graph requests a tool outside the declared server allowlist')
        models = [n for n in self.nodes if n.type == 'agent_task']
        if len(models) > 1: raise ValueError('at most one bound model node per reviewed run')
        if models and not self.agent.model_route: raise ValueError('agent_task requires a registered model route')
        if self.agent.model_route and not models: raise ValueError('model route requires an explicit agent_task node')
        if not tools and not models: raise ValueError('at least one preparation or bound model node is required')
        # The original engine executes ready branches in topological order.
        # Every branch must join the single review gate before the only artifact;
        # there is no conditional routing, parallel executor or hidden dataflow.
        incoming = {n.id: [] for n in self.nodes}; outgoing = {n.id: [] for n in self.nodes}
        for edge in self.edges:
            if edge.source in incoming[edge.target]: raise ValueError('duplicate edge')
            incoming[edge.target].append(edge.source); outgoing[edge.source].append(edge.target)
        if len([key for key, values in incoming.items() if not values]) != 1:
            raise ValueError('supported DAG requires one connected root')
        by_id = {n.id: n for n in self.nodes}
        if by_id[order[-1]].type != 'review_artifact': raise ValueError('workflow must finish with a reviewed artifact')
        if sum(n.type == 'review_artifact' for n in self.nodes) != 1: raise ValueError('one terminal artifact required')
        review_positions = [i for i, rid in enumerate(order) if by_id[rid].type == 'manual_approval']
        if len(review_positions) != 1 or review_positions[-1] != len(order) - 2:
            raise ValueError('explicit review gate must immediately precede the terminal artifact')
        gate, artifact = order[-2:]
        if incoming[artifact] != [gate] or outgoing[gate] != [artifact]:
            raise ValueError('all publication paths must pass the review gate')
        ancestors = {gate}
        for node_id in reversed(order[:-1]):
            if node_id in ancestors: ancestors.update(incoming[node_id])
        if ancestors != set(order[:-1]):
            raise ValueError('every branch must join before human review')
        return self


def default_definition():
    recipe = recipe_definition('planning_draft', 'declarative-placeholder')
    return WorkflowAuthoring(agent=AgentDefinition(title='本地草稿整理', purpose='整理明确提供的文字，人工审核后保存草稿材料。'),
        nodes=[{k: v for k, v in node.items() if k != 'config'} for node in recipe['nodes']], edges=recipe['edges']).model_dump()


class SaveDefinitionIn(Strict):
    expected_version: int = Field(default=0, ge=0)
    definition: WorkflowAuthoring


class TestIn(Strict):
    expected_version: int = Field(ge=1)
    input: dict = Field(default_factory=dict)
    chapter_ids: list[str] = Field(default_factory=list, max_length=1)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    reviewed_definition_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_version: int | None = Field(default=None, ge=1)
    anchor_chapter_id: str | None = Field(default=None, min_length=1, max_length=240)
    anchor_chapter_version: int | None = Field(default=None, ge=1)


class ActionIn(Strict):
    expected_version: int = Field(ge=1)
    note: str = Field(default='', max_length=1000)


class OutputLimitError(ValueError): pass


class _ScopedOriginalWorkflowHost(V1CapabilityService):
    """Only the existing engine algorithms execute; this host performs no provider IO.

    The parent transaction atomically persists the returned run plus every
    original engine transition receipt. The engine's private revisions are not
    exposed as domain CAS versions. Failed authority checks abort the transaction.
    """
    def __init__(self, row, guard):
        self.row = deepcopy(row)
        self._lock = threading.RLock()
        self.guard = guard
        self.transitions = []
        self.dispatches = []

    def _get(self, name, rid):
        if name != 'workflow_runs' or rid != self.row['id']: raise FileNotFoundError(rid)
        self.guard()
        return deepcopy(self.row)

    def _update(self, name, rid, payload, *, novel_id, expected_version, action, target_type):
        if name != 'workflow_runs' or rid != self.row['id'] or novel_id != self.row['novel_id']:
            raise ValueError('workflow host scope mismatch')
        check_version(self.row, expected_version)
        self.guard()
        payload = deepcopy(payload)
        for node_state in payload.get('node_states', {}).values():
            output = node_state.get('output')
            if isinstance(output, dict) and isinstance(output.get('result'), dict) and output['result'].get('provenance'):
                output['provenance'] = deepcopy(output['result']['provenance'])
            if len(canonical(node_state.get('output')).encode()) > self.row['max_output_bytes']:
                raise OutputLimitError('WORKFLOW_OUTPUT_LIMIT')
        if len(canonical(payload).encode()) > 256000: raise OutputLimitError('WORKFLOW_TOTAL_OUTPUT_LIMIT')
        self.row.update(deepcopy(payload), version=self.row['version'] + 1)
        self.transitions.append({'action': action, 'engine_revision': self.row['version'], 'status': self.row['status'],
            'node_statuses': {k: v['status'] for k, v in self.row['node_states'].items()}, 'at': now()})
        self.guard()
        return deepcopy(self.row)

    def workflow_dispatch_guard(self, run, node):
        self.guard()
        if node['type'] not in LOCAL_NODES or node.get('config', {}):
            raise ValueError('unregistered executable node; DENY_ALL')
        self.dispatches.append({'node_id': node['id'], 'type': node['type'], 'at': now(), 'model_called': False})


class DeclarativeAgentsService(DomainService):
    DEFINITIONS = 'declarative_agent_definitions_v2'
    RUNS = 'declarative_agent_runs_v2'
    def __init__(self, store, novels, chapters, *, sources=None, broker=None):
        super().__init__(store, novels, chapters)
        self.sources = sources
        self.broker = broker
        self.model_coordinator = None

    def _owned(self, ctx, name, rid, state=None):
        self.novels.get(ctx.novel_id)
        row = require_row(state or self.store.read(ctx.novel_id, ctx.scope), name, rid)
        if row['created_by'] != ctx.actor: raise FileNotFoundError(rid)
        return row

    def _rows(self, ctx, name):
        return [r for r in self.list(ctx.novel_id, ctx.scope, name) if r['created_by'] == ctx.actor]

    def _model_routes(self):
        # The broker reads its actual registry. Cataloging does not contact any
        # provider, enable a model, reserve a budget or authorize a dispatch.
        if self.broker is None: return []
        return [{'id': r['route_id'], 'model_id': r.get('model_id'), 'provider_id': r.get('provider_id'),
                 'available': bool(self.model_coordinator and r.get('available') and not r.get('cloud')),
                 'synthetic': r.get('synthetic', False),
                 'reason': 'LOCAL_ONLY' if r.get('cloud') else 'CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED' if not self.model_coordinator else ', '.join(r.get('reasons', []))}
                for r in self.broker.candidates() if r.get('capability') == 'TEXT']

    def catalog(self, ctx):
        self.novels.get(ctx.novel_id)
        chapters = [] if self.sources is None else self.sources._source_rows(ctx, 'chapter')
        return {'tools': sorted(TOOLS), 'node_types': sorted(LOCAL_NODES), 'model_routes': self._model_routes(),
            'default_definition': default_definition(), 'chapters': [{'id': r['id'], 'title': r.get('title', ''), 'version': r.get('version')} for r in chapters],
            'execution_mode': 'LOCAL_RULES_OR_BOUND_LOCAL_MODEL' if self.model_coordinator else 'LOCAL_RULES', 'executable_extensions': 'DENY_ALL', 'remote_calls': 0,
            'graph_subset': 'ROOTED_DAG_JOIN_BEFORE_EXPLICIT_REVIEW', 'schema_subset': 'FINITE_SCALAR_OBJECT',
            'model_dependency': 'ORIGINAL_AUTHOR_BROKER_JOB_MANAGER' if self.model_coordinator else 'CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED', 'sdk_version': 1}

    def validate(self, definition):
        definition = WorkflowAuthoring.model_validate(definition).model_dump()
        route = definition['agent']['model_route']
        if route and route not in {r['id'] for r in self._model_routes()}:
            raise ValueError('model is not in the server broker registry')
        return definition

    def preflight(self, ctx, body):
        self.novels.get(ctx.novel_id)
        definition = self.validate(body)
        route = next((r for r in self._model_routes() if r['id'] == definition['agent']['model_route']), None)
        blockers = ['MODEL_ROUTE_UNAVAILABLE'] if definition['agent']['model_route'] and route is None else [route['reason'] or 'MODEL_ROUTE_UNAVAILABLE'] if route and not route['available'] else []
        return {'valid': True, 'definition_digest': digest(definition),
            'topological_order': V1CapabilityService._workflow_order(definition['nodes'], definition['edges']),
            'execution_available': not blockers,
            'blockers': blockers,
            'model_called': False, 'applied': False, 'external_calls': 0}

    def definitions(self, ctx):
        return {'items': [{k: v for k, v in r.items() if k != 'history'} for r in self._rows(ctx, self.DEFINITIONS)]}

    def save(self, ctx, rid, body, reauthorize=lambda: None):
        body = SaveDefinitionIn.model_validate(body)
        definition = self.validate(body.definition)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            payload = {'definition': definition, 'definition_digest': digest(definition), 'status': 'DRAFT', 'applied': False}
            if rid:
                row = self._owned(ctx, self.DEFINITIONS, rid, state)
                change_row(row, ctx.actor, body.expected_version, lambda r: r.update(payload))
            else:
                if body.expected_version != 0: raise ValueError('new definition expects version zero')
                row = new_row(ctx.novel_id, ctx.scope, ctx.actor, payload)
                collection(state, self.DEFINITIONS)[row['id']] = row
            reauthorize()
            return deepcopy({k: v for k, v in row.items() if k != 'history'})

    def _capture_input(self, ctx, definition, body):
        sources = {}
        value = deepcopy(body.input)
        if body.chapter_ids:
            if value.get('source_text'): raise ValueError('choose explicit text or a current chapter, not both')
            if self.sources is None: raise ValueError('BRANCH_SOURCE_ADAPTER_REQUIRED')
            cid = body.chapter_ids[0]
            row = self.sources._source(ctx, 'chapter', cid)
            if row['version'] != body.source_version: raise StaleSourceError('selected chapter version changed; review current source')
            if row['truncated']: raise ValueError('source exceeds bounded input; explicitly select a smaller excerpt')
            value['source_text'] = row['text']
            sources[cid] = {'revision': row['revision'], 'version': row['version']}
        elif body.source_version is not None:
            raise ValueError('source_version requires a selected chapter')
        validate_object(definition['agent']['input_schema'], value)
        text = value.get('source_text', '')
        if not text.strip() or len(text.splitlines()) > 100: raise ValueError('source requires 1-100 lines')
        return value, sources

    def _assert_current(self, ctx, row, state=None):
        definition = self._owned(ctx, self.DEFINITIONS, row['definition_id'], state)
        if definition['version'] != row['definition_version'] or definition['definition_digest'] != row['definition_digest']:
            raise StaleSourceError('agent definition changed; create a new reviewed run')
        self.validate(definition['definition'])
        for cid, source in row['sources'].items():
            if self.sources is None: raise StaleSourceError('source adapter unavailable')
            try: current = self.sources._source(ctx, 'chapter', cid)
            except FileNotFoundError as exc: raise StaleSourceError('source is no longer visible') from exc
            if current['revision'] != source['revision']: raise StaleSourceError('source changed; create a new run')
        if row.get('anchor'):
            anchor = row['anchor']; current = self.sources._source(ctx, 'chapter', anchor['id']) if self.sources else None
            if not current or current['revision'] != anchor['revision'] or current['version'] != anchor['version']:
                raise StaleSourceError('model anchor changed; create a new reviewed run')
        if row['definition_snapshot']['agent']['model_route'] and self.model_coordinator is None:
            raise ValueError('CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED')

    def _public_run(self, ctx, row):
        public = deepcopy({k: v for k, v in row.items() if k != 'history'})
        try: self._assert_current(ctx, row); public['stale'] = False
        except (ValueError, FileNotFoundError):
            public.update(stale=True, input={}, agent_output=None, model_preview=None, node_states={k: {'status': v['status'], 'output': None, 'error': None} for k, v in row['node_states'].items()})
        return public

    def runs(self, ctx):
        return {'items': [self._public_run(ctx, r) for r in self._rows(ctx, self.RUNS)]}

    def get_run(self, ctx, rid):
        return self._public_run(ctx, self._owned(ctx, self.RUNS, rid))

    def create_run(self, ctx, rid, body, reauthorize=lambda: None):
        body = TestIn.model_validate(body)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            definition = self._owned(ctx, self.DEFINITIONS, rid, state)
            check_version(definition, body.expected_version)
            if body.reviewed_definition_digest != definition['definition_digest']:
                raise StaleSourceError('reviewed graph digest changed')
            authored = self.validate(definition['definition'])
            if authored['agent']['model_route'] and self.model_coordinator is None: raise ValueError('CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED')
            inputs, sources = self._capture_input(ctx, authored, body)
            anchor = None
            if authored['agent']['model_route']:
                cid = body.chapter_ids[0] if body.chapter_ids else body.anchor_chapter_id
                version = body.source_version if body.chapter_ids else body.anchor_chapter_version
                if not cid or not version or self.sources is None: raise ValueError('MODEL_ANCHOR_CHAPTER_REQUIRED')
                source = self.sources._source(ctx, 'chapter', cid)
                if source['version'] != version: raise StaleSourceError('model anchor version changed')
                anchor = {'id': cid, 'version': version, 'revision': source['revision']}
            elif body.anchor_chapter_id or body.anchor_chapter_version:
                raise ValueError('model anchor requires an explicit model node')
            request_digest = digest([rid, body.model_dump(), definition['definition_digest'], sources, anchor])
            for existing in collection(state, self.RUNS).values():
                if existing['created_by'] == ctx.actor and existing.get('request_id') == body.request_id:
                    if existing['request_digest'] != request_digest: raise ValueError('REQUEST_ID_REUSED_WITH_DIFFERENT_INPUT')
                    reauthorize(); return self._public_run(ctx, existing)
            snapshot = {**authored, 'title': authored['agent']['title'],
                'topological_order': V1CapabilityService._workflow_order(authored['nodes'], authored['edges'])}
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {
                'definition_id': rid, 'definition_version': definition['version'], 'definition_digest': definition['definition_digest'],
                'definition_snapshot': snapshot, 'request_id': body.request_id, 'request_digest': request_digest,
                'input': inputs, 'sources': sources, 'anchor': anchor, 'model_preview': None, 'model_execution': None, 'input_digest': digest(inputs), 'status': 'QUEUED', 'initiated_by': ctx.actor,
                'node_states': {n['id']: {'status': 'PENDING', 'output': None, 'error': None} for n in snapshot['nodes']},
                'timeout_seconds': authored['agent']['timeout_seconds'], 'max_output_bytes': authored['agent']['max_output_bytes'],
                'step_limit': authored['agent']['max_steps'], 'steps_completed': 0, 'attempt': 1, 'retry_of': None,
                'trace': [], 'dispatch_trace': [], 'agent_output': None, 'external_ai_calls': False,
                'external_calls': 0, 'model_called': False, 'applied': False, 'privacy_level': 'LOCAL_ONLY', 'execution_mode': 'ORIGINAL_BOUND_MODEL' if authored['agent']['model_route'] else 'LOCAL_RULES'})
            collection(state, self.RUNS)[row['id']] = row
            self._assert_current(ctx, row, state); reauthorize()
            return self._public_run(ctx, row)

    def transition(self, ctx, rid, action, body, reauthorize=lambda: None):
        body = ActionIn.model_validate(body)
        if action not in {'execute', 'approve', 'reject', 'pause', 'resume', 'cancel', 'retry'}: raise ValueError('unsupported action')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._owned(ctx, self.RUNS, rid, state); check_version(row, body.expected_version)
            def guard():
                reauthorize()
                if action not in {'cancel', 'reject'}: self._assert_current(ctx, row, state)
            guard()
            if action == 'retry':
                if row.get('model_execution'): raise ValueError('MODEL_RUN_REPLAY_DENIED_CREATE_NEW_REVIEWED_RUN')
                if row['status'] not in {'FAILED', 'CANCELLED'}: raise ValueError('only failed or cancelled runs may retry')
                # Explicit retry of the same reviewed snapshot; never an
                # automatic fallback. Completed pure-node receipts are retained.
                payload = deepcopy(row)
                payload.update(status='QUEUED', started_at=now(), attempt=row['attempt'] + 1, agent_output=None)
                payload.pop('error', None)
                for value in payload['node_states'].values():
                    if value['status'] != 'SUCCEEDED': value.update(status='PENDING', output=None, error=None)
                change_row(row, ctx.actor, body.expected_version, lambda r: r.update({k: v for k, v in payload.items() if k not in {'history', 'version'}}))
                guard(); return self._public_run(ctx, row)
            if action in {'pause', 'resume'} and row.get('model_execution') and row['status'] == 'RUNNING':
                raise ValueError('INFLIGHT_MODEL_CANNOT_PAUSE_USE_CANCEL')
            engine_row = deepcopy(row)
            if action == 'execute':
                if row['status'] != 'QUEUED': raise ValueError('execute requires a queued run')
                engine_row['started_at'] = now()
            host = _ScopedOriginalWorkflowHost(engine_row, guard)
            try:
                current = host.get_workflow_run(rid)
                if current['status'] == 'FAILED' and current.get('error', {}).get('code') == 'WORKFLOW_TIMEOUT': result = current
                elif action == 'execute': result = host._advance_workflow_run(rid)
                elif action in {'approve', 'reject'}:
                    current = row.get('current_node_id')
                    if action == 'approve': result = host.approve_workflow_node(rid, current, ctx.actor, body.note)
                    else: result = host.reject_workflow_node(rid, current, ctx.actor, body.note)
                else: result = host.set_workflow_run_state(rid, action)
            except OutputLimitError:
                result = deepcopy(row); result.update(status='FAILED', error={'code': 'WORKFLOW_OUTPUT_LIMIT'}, agent_output=None)
                for node in result['node_states'].values():
                    if node['status'] != 'SUCCEEDED': node.update(status='SKIPPED', output=None)
            if result['status'] == 'SUCCEEDED':
                draft = next((state.get('output', {}).get('result', {}).get('draft') for state in result['node_states'].values() if isinstance(state.get('output'), dict) and isinstance(state['output'].get('result'), dict) and 'draft' in state['output']['result']), row['input']['source_text'])
                raw = {'draft': draft, 'summary': 'Model draft reviewed; literary quality not measured.' if row.get('model_called') else 'Local rules prepared ' + str(len(row['input']['source_text'].splitlines())) + ' source lines. Human review recorded; no model called.'}
                schema = row['definition_snapshot']['agent']['output_schema']
                output = {f['name']: raw[f['name']] for f in schema['fields']}
                try:
                    validate_object(schema, output)
                    if len(canonical(output).encode()) > row['max_output_bytes']: raise OutputLimitError('WORKFLOW_OUTPUT_LIMIT')
                    result['agent_output'] = output
                except ValueError:
                    result.update(status='FAILED', error={'code': 'AGENT_OUTPUT_SCHEMA_LIMIT'}, agent_output=None)
            payload = {k: v for k, v in result.items() if k not in {'history', 'version'}}
            payload['trace'] = row['trace'] + host.transitions
            payload['dispatch_trace'] = row['dispatch_trace'] + host.dispatches
            change_row(row, ctx.actor, body.expected_version, lambda r: r.update(payload))
            guard()
            return self._public_run(ctx, row)
