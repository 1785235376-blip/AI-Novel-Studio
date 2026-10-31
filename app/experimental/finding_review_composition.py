"""Read-through Inbox bindings; original finding/Canon services remain owners.

Navigation metadata is a formal target contract. The generic Inbox does not
pretend to open a source version or manufacture the detailed review inputs.
"""
from copy import deepcopy
from fastapi import HTTPException
from .inbox import ReviewBinding, digest

FEATURE = 'finding_review_v1'
CANON_DOMAIN = 'pending_canon'


def register_finding_review_bindings(inbox, legacy_api, authorize, require_flag):
    def guard(ctx, *, project=False):
        require_flag('unified_review_inbox'); require_flag(FEATURE)
        if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.read') != (ctx.actor, ctx.scope):
            raise HTTPException(403, {'code': 'REVIEW_AUTHORITY_CHANGED'})
        if project and legacy_api._pending_canon_review_authorize(ctx.novel_id, ctx.token, 'domain.read') != ctx.actor:
            raise HTTPException(403, {'code': 'CANON_ACTOR_CHANGED'})

    def base(row, ctx, source, *, version, preview, target, stale, authority_scope):
        return {'id': row['id'], 'novel_id': ctx.novel_id, 'scope': deepcopy(ctx.scope),
                'authority_scope': deepcopy(authority_scope), 'status': row.get('effective_status', row['status']),
                'version': version, 'review_revision': version,
                'source_revision': source.get('version') if source else None,
                'source_versions': {source['chapter_id']: deepcopy(source)} if source else {},
                'source_hash': row.get('source_digest') or row.get('preview_digest') or digest(row),
                'preview': preview, 'target': target, 'stale': stale,
                'allowed_actions': [], 'batch_safe': False, 'risk': 'ORIGINAL_PREVIEW_AND_HUMAN_CONFIRMATION_REQUIRED',
                'privacy_state': row.get('privacy_level', 'UNKNOWN'),
                'created_at': row.get('created_at', ''), 'created_by': row.get('created_by', 'UNKNOWN')}

    def findings(ctx, kind):
        guard(ctx)
        result = legacy_api.finding_review_service.list(ctx.novel_id, ctx.scope, kind)
        guard(ctx)
        rows = []
        for row in result['items']:
            target = {'module': 'write', 'panel': 'check', 'surface': 'finding-review', 'kind': kind,
                      'finding_id': row['id'], 'review_version': row['review_version'],
                      'source_navigation': deepcopy(row['navigation']),
                      'navigation_contract': 'FORMAL_TARGET_ONLY'}
            rows.append(base(row, ctx, row['source'], version=row['review_version'], preview=row['description'],
                             target=target, stale=row['stale_source'], authority_scope=row['scope']))
        return rows

    for kind in ('continuity', 'narrative'):
        inbox.register(ReviewBinding(kind + '_finding', lambda ctx, kind=kind: findings(ctx, kind), feature=FEATURE))

    def canon(ctx):
        guard(ctx, project=True)
        result = legacy_api.pending_canon_review_service.list(ctx.novel_id)
        guard(ctx, project=True)
        rows = []
        for row in result['items']:
            authority = row['scope']
            source = row.get('review_source') or row['source']
            target = {'module': 'write', 'panel': 'check', 'surface': 'pending-canon-review',
                      'pending_id': row['id'], 'review_version': row['version'],
                      'authority_scope': deepcopy(authority), 'navigation_contract': 'FORMAL_TARGET_ONLY',
                      'source_navigation': {'chapter_id': source['chapter_id'], 'chapter_version': source['version'],
                                            'source_digest': source['digest'], 'scope': deepcopy(authority),
                                            'available': source == row['source'],
                                            'source_state': row['source_state'],
                                            'historical_review_source': bool(row.get('review_source'))} if source else None}
            item = base(row, ctx, source, version=row['version'],
                        preview={'proposals': deepcopy(row['proposals']), 'source_state': row['source_state'], 'lineage': row['lineage']},
                        target=target, stale=row['stale_source'], authority_scope=authority)
            item['recovery_required'] = row['recovery_required']
            item['current_source_revision'] = row['source']['version'] if row['source'] else None
            rows.append(item)
        return rows

    inbox.register(ReviewBinding(CANON_DOMAIN, canon, feature=FEATURE))
