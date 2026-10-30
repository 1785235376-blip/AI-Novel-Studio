"""Local deterministic STYLE projection through original source owners.

No new canonical collection, automatic execution, source adoption or target write.
The original Workbench owns durable rules and its entire lifecycle; this adapter
provides source validation and a scope -> project lease, including for generic APIs.
"""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar

from ..style_dna_contract import StyleDNA, StyleTarget, StyleResolutionIn, DIMENSIONS
from ..source_privacy import content_digest
from ..creative.service import document_digest
from .common import StaleSourceError, snapshot
from .planning import digest

EPOCH = 'style_dna_project_incarnation'

class StyleDNAService:
    def __init__(self, creative, creation, *, require_enabled=lambda: None, require_creative_enabled=lambda: None):
        self.creative, self.creation, self.require_enabled = creative, creation, require_enabled
        self.require_creative_enabled = require_creative_enabled
        self._active = ContextVar("style_dna_owner_lease", default=None)

    @contextmanager
    def lease(self, nid, scope, *, create=False, _observation=False):
        self.require_enabled()
        active = self._active.get()
        if active is not None:
            if active[:2] != (nid, scope):
                raise ValueError('STYLE_DNA_NESTED_SCOPE_INVALID')
            if active[3] and not _observation:
                raise ValueError('STYLE_DNA_OBSERVATION_WRITE_DENIED')
            yield active[2]
            return
        # Workbench lock -> scope -> project. Do not acquire a project lease
        # before the scope lock, or provision identities during observation.
        store = self.creative.store
        with (nullcontext() if create else store.existing_owner_only()):
            with store.source_lease(nid, scope, _observation=_observation):
                with store.owner_lease(nid) as identity:
                    self.creation.novels.get(nid)
                    token = self._active.set((nid, scope, identity, _observation))
                    try:
                        yield identity
                    finally:
                        self._active.reset(token)
                    self.require_enabled()
                    if store.incarnation(nid) != identity:
                        raise StaleSourceError('STYLE_DNA_PROJECT_CHANGED')

    @staticmethod
    def assert_epoch(row, identity):
        if not row.get('style_dna') or row.get(EPOCH) != identity:
            raise FileNotFoundError('style authority unavailable')

    def assert_access(self, nid, scope, row):
        """Access is independent of freshness; protect history and error payloads too.

        Text/version drift can be repaired. Missing/hidden sources, changed
        privacy, retired owner/member IDs and inaccessible ancestry cannot be
        disclosed through a generic STYLE read or optimistic-conflict response.
        """
        identity = self.creative.store.incarnation(nid)
        budget = [1000]
        def chapter(cid):
            value = self.creation.chapters_for(scope).get(cid)
            if value.get('novel_id') != nid or value.get('hidden') or value.get('secret'):
                raise FileNotFoundError('style source unavailable')
        def document(rid, stack=()):
            budget[0] -= 1
            if budget[0] < 0 or rid in stack or len(stack) >= 16:
                raise FileNotFoundError('style source unavailable')
            self.require_creative_enabled()
            value = self.creative._raw(nid, scope, rid)
            if (value.get('project_incarnation') != identity or value.get('scope') != scope
                    or value.get('novel_id') != nid or value.get('status') == 'ARCHIVED'):
                raise FileNotFoundError('style source unavailable')
            for cid in set(value.get('source_chapter_ids', [])) | set(value.get('source_evidence', {})):
                chapter(cid)
            _, privacy = self.creative._chapter_evidence(nid, scope, value.get('source_chapter_ids', []))
            if privacy != value.get('source_privacy', {}):
                raise FileNotFoundError('style source unavailable')
            for parent in value.get('source_documents', {}):
                document(parent, (*stack, rid))
            return value
        try:
            for version in [row, *row.get('history', [])]:
                self.assert_epoch(version, identity)
                for cid in version.get('source_versions', {}):
                    chapter(cid)
                spec = StyleDNA.model_validate(version['style_dna'])
                for override in spec.overrides:
                    target = override.target
                    if target.chapter is not None:
                        chapter(target.chapter.id)
                    else:
                        value = document(target.document.id)
                        if not any(s.get('id') == target.scene_id for s in value.get('scenes', [])):
                            raise FileNotFoundError('style source unavailable')
                        if target.shot_id is not None and not any(s.get('id') == target.shot_id and s.get('scene_id') == target.scene_id for s in value.get('shots', [])):
                            raise FileNotFoundError('style source unavailable')
        except (ValueError, KeyError):
            raise FileNotFoundError('style source unavailable') from None

    def target(self, nid, scope, target):
        """Validate exact pins via original owners; no client-authored ancestry."""
        target = StyleTarget.model_validate(target)
        if target.level == 'GLOBAL':
            return {'chapter_id': None, 'document': None, 'scene': None, 'shot': None}
        if target.level == 'CHAPTER':
            chapter = self.creation.chapters_for(scope).get(target.chapter.id)
            if chapter.get('novel_id') != nid or chapter.get('hidden') or chapter.get('secret'):
                raise FileNotFoundError('style chapter unavailable')
            if chapter.get('version') != target.chapter.version or content_digest(chapter) != target.chapter.digest:
                raise StaleSourceError('STYLE_DNA_CHAPTER_CHANGED')
            return {'chapter_id': chapter['id'], 'document': None, 'scene': None, 'shot': None}
        self.require_creative_enabled()
        row = self.creative.get(nid, scope, target.document.id)
        if row['version'] != target.document.version or document_digest(row) != target.document.digest:
            raise StaleSourceError('STYLE_DNA_DOCUMENT_CHANGED')
        scene = next((item for item in row.get('scenes', []) if item['id'] == target.scene_id), None)
        if scene is None:
            raise FileNotFoundError('style scene unavailable')
        shot = None
        if target.level == 'SHOT':
            shot = next((item for item in row.get('shots', []) if item['id'] == target.shot_id), None)
            if shot is None or shot.get('scene_id') != scene['id']:
                raise FileNotFoundError('style shot unavailable')
        chapter_id = scene.get('source_chapter_id')
        if chapter_id and chapter_id not in row.get('source_evidence', {}):
            raise StaleSourceError('STYLE_DNA_CHAPTER_ANCESTRY_UNVERIFIED')
        return {'chapter_id': chapter_id, 'document': row, 'scene': scene, 'shot': shot}

    def validate(self, nid, scope, spec):
        spec = StyleDNA.model_validate(spec)
        for override in spec.overrides:
            self.target(nid, scope, override.target)
        return spec

    def resolve(self, nid, scope, rid, value, reauthorize=lambda: None):
        body = StyleResolutionIn.model_validate(value)
        creation = self.creation
        # Same lock order as all original Workbench writes. Nested get_record
        # observes the same capability lock; the source lease is acquired once.
        from ..repositories.file.mutation_coordinator import workspace_mutation
        with creation.store._lock, workspace_mutation(creation.store.root, 'creation-workbench'):
            with self.lease(nid, scope, _observation=True) as identity:
                rows = creation._rows('creation_records')
                row = creation._find(rows, nid, scope, rid)
                self.assert_epoch(row, identity)
                self.assert_access(nid, scope, row)
                reauthorize()
                if row['kind'] != 'STYLE' or row['status'] != 'APPROVED':
                    raise ValueError('STYLE_DNA_APPROVED_PROFILE_REQUIRED')
                if row['version'] != body.expected_version or digest(snapshot(row)) != body.expected_digest:
                    raise StaleSourceError('STYLE_DNA_PROFILE_CHANGED')
                spec = self.validate(nid, scope, row['style_dna'])
                # Original selected text sources remain part of this authority.
                creation._style_sources_current(nid, scope, row)
                current = self.target(nid, scope, body.target)
                layers = [('GLOBAL', spec.global_rules, {'kind': 'STYLE', 'id': rid,
                    'version': row['version'], 'digest': body.expected_digest})]
                for level in ('CHAPTER', 'SCENE', 'SHOT'):
                    for override in spec.overrides:
                        target = override.target
                        matches = target.level == level
                        if level == 'CHAPTER':
                            matches = matches and target.chapter.id == current['chapter_id']
                        else:
                            matches = matches and body.target.document is not None and target.document.id == body.target.document.id and target.scene_id == body.target.scene_id
                            if level == 'SHOT':
                                matches = matches and target.shot_id == body.target.shot_id
                        if matches:
                            layers.append((level, override.rules, target.model_dump(mode='json', exclude_none=True)))
                effective, conflicts, contributors = {}, [], []
                for level, rules, source in layers:
                    contributors.append({'level': level, 'source': source, 'dimensions': list(rules)})
                    for dimension, text in rules.items():
                        next_value = {'value': text, 'level': level, 'source': source}
                        if dimension in effective and effective[dimension]['value'] != text:
                            conflicts.append({'kind': 'EXPLICIT_OVERRIDE', 'dimension': dimension,
                                              'earlier': effective[dimension], 'selected': next_value})
                        effective[dimension] = next_value
                authored = []
                document = current['document'] or {}
                for path, owner, mapping in (
                    ('visual_target', document.get('visual_target') or {}, {'style': None, 'color': 'color', 'rhythm': None, 'atmosphere': None}),
                    ('shot', current['shot'] or {}, {'composition': 'composition', 'color': 'color', 'sound': 'sound', 'sound_effect': None,
                                                  'camera_angle': 'camera_language', 'camera_motion': 'camera_language'})):
                    for field, dimension in mapping.items():
                        text = owner.get(field)
                        if isinstance(text, str) and text.strip():
                            entry = {'path': path + '.' + field, 'value': text,
                                     'source': body.target.document.model_dump(mode='json')}
                            authored.append(entry)
                            if dimension in effective and effective[dimension]['value'] != text:
                                conflicts.append({'kind': 'AUTHORED_TEXT_DIFFERS', 'dimension': dimension,
                                                  'rule': effective[dimension], 'authored': entry})
                # Re-read all source pins and authority immediately before publication.
                self.validate(nid, scope, row['style_dna'])
                self.target(nid, scope, body.target)
                creation._style_sources_current(nid, scope, row)
                reauthorize()
                return {'style_source': {'id': rid, 'version': row['version'], 'digest': body.expected_digest},
                    'target': body.target.model_dump(mode='json', exclude_none=True), 'effective': effective,
                    'contributors': contributors, 'conflicts': conflicts, 'authored_context': authored,
                    'uncovered_dimensions': [d for d in DIMENSIONS if d not in effective],
                    'coverage': 'PARTIAL_AUTHORED_RULES_ONLY', 'semantic_conflicts_verified': False,
                    'execution_ready': False, 'model_called': False, 'target_mutated': False,
                    'limitations': ['Local preview only; no generation or approval adoption.',
                        'Comic pages, panels, assets and legacy style/profile.json are not resolved.',
                        'Text differences are visible, not semantic contradiction detection.']}
