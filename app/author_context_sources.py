"""U08 exact controls over identified records in the actual authorized context.

This is a deterministic projection, not another context resolver. Unknown
provenance is never solved by text redaction: any item exclusion removes the
entire potentially dependent context bundle. Explicit manuscript/instruction
inputs are independent author choices, not promised semantic DLP.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json

RECORD_SECTIONS = {'characters': 'CHARACTER', 'locations': 'LOCATION',
                   'active_foreshadowing': 'FORESHADOWING', 'forbidden_secrets': 'SECRET'}
# Only numeric location metadata is inherently independent. Author instructions
# remain separately in the original prompt task, not copied from context.
MAX_SOURCE_ITEMS = 256


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def apply_source_controls(context, novel_id, controls=None, *, omit_dependents=False):
    """Return exact filtered context and local-only review metadata.

    Catalog rows come only from already authorized/provider-eligible context,
    never raw hidden/denied sources or omission identifiers. Pins use actual
    content fingerprints where the source lacks a numeric revision authority.
    """
    choices = controls or []
    if not isinstance(choices, list) or len(choices) > MAX_SOURCE_ITEMS:
        raise ValueError('AUTHOR_SOURCE_CONTROL_LIMIT')
    catalog = []; identities = {}; unidentifiable = False
    for section, kind in RECORD_SECTIONS.items():
        rows = context.get(section, [])
        if not isinstance(rows, list):
            unidentifiable = True; continue
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), (str, int)) or not str(row['id']):
                unidentifiable = True; continue
            key = fingerprint([novel_id, section, str(row['id'])])
            if key in identities:
                raise ValueError('AUTHOR_SOURCE_IDENTITY_AMBIGUOUS')
            identities[key] = (section, str(row['id']))
            version = row.get('version') if type(row.get('version')) is int and row['version'] >= 1 else None
            catalog.append({'key': key, 'kind': kind, 'label': str(row.get('name') or row.get('title') or row['id'])[:200],
                'version': version, 'version_state': 'VERSION_AND_CONTENT_DIGEST' if version else 'CONTENT_DIGEST_ONLY',
                'source_digest': fingerprint(row), 'included': True, 'pinned': False})
            if len(catalog) > MAX_SOURCE_ITEMS: raise ValueError('AUTHOR_SOURCE_CATALOG_LIMIT')
    by_key = {row['key']: row for row in catalog}; seen = set(); excluded = set()
    for choice in choices:
        if not isinstance(choice, dict) or set(choice) != {'key', 'source_digest', 'include'} or type(choice['include']) is not bool:
            raise ValueError('AUTHOR_SOURCE_CONTROL_INVALID')
        key = choice['key']
        if key in seen: raise ValueError('AUTHOR_SOURCE_CONTROL_DUPLICATE')
        seen.add(key)
        # Deliberately identical error for revocation, removal and stale pins;
        # do not echo identifiers, current titles or hidden source counts.
        if key not in by_key or choice['source_digest'] != by_key[key]['source_digest']:
            raise ValueError('AUTHOR_SOURCE_UNAVAILABLE_OR_CHANGED')
        by_key[key]['pinned'] = True
        by_key[key]['included'] = choice['include']
        if not choice['include']: excluded.add(key)
    result = deepcopy(context)
    if excluded or omit_dependents:
        # Base state, summaries, lore/narrative/policy/context packs and legacy
        # style may contain copied content without complete dependency edges.
        # Preserve only identified independent records and authored scaffolding.
        result = {'chapter': context['chapter']} if type(context.get('chapter')) is int else {}
        for section in RECORD_SECTIONS:
            rows = context.get(section, [])
            result[section] = [deepcopy(row) for row in (rows if isinstance(rows, list) else [])
                if isinstance(row, dict) and isinstance(row.get('id'), (str, int))
                and fingerprint([novel_id, section, str(row['id'])]) in by_key
                and fingerprint([novel_id, section, str(row['id'])]) not in excluded]
    return result, {'items': catalog, 'granularity': 'IDENTIFIED_RECORDS_WITH_CONSERVATIVE_DEPENDENCIES',
        'dependent_context_omitted': bool(excluded or omit_dependents),
        'omission_reason': 'DEPENDENCY_PROVENANCE_INCOMPLETE' if excluded or omit_dependents else None,
        'unidentified_sources_require_bundle_removal': unidentifiable,
        'primary_manuscript_and_author_input_separate': True}


# Explicit additions extend this existing context owner. They are pointers to
# original records, never client-authored context or a parallel source store.
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from fastapi import HTTPException
from .experimental.research_library import CitationIn
from .privacy import normalize_privacy, merge_privacy

NATIVE_SOURCE_FLAGS = {'RESEARCH': 'research_library_v2', 'CANON': 'world_character_engines_v2',
                       'STORY_GRAPH': 'temporal_story_graph_v2'}
MAX_ADDED_SOURCES = 16
MAX_ADDED_CHARACTERS = 32000


class AddedAuthorSource(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['CHAPTER', 'CANON', 'STORY_GRAPH', 'RESEARCH']
    id: str = Field(min_length=1, max_length=240)
    version: int | None = Field(default=None, ge=1)
    source_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    citation: CitationIn | None = None
    include: bool = True
    max_characters: int = Field(default=4000, ge=256, le=8000)

    @model_validator(mode='after')
    def exact_citation(self):
        if self.kind == 'RESEARCH':
            if self.citation is None or self.citation.source_id != self.id or self.citation.source_version != self.version or self.citation.paragraph == 0:
                raise ValueError('AUTHOR_RESEARCH_TEXT_CITATION_REQUIRED')
        elif self.citation is not None:
            raise ValueError('AUTHOR_SOURCE_CITATION_KIND_MISMATCH')
        return self


def added_source_key(row):
    return fingerprint([row['kind'], row['id'], (row.get('citation') or {}).get('paragraph')])


@dataclass(frozen=True)
class NativeAuthorContext:
    novel_id: str
    scope: dict
    actor: str
    token: str | None = None
    branch: str | None = None


class NativeAuthorSources:
    """Read-only adapters to original Chapter/Canon/Graph/Research authorities."""
    def __init__(self, legacy, world, graph, research, authorize, require_flag):
        self.legacy, self.world, self.graph, self.research = legacy, world, graph, research
        self.authorize, self.require_flag = authorize, require_flag

    @staticmethod
    def _identified(rows):
        result = {}
        for row in rows:
            previous = result.get(row['key'])
            if previous is not None and previous != row:
                raise ValueError('AUTHOR_SOURCE_IDENTITY_AMBIGUOUS')
            result[row['key']] = row
        return result

    def _guard(self, ctx, kind, *, stored_job=None):
        self.require_flag('author_context_inspector_v2')
        if kind in NATIVE_SOURCE_FLAGS: self.require_flag(NATIVE_SOURCE_FLAGS[kind])
        permission = 'domain.write' if kind == 'STORY_GRAPH' else 'domain.read'
        if stored_job is None:
            if self.authorize(ctx.novel_id, ctx.token, ctx.branch, permission) != (ctx.actor, ctx.scope):
                raise ValueError('AUTHOR_SOURCE_AUTHORITY_CHANGED')
        elif ctx.scope.get('mode') == 'collaboration':
            if not self.legacy.settings.enable_collaboration_runtime:
                raise ValueError('AUTHOR_SOURCE_SCOPE_UNAVAILABLE')
            from .actor_context import ActorContext, SessionContext
            from .authorization import AuthorizationScope, ScopeKind, ModalityDomain
            session = SessionContext(stored_job.session_id, stored_job.client_id, stored_job.actor_id, stored_job.workspace_id)
            actor = ActorContext(stored_job.actor_id, stored_job.workspace_id, session)
            raw = stored_job.scope
            scope = AuthorizationScope(ScopeKind(raw['kind']), raw['workspace_id'], raw.get('project_id'), raw.get('storyline_id'), raw.get('branch_id'))
            self.legacy.membership_authorization_service.require(actor, permission, ModalityDomain.NOVEL, scope)
        elif (self.legacy.settings.enable_collaboration_runtime or stored_job.actor_id
              or stored_job.workspace_id or stored_job.scope or ctx.actor != 'local-author'):
            raise ValueError('AUTHOR_SOURCE_SCOPE_UNAVAILABLE')
        self.legacy.novel_service.get(ctx.novel_id)

    @staticmethod
    def _record(kind, row, text, *, label=None, citation=None, evidence=None, privacy=None):
        def policies(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {'privacy_level', 'privacy', 'locality', 'privacy_state'}: yield normalize_privacy(child)
                    elif key != 'history': yield from policies(child)
            elif isinstance(value, list):
                for child in value: yield from policies(child)
        version = row.get('version') if type(row.get('version')) is int and row['version'] > 0 else None
        identity = str(row.get('id') or ('legacy-content:' + fingerprint(row)))
        projection = {'kind': kind, 'id': identity, 'version': version,
            'label': str(label or row.get('title') or row.get('name') or row.get('fact_key') or identity)[:240],
            'privacy_level': merge_privacy(privacy if privacy is not None else row.get('privacy_level'), *policies(row)),
            'text': text, 'citation': citation, 'evidence': evidence or {},
            'source_digest': fingerprint({key: value for key, value in row.items() if key != 'history'})}
        if citation is not None:
            projection['source_digest'] = fingerprint({'source': projection['source_digest'], 'citation': citation})
        projection['key'] = added_source_key(projection)
        return projection

    def _rows(self, ctx, kind, *, stored_job=None, query=''):
        self._guard(ctx, kind, stored_job=stored_job)
        rows = []
        if kind == 'CHAPTER':
            from .experimental.planning import scoped_sources
            from .source_privacy import effective_source_privacy
            for entry in self.legacy.chapter_service.list(ctx.novel_id):
                if query.strip() and query.strip().casefold() not in (str(entry.get('title', '')) + ' ' + str(entry.get('content', ''))).casefold(): continue
                row = self.legacy.chapter_service.get(entry['id'])
                if row.get('is_archived') or row.get('novel_id') != ctx.novel_id: continue
                if ctx.scope.get('mode') != 'local':
                    # Original branch manuscript adapter is still unavailable.
                    continue
                if row.get('branch_id'): continue
                scoped_sources(self.world, ctx.novel_id, ctx.scope, [row['id']])
                rows.append(self._record(kind, row, str(row.get('content') or ''),
                    privacy=effective_source_privacy(row, ctx.branch), evidence={'chapter_id': row['id'], 'chapter_version': row['version']}))
        elif kind == 'CANON':
            for row in self.world.canon(ctx.novel_id, ctx.scope):
                if row.get('stale') or row.get('status') != 'ACTIVE': continue
                text = json.dumps({'kind': row['kind'], 'title': row['title'], 'data': row['data']}, ensure_ascii=False, sort_keys=True)
                rows.append(self._record(kind, row, text, evidence={'source_record_id': row['source_record_id'],
                    'source_record_version': row.get('source_record_version'), 'sources': row.get('sources', {})}))
            if ctx.scope.get('mode') == 'local':
                for original in self.legacy.canon_service.list(ctx.novel_id):
                    if original.get('branch_id') or original.get('status') in {'REJECTED', 'ARCHIVED', 'PENDING'}: continue
                    # Preserve historical records without manufacturing a numeric
                    # version: content-address their exact original record.
                    row = {**original, 'id': 'legacy:' + str(original['id'])} if original.get('id') else original
                    payload = {key: original[key] for key in ('entity_type', 'entity_id', 'fact_key', 'fact_value', 'fact_type', 'key', 'value', 'fact', 'content') if key in original}
                    if payload: rows.append(self._record(kind, row, json.dumps(payload, ensure_ascii=False, sort_keys=True),
                        evidence={'origin': 'ORIGINAL_CANON', 'source': original.get('source'), 'version_state': 'CONTENT_DIGEST_ONLY' if not row.get('version') else 'VERSION_AND_DIGEST'}))
        elif kind == 'STORY_GRAPH':
            for row in self.graph.records(ctx.novel_id, ctx.scope):
                if row.get('status') != 'APPROVED' or row.get('stale'): continue
                if row['kind'] == 'KNOWLEDGE_EVENT':
                    try: self.require_flag('character_mind_v2')
                    except HTTPException as exc:
                        if exc.status_code == 404: continue
                        raise
                rows.append(self._record(kind, row, json.dumps({'kind': row['kind'], 'title': row['title'], 'data': row['data']}, ensure_ascii=False, sort_keys=True),
                    evidence={'sources': row.get('sources', {}), 'record_kind': row['kind'], 'epistemic_layer': row['data'].get('layer')}))
        elif kind == 'RESEARCH':
            if query.strip():
                # Use the original literal search across all original paragraphs;
                # a late paragraph must not disappear behind a catalogue window.
                matches = self.research.search(ctx.novel_id, ctx.scope, ctx.actor, query, limit=31)
                for evidence in matches['items']:
                    citation = evidence['citation']
                    current = self.research.source(ctx.novel_id, ctx.scope, ctx.actor, citation['source_id'])
                    resolved = self.research.resolve(ctx.novel_id, ctx.scope, ctx.actor, citation)
                    rows.append(self._record(kind, {key: value for key, value in current.items() if key != 'paragraphs'}, resolved['text'], citation=citation,
                        label=f"{current['title']} · 段落 {citation['paragraph']}", privacy='LOCAL_ONLY',
                        evidence={key: resolved.get(key) for key in ('source_digest', 'imported_at', 'accessed_at', 'source_version_label', 'page', 'paragraph')}))
                self._guard(ctx, kind, stored_job=stored_job)
                return rows
            for source in self.research.sources(ctx.novel_id, ctx.scope, ctx.actor)['items'][:100]:
                current = self.research.source(ctx.novel_id, ctx.scope, ctx.actor, source['id'])
                reference_row = {key: value for key, value in current.items() if key != 'paragraphs'}
                for paragraph in current.get('paragraphs', [])[:200]:
                    citation = paragraph['citation']
                    evidence = self.research.resolve(ctx.novel_id, ctx.scope, ctx.actor, citation)
                    rows.append(self._record(kind, reference_row, evidence['text'], citation=citation,
                        label=f"{current['title']} · 段落 {citation['paragraph']}", privacy='LOCAL_ONLY',
                        evidence={key: evidence.get(key) for key in ('source_digest', 'imported_at', 'accessed_at', 'source_version_label', 'page', 'paragraph')}))
                    if len(rows) >= 500: break
                if len(rows) >= 500: break
        self._guard(ctx, kind, stored_job=stored_job)
        return rows

    def catalog(self, ctx, *, kind='CHAPTER', query='', cloud=False):
        rows = [row for row in self._identified(self._rows(ctx, kind, query=query)).values() if not cloud or row['privacy_level'] == 'CLOUD_ALLOWED']
        if query.strip() and kind != 'RESEARCH': rows = [row for row in rows if query.strip().casefold() in (row['label'] + ' ' + row['text']).casefold()]
        result = []
        for row in rows[:30]:
            result.append({**{key: deepcopy(value) for key, value in row.items() if key != 'text'},
                           'preview': row['text'][:500], 'characters': len(row['text']), 'preview_truncated': len(row['text']) > 500})
        self._guard(ctx, kind)
        return {'items': result, 'truncated': len(rows) > 30, 'limit': 30, 'model_called': False, 'automatic_add': False,
                'branch_sources_available': kind != 'CHAPTER' or ctx.scope.get('mode') == 'local'}

    def resolve(self, ctx, refs, *, cloud=False, stored_job=None):
        if len(refs) > MAX_ADDED_SOURCES: raise ValueError('AUTHOR_ADDED_SOURCE_LIMIT')
        parsed = [AddedAuthorSource.model_validate(ref).model_dump(exclude_none=True) for ref in refs]
        if len({added_source_key(ref) for ref in parsed}) != len(parsed): raise ValueError('AUTHOR_ADDED_SOURCE_DUPLICATE')
        catalogs = {}; items = []; manifest = []; total = 0
        for ref in parsed:
            kind = ref['kind']
            self._guard(ctx, kind, stored_job=stored_job)
            if kind == 'CHAPTER':
                from .experimental.planning import scoped_sources
                from .source_privacy import effective_source_privacy
                original = self.legacy.chapter_service.get(ref['id'])
                if (ctx.scope.get('mode') != 'local' or original.get('branch_id') or original.get('is_archived')
                    or original.get('novel_id') != ctx.novel_id):
                    raise ValueError('AUTHOR_ADDED_SOURCE_UNAVAILABLE_OR_CHANGED')
                scoped_sources(self.world, ctx.novel_id, ctx.scope, [original['id']])
                row = self._record(kind, original, str(original.get('content') or ''),
                    privacy=effective_source_privacy(original, ctx.branch), evidence={'chapter_id': original['id'], 'chapter_version': original['version']})
            elif kind == 'RESEARCH':
                original = self.research.source(ctx.novel_id, ctx.scope, ctx.actor, ref['id'])
                evidence = self.research.resolve(ctx.novel_id, ctx.scope, ctx.actor, ref['citation'])
                row = self._record(kind, {key: value for key, value in original.items() if key != 'paragraphs'}, evidence['text'],
                    citation=ref['citation'], label=f"{original['title']} · 段落 {ref['citation']['paragraph']}", privacy='LOCAL_ONLY',
                    evidence={key: evidence.get(key) for key in ('source_digest', 'imported_at', 'accessed_at', 'source_version_label', 'page', 'paragraph')})
            else:
                if kind not in catalogs: catalogs[kind] = self._identified(self._rows(ctx, kind, stored_job=stored_job))
                row = catalogs[kind].get(added_source_key(ref))
            if (row is None or row['source_digest'] != ref['source_digest'] or row['version'] != ref.get('version')
                or (row.get('citation') or None) != (ref.get('citation') or None)
                or cloud and row['privacy_level'] != 'CLOUD_ALLOWED'):
                raise ValueError('AUTHOR_ADDED_SOURCE_UNAVAILABLE_OR_CHANGED')
            text = row['text'][:ref['max_characters']]
            if ref['include']:
                total += len(text)
                if total > MAX_ADDED_CHARACTERS: raise ValueError('AUTHOR_ADDED_CONTEXT_BUDGET_EXCEEDED')
                items.append({**{key: deepcopy(row[key]) for key in ('kind', 'id', 'version', 'label', 'source_digest', 'citation', 'evidence', 'privacy_level')},
                    'text': text, 'layer': 'RESEARCH' if kind == 'RESEARCH' else 'CANON' if kind == 'CANON' else 'AUTHOR_REFERENCE',
                    'untrusted_data': True, 'instructions_allowed': False,
                    'truncated': len(text) < len(row['text']), 'truncation_reason': 'EXPLICIT_CHARACTER_BUDGET' if len(text) < len(row['text']) else None})
            manifest.append({**{key: deepcopy(row[key]) for key in ('key', 'kind', 'id', 'version', 'label', 'source_digest', 'citation', 'privacy_level')},
                'included': ref['include'], 'pinned': True, 'characters': len(text) if ref['include'] else 0,
                'truncated': ref['include'] and len(text) < len(row['text']),
                'truncation_reason': 'EXPLICIT_CHARACTER_BUDGET' if ref['include'] and len(text) < len(row['text']) else None})
        for kind in {ref['kind'] for ref in parsed}: self._guard(ctx, kind, stored_job=stored_job)
        return {'items': items, 'manifest': manifest, 'characters': total, 'model_called': False}

    def check_job(self, job):
        scope = ({'mode': 'collaboration', 'novel_id': job.novel_id, 'workspace_id': job.scope['workspace_id'],
                  'storyline_id': job.scope.get('storyline_id'), 'branch_id': job.scope.get('branch_id')}
                 if job.scope else {'mode': 'local', 'novel_id': job.novel_id})
        ctx = NativeAuthorContext(job.novel_id, scope, job.actor_id or 'local-author', branch=scope.get('branch_id'))
        provider = job.provider or job.requested_provider
        self.resolve(ctx, (job.request_scope or {}).get('added_sources') or [],
                     cloud=self.legacy.runtime.is_remote_text_provider(provider), stored_job=job)


def added_source_content_available(job):
    """Persisted output/history is withheld after source or privacy revocation."""
    refs = (getattr(job, 'request_scope', None) or {}).get('added_sources')
    if not refs: return True
    try:
        validator = getattr(getattr(job, 'author_context_resolver', None), 'validate_content', None)
        if callable(validator):
            validator(job)
            return True
        from .experimental.api import author_preparer
        if author_preparer.native_sources is None: return False
        author_preparer.native_sources.check_job(job)
        return True
    except Exception:
        return False


def apply_added_sources(job, context, *, cloud=False):
    refs = (getattr(job, 'request_scope', None) or {}).get('added_sources') or []
    resolver = getattr(job, 'author_context_resolver', None)
    if not refs:
        if resolver is not None: raise ValueError('AUTHOR_ADDED_SOURCE_UNBOUND')
        return context
    from .experimental.character_author_context import is_character_job
    if is_character_job(job) or not callable(resolver):
        raise ValueError('AUTHOR_ADDED_SOURCE_AUTHORITY_REQUIRED')
    resolved = resolver(cloud=cloud)
    result = deepcopy(context)
    result['explicit_sources'] = {'items': resolved['items'], 'untrusted_data': True, 'instructions_allowed': False,
        'scope': 'EXPLICIT_REVIEWED_ADDITIONS', 'research_is_canon': False}
    job.author_source_manifest = {**(getattr(job, 'author_source_manifest', None) or {}), 'added_items': resolved['manifest']}
    return result
