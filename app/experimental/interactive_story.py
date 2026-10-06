"""B07 author-owned adaptations of original planning nodes, never manuscript branches.

Expressions are parsed into a tiny typed tree, never evaluated as Python. Playback
is server-replayed from a bounded choice log. Export emits only our trusted text
subset template; it never executes imported scripts or fetches resource URLs.
"""
from __future__ import annotations

import ast
import base64
from collections import deque
from copy import deepcopy
import hashlib
import io
import json
import re
from typing import Annotated, Literal
import zipfile

from pydantic import ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

from .common import StaleSourceError, change_row, new_row, now
from .planning import StrictModel, collection, require_row, digest, entity_sources
from .style_analysis import SourceFencedService
from ..services.v1_capability_service import CapabilityVersionConflict

FEATURE = 'interactive_story_v2'
SCHEMA = 'ai-novel-interactive-story/1'
LIMITS = {'nodes': 100, 'choices_per_node': 8, 'variables': 16, 'steps': 128, 'analysis_states': 4096}
Scalar = StrictBool | Annotated[StrictInt, Field(ge=-10000, le=10000)]
Identifier = Annotated[str, Field(min_length=1, max_length=160)]
Name = Annotated[str, Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')]


def text_safe(value):
    if any((ord(c) < 32 and c not in '\n\t\r') or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError('unsupported text control or surrogate')
    return value


class Variable(StrictModel):
    name: Name
    type: Literal['bool', 'int']
    initial: Scalar
    minimum: int = Field(default=0, ge=-10000, le=10000, strict=True)
    maximum: int = Field(default=100, ge=-10000, le=10000, strict=True)

    @model_validator(mode='after')
    def bounded(self):
        if self.minimum > self.maximum: raise ValueError('invalid variable bounds')
        if self.type == 'bool' and type(self.initial) is not bool: raise ValueError('boolean initial value required')
        if self.type == 'int' and (type(self.initial) is not int or not self.minimum <= self.initial <= self.maximum):
            raise ValueError('integer initial value outside bounds')
        return self


class Choice(StrictModel):
    id: Name
    label: str = Field(min_length=1, max_length=240)
    target: Identifier
    condition: str = Field(default='', max_length=240)
    assignments: dict[Name, Scalar] = Field(default_factory=dict, max_length=16)
    _label = field_validator('label')(text_safe)

    @field_validator('condition')
    @classmethod
    def syntax(cls, value):
        parse_condition(value)
        return value


class StoryNode(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    node_id: Identifier
    node_version: int = Field(ge=1, strict=True)
    title: str = Field(min_length=1, max_length=240)
    dialogue: str = Field(default='', max_length=8000)
    character_id: Identifier | None = None
    background_asset_id: Identifier | None = None
    music_asset_id: Identifier | None = None
    ending: str = Field(default='', max_length=240)
    choices: list[Choice] = Field(default_factory=list, max_length=8)
    _texts = field_validator('title', 'dialogue', 'ending')(text_safe)

    @model_validator(mode='after')
    def shape(self):
        if len({c.id for c in self.choices}) != len(self.choices): raise ValueError('choice IDs must be unique within a node')
        if self.ending and self.choices: raise ValueError('ending nodes cannot have outgoing choices')
        return self


class StorySpec(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    graph_id: Identifier
    graph_version: int = Field(ge=1, strict=True)
    entry_node_id: Identifier
    nodes: list[StoryNode] = Field(min_length=1, max_length=100)
    variables: list[Variable] = Field(default_factory=list, max_length=16)
    graph_record_ids: list[Identifier] = Field(default_factory=list, max_length=50)
    max_steps: int = Field(default=32, ge=1, le=128, strict=True)
    _title = field_validator('title')(text_safe)

    @model_validator(mode='after')
    def unique(self):
        if len({n.node_id for n in self.nodes}) != len(self.nodes): raise ValueError('planning node IDs must be unique')
        if self.entry_node_id not in {n.node_id for n in self.nodes}: raise ValueError('entry must be a selected planning node')
        if len({v.name for v in self.variables}) != len(self.variables): raise ValueError('variable names must be unique')
        if len(set(self.graph_record_ids)) != len(self.graph_record_ids): raise ValueError('duplicate story graph reference')
        if sum(len(n.dialogue) for n in self.nodes) > 100000: raise ValueError('adaptation exceeds 100000 characters')
        return self


class CreateIn(StrictModel):
    spec: StorySpec


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)


class SaveIn(VersionIn):
    spec: StorySpec


class ReviewIn(VersionIn):
    action: Literal['submit', 'approve', 'reopen', 'archive', 'restore']
    preview_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class RestoreIn(VersionIn):
    restore_version: int = Field(ge=1, strict=True)
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class PlayIn(VersionIn):
    choices: list[Name] = Field(default_factory=list, max_length=128)


class ExportIn(VersionIn):
    preview_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


def parse_condition(expression):
    """No calls, attributes, subscripts, arithmetic, strings or Python execution."""
    if not expression.strip(): return {'op': 'literal', 'value': True}
    if len(expression) > 240: raise ValueError('condition too long')
    try: root = ast.parse(expression.strip(), mode='eval')
    except (SyntaxError, RecursionError, ValueError): raise ValueError('invalid restricted condition') from None
    if sum(1 for _ in ast.walk(root)) > 64: raise ValueError('condition is too complex')
    def walk(node, depth=0):
        if depth > 12: raise ValueError('condition nesting limit')
        if isinstance(node, ast.Constant) and type(node.value) in {int, bool} and (type(node.value) is bool or -10000 <= node.value <= 10000):
            return {'op': 'literal', 'value': node.value}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) and type(node.operand.value) is int and 0 <= node.operand.value <= 10000:
            return {'op': 'literal', 'value': -node.operand.value}
        if isinstance(node, ast.Name) and re.fullmatch(r'[a-z][a-z0-9_]{0,31}', node.id): return {'op': 'var', 'name': node.id}
        if isinstance(node, ast.BoolOp): return {'op': 'and' if isinstance(node.op, ast.And) else 'or', 'args': [walk(n, depth + 1) for n in node.values]}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not): return {'op': 'not', 'arg': walk(node.operand, depth + 1)}
        comparisons = {ast.Eq: 'eq', ast.NotEq: 'ne', ast.Lt: 'lt', ast.LtE: 'le', ast.Gt: 'gt', ast.GtE: 'ge'}
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in comparisons:
            return {'op': comparisons[type(node.ops[0])], 'left': walk(node.left, depth + 1), 'right': walk(node.comparators[0], depth + 1)}
        raise ValueError('only bool/int names, literals, comparisons, and/or/not and parentheses are allowed')
    return walk(root.body)


def expression_type(tree, variables):
    op = tree['op']
    if op == 'literal': return type(tree['value'])
    if op == 'var':
        if tree['name'] not in variables: raise ValueError('UNDEFINED_VARIABLE')
        return bool if variables[tree['name']]['type'] == 'bool' else int
    if op in {'and', 'or', 'not'}:
        args = tree['args'] if op != 'not' else [tree['arg']]
        if any(expression_type(a, variables) is not bool for a in args): raise ValueError('CONDITION_TYPE_MISMATCH')
        return bool
    left, right = expression_type(tree['left'], variables), expression_type(tree['right'], variables)
    if left is not right or (op not in {'eq', 'ne'} and left is not int): raise ValueError('CONDITION_TYPE_MISMATCH')
    return bool


def interpret(tree, values):
    op = tree['op']
    if op == 'literal': return tree['value']
    if op == 'var': return values[tree['name']]
    if op == 'and': return all(interpret(a, values) for a in tree['args'])
    if op == 'or': return any(interpret(a, values) for a in tree['args'])
    if op == 'not': return not interpret(tree['arg'], values)
    a, b = interpret(tree['left'], values), interpret(tree['right'], values)
    if op == 'eq': return a == b
    if op == 'ne': return a != b
    if op == 'lt': return a < b
    if op == 'le': return a <= b
    if op == 'gt': return a > b
    if op == 'ge': return a >= b
    raise ValueError('unknown restricted operator')


def compile_story(spec):
    nodes = {n['node_id']: n for n in spec['nodes']}; variables = {v['name']: v for v in spec['variables']}
    compiled, issues = {}, []
    for node in nodes.values():
        if not node['ending'] and not node['choices']: issues.append({'code': 'NO_EXIT', 'node_id': node['node_id']})
        for choice in node['choices']:
            key = (node['node_id'], choice['id']); tree = parse_condition(choice['condition']); compiled[key] = tree
            if choice['target'] not in nodes: issues.append({'code': 'UNDEFINED_TARGET', 'node_id': node['node_id'], 'choice_id': choice['id']})
            try:
                if expression_type(tree, variables) is not bool: raise ValueError('CONDITION_TYPE_MISMATCH')
                for name, value in choice['assignments'].items():
                    if name not in variables: raise ValueError('UNDEFINED_VARIABLE')
                    var = variables[name]
                    if type(value) is not (bool if var['type'] == 'bool' else int): raise ValueError('ASSIGNMENT_TYPE_MISMATCH')
                    if var['type'] == 'int' and not var['minimum'] <= value <= var['maximum']: raise ValueError('ASSIGNMENT_OUT_OF_BOUNDS')
            except ValueError as exc: issues.append({'code': str(exc), 'node_id': node['node_id'], 'choice_id': choice['id']})
    return nodes, compiled, issues


def analyze(spec):
    nodes, compiled, issues = compile_story(spec)
    reachable, cycles, active = set(), set(), set()
    def visit(nid):
        if nid in active: cycles.add(nid); return
        if nid in reachable or nid not in nodes: return
        reachable.add(nid); active.add(nid)
        for choice in nodes[nid]['choices']: visit(choice['target'])
        active.remove(nid)
    visit(spec['entry_node_id'])
    exits = {n['node_id'] for n in nodes.values() if n['ending']}
    can_exit = set(exits)
    for _ in nodes:
        old = set(can_exit)
        can_exit.update(n['node_id'] for n in nodes.values() if any(c['target'] in can_exit for c in n['choices']))
        if old == can_exit: break
    warnings = ([{'code': 'UNREACHABLE_NODE', 'node_id': n} for n in sorted(set(nodes) - reachable)] +
                [{'code': 'CYCLE_STEP_CAP_REQUIRED', 'node_id': n} for n in sorted(cycles)])
    issues += [{'code': 'NO_ENDING_PATH', 'node_id': n} for n in sorted(reachable - can_exit)]
    witnesses, dead_states, seen = {}, [], set(); truncated = False; step_limited = False
    if not issues:
        initial = {v['name']: v['initial'] for v in spec['variables']}
        queue = deque([(spec['entry_node_id'], initial, [])])
        while queue:
            nid, values, path = queue.popleft(); key = digest([nid, values])
            if key in seen: continue
            if len(seen) >= LIMITS['analysis_states']: truncated = True; break
            seen.add(key); node = nodes[nid]
            if node['ending']:
                witnesses.setdefault(nid, {'node_id': nid, 'ending': node['ending'], 'choices': path}); continue
            available = [c for c in node['choices'] if interpret(compiled[(nid, c['id'])], values)]
            if not available: dead_states.append({'node_id': nid, 'choices': path, 'code': 'CONDITIONAL_NO_EXIT'})
            if len(path) >= spec['max_steps']: step_limited = True; continue
            for choice in available:
                queue.append((choice['target'], {**values, **choice['assignments']}, path + [choice['id']]))
        issues.extend(dead_states[:100])
        if not witnesses: issues.append({'code': 'NO_REACHABLE_ENDING_WITHIN_CAP'})
    return {'issues': issues, 'warnings': warnings, 'endings': list(witnesses.values()), 'states_checked': len(seen),
            'analysis_complete': not truncated and not step_limited, 'state_limit_reached': truncated,
            'step_limit_reached': step_limited, 'max_steps': spec['max_steps'],
            'can_review': not issues and not truncated and not step_limited,
            'method': 'BOUNDED_TYPED_STATE_SEARCH_NOT_UNBOUNDED_PROOF'}


def play(spec, path):
    nodes, compiled, issues = compile_story(spec)
    if issues: raise ValueError('fix path, variable and condition errors before playback')
    if len(path) > spec['max_steps']: raise ValueError('STEP_CAP_REACHED')
    values = {v['name']: v['initial'] for v in spec['variables']}; nid = spec['entry_node_id']
    for cid in path:
        node = nodes[nid]
        choice = next((c for c in node['choices'] if c['id'] == cid), None)
        if node['ending'] or not choice or not interpret(compiled[(nid, cid)], values): raise ValueError('CHOICE_UNAVAILABLE')
        values.update(choice['assignments']); nid = choice['target']
    node = nodes[nid]
    choices = [{'id': c['id'], 'label': c['label'], 'enabled': interpret(compiled[(nid, c['id'])], values)} for c in node['choices']]
    status = 'ENDING' if node['ending'] else 'STEP_CAP_REACHED' if len(path) >= spec['max_steps'] else 'PLAYING' if any(c['enabled'] for c in choices) else 'NO_EXIT'
    return {'node': {k: deepcopy(v) for k, v in node.items() if k != 'choices'}, 'choices': choices, 'variables': values,
            'steps': len(path), 'max_steps': spec['max_steps'], 'status': status, 'path': path}


def renpy_text(value):
    # Escape the script string, then Ren'Py's interpolation, markup and ruby.
    escaped = value.replace('[', '[[').replace('{', '{{').replace('〖', '〖〖').replace('%', '%%')
    return json.dumps(escaped, ensure_ascii=False)


def renpy_expression(tree, names):
    op = tree['op']
    if op == 'literal': return str(tree['value'])
    if op == 'var': return names[tree['name']]
    if op == 'not': return '(not ' + renpy_expression(tree['arg'], names) + ')'
    if op in {'and', 'or'}: return '(' + (' ' + op + ' ').join(renpy_expression(x, names) for x in tree['args']) + ')'
    operators = {'eq': '==', 'ne': '!=', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}
    return '(' + renpy_expression(tree['left'], names) + ' ' + operators[op] + ' ' + renpy_expression(tree['right'], names) + ')'


def renpy_export(spec, characters):
    nodes, compiled, issues = compile_story(spec)
    if issues: raise ValueError('invalid target story')
    labels = {nid: 'ans_node_' + str(i) for i, nid in enumerate(nodes)}
    names = {v['name']: 'ans_var_' + str(i) for i, v in enumerate(spec['variables'])}
    lines = ['# AI-Novel-Studio B07 trusted generated subset; Ren\'Py 8.5.4 docs.', '# Media references are manifest-only. Target runtime: NOT_RUN.', 'default ans_steps = 0']
    lines += ['default ' + names[v['name']] + ' = ' + str(v['initial']) for v in spec['variables']]
    lines += ['', 'label start:', '    $ ans_steps = 0']
    lines += ['    $ ' + names[v['name']] + ' = ' + str(v['initial']) for v in spec['variables']]
    lines += ['    jump ' + labels[spec['entry_node_id']]]
    for nid, node in nodes.items():
        lines += ['', 'label ' + labels[nid] + ':']
        if node['dialogue']:
            speaker = characters.get(node['character_id']) if node['character_id'] else None
            lines.append('    ' + (renpy_text(speaker) + ' ' if speaker else '') + renpy_text(node['dialogue']))
        if node['ending']:
            lines += ['    ' + renpy_text(node['ending']), '    return']; continue
        lines += ['    if ans_steps >= ' + str(spec['max_steps']) + ':', '        "Step cap reached."', '        return']
        conditions = [renpy_expression(compiled[(nid, c['id'])], names) for c in node['choices']]
        lines += ['    if not (' + ' or '.join(conditions) + '):', '        "No available choice."', '        return', '    menu:']
        for choice, condition in zip(node['choices'], conditions):
            lines += ['        ' + renpy_text(choice['label']) + ' if ' + condition + ':', '            $ ans_steps += 1']
            lines += ['            $ ' + names[name] + ' = ' + str(value) for name, value in choice['assignments'].items()]
            lines += ['            jump ' + labels[choice['target']]]
    return '\n'.join(lines) + '\n'


class InteractiveStoryService(SourceFencedService):
    COLLECTION = 'interactive_story_adaptations'

    def __init__(self, store, novels, chapters, planning, story_graph, assets):
        super().__init__(store, novels, chapters)
        self.planning, self.story_graph, self.assets = planning, story_graph, assets

    def capture(self, nid, scope, chapter_ids, expected=None):
        sources, chapters = super().capture(nid, scope, chapter_ids, expected)
        if any(r.get('hidden') or r.get('secret') or str(r.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'} for r in chapters.values()):
            raise FileNotFoundError('source unavailable')
        return sources, chapters

    def _asset(self, nid, scope, aid):
        row = self.assets.get(aid, branch_id=scope.get('branch_id'))
        if row.get('novel_id') != nid or row.get('branch_id') != scope.get('branch_id') or row.get('_owner_actor_id'):
            raise FileNotFoundError(aid)
        return row

    @staticmethod
    def _visible_entity(row, scope):
        return bool(row and row.get('status') != 'ARCHIVED' and not row.get('hidden') and not row.get('secret')
            and str(row.get('visibility', '')).upper() not in {'PRIVATE', 'SECRET', 'DENIED'}
            and (not row.get('branch_id') or row['branch_id'] == scope.get('branch_id')))

    def _visible_links(self, nid, scope, links, state):
        captures = entity_sources(self, nid, scope, links, state)
        for key in captures:
            kind, rid = key.split(':', 1)
            if kind == 'world': row = require_row(state, self.story_graph.RECORDS, rid)
            else: row = next((r for r in self.novels.data_set(nid, kind) if str(r.get('id')) == rid), None)
            if not self._visible_entity(row, scope): raise FileNotFoundError('interactive source entity unavailable')
        return captures

    @staticmethod
    def engine_contract():
        return {'schema': SCHEMA, 'input_schema': StorySpec.model_json_schema(), 'condition_language': 'BOUNDED_BOOL_INT_AST',
                'supported_targets': ['ENGINE_NEUTRAL_JSON', 'RENPY_8_5_4_TEXT_MENU_SUBSET'],
                'third_party_execution': 'DENY_ALL', 'runtime_status': 'NOT_RUN',
                'media_policy': 'VERSIONED_REFERENCES_ONLY_NOT_DEPLOYED', 'adapter_policy': 'SHIPPED_TRUSTED_EXPORTERS_ONLY',
                'max_steps': LIMITS['steps'], 'max_analysis_states': LIMITS['analysis_states']}

    def catalog(self, nid, scope):
        self.novels.get(nid); state = self.store.read(nid, scope); graphs = []
        for graph in collection(state, self.planning.GRAPHS).values():
            require_row(state, self.planning.GRAPHS, graph['id'])
            if graph['status'] != 'ACTIVE': continue
            nodes = []
            for n in collection(state, self.planning.NODES).values():
                if n['graph_id'] != graph['id'] or n['status'] == 'ARCHIVED': continue
                try:
                    chain = [*self.planning._ancestors(state, n), n]
                    self.capture(nid, scope, sorted({cid for original in chain for cid in original['links']['chapter_ids']}))
                    for original in chain: self._visible_links(nid, scope, original['links'], state)
                except (ValueError, FileNotFoundError): continue
                nodes.append({'node_id': n['id'], 'node_version': n['version'], 'title': n['title']})
            if not nodes: continue
            graphs.append({'id': graph['id'], 'version': graph['version'], 'title': graph['title'], 'nodes': nodes[:100], 'truncated': len(nodes) > 100})
        characters = [r for r in self.novels.data_set(nid, 'characters') if not r.get('branch_id') or r['branch_id'] == scope.get('branch_id')]
        characters = [{'id': r['id'], 'name': r.get('name', r['id'])} for r in characters if self._visible_entity(r, scope)]
        graph_records = []
        for row in self.story_graph.records(nid, scope):
            if row['status'] == 'APPROVED' and not row.get('stale'):
                graph_records.append({'id': row['id'], 'title': row['title'], 'version': row['version']})
        assets = []
        for row in self.assets.list(nid, branch_id=scope.get('branch_id')):
            if row.get('branch_id') == scope.get('branch_id') and not row.get('_owner_actor_id'):
                assets.append({'id': row['id'], 'label': row['filename'], 'kind': row['kind'], 'version': row['version']})
        return {'graphs': graphs, 'characters': characters, 'graph_records': graph_records[:50], 'assets': assets[:200], 'limits': LIMITS,
                'target': 'RENPY_8_5_4_TEXT_MENU_SUBSET', 'target_runtime': 'NOT_RUN', 'model_called': False}

    def _capture_spec(self, nid, scope, spec, state):
        graph = require_row(state, self.planning.GRAPHS, spec['graph_id'])
        if graph['status'] != 'ACTIVE' or graph['version'] != spec['graph_version']: raise StaleSourceError('planning graph changed')
        captures, source_ids = {}, set()
        for item in spec['nodes']:
            node = require_row(state, self.planning.NODES, item['node_id'])
            if node['graph_id'] != graph['id'] or node['status'] == 'ARCHIVED' or node['version'] != item['node_version']:
                raise StaleSourceError('planning node changed')
            chain = [*self.planning._ancestors(state, node), node]
            for original in chain:
                captures[original['id']] = digest([{k: v for k, v in original.items() if k != 'history'}, self._visible_links(nid, scope, original['links'], state)])
                source_ids.update(original['links']['chapter_ids'])
        graph_refs = {}
        for rid in spec['graph_record_ids']:
            row = require_row(state, self.story_graph.RECORDS, rid)
            if row['status'] != 'APPROVED' or row['kind'] not in {'STORY_CONCEPT', 'STORY_RELATION', 'KNOWLEDGE_EVENT'}:
                raise ValueError('story graph evidence must be approved')
            if not self._visible_entity(row, scope): raise FileNotFoundError('graph evidence unavailable')
            self._visible_links(nid, scope, row.get('links', {}), state)
            self.story_graph._assert_fresh(nid, scope, row, state)
            source_ids.update(row.get('sources', {})); graph_refs[rid] = digest({k: v for k, v in row.items() if k != 'history'})
        char_ids = sorted({n['character_id'] for n in spec['nodes'] if n['character_id']})
        entities = self._visible_links(nid, scope, {'character_ids': char_ids}, state)
        chars = {r['id']: r for r in self.novels.data_set(nid, 'characters')}
        if any(chars[c].get('hidden') or chars[c].get('secret') for c in char_ids): raise FileNotFoundError('character unavailable')
        names = {c: chars[c].get('name') or c for c in char_ids}
        for name in names.values():
            if not isinstance(name, str) or len(name) > 240: raise ValueError('character display name must be bounded text')
            text_safe(name)
        asset_refs = {}
        for n in spec['nodes']:
            for field, kind in [('background_asset_id', 'image'), ('music_asset_id', 'audio')]:
                if not n[field]: continue
                asset = self._asset(nid, scope, n[field])
                if asset['kind'] != kind: raise ValueError('asset reference has incorrect kind')
                asset_refs[asset['id']] = {'version': asset['version'], 'sha256': asset['sha256'], 'kind': asset['kind'], 'metadata_digest': digest(asset), 'size': asset['size']}
        if sum(asset['size'] for asset in asset_refs.values()) > 32 * 1024 * 1024:
            raise ValueError('selected media references exceed 32 MiB integrity-check budget')
        sources, _ = self.capture(nid, scope, sorted(source_ids))
        return {'planning': captures, 'sources': sources, 'entities': entities, 'graph_records': graph_refs, 'assets': asset_refs,
                'characters': names}

    def _current(self, nid, scope, row, state=None):
        state = state if state is not None else self.store.read(nid, scope)
        if self._capture_spec(nid, scope, row['spec'], state) != row['capture']:
            raise StaleSourceError('source, planning, character, evidence or asset authority changed')

    @staticmethod
    def _version(row, expected):
        if row['version'] != expected: raise CapabilityVersionConflict({k: row[k] for k in ['id', 'version', 'status']})

    def _owned(self, nid, scope, actor, sid, state=None):
        row = require_row(state, self.COLLECTION, sid) if state is not None else self.get(nid, scope, self.COLLECTION, sid)
        if row['created_by'] != actor: raise FileNotFoundError(sid)
        return row

    def _view(self, nid, scope, row):
        try: self._current(nid, scope, row)
        except (ValueError, FileNotFoundError):
            return {k: row[k] for k in ['id', 'version', 'status']} | {'stale': True, 'content_withheld': True,
                'recovery': 'EXPLICIT_REBIND_CURRENT_AUTHORIZED_SOURCES_OR_CREATE_NEW'}
        return {k: deepcopy(row[k]) for k in ['id', 'version', 'status', 'spec', 'privacy_level']} | {
            'stale': False, 'content_withheld': False, 'analysis': analyze(row['spec']), 'model_called': False}

    def stories(self, nid, scope, actor):
        rows = [r for r in self.list(nid, scope, self.COLLECTION) if r['created_by'] == actor]
        return {'items': [self._view(nid, scope, r) for r in rows[-50:]], 'truncated': len(rows) > 50}

    def story(self, nid, scope, actor, sid): return self._view(nid, scope, self._owned(nid, scope, actor, sid))

    def create_story(self, nid, scope, actor, value, *, reauthorize=lambda: None):
        spec = CreateIn.model_validate(value).spec.model_dump(); reauthorize()
        with self.store.transaction(nid, scope) as state:
            if len(collection(state, self.COLLECTION)) >= 100: raise ValueError('adaptation limit reached')
            captures = self._capture_spec(nid, scope, spec, state)
            row = new_row(nid, scope, actor, {'spec': spec, 'capture': captures, 'privacy_level': 'LOCAL_ONLY',
                'storage_contract': 'ADAPTATION_OVER_PLANNING_IDS_NOT_COLLABORATION_BRANCH'})
            self._current(nid, scope, row, state); reauthorize(); collection(state, self.COLLECTION)[row['id']] = row
        return self._view(nid, scope, row)

    def save(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = SaveIn.model_validate(value); reauthorize()
        with self.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, sid, state); self._version(row, data.expected_version); self._current(nid, scope, row, state)
            if row['status'] == 'ARCHIVED': raise ValueError('restore before editing')
            spec = data.spec.model_dump()
            if spec['graph_id'] != row['spec']['graph_id']: raise ValueError('create a separate adaptation for a different graph')
            capture = self._capture_spec(nid, scope, spec, state); reauthorize()
            change_row(row, actor, data.expected_version, lambda r: r.update(spec=spec, capture=capture, status='DRAFT', reviewed_at=None, reviewed_by=None))
            self._current(nid, scope, row, state); reauthorize(); result = deepcopy(row)
        return self._view(nid, scope, result)

    def _receipt(self, row):
        return digest([SCHEMA, row['id'], row['version'], row['status'], row['spec'], row['capture']])

    def review_preview(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = VersionIn.model_validate(value); row = self._owned(nid, scope, actor, sid)
        self._version(row, data.expected_version); self._current(nid, scope, row); analysis = analyze(row['spec'])
        current = self._owned(nid, scope, actor, sid); self._version(current, data.expected_version); self._current(nid, scope, current); reauthorize()
        return {'preview_digest': self._receipt(row), 'analysis': analysis, 'can_approve': row['status'] == 'REVIEW' and analysis['can_review']}

    def review(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = ReviewIn.model_validate(value); reauthorize()
        with self.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, sid, state); self._version(row, data.expected_version)
            # Archive is the one safe operation allowed while sources are stale.
            if data.action != 'archive': self._current(nid, scope, row, state)
            transitions = {'submit': ('DRAFT', 'REVIEW'), 'approve': ('REVIEW', 'APPROVED'), 'restore': ('ARCHIVED', 'DRAFT')}
            if data.action in transitions:
                before, after = transitions[data.action]
                if row['status'] != before: raise ValueError('invalid review transition')
            elif data.action == 'archive': after = 'ARCHIVED'
            else:
                if row['status'] == 'ARCHIVED': raise ValueError('use restore')
                after = 'DRAFT'
            if data.action == 'approve':
                if data.preview_digest != self._receipt(row): raise StaleSourceError('review exact current preview')
                if not analyze(row['spec'])['can_review']: raise ValueError('resolve path errors or analysis limits before approval')
            reauthorize()
            change_row(row, actor, data.expected_version, lambda r: r.update(status=after, reviewed_at=now() if after == 'APPROVED' else None, reviewed_by=actor if after == 'APPROVED' else None))
            if data.action != 'archive': self._current(nid, scope, row, state)
            reauthorize(); result = deepcopy(row)
        return self._view(nid, scope, result)

    def preview(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = PlayIn.model_validate(value); row = self._owned(nid, scope, actor, sid)
        self._version(row, data.expected_version); self._current(nid, scope, row)
        if row['status'] == 'ARCHIVED': raise ValueError('restore before playback')
        result = play(row['spec'], data.choices)
        result['character_name'] = row['capture']['characters'].get(result['node']['character_id'])
        current = self._owned(nid, scope, actor, sid); self._version(current, data.expected_version); self._current(nid, scope, current); reauthorize(); return result

    def _refresh_candidate(self, nid, scope, row, state):
        spec = deepcopy(row['spec'])
        graph = require_row(state, self.planning.GRAPHS, spec['graph_id'])
        if graph['status'] != 'ACTIVE': raise StaleSourceError('restore the original planning graph before rebinding')
        spec['graph_version'] = graph['version']
        for node in spec['nodes']:
            current = require_row(state, self.planning.NODES, node['node_id'])
            if current['graph_id'] != graph['id'] or current['status'] == 'ARCHIVED':
                raise StaleSourceError('original planning node unavailable; create a new adaptation')
            node['node_version'] = current['version']
        capture = self._capture_spec(nid, scope, spec, state)
        return spec, capture

    def refresh_preview(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = VersionIn.model_validate(value); row = self._owned(nid, scope, actor, sid)
        self._version(row, data.expected_version)
        spec, capture = self._refresh_candidate(nid, scope, row, self.store.read(nid, scope)); reauthorize()
        return {'preview_digest': digest([self._receipt(row), spec, capture]), 'retained_nodes': len(spec['nodes']),
                'changed_source_count': sum(row['capture']['sources'].get(cid) != source for cid, source in capture['sources'].items()),
                'content_policy': 'RETAIN_AUTHOR_TEXT_AS_UNREVIEWED_DRAFT_NO_AUTOMATIC_REWRITE'}

    def refresh(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = ExportIn.model_validate(value); reauthorize()
        with self.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, sid, state); self._version(row, data.expected_version)
            spec, capture = self._refresh_candidate(nid, scope, row, state)
            if data.preview_digest != digest([self._receipt(row), spec, capture]): raise StaleSourceError('source rebind preview changed')
            reauthorize()
            change_row(row, actor, data.expected_version, lambda r: r.update(spec=spec, capture=capture,
                status='ARCHIVED' if r['status'] == 'ARCHIVED' else 'DRAFT', reviewed_at=None, reviewed_by=None))
            self._current(nid, scope, row, state); reauthorize(); result = deepcopy(row)
        return self._view(nid, scope, result)

    def revisions(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = VersionIn.model_validate(value); row = self._owned(nid, scope, actor, sid)
        self._version(row, data.expected_version); self._current(nid, scope, row); result = []
        for old in row.get('history', []):
            try: self._current(nid, scope, old)
            except (FileNotFoundError, ValueError): continue
            result.append({'version': old['version'], 'status': old['status'], 'spec': deepcopy(old['spec']),
                           'preview_digest': digest([self._receipt(row), self._receipt(old)])})
        reauthorize(); return {'items': result[-100:], 'truncated': len(result) > 100, 'restore_as': 'NEW_DRAFT'}

    def restore_revision(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = RestoreIn.model_validate(value); reauthorize()
        with self.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, sid, state); self._version(row, data.expected_version); self._current(nid, scope, row, state)
            if row['status'] == 'ARCHIVED': raise ValueError('restore the adaptation before restoring a revision')
            old = next((h for h in row.get('history', []) if h['version'] == data.restore_version), None)
            if old is None: raise FileNotFoundError('interactive revision')
            self._current(nid, scope, old, state)
            if data.preview_digest != digest([self._receipt(row), self._receipt(old)]): raise StaleSourceError('interactive historical preview changed')
            change_row(row, actor, data.expected_version, lambda r: r.update(spec=deepcopy(old['spec']), capture=deepcopy(old['capture']),
                status='DRAFT', reviewed_at=None, reviewed_by=None, restored_from_version=old['version']))
            self._current(nid, scope, row, state); reauthorize(); result = deepcopy(row)
        return self._view(nid, scope, result)

    def _manifest(self, nid, scope, row):
        manifest = []
        for aid, capture in row['capture']['assets'].items():
            self._asset(nid, scope, aid)
            missing = False
            try: self.assets.content(aid, branch_id=scope.get('branch_id'))
            except (FileNotFoundError, ValueError): missing = True
            manifest.append({'asset_id': aid, 'version': capture['version'], 'sha256': capture['sha256'], 'kind': capture['kind'],
                'missing': missing, 'packaged': False, 'reason': 'MISSING_OR_CORRUPT' if missing else 'TEXT_SUBSET_REFERENCE_ONLY'})
        return manifest

    def export_preview(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = ExportIn.model_validate(value); row = self._owned(nid, scope, actor, sid)
        self._version(row, data.expected_version); self._current(nid, scope, row)
        manifest = self._manifest(nid, scope, row); analysis = analyze(row['spec'])
        result = {'can_export': row['status'] == 'APPROVED' and analysis['can_review'], 'media_manifest': manifest,
            'losses': ['MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED', 'NO_TARGET_CUSTOM_SCREENS_ANIMATION_OR_PLUGINS', 'TARGET_WHITESPACE_AND_FONT_RENDERING_NOT_VERIFIED'],
            'target_runtime': 'NOT_RUN', 'schema': SCHEMA, 'analysis': analysis}
        result['preview_digest'] = digest([self._receipt(row), result]); self._current(nid, scope, row); reauthorize(); return result

    def export(self, nid, scope, actor, sid, value, *, reauthorize=lambda: None):
        data = ExportIn.model_validate(value); preview = self.export_preview(nid, scope, actor, sid, data, reauthorize=reauthorize)
        if data.preview_digest != preview['preview_digest']: raise StaleSourceError('export preview changed')
        if not preview['can_export']: raise ValueError('approve exact current story before export')
        row = self._owned(nid, scope, actor, sid); self._version(row, data.expected_version); self._current(nid, scope, row)
        spec = deepcopy(row['spec'])
        for n in spec['nodes']:
            for c in n['choices']: c['condition_tree'] = parse_condition(c['condition'])
        neutral = {'schema': SCHEMA, 'adaptation_id': row['id'], 'adaptation_version': row['version'], 'spec': spec,
            'source_versions': {cid: source['version'] for cid, source in row['capture']['sources'].items()}, 'characters': row['capture']['characters'],
            'privacy': 'LOCAL_ONLY', 'collaboration_branch_is_not_narrative_ending': True}
        encode = lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
        files = {'story.json': encode(neutral), 'media-manifest.json': encode(preview['media_manifest']), 'compatibility.json': encode(preview),
            'game/story.rpy': renpy_export(row['spec'], row['capture']['characters']).encode('utf-8'),
            'README.txt': ('Experimental B07 independent export, not a manuscript or Canon write.\nExtract into a NEW empty directory.\nstory.json is the versioned engine-neutral story.\ngame/story.rpy is a generated Ren\'Py 8.5.4 documented text/menu subset.\nTarget runtime NOT_RUN. No runtime, plugins, media bytes or third-party scripts included.\nUse a new Ren\'Py project to inspect the generated file. Never overwrite an existing project.\nMedia references, missing resources and compatibility losses are listed separately.\nThe in-app preview uses bounded deterministic playback; character names and dialogue are escaped.\n').encode('utf-8')}
        files['checksums.json'] = encode({name: hashlib.sha256(content).hexdigest() for name, content in files.items()})
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                info = zipfile.ZipInfo('interactive-story-' + row['id'] + '/' + name, date_time=(2026, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
        current = self.export_preview(nid, scope, actor, sid, data, reauthorize=reauthorize)
        if current['preview_digest'] != preview['preview_digest']: raise StaleSourceError('export authority changed')
        self._current(nid, scope, row); reauthorize(); content = buffer.getvalue()
        return {'filename': 'interactive-story-' + row['id'] + '-v' + str(row['version']) + '.zip', 'mime': 'application/zip',
            'content_base64': base64.b64encode(content).decode(), 'sha256': hashlib.sha256(content).hexdigest(), 'published': False, 'target_runtime': 'NOT_RUN'}
