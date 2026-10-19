"""Request-local, intent-only projection of authorized direct Storyboard pins.

The three reader ports are supplied by the original owners, never JSON clients.
Each returns a context manager whose lease remains open through the DIF operation.
Its guard MUST recheck original permission/Host/feature/incarnation authority AND
the captured version/digest, or hold the original owner lease that keeps that pin
stable. An auth-only guard, raw store reader or detached HTTP response is not this
contract. Missing ports fail closed; this module registers no API or executor.

Acquire these contexts before entering the original DIF transaction. Graph reads
inside a scope transaction are forbidden for some original schemas. The adapter
therefore does not repeat list/get inside that transaction; retained owner guards
must be safe at its commit boundary. The owner wiring must establish that safety.
"""
from __future__ import annotations

from contextlib import AbstractContextManager, ExitStack, contextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..creative.graph_models import MAX_GRAPHS, MAX_MEDIA_NODES, MAX_NODES
from .common import StaleSourceError
from .media import digest


SOURCE_KIND = 'CREATIVE_STORYBOARD'
TARGET_KIND = 'CREATIVE_GRAPH_NODE'
MAX_TARGETS = 20
MAX_GRAPH_NODES = max(MAX_NODES, MAX_MEDIA_NODES)


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Pin(Strict):
    id: str = Field(min_length=1, max_length=240, pattern=r'^[^\x00-\x1f\x7f]+$')
    version: int = Field(ge=1)
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class StoryboardProjection(Strict):
    contract: Literal['studio-storyboard/1']
    document_snapshot: Pin


class GraphIdentity(Strict):
    id: str = Field(min_length=1, max_length=240, pattern=r'^[^\x00-\x1f\x7f]+$')
    version: int = Field(ge=1)
    definition_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    execution_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class GraphIndex(Strict):
    items: list[GraphIdentity] = Field(max_length=MAX_GRAPHS)

    @model_validator(mode='after')
    def unique(self):
        if len({row.id for row in self.items}) != len(self.items):
            raise ValueError('CHANGE_IMPACT_GRAPH_IDENTITY_INVALID')
        return self


class DirectReference(Strict):
    node_id: str = Field(min_length=1, max_length=240, pattern=r'^[^\x00-\x1f\x7f]+$')
    definition_id: Literal['storyboard_plan']
    enabled: bool
    document_snapshot: Pin
    state: Literal['CURRENT', 'STALE']


class GraphProjection(GraphIdentity):
    title: str = Field(min_length=1, max_length=2000, pattern=r'^[^\x00-\x1f\x7f]+$')
    references: list[DirectReference] = Field(max_length=MAX_GRAPH_NODES)

    @model_validator(mode='after')
    def unique(self):
        if len({row.node_id for row in self.references}) != len(self.references):
            raise ValueError('CHANGE_IMPACT_GRAPH_NODE_IDENTITY_INVALID')
        return self


def storyboard_projection(value):
    """Project ONLY an already authorized original Storyboard get receipt."""
    return StoryboardProjection.model_validate({key: value[key] for key in
        ('contract', 'document_snapshot')}).model_dump()


def graph_index_projection(value):
    """Original complete Graph list, not pagination or a caller-filtered list."""
    if not isinstance(value, dict) or set(value) != {'items'} or not isinstance(value['items'], list):
        raise ValueError('CHANGE_IMPACT_GRAPH_INDEX_INVALID')
    if len(value['items']) > MAX_GRAPHS:
        raise ValueError('CHANGE_IMPACT_GRAPH_INDEX_LIMIT')
    return GraphIndex.model_validate({'items': [{key: row[key] for key in GraphIdentity.model_fields}
        for row in value['items']]}).model_dump()


