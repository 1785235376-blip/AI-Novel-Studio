"""Explicit reviewed fact-use pointers on original Creative ownership.

No canonical facts, document content, assets, executors or approvals are copied.
Impact is a bounded author-only observation of these declared uses and the
original shot's verified formal bindings; absence of an edge proves nothing.
"""
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..experimental.common import StaleSourceError, new_row, snapshot
from ..experimental.planning import digest
from .models import CreativeProductionDocumentIn
from .storyboard import storyboard_receipt

COLLECTION = 'creative_story_fact_uses_v1'
MAX_USES = 200
MAX_FACTS = 5000
MAX_FACT_VISITS = 1000


class FactCapacityError(ValueError):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class FactPin(Strict):
    id: str = Field(min_length=1, max_length=160)
    version: int = Field(ge=1)
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class FactTarget(Strict):
    document_id: str = Field(min_length=1, max_length=240)
    document_version: int = Field(ge=1)
    document_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    scene_id: str = Field(min_length=1, max_length=240)
    shot_id: str = Field(min_length=1, max_length=240)
    shot_version: int = Field(ge=1)
    shot_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class FactUseIn(Strict):
    expected_version: int = Field(ge=1)
    document_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    shot_version: int = Field(ge=1)
    shot_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    fact: FactPin
    purpose: Literal['APPEARANCE_STATE', 'PROP_STATE', 'KNOWLEDGE', 'CAUSAL_CONTEXT']
    rationale: str = Field(min_length=1, max_length=1000)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_boolean(cls, value):
        if value is not True:
            raise ValueError("CREATIVE_STORY_FACT_CONFIRMATION_REQUIRED")
        return value


