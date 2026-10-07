"""Composition hooks for the existing Write / Tasks / Review surfaces."""
from ..services.branch_manuscript_service import FEATURE
from .branch_manuscript_api import create_branch_manuscript_router
from .inbox import ReviewBinding


def mount_branch_manuscript(router, legacy_api, owner, require_flag, require_host_session,
                             *, source_services=(), inbox=None):
    def authorize_mainline(nid, token, permission):
        require_flag(FEATURE); require_host_session(token)
        # No branch role inherits PROJECT authority. Mainline import/merge is
        # an explicit project-bound operation through the original resolver.
        return legacy_api._authorize_novel_project(nid, token, permission)

    def save_mainline(nid, cid, document, version, source, token):
        actor, scope = authorize_mainline(nid, token, 'domain.write')
        authorize_mainline(nid, token, 'domain.review')
        current = legacy_api.chapter_service.get(cid)
        if current['novel_id'] != nid: raise FileNotFoundError(cid)
        event = legacy_api.audit_service.build(actor, 'BRANCH_HUMAN_MERGE', 'Chapter', cid, scope,
                                               {'expected_version': version, 'result_version': version + 1})
        authorize_mainline(nid, token, 'domain.write')
        return legacy_api.collaboration_application_service.atomic_updates.save_chapter_with_audit(
            cid, document, version, source, actor.actor_id, event)

    router.include_router(create_branch_manuscript_router(owner, legacy_api._workbench_authorize,
        require_flag, require_host_session, authorize_mainline=authorize_mainline, save_mainline=save_mainline))
    for source in source_services:
        source.chapter_reader = owner.bind_reader(source)
    if inbox is not None:
        def read(ctx):
            from fastapi import HTTPException
            require_flag(FEATURE)
            def current():
                require_flag(FEATURE)
                if legacy_api._workbench_authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.read') != (ctx.actor, ctx.scope):
                    raise HTTPException(403, {'code': 'BRANCH_AUTHORITY_CHANGED'})
            current()
            if ctx.scope.get('mode') != 'collaboration': return []
            visible = []
            for row in owner.review_items(ctx):
                counterpart = row['source_scope' if row['target']['kind'] == 'forks' else 'target_scope']
                try:
                    if counterpart.get('mode') == 'local':
                        actor, _ = authorize_mainline(ctx.novel_id, ctx.token, 'domain.read')
                        if actor.actor_id != ctx.actor: raise HTTPException(403)
                    elif legacy_api._workbench_authorize(ctx.novel_id, ctx.token, counterpart.get('branch_id'), 'domain.read') != (ctx.actor, counterpart):
                        raise HTTPException(403)
                except HTTPException as exc:
                    if exc.status_code in {401, 403, 404}: continue
                    raise
                visible.append(row)
            current()
            return visible
        # Shared inbox action schemas do not own branch cancel/apply semantics.
        # Expose exact original navigation only; all mutations stay in its API.
        inbox.register(ReviewBinding('branch_manuscript', read, None, FEATURE, frozenset()))
