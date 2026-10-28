"""Original File project-management authority fenced across a quota mutation.

This adapter performs no storage or quota mutation. Its caller must use the
existing asset owner while inside the returned context. Unsupported authority
owners are rejected rather than approximated from a branch write permission.
"""
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException


@contextmanager
def project_quota_authority(workspace, nid, scope, actor, token, guard):
    from .. import api
    from ..authorization import AuthorizationScope, ModalityDomain, ScopeKind
    from ..collaboration import CollaborationScope
    from ..config import settings
    from ..repositories.file.identity import FileIdentityRepository
    from ..repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
    from ..trusted_sessions import TrustedSessionResolver

    if (workspace.store.backend != 'file' or scope.get('novel_id') != nid
            or scope.get('mode') not in {'local', 'collaboration'}
            or (scope.get('mode') == 'local') == bool(settings.enable_collaboration_runtime)):
        raise HTTPException(409, {'code': 'PROJECT_QUOTA_AUTHORITY_UNSUPPORTED'})
    if scope.get('mode') == 'local':
        # Local mode has no collaboration-session authority. The original
        # host/workbench guard remains the caller's admission boundary.
        if actor != 'local-author' or scope != {'mode': 'local', 'novel_id': nid}:
            raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
        guard()
        expected = workspace.store.incarnation(nid)
        with workspace._asset_scope(nid, scope):
            guard()
            if workspace.store.incarnation(nid) != expected:
                raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
            yield expected
            guard()
        return

    membership = api.membership_authorization_service
    resolver = api.trusted_session_resolver
    admin = api.collaboration_admin_service
    try:
        identity = membership.identity_service.repository
        auth = membership.authorization_service
        grants = auth.repository
        topology = api.collaboration_scope_service.repository
        root = Path(workspace.store.root).resolve()
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
            raise ValueError('unsupported authority owners')
        ws = scope['workspace_id']
        selected = CollaborationScope(ws, nid, scope['storyline_id'], scope['branch_id'])
        project = AuthorizationScope(ScopeKind.PROJECT, ws, nid)
        workspace_scope = AuthorizationScope(ScopeKind.WORKSPACE, ws)

        def observe():
            with grants.mutation():
                current = admin.actor(token, ws)
                if current.actor_id != actor or current.workspace_id != ws:
                    raise PermissionError('actor mismatch')
                admin.require_domain_manager(current, ModalityDomain.NOVEL, project)
                # The original manager allows either workspace.admin at the
                # workspace or domain.write at PROJECT, never branch-only.
                chosen = (('workspace.admin', workspace_scope)
                    if auth.is_allowed(actor, 'workspace.admin', ModalityDomain.NOVEL, workspace_scope)
                    else ('domain.write', project))
                return (resolver.binding_observation(token), identity.binding_observation(actor, ws),
                    topology.binding_observation(selected), grants.binding_observation(
                        auth, actor, chosen[0], ModalityDomain.NOVEL, chosen[1]))

        guard()
        before = observe()
        expected = workspace.store.incarnation(nid)
    except HTTPException:
        raise
    except (KeyError, ValueError, PermissionError):
        raise HTTPException(409, {'code': 'PROJECT_QUOTA_AUTHORITY_UNSUPPORTED'}) from None
    with api._workbench_authority_lease(nid, token, actor, scope):
        guard()
        try:
            unchanged = observe() == before
        except (KeyError, ValueError, PermissionError):
            unchanged = False
        if not unchanged:
            raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
        with workspace._asset_scope(nid, scope):
            guard()
            if workspace.store.incarnation(nid) != expected:
                raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
            yield expected
            guard()