class CreativeStoryFacts:
    def __init__(self, creative):
        self.creative = creative
        self.graph = None

    def configure(self, graph):
        self.graph = graph
        graph.configure_creation_owner(self.creative.store)

    def _fact(self, nid, scope, rid, *, observation=None):
        if self.graph is None:
            raise FileNotFoundError('CREATIVE_STORY_FACT_OWNER_UNAVAILABLE')
        if observation is None:
            state, rows = self.graph._rows(nid, scope)
            observation = (state, rows, {}, [MAX_FACT_VISITS])
        state, rows, memo, budget = observation
        row = rows.get(rid)
        if (not isinstance(row, dict) or row.get('novel_id') != nid or row.get('scope') != scope
                or row.get('kind') != 'STORY_RELATION' or row.get('data', {}).get('layer') != 'WORLD_FACT'
                or 'research_sources' in row):
            raise FileNotFoundError('CREATIVE_STORY_FACT_UNAVAILABLE')
        # Check accessibility independently from freshness. Changed public sources
        # may explain stale evidence; hidden/deleted/foreign ancestors may not.
        def accessible(item, seen):
            if len(seen) >= 32 or item['id'] in seen:
                raise FactCapacityError('CREATIVE_STORY_FACT_CYCLE_OR_DEPTH')
            if item['id'] in memo:
                return memo[item['id']]
            budget[0] -= 1
            if budget[0] < 0:
                raise FactCapacityError('CREATIVE_STORY_FACT_TRAVERSAL_LIMIT')
            if (item.get('novel_id') != nid or item.get('scope') != scope or 'research_sources' in item
                    or item.get('story_project_incarnation') != self.creative.store.incarnation(nid)):
                raise FileNotFoundError('CREATIVE_STORY_FACT_UNAVAILABLE')
            # Re-resolve original entity/scene/planning/world references before
            # classifying a version mismatch as merely stale. The World owner's
            # freshness check intentionally coalesces these cases; this metadata
            # projection must not expose a revoked ancestor as stale evidence.
            try:
                captured = self.graph._capture(nid, scope, item, state)
            except (ValueError, FileNotFoundError, KeyError):
                raise FileNotFoundError('CREATIVE_STORY_FACT_UNAVAILABLE') from None
            for field, dataset in (('character_ids', 'characters'), ('location_ids', 'locations')):
                entities = {entry['id']: entry for entry in self.graph.novels.data_set(nid, dataset)}
                for entity_id in item.get('links', {}).get(field, []):
                    entity = entities.get(entity_id)
                    if (entity is None or entity.get('hidden') or entity.get('secret')
                            or entity.get('branch_id') != scope.get('branch_id')):
                        raise FileNotFoundError('CREATIVE_STORY_FACT_UNAVAILABLE')
            self.creative._chapter_evidence(nid, scope, list(item.get('sources', {})))
            for cid in item.get('sources', {}):
                if self.creative.chapters_for(scope).get(cid).get('branch_id') != scope.get('branch_id'):
                    raise FileNotFoundError('CREATIVE_STORY_FACT_UNAVAILABLE')
            fresh = True
            try:
                self.graph.assert_sources(nid, item['sources'], scope)
            except StaleSourceError:
                fresh = False
            for key in self.graph._fresh_capture_fields(item):
                if captured[key] != item[key]: fresh = False
            for parent_id in item.get('semantic_sources', {}):
                parent = rows.get(parent_id)
                if not isinstance(parent, dict):
                    raise FileNotFoundError('CREATIVE_STORY_FACT_UNAVAILABLE')
                if not accessible(parent, (*seen, item['id'])): fresh = False
            memo[item['id']] = fresh
            return fresh
        fresh = accessible(row, ())
        pin = {'id': row['id'], 'version': row['version'], 'digest': digest(snapshot(row))}
        return {**pin, 'title': row['title'], 'status': row['status'], 'fresh': fresh}

    def _document(self, nid, scope, rid):
        creative = self.creative
        incarnation = creative.store.incarnation(nid)
        budget = [100]
        def accessible(document_id, seen):
            budget[0] -= 1
            if budget[0] < 0 or len(seen) >= 16 or document_id in seen:
                raise StaleSourceError('CREATIVE_STORY_FACT_DOCUMENT_CYCLE_OR_DEPTH')
            row = creative._raw(nid, scope, document_id)
            if (row.get('project_incarnation') != incarnation or row.get('status') == 'ARCHIVED'
                    or row.get('scope') != scope or row.get('novel_id') != nid):
                raise FileNotFoundError('CREATIVE_STORY_FACT_TARGET_UNAVAILABLE')
            CreativeProductionDocumentIn.model_validate({k: row[k] for k in CreativeProductionDocumentIn.model_fields if k in row})
            creative._chapter_evidence(nid, scope, row.get('source_chapter_ids', []))
            parents = row.get('source_documents', {})
            if not isinstance(parents, dict) or len(parents) > 8:
                raise ValueError('CREATIVE_SOURCE_BINDING_CHANGED')
            for parent in parents:
                accessible(parent, (*seen, document_id))
            return row
        row = accessible(rid, ())
        try:
            creative.assert_current(nid, scope, row)
            fresh = True
        except StaleSourceError:
            fresh = False
        if row.get('mode') != 'STORYBOARD':
            raise FileNotFoundError('CREATIVE_STORY_FACT_TARGET_UNAVAILABLE')
        return row, fresh

    def _rows(self, nid, scope):
        rows = self.creative.store.read(nid, scope)['collections'].get(COLLECTION, {})
        if not isinstance(rows, dict) or len(rows) > MAX_USES:
            raise ValueError('CREATIVE_STORY_FACT_CAPACITY')
        incarnation = self.creative.store.incarnation(nid)
        for key, row in rows.items():
            if (not isinstance(row, dict) or row.get('id') != key or row.get('novel_id') != nid
                    or row.get('scope') != scope or row.get('project_incarnation') != incarnation
                    or row.get('contract') != 'creative-fact-use/1' or row.get('status') != 'CONFIRMED'):
                raise ValueError('CREATIVE_STORY_FACT_BINDING_INVALID')
            FactPin.model_validate(row.get('fact'))
            target = FactTarget.model_validate(row.get('target'))
            FactUseIn.model_validate({'expected_version': target.document_version, 'document_digest': target.document_digest,
                'shot_version': target.shot_version, 'shot_digest': target.shot_digest, 'fact': row['fact'],
                'purpose': row.get('purpose'), 'rationale': row.get('rationale'), 'confirmed': True})
            if type(row.get('version')) is not int or row['version'] != 1:
                raise ValueError('CREATIVE_STORY_FACT_BINDING_INVALID')
        return rows

    def catalog(self, nid, scope, actor, guard=lambda: None):
        with self.creative.store.existing_owner_only(), self.creative.storyboards._phase(nid, scope, actor, guard):
            guard()
            if self.graph is None:
                raise FileNotFoundError('CREATIVE_STORY_FACT_OWNER_UNAVAILABLE')
            state, rows = self.graph._rows(nid, scope)
            observation = (state, rows, {}, [MAX_FACT_VISITS])
            if len(rows) > MAX_FACTS:
                raise ValueError('CREATIVE_STORY_FACT_CAPACITY')
            items = []
            for rid in sorted(rows):
                try:
                    fact = self._fact(nid, scope, rid, observation=observation)
                    if fact['fresh'] and fact['status'] == 'APPROVED':
                        items.append({k: fact[k] for k in ('id', 'version', 'digest', 'title')})
                except FactCapacityError:
                    raise
                except (FileNotFoundError, ValueError):
                    continue
            guard()
            state, rows = self.graph._rows(nid, scope)
            observation = (state, rows, {}, [MAX_FACT_VISITS])
            for item in items:
                latest = self._fact(nid, scope, item['id'], observation=observation)
                if not latest['fresh'] or latest['status'] != 'APPROVED' or any(latest[k] != item[k] for k in item):
                    raise StaleSourceError('CREATIVE_STORY_FACT_OBSERVATION_CHANGED')
            guard()
            return {'contract': 'creative-story-facts/1', 'items': items,
                    'coverage': 'APPROVED_WORLD_FACT_RELATIONS_ONLY',
                    'legacy_unbound_facts': 'RECREATE_CANDIDATE_AND_REVIEW_IN_ORIGINAL_STORY_GRAPH'}

    def confirm(self, nid, scope, actor, rid, shot_id, value, guard=lambda: None):
        body = FactUseIn.model_validate(value.model_dump() if hasattr(value, 'model_dump') else value)
        if not body.rationale.strip():
            raise ValueError('CREATIVE_STORY_FACT_RATIONALE_REQUIRED')
        creative = self.creative
        with creative.store.existing_owner_only(), creative.storyboards._phase(nid, scope, actor, guard, write=True):
            guard()
            fact = self._fact(nid, scope, body.fact.id)
            if (not fact['fresh'] or fact['status'] != 'APPROVED'
                    or {k: fact[k] for k in ('id', 'version', 'digest')} != body.fact.model_dump()):
                raise StaleSourceError('CREATIVE_STORY_FACT_CHANGED')
            row = creative.get(nid, scope, rid)
            if row['version'] != body.expected_version or creative.document_digest(row) != body.document_digest:
                raise StaleSourceError('CREATIVE_STORY_FACT_DOCUMENT_CHANGED')
            receipt, shot = creative.storyboards._owned_shot(row, shot_id, body)
            target = {'document_id': rid, 'document_version': row['version'], 'document_digest': body.document_digest,
                      'scene_id': shot['shot']['scene_id'], 'shot_id': shot_id,
                      'shot_version': shot['shot_version'], 'shot_digest': shot['shot_digest']}
            rows = self._rows(nid, scope)
            # Identical explicit confirmations are idempotent, including after reopen.
            for old in rows.values():
                if (old['created_by'] == actor and old['fact'] == body.fact.model_dump() and old['target'] == target
                        and old['purpose'] == body.purpose and old['rationale'] == body.rationale):
                    guard()
                    return self._saved(old)
            if len(rows) >= MAX_USES:
                raise ValueError('CREATIVE_STORY_FACT_CAPACITY')
            saved = new_row(nid, scope, actor, {'contract': 'creative-fact-use/1', 'status': 'CONFIRMED',
                'project_incarnation': creative.store.incarnation(nid), 'fact': body.fact.model_dump(),
                'target': target, 'purpose': body.purpose, 'rationale': body.rationale})
            guard()
            if self._fact(nid, scope, body.fact.id) != fact or creative.document_digest(creative.get(nid, scope, rid)) != body.document_digest:
                raise StaleSourceError('CREATIVE_STORY_FACT_OBSERVATION_CHANGED')
            # Writes use the active original Creative/Asset phase, not a new store.
            state = creative.store._local.active[creative.store.key(nid, scope)]
            state['collections'].setdefault(COLLECTION, {})[saved['id']] = saved
            guard()
            return self._saved(saved)

    @staticmethod
    def _saved(row):
        return deepcopy({k: row[k] for k in ('id', 'version', 'status', 'fact', 'target', 'purpose', 'rationale')})

    def _item(self, nid, scope, binding, guard, observation=None):
        fact = self._fact(nid, scope, binding['fact']['id'], observation=observation)
        row, fresh = self._document(nid, scope, binding['target']['document_id'])
        receipt = storyboard_receipt(row)
        shot = next((s for s in receipt['shots'] if s['shot_id'] == binding['target']['shot_id']), None)
        if shot is None:
            # Deleted identities cannot be exposed from a saved pointer alone.
            raise FileNotFoundError('CREATIVE_STORY_FACT_TARGET_UNAVAILABLE')
        target = binding['target']
        blockers = []
        if not fact['fresh'] or fact['status'] != 'APPROVED': blockers.append('FACT_NOT_CURRENT_APPROVED')
        if {k: fact[k] for k in ('id', 'version', 'digest')} != binding['fact']: blockers.append('FACT_PIN_CHANGED')
        if not fresh: blockers.append('DOCUMENT_SOURCE_STALE')
        if receipt['document_snapshot'] != {'id': target['document_id'], 'version': target['document_version'], 'digest': target['document_digest']}:
            blockers.append('DOCUMENT_PIN_CHANGED')
        same_shot = shot['shot_version'] == target['shot_version'] and shot['shot_digest'] == target['shot_digest']
        if not same_shot: blockers.append('SHOT_PIN_CHANGED')
        assets = []
        if same_shot:
            selected = {**receipt, 'shots': [shot]}
            self.creative.storyboards._formal_images(nid, scope, selected, guard)
            if shot['image_asset'] is not None: assets.append(deepcopy(shot['image_asset']))
            if shot.get('video_result') is not None: assets.append(deepcopy(shot['video_result']['asset']))
        return {**self._saved(binding), 'current_fact': {k: fact[k] for k in ('id', 'version', 'digest', 'title', 'status')},
                'state': 'STALE' if blockers else 'CURRENT', 'blockers': blockers, 'assets': assets,
                'evidence': 'AUTHOR_CONFIRMED_FACT_USE_AND_EXACT_ORIGINAL_SHOT_BINDINGS',
                'evidence_path': [{'kind': 'WORLD_RECORD', **deepcopy(binding['fact'])},
                    {'kind': 'CREATIVE_SHOT', **deepcopy(target)}],
                'asset_paths': [{'asset': deepcopy(asset), 'via': 'EXACT_ORIGINAL_SHOT_BINDING'} for asset in assets],
                'recommendation': 'ORIGINAL_OWNER_MANUAL_REVIEW', 'cost': 'UNKNOWN'}

    def impact(self, nid, scope, actor, *, document_id=None, fact_id=None, guard=lambda: None):
        creative = self.creative
        with creative.store.existing_owner_only(), creative.storyboards._phase(nid, scope, actor, guard):
            guard()
            if self.graph is None:
                raise FileNotFoundError('CREATIVE_STORY_FACT_OWNER_UNAVAILABLE')
            if document_id is not None: self._document(nid, scope, document_id)
            if fact_id is not None: self._fact(nid, scope, fact_id)
            state, facts = self.graph._rows(nid, scope)
            observation = (state, facts, {}, [MAX_FACT_VISITS])
            items, observed = [], []
            for binding in sorted(self._rows(nid, scope).values(), key=lambda row: row['id']):
                if document_id is not None and binding['target']['document_id'] != document_id: continue
                if fact_id is not None and binding['fact']['id'] != fact_id: continue
                try:
                    item = self._item(nid, scope, binding, guard, observation)
                    items.append(item); observed.append(binding)
                except FactCapacityError:
                    raise
                except (FileNotFoundError, ValueError):
                    # No hidden IDs, labels, saved rationale, or omitted counts.
                    continue
            guard()
            state, facts = self.graph._rows(nid, scope)
            observation = (state, facts, {}, [MAX_FACT_VISITS])
            for binding, item in zip(observed, items):
                if self._item(nid, scope, binding, guard, observation) != item:
                    raise StaleSourceError('CREATIVE_STORY_FACT_OBSERVATION_CHANGED')
            guard()
            return {'contract': 'creative-fact-impact/1', 'items': items,
                    'coverage': 'EXPLICIT_CONFIRMED_FACT_USES_AND_CURRENT_SHOT_ASSET_BINDINGS',
                    'unavailable_or_unrecorded_dependencies': 'UNKNOWN', 'unrecorded_dependencies': 'UNKNOWN',
                    'temporal_reasoning': 'NOT_EVALUATED', 'transitive_graph_timeline_export_coverage': 'NOT_EVALUATED',
                    'automatic_regeneration': False, 'model_called': False}
