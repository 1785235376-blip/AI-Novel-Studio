"""Explicit, bounded source markers only; ordinary prose needs semantic review.

This does not infer lasting facts or call a model. Candidate values and evidence
are exact substrings of an accepted canonical chapter revision.
"""
from __future__ import annotations
import re
import uuid
from .source_privacy import content_digest

METHOD = 'EXPLICIT_SOURCE_MARKER'
CONTRACT = 'ACCEPTED_CANON_SOURCE_V1'
_MARKER = re.compile(r'(?im)^[ \t]*(?:Canon fact|设定事实)[ \t]*[:：][ \t]*(?P<value>[^\r\n]*)\r?$')


def build_pending_canon(job_id, chapter):
    version = chapter.get('version')
    if type(version) is not int or version < 1 or not chapter.get('id') or not chapter.get('novel_id'):
        raise ValueError('CANON_ACCEPTED_REVISION_REQUIRED')
    if chapter.get('branch_id') or chapter.get('scope', {}).get('mode') == 'collaboration':
        raise ValueError('BRANCH_CANON_REVIEW_ADAPTER_REQUIRED')
    text = chapter.get('content')
    if not isinstance(text, str):
        raise ValueError('CANON_ACCEPTED_REVISION_REQUIRED')
    limit_reason = 'SOURCE_SIZE' if len(text) > 2_000_000 else None
    sha = content_digest(chapter); proposals = []; seen = set()
    for match in (_MARKER.finditer(text) if limit_reason is None else ()):
        raw = match.group('value'); value = raw.strip()
        if not value or value in seen: continue
        if len(value) > 4000 or len(proposals) >= 100:
            limit_reason = 'FACT_SIZE' if len(value) > 4000 else 'CANDIDATE_COUNT'
            break
        start = match.start('value') + len(raw) - len(raw.lstrip())
        evidence = {'chapter_id': chapter['id'], 'chapter_version': version,
                    'content_sha256': sha, 'start': start, 'end': start + len(value), 'quote': value}
        proposals.append({'fact': value, 'source_job': job_id, 'source_evidence': [evidence],
                          'analysis_source': METHOD, 'privacy_level': 'LOCAL_ONLY'})
        seen.add(value)
    if len(str(proposals).encode('utf-8')) > 450_000:
        limit_reason = 'PROPOSAL_BYTES'
    if limit_reason: proposals = []  # Never promote a silently partial extraction.
    return {'producer_contract': CONTRACT, 'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'novel-generation-accept:{job_id}')),
            'novel_id': chapter['novel_id'], 'chapter': chapter.get('number'), 'chapter_id': chapter['id'],
            'status': 'PENDING', 'proposals': proposals, 'source': 'archivist', 'source_job': job_id,
            'source_version': version, 'source_digest': sha, 'review_owner': 'PENDING_CANON_REVIEW_V1',
            'privacy_level': 'LOCAL_ONLY',
            'extraction': {'method': METHOD, 'version': 1, 'model_called': False,
                           'status': 'LIMIT_EXCEEDED' if limit_reason else 'CANDIDATES_FOUND' if proposals else 'NO_EXPLICIT_FACTS',
                           'complete': limit_reason is None, 'limit_reason': limit_reason,
                           'semantic_extraction': 'NOT_PERFORMED'}}
