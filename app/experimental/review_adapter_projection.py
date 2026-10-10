"""Read-through receipt views; original services retain every state transition.

The source inspectors are formal surface contracts, not rendered exact-open
routes. These projections intentionally carry no source preview or lineage.
"""
from copy import deepcopy

from fastapi import HTTPException

from .inbox import ReviewBinding
from .ux import TaskReader, safe_code


FORMAL_SOURCE_ONLY = 'FORMAL_SOURCE_ONLY'
CANCEL_STATES = frozenset({'DRAFT', 'NOT_CONFIGURED', 'RUNNING', 'REVIEW_REQUIRED', 'FAILED', 'STALE'})


def adapter_reader(service, domain, feature, permission, list_method, get_method, authorize, require_flag):
    def guard(ctx, write=False):
        require_flag(feature)
        if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.write' if write else permission) != (ctx.actor, ctx.scope):
            raise HTTPException(403, {'code': 'ADAPTER_PROJECTION_AUTHORITY_CHANGED'})

    def read(ctx):
        guard(ctx)
        # Research sources and receipts share this original transaction view.
        # Visual references are reread through their original owner as well.
        with service.store.transaction(ctx.novel_id, ctx.scope):
            guard(ctx)
            candidates = getattr(service, list_method)(ctx.novel_id, ctx.scope, ctx.actor)['items']
            rows = []
            for candidate in candidates:
                guard(ctx)
                if (candidate.get('novel_id') != ctx.novel_id or candidate.get('scope') != ctx.scope
                        or candidate.get('created_by') != ctx.actor):
                    continue
                try:
                    row = getattr(service, get_method)(ctx.novel_id, ctx.scope, ctx.actor, candidate['id'])
                except FileNotFoundError:
                    # Only an original source/receipt visibility denial is an
                    # omission. Corruption and other failures propagate.
                    continue
                guard(ctx)
                if (row.get('id') != candidate['id'] or row.get('novel_id') != ctx.novel_id
                        or row.get('scope') != ctx.scope or row.get('created_by') != ctx.actor):
                    continue
                rows.append(row)
            verified = []
            # Asset/reference owners live outside the experimental transaction.
            # Recheck every original source after the first complete read pass.
            for candidate in rows:
                guard(ctx)
                try:
                    row = getattr(service, get_method)(ctx.novel_id, ctx.scope, ctx.actor, candidate['id'])
                except FileNotFoundError:
                    continue
                guard(ctx)
                if (row.get('id') != candidate['id'] or row.get('novel_id') != ctx.novel_id
                        or row.get('scope') != ctx.scope or row.get('created_by') != ctx.actor):
                    continue
                verified.append({'id': row['id'], 'novel_id': ctx.novel_id, 'scope': deepcopy(ctx.scope),
                    'created_by': ctx.actor, 'created_at': row['created_at'], 'version': row['version'],
                    'status': row['status'], 'stale': row['status'] in {'STALE', 'INVALIDATED'},
                    'recovery_required': bool(row.get('recovery_required')),
                    'cancel_available': row.get('capacity', {}).get('cancel_available') is not False,
                    'error_code': safe_code(row['error_code']) if row.get('error_code') else None,
                    'allowed_actions': [], 'batch_safe': False,
                    'privacy_state': 'SOURCE_AUTHORITY_ONLY', 'risk': 'ORIGINAL_DOMAIN_REVIEW_REQUIRED',
                    'source_versions': {'receipt_version': row['version']},
                    'navigation_contract': FORMAL_SOURCE_ONLY,
                    'target': {'id': row['id'], 'domain': domain, 'version': row['version'],
                               'navigation_contract': FORMAL_SOURCE_ONLY},
                    'automatic_resume': False, 'model_quality': 'NOT_RUN',
                    'runtime_admission': 'NOT_CONFIGURED', 'durable_worker': False})
            guard(ctx)
            return verified

    return read, guard


def mount_review_adapter_projections(workspace, inbox, research, embedding, authorize, require_flag):
    for service, domain, label, feature, permission, list_method, get_method, action_method in (
        (research, 'research_analysis', 'Research 原分析回执', 'research_library_v2', 'domain.write',
         'analysis_jobs', 'analysis_job', 'analysis_action'),
        (embedding, 'visual_identity', '视觉身份原比较回执', 'visual_embeddings', 'domain.read',
         'visual_checks', 'visual_check', 'visual_action'),
    ):
        read, guard = adapter_reader(service, domain, feature, permission, list_method, get_method, authorize, require_flag)

        def cancel(ctx, rid, version, service=service, action_method=action_method, guard=guard):
            current = lambda: guard(ctx, write=True)
            current()
            if action_method == 'analysis_action':
                result = service.analysis_action(ctx.novel_id, ctx.scope, ctx.actor, rid, 'cancel', version, guard=current)
            else:
                result = service.visual_action(ctx.novel_id, ctx.scope, ctx.actor, rid, 'cancel', version, current)
            current()
            return result

        workspace.task_readers += (TaskReader(domain, label, feature, read, feature, cancel, CANCEL_STATES),)
        inbox.register(ReviewBinding(domain, read, None, feature, frozenset()))