def graph_projection(value):
    """Project original get; unavailable pins stay redacted, never inferred."""
    definition, states = value['definition'], value['reference_states']
    if (not isinstance(definition, dict) or not isinstance(definition.get('nodes'), list)
            or len(definition['nodes']) > MAX_GRAPH_NODES or not isinstance(states, list)
            or len(states) > MAX_GRAPH_NODES):
        raise ValueError('CHANGE_IMPACT_GRAPH_PROJECTION_LIMIT')
    if (any(not isinstance(row, dict) or set(row) != {'node_id', 'state'} or not isinstance(row['node_id'], str)
            or row['state'] not in {'CURRENT', 'STALE', 'UNAVAILABLE'} for row in states)
            or len({row['node_id'] for row in states}) != len(states)):
        raise ValueError('CHANGE_IMPACT_GRAPH_REFERENCE_STATE_INVALID')
    by_id = {row['node_id']: row['state'] for row in states}
    references, ids = [], set()
    for node in definition['nodes']:
        if not isinstance(node, dict) or not isinstance(node.get('id'), str) or node['id'] in ids:
            raise ValueError('CHANGE_IMPACT_GRAPH_NODE_IDENTITY_INVALID')
        ids.add(node['id'])
        if node.get('definition_id') != 'storyboard_plan':
            continue  # Other nodes consume ports, not a direct saved Storyboard pin.
        if definition.get('schema_version') not in {4, 5}:
            raise ValueError('CHANGE_IMPACT_GRAPH_STORYBOARD_SCHEMA_INVALID')
        state = by_id.get(node['id'])
        if state == 'UNAVAILABLE':
            continue
        if state is None or not isinstance(node.get('parameters'), dict):
            raise ValueError('CHANGE_IMPACT_GRAPH_REFERENCE_STATE_INVALID')
        references.append({'node_id': node['id'], 'definition_id': 'storyboard_plan',
            'enabled': node['enabled'], 'document_snapshot': node['parameters']['document_snapshot'], 'state': state})
    return GraphProjection.model_validate({**{key: value[key] for key in GraphIdentity.model_fields},
        'title': definition['title'], 'references': references}).model_dump()


@dataclass(frozen=True)
class OwnerRead:
    """Server-only owner observation; never accept this envelope from a client.

    guard must raise on authority OR captured pin changes throughout the lease.
    nid/actor/scope/incarnation are the actual original owner's resolved identity.
    value is one of the small projections above, not raw storage or permissions.
    """
    owner: Literal['STORYBOARD', 'GRAPH_INDEX', 'GRAPH']
    nid: str
    actor: str
    scope: dict
    incarnation: str
    value: dict
    guard: Callable[[], None]


@dataclass(frozen=True)
class StoryboardReaders:
    """Per-request ports retaining the ORIGINAL invokers and owner read leases.

    storyboard(nid, document_id), graph_index(nid), graph(nid, graph_id).
    Every graph get is individually authorized; list authorization is insufficient.
    No port may return after discarding the guard/lease required at DIF commit.
    """
    storyboard: Callable[[str, str], AbstractContextManager[OwnerRead]]
    graph_index: Callable[[str], AbstractContextManager[OwnerRead]]
    graph: Callable[[str, str], AbstractContextManager[OwnerRead]]


class StoryboardObservation:
    def __init__(self, nid, scope, actor, rid, guard):
        self.nid, self.scope, self.actor, self.rid = nid, deepcopy(scope), actor, rid
        self._outer_guard, self._reads = guard, []
        self._active, self._incarnation = True, None
        self._source, self._nodes = None, None

    def _capture(self, value, owner):
        if (not isinstance(value, OwnerRead) or value.owner != owner or value.nid != self.nid
                or value.actor != self.actor or value.scope != self.scope or not callable(value.guard)
                or not isinstance(value.incarnation, str) or not 1 <= len(value.incarnation) <= 240):
            raise PermissionError('CHANGE_IMPACT_ORIGINAL_OWNER_AUTHORITY_REQUIRED')
        if self._incarnation is None:
            self._incarnation = value.incarnation
        if value.incarnation != self._incarnation:
            raise PermissionError('CHANGE_IMPACT_ORIGINAL_OWNER_INCARNATION_CHANGED')
        self._reads.append(value)
        self.guard()
        return value.value

    def guard(self):
        if not self._active:
            raise PermissionError('CHANGE_IMPACT_ORIGINAL_OWNER_READ_LEASE_CLOSED')
        self._outer_guard()
        for value in self._reads:
            if (value.nid != self.nid or value.actor != self.actor or value.scope != self.scope
                    or value.incarnation != self._incarnation or value.guard() is not None):
                raise PermissionError('CHANGE_IMPACT_ORIGINAL_OWNER_AUTHORITY_CHANGED')
        self._outer_guard()

    def context(self, nid, scope, actor, rid):
        self.guard()
        if (nid, scope, actor, rid) != (self.nid, self.scope, self.actor, self.rid):
            raise PermissionError('CHANGE_IMPACT_OBSERVATION_REQUEST_MISMATCH')
        if self._source is None or self._nodes is None:
            raise FileNotFoundError('CHANGE_IMPACT_ORIGINAL_OWNER_READ_INCOMPLETE')
        return deepcopy(self._source), deepcopy(self._nodes)

    def view(self, nid, scope, actor, rid):
        source, nodes = self.context(nid, scope, actor, rid)
        return {'source': source, 'items': [row['public'] for _, row in sorted(nodes.items())],
            'coverage': 'EXACT_AUTHORIZED_DIRECT_STORYBOARD_GRAPH_REFERENCES_ONLY', 'inferred': [],
            'unrecorded_dependencies': 'UNKNOWN', 'other_owner_coverage': 'NOT_EVALUATED',
            'automatic_regeneration': False, 'truncated': False, 'target_limit': MAX_TARGETS}


