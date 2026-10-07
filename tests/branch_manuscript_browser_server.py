"""Disposable synthetic File host for the real two-browser branch workflow."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    from app.dependencies import (novel_service, chapter_service, collaboration_scope_service as scopes,
        identity_service as identities, authorization_service as authorization, branch_manuscript_service as branches)
    from app.collaboration import Workspace, Storyline, Branch
    from app.identity import User, WorkspaceMembership
    from app.authorization import AuthorizationScope, ScopeKind, ModalityDomain, DomainRole, DomainRoleAssignment
    from app.experimental.ux import ReadContext
    nid, wid, sid, bid = 'surface-branch-book', 'surface-branch-workspace', 'surface-branch-story', 'surface-branch-a'
    novel_service.create({'id': nid, 'title': '合成分支验收作品'})
    chapter_service.create(nid, {'title': '主线保留章节', 'content': 'MAINLINE_UNCHANGED_SYNTHETIC'})
    scopes.create_workspace(Workspace(wid, '合成验收工作区')); scopes.link_project(wid, nid)
    scopes.create_storyline(Storyline(sid, wid, nid, '合成故事线')); scopes.create_branch(Branch(bid, wid, nid, sid, '合成分支'))
    for actor in ('surface-writer-a', 'surface-writer-b'):
        identities.create_user(User(actor, actor)); identities.add_membership(WorkspaceMembership('membership-' + actor, actor, wid))
        authorization.assign_role(DomainRoleAssignment('project-' + actor, actor, DomainRole.DOMAIN_LEAD,
            ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.PROJECT, wid, nid), actor))
    scope = {'mode': 'collaboration', 'novel_id': nid, 'workspace_id': wid, 'storyline_id': sid, 'branch_id': bid}
    branches.create(ReadContext(nid, scope, 'surface-writer-a', 'surface-writer-a', bid),
                    {'title': '合成分支正文', 'content': 'BRANCH_BASE_SYNTHETIC'})
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8057, log_level='warning')
