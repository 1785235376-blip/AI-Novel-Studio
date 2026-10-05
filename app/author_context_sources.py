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
