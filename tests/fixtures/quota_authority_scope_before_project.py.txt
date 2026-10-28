"""Branchless File project management lease, for a future quota operation.

No route or ledger is attached. The yielded identity is server-owned; callers
must not substitute a branch binding or reuse it after this lease exits.
"""
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException


@contextmanager
def project_management_lease(workspace, nid, token):
    from .. import api
    from ..authorization import AuthorizationScope, ModalityDomain, ScopeKind
    from ..config import settings
    from ..repositories.file.identity import FileIdentityRepository
    from ..repositories.file.mutation_coordinator import workspace_mutation
    from ..repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
    from ..trusted_sessions import TrustedSessionResolver

    if workspace.store.backend != 'file':
        raise HTTPException(409, {'code': 'PROJECT_QUOTA_AUTHORITY_UNSUPPORTED'})
    root = Path(workspace.store.root).resolve()
    if Path(workspace.assets.root).resolve().parent != root:
        raise HTTPException(409, {'code': 'PROJECT_QUOTA_AUTHORITY_UNSUPPORTED'})
    if not settings.enable_collaboration_runtime:
        def check_local():
            actor, scope = api._workbench_authorize(nid, token, None, 'domain.write')
            if actor != 'local-author' or scope != {'mode': 'local', 'novel_id': nid}:
                raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
        check_local()
        expected = workspace.store.incarnation(nid)
        with workspace.assets._lock, workspace_mutation(workspace.assets.root, 'asset-library'):
            with workspace.store.owner_lease(nid) as current:
                check_local()
                if current != expected:
                    raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
                yield {'novel_id': nid, 'incarnation': current}
        return

    resolver = api.trusted_session_resolver
    membership = api.membership_authorization_service
    admin = api.collaboration_admin_service
    try:
        identity = membership.identity_service.repository
        auth = membership.authorization_service
        grants = auth.repository
        topology = api.collaboration_scope_service.repository
        if (type(resolver) is not TrustedSessionResolver
                or type(identity) is not FileIdentityRepository
                or type(grants) is not FileAuthorizationRepository
                or type(topology) is not FileScopeRepository
                or admin.sessions is not resolver or admin.identity is not membership.identity_service
                or admin.authorization is not auth or admin.scopes is not api.collaboration_scope_service
                or api.authorization_service is not auth
                or auth.scope_service is not api.collaboration_scope_service
                or membership.identity_service.scope_service is not api.collaboration_scope_service
                or any(Path(item.path).parent.resolve() != root for item in (identity, grants, topology))):
            raise ValueError('unsupported original authority owners')
        current = admin.trusted_actor(token)
        actor, ws = current.actor_id, current.workspace_id
        project = AuthorizationScope(ScopeKind.PROJECT, ws, nid)
        top = AuthorizationScope(ScopeKind.WORKSPACE, ws)

        def observe():
            with grants.mutation():
                now = admin.actor(token, ws)
                if now.actor_id != actor or now.workspace_id != ws:
                    raise PermissionError('actor changed')
                if topology.project_workspace(nid) != ws:
                    raise PermissionError('project outside workspace')
                admin.require_domain_manager(now, ModalityDomain.NOVEL, project)
                chosen = (('workspace.admin', top)
                    if auth.is_allowed(actor, 'workspace.admin', ModalityDomain.NOVEL, top)
                    else ('domain.write', project))
                return (resolver.binding_observation(token), identity.binding_observation(actor, ws),
                    topology.project_binding_observation(ws, nid), grants.binding_observation(
                        auth, actor, chosen[0], ModalityDomain.NOVEL, chosen[1]))

        before = observe()
        expected = workspace.store.incarnation(nid)
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(403, {'code': 'PROJECT_SCOPE_FORBIDDEN'}) from None
    except (KeyError, ValueError, TypeError):
        raise HTTPException(409, {'code': 'PROJECT_QUOTA_AUTHORITY_UNSUPPORTED'}) from None

    # Match the established File authorization-before-project order, while
    # retaining asset-before-project and scope-before-project. Holding scope
    # after asset also avoids the asset -> scope order used by asset guards.
    with api._workbench_authority_lease(nid, token, actor, {'workspace_id': ws}):
        with workspace.assets._lock, workspace_mutation(workspace.assets.root, 'asset-library'):
            with workspace_mutation(root, 'collaboration-scope'):
                with workspace.store.owner_lease(nid) as current:
                    try:
                        unchanged = observe() == before and current == expected
                    except (HTTPException, KeyError, ValueError, TypeError, PermissionError):
                        unchanged = False
                    if not unchanged:
                        raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
                    yield {'novel_id': nid, 'incarnation': current}
