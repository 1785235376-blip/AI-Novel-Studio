"""Portable B05 drafts, composed through the original edition owner only.

No approval, lock, source prose, identity or history crosses the file boundary.
Preview is advisory: adoption recomputes it inside the owner's CAS transaction.
"""
from copy import deepcopy
from contextlib import ExitStack, contextmanager
import json
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from .common import StaleSourceError, new_id
from ..creative.project_store import CreativeProjectStore
from .multilingual_editions import RuleIn, VersionIn, language_code
from .planning import StrictModel, digest

MAX_GLOSSARY_BYTES = 512 * 1024
MAX_GLOSSARY_RULES = 100
SCHEMA = 'language-terminology-v1'
RULE_FIELDS = frozenset(RuleIn.model_fields) - {'expected_version'}


class GlossaryPreviewIn(VersionIn):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    document: str = Field(min_length=1, max_length=MAX_GLOSSARY_BYTES)


class GlossaryAdoptIn(GlossaryPreviewIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    selected_indices: list[Annotated[int, Field(strict=True, ge=0, lt=MAX_GLOSSARY_RULES)]] = Field(min_length=1, max_length=MAX_GLOSSARY_RULES)


class GlossaryDocument(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False, strict=True)
    schema: Literal['language-terminology-v1']
    source_language: str = Field(min_length=2, max_length=64)
    target_language: str = Field(min_length=2, max_length=64)
    rules: list[dict] = Field(max_length=MAX_GLOSSARY_RULES)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate JSON object key')
        result[key] = value
    return result


def parse_glossary(document):
    try:
        if len(document.encode('utf-8')) > MAX_GLOSSARY_BYTES:
            raise ValueError('glossary exceeds 512 KiB UTF-8')
        parsed = json.loads(document, object_pairs_hook=_unique_object,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid JSON constant')))
        data = GlossaryDocument.model_validate(parsed)
        language_code(data.source_language); language_code(data.target_language)
        for rule in data.rules:
            if set(rule) != RULE_FIELDS: raise ValueError('exact portable rule fields required')
            value = RuleIn.model_validate({'expected_version': 1, **rule}, strict=True)
            if value.model_dump(exclude={'expected_version'}) != rule:
                raise ValueError('portable rules must not require whitespace normalization')
        return data.model_dump()
    except (ValueError, TypeError, RecursionError, UnicodeError):
        # Never echo imported text through validation errors.
        raise ValueError('invalid glossary: use the closed v1 JSON schema, literal valid Unicode and original rule limits') from None


def portable_rule(rule):
    return {key: deepcopy(rule[key]) for key in sorted(RULE_FIELDS)}


def source_terms(rule):
    return {rule['source_term'], *rule['source_aliases']}


class TerminologyPortability:
    def __init__(self, service):
        self.service = service
        # Reuse the existing project identity owner, never provision a marker.
        self.owner = CreativeProjectStore(service.store)

    @contextmanager
    def _read_owner(self, nid, scope):
        with self.owner.existing_owner_only():
            with self.service.store.transaction(nid, scope):
                with self.owner.owner_lease(nid):
                    yield

    def _preview(self, nid, scope, actor, row, document):
        if (document['source_language'], document['target_language']) != (row['source_language'], row['target_language']):
            raise ValueError('glossary language pair must exactly match this edition')
        entries = []
        incoming = document['rules']
        for index, rule in enumerate(incoming):
            duplicates, conflicts = [], []
            # Every existing state participates, including revoked and locked.
            # Overlapping aliases remain ambiguous even when preferred text agrees.
            for old_index, old in enumerate(row['rules']):
                if portable_rule(old) == rule: duplicates.append({'kind': 'existing', 'index': old_index})
                elif source_terms(old) & source_terms(rule): conflicts.append({'kind': 'existing', 'index': old_index})
            for other_index, other in enumerate(incoming):
                if index == other_index: continue
                if other == rule: duplicates.append({'kind': 'file', 'index': other_index})
                elif source_terms(other) & source_terms(rule): conflicts.append({'kind': 'file', 'index': other_index})
            # Keep the first otherwise eligible duplicate in a file; all duplicate
            # rows still appear in preview, never silently discarded on adoption.
            duplicate_blocks = any(r['kind'] == 'existing' or r['index'] < index for r in duplicates)
            entries.append({'index': index, 'rule': rule, 'duplicates': duplicates, 'conflicts': conflicts,
                            'eligible': not duplicate_blocks and not conflicts})
        return {'preview_digest': digest([SCHEMA, nid, scope, actor, row['id'], row['version'], row['created_at'], row['created_by'], row['novel_id'], row['scope'], self.owner.incarnation(nid), row['sources'], row['rules'], document]),
                'entries': entries, 'remaining_capacity': MAX_GLOSSARY_RULES - len(row['rules']),
                'edition_version': row['version'], 'draft_only': True}

    def preview(self, nid, scope, actor, eid, value, *, reauthorize=lambda: None):
        data = GlossaryPreviewIn.model_validate(value)
        document = parse_glossary(data.document)
        with self._read_owner(nid, scope):
            reauthorize()
            row = self.service._owned(nid, scope, actor, eid)
            self.service._version(row, data.expected_version)
            self.service._current(nid, scope, row)
            result = self._preview(nid, scope, actor, row, document)
            self.service._current(nid, scope, row)
            reauthorize()
            return result

    def adopt(self, nid, scope, actor, eid, value, *, reauthorize=lambda: None):
        data = GlossaryAdoptIn.model_validate(value)
        document = parse_glossary(data.document)
        selected = data.selected_indices
        if any(type(index) is not int for index in selected) or len(set(selected)) != len(selected):
            raise ValueError('select unique glossary row indices')
        def update(row, texts):
            preview = self._preview(nid, scope, actor, row, document)
            if preview['preview_digest'] != data.preview_digest:
                raise StaleSourceError('glossary preview changed; preview and confirm again')
            if len(selected) > preview['remaining_capacity']:
                raise ValueError('edition supports at most 100 terminology rules')
            if any(index < 0 or index >= len(preview['entries']) or not preview['entries'][index]['eligible'] for index in selected):
                raise ValueError('selected glossary rows are unavailable or conflicting')
            for index in sorted(selected):
                row['rules'].append({'id': new_id(), 'version': 1, 'status': 'DRAFT', 'created_by': actor,
                                     **deepcopy(document['rules'][index])})
        # _mutate owns the scope transaction. Acquire its project lease only
        # after that transaction begins, retaining it through the original
        # atomic commit. The initial pre-transaction guard holds no owner lock.
        with self.owner.existing_owner_only(), ExitStack() as lifecycle:
            incarnation = self.owner.incarnation(nid)
            leased = False
            def guarded():
                nonlocal leased
                reauthorize()
                active = getattr(self.service.store._local, 'active', {})
                if self.service.store.key(nid, scope) in active and not leased:
                    lifecycle.enter_context(self.owner.owner_lease(nid))
                    leased = True
                if self.owner.incarnation(nid) != incarnation:
                    raise StaleSourceError('project incarnation changed; reopen the current project')
            return self.service._mutate(nid, scope, actor, eid, data.expected_version, update, guarded)

    def export(self, nid, scope, actor, eid, value, *, reauthorize=lambda: None):
        data = VersionIn.model_validate(value)
        with self._read_owner(nid, scope):
            reauthorize()
            row = self.service._owned(nid, scope, actor, eid)
            self.service._version(row, data.expected_version)
            self.service._current(nid, scope, row)
            document = {'schema': SCHEMA, 'source_language': row['source_language'], 'target_language': row['target_language'],
                        'rules': [portable_rule(rule) for rule in row['rules']]}
            content = json.dumps(document, ensure_ascii=False, indent=2) + '\n'
            # A successful download is always importable within the same bounds.
            parse_glossary(content)
            self.service._current(nid, scope, row)
            reauthorize()
            return {'filename': 'terminology-v1.json', 'mime': 'application/json;charset=utf-8', 'content': content,
                    'rule_count': len(document['rules']), 'draft_only': True, 'published': False}