@contextmanager
def observe_storyboard(nid, scope, actor, document_id, readers, guard=lambda: None):
    """Open original read contexts first; expose no partial/truncated inventory."""
    if (not isinstance(readers, StoryboardReaders)
            or not all(callable(port) for port in (readers.storyboard, readers.graph_index, readers.graph))):
        raise FileNotFoundError('CHANGE_IMPACT_STORYBOARD_READ_OWNER_UNAVAILABLE')
    if not isinstance(actor, str) or not actor or not isinstance(scope, dict):
        raise PermissionError('CHANGE_IMPACT_ORIGINAL_OWNER_AUTHORITY_REQUIRED')
    observation = StoryboardObservation(nid, scope, actor, document_id, guard)
    try:
        with ExitStack() as leases:
            source = StoryboardProjection.model_validate(observation._capture(
                leases.enter_context(readers.storyboard(nid, document_id)), 'STORYBOARD'))
            if source.document_snapshot.id != document_id:
                raise PermissionError('CHANGE_IMPACT_STORYBOARD_IDENTITY_MISMATCH')
            index = GraphIndex.model_validate(observation._capture(
                leases.enter_context(readers.graph_index(nid)), 'GRAPH_INDEX'))
            epoch = digest(observation._incarnation)
            label = 'Storyboard · ' + document_id
            observation._source = {'kind': SOURCE_KIND, 'id': document_id, 'label': label,
                'binding': {**source.document_snapshot.model_dump(exclude={'id'}), 'incarnation_digest': epoch}}
            nodes = {}
            for identity in sorted(index.items, key=lambda row: row.id):
                graph = GraphProjection.model_validate(observation._capture(
                    leases.enter_context(readers.graph(nid, identity.id)), 'GRAPH'))
                if {key: getattr(graph, key) for key in GraphIdentity.model_fields} != identity.model_dump():
                    raise StaleSourceError('CHANGE_IMPACT_GRAPH_OBSERVATION_CHANGED')
                for reference in sorted(graph.references, key=lambda row: row.node_id):
                    if reference.document_snapshot.id != document_id:
                        continue
                    if len(nodes) >= MAX_TARGETS:
                        raise ValueError('CHANGE_IMPACT_STORYBOARD_TARGET_LIMIT')
                    same = reference.document_snapshot == source.document_snapshot
                    if reference.state == 'CURRENT' and not same:
                        raise StaleSourceError('CHANGE_IMPACT_STORYBOARD_OBSERVATION_CHANGED')
                    stale = not same or reference.state == 'STALE'
                    key = TARGET_KIND + ':' + digest([graph.id, reference.node_id])
                    public = {'key': key, 'kind': TARGET_KIND, 'id': graph.id + '/' + reference.node_id,
                        'label': graph.title + ' · ' + reference.node_id, 'version': graph.version,
                        'status': 'SAVED' if reference.enabled else 'DISABLED', 'feature': 'narrative_production_v2',
                        'stale': stale, 'locked': False, 'lock_version': 0, 'refresh_candidate': False,
                        'refresh_reason': 'ORIGINAL_DOMAIN_MANUAL_REVIEW_REQUIRED',
                        'evidence_type': 'EXACT_SAVED_DIRECT_STORYBOARD_REFERENCE',
                        'evidence': [{'key': SOURCE_KIND + ':' + document_id, 'label': label,
                            'state': 'STALE' if stale else 'CURRENT', 'recorded_version': reference.document_snapshot.version,
                            'current_version': source.document_snapshot.version}]}
                    nodes[key] = {'public': public, 'fingerprint': digest([epoch, graph.id, graph.version,
                        graph.definition_digest, graph.execution_digest, reference.model_dump()])}
            observation._nodes = nodes
            observation.guard()
            yield observation
            observation.guard()
    finally:
        observation._active = False
