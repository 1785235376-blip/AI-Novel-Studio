"""CAS/human-review facade over the original pending Canon and Canon owners."""
from __future__ import annotations
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .finding_review_service import digest, now, FindingReviewConflict
from ..source_privacy import content_digest

OWNER = 'PENDING_CANON_REVIEW_V1'


class CanonPreviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    chapter_id: str | None = Field(default=None, min_length=1, max_length=200)


class CanonDecisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    preview_digest: str = Field(pattern='^[a-f0-9]{64}$')
    chapter_id: str | None = Field(default=None, min_length=1, max_length=200)
    action: Literal['approve', 'reject']
    reason: str = Field(min_length=1, max_length=2000)
    operation_id: str = Field(min_length=1, max_length=120)
    confirmed: Literal[True]


def pending_digest(row):
    return digest({k: v for k, v in row.items() if k not in {'_review_commit', 'review_receipts'}})


class PendingCanonReviewService:
    def __init__(self, canon, chapters, novels):
        self.canon, self.chapters, self.novels = canon, chapters, novels

    def _source(self, nid, row, requested):
        recorded = row.get('chapter_id') or (row.get('review_source') or {}).get('chapter_id')
        cid = recorded or requested
        if row.get('status', 'PENDING') == 'PENDING' and recorded and requested and recorded != requested:
            raise ValueError('CANON_SOURCE_ID_MISMATCH')
        if not cid: return None, None
        chapter = self.chapters.get(cid)
        if chapter.get('is_archived') or chapter.get('novel_id') != nid or chapter.get('branch_id') or chapter.get('scope', {}).get('mode') == 'collaboration':
            raise FileNotFoundError(cid)
        return ({'chapter_id': cid, 'version': chapter['version'], 'digest': content_digest(chapter)},
                {'chapter_id': cid, 'version': chapter['version'], 'content': chapter.get('content', ''),
                 'document': deepcopy(chapter.get('document'))})

    def _preview(self, nid, row, chapter_id=None):
        if row.get('novel_id') != nid: raise FileNotFoundError(row.get('id'))
        row = {'status': 'PENDING', **row}
        proposals = row.get('proposals', [])
        if not isinstance(proposals, list) or len(proposals) > 500 or any(not isinstance(x, dict) for x in proposals): raise ValueError('CANON_PROPOSAL_LIMIT')
        if len(str(proposals).encode()) > 500_000: raise ValueError('CANON_PROPOSAL_LIMIT')
        unavailable = False
        try: source, evidence = self._source(nid, row, chapter_id)
        except FileNotFoundError:
            if chapter_id and row.get('status', 'PENDING') == 'PENDING' and not row.get('_review_commit'): raise
            source, evidence = None, None; unavailable = True
        source_state = 'EXPLICIT_CURRENT_SOURCE' if source else 'SOURCE_UNAVAILABLE' if unavailable else 'NOT_CONFIGURED'
        # Historical generated candidates did not record a source version. Do
        # not fabricate that lineage: the author reviews the current source.
        basis = {'pending_digest': pending_digest(row), 'source': source,
                 'source_state': source_state, 'version': row.get('review_version', 1)}
        return {'id': row['id'], 'novel_id': nid, 'scope': {'mode': 'project', 'novel_id': nid},
                'version': row.get('review_version', 1), 'status': row['status'], 'proposals': deepcopy(proposals),
                'preview_digest': digest(basis), 'source': source, 'source_state': source_state,
                'source_evidence': evidence,
                'lineage': 'LEGACY_SOURCE_VERSION_NOT_RECORDED' if not row.get('source_version') else 'SOURCE_VERSION_RECORDED',
                'review_source': deepcopy(row.get('review_source')),
                'stale_source': bool(row.get('review_source') and row['review_source'] != source),
                'history': deepcopy(row.get('review_history', [])), 'recovery_required': bool(row.get('_review_commit')),
                'allowed_actions': (['recover', 'cancel_recovery'] if row.get('_review_commit') else
                                    ['approve', 'reject'] if row['status'] == 'PENDING' and source else
                                    ['reject'] if row['status'] == 'PENDING' else []),
                'owner': OWNER, 'model_called': False}

    def list(self, nid):
        self.novels.get(nid)
        rows = self.canon.repository.list_reviewable(nid)
        return {'items': [self._preview(nid, row) for row in rows[-500:]], 'total': len(rows), 'owner': OWNER}

    def preview(self, nid, pid, body):
        self.novels.get(nid)
        return self._preview(nid, self.canon.repository.get_pending(pid), body.chapter_id)

    def review(self, nid, pid, actor, body, check=lambda: None):
        self.novels.get(nid)
        request_digest = digest({**body.model_dump(), 'actor_id': actor})
        def decide(row):
            check()
            if row.get('novel_id') != nid: raise FileNotFoundError(pid)
            receipt = row.get('review_receipts', {}).get(body.operation_id)
            if receipt:
                if receipt['digest'] != request_digest: raise FindingReviewConflict('CANON_OPERATION_REUSED')
                return row, False
            if row.get('review_version', 1) != body.expected_version:
                raise FindingReviewConflict('CANON_VERSION_CONFLICT', {'id': pid, 'version': row.get('review_version', 1)})
            if row.get('status', 'PENDING') != 'PENDING': raise FindingReviewConflict('CANON_ALREADY_REVIEWED')
            preview = self._preview(nid, row, body.chapter_id)
            if preview['preview_digest'] != body.preview_digest: raise FindingReviewConflict('CANON_PREVIEW_STALE')
            if body.action == 'approve' and not preview['source']: raise ValueError('CANON_SOURCE_REQUIRED')
            if not body.reason.strip(): raise ValueError('CANON_REASON_REQUIRED')
            if len(row.get('review_history', [])) >= 100: raise ValueError('CANON_HISTORY_LIMIT')
            result = deepcopy(row); version = row.get('review_version', 1)
            result.update(review_owner=OWNER, review_version=version + 1, status='APPROVED' if body.action == 'approve' else 'REJECTED',
                          review_source=preview['source'], reviewed_by=actor, reviewed_at=now())
            result.setdefault('review_history', []).append({'version': version, 'action': body.action.upper(), 'actor_id': actor,
                 'reason': body.reason.strip(), 'timestamp': now(), 'preview_digest': body.preview_digest, 'source': preview['source']})
            result.setdefault('review_receipts', {})[body.operation_id] = {'digest': request_digest, 'version': version + 1}
            check()
            return result, body.action == 'approve'
        row = self.canon.repository.review_pending_atomic(nid, pid, body.operation_id, request_digest, decide, check)
        return self._preview(nid, row, body.chapter_id)

    def cancel_recovery(self, nid, pid, actor, expected_version, check=lambda: None):
        self.novels.get(nid)
        row = self.canon.repository.cancel_pending_recovery(nid, pid, actor, expected_version, check)
        return self._preview(nid, row)

    def recover(self, nid, pid, expected_version, check=lambda: None):
        self.novels.get(nid)
        row = self.canon.repository.recover_pending_committed(nid, pid, expected_version, check)
        return self._preview(nid, row)
