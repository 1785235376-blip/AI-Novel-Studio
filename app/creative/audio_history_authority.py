"""Existing File authority observations for a read-only audio status."""
from pathlib import Path

from fastapi import HTTPException


def file_collaboration_observation(workspace, nid, scope, actor, token):
    from .. import api
    from ..authorization import AuthorizationScope, ScopeKind, ModalityDomain
    from ..collaboration import CollaborationScope
    from ..repositories.file.identity import FileIdentityRepository
    from ..repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
    from ..trusted_sessions import TrustedSessionResolver

    resolver = api.trusted_session_resolver
    membership = api.membership_authorization_service
    scopes = api.collaboration_scope_service
    try:
        identities = membership.identity_service.repository
        authorization = membership.authorization_service
        grants = authorization.repository
        topology = scopes.repository
        root = Path(workspace.store.root).resolve()
        if (workspace.store.backend != 'file' or type(resolver) is not TrustedSessionResolver
                or type(identities) is not FileIdentityRepository
                or type(grants) is not FileAuthorizationRepository
                or type(topology) is not FileScopeRepository
                or membership.identity_service.scope_service is not scopes
                or authorization.scope_service is not scopes
                or any(Path(item.path).parent.resolve() != root for item in (identities, grants, topology))):
            raise ValueError('unsupported authority owners')
        selected = CollaborationScope(scope['workspace_id'], nid, scope['storyline_id'], scope['branch_id'])
        auth_scope = AuthorizationScope(ScopeKind.BRANCH, selected.workspace_id, nid,
                                        selected.storyline_id, selected.branch_id)
        with grants.mutation():
            current = resolver.resolve(token)
            if current.actor_id != actor or current.workspace_id != selected.workspace_id:
                raise ValueError('authority mismatch')
            membership.require(current, 'domain.read', ModalityDomain.NOVEL, auth_scope)
            return (resolver.binding_observation(token),
                    identities.binding_observation(actor, selected.workspace_id),
                    topology.binding_observation(selected),
                    grants.binding_observation(authorization, actor, 'domain.read', ModalityDomain.NOVEL, auth_scope))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(409, {'code': 'AUDIO_HISTORY_AUTHORITY_OBSERVATION_UNAVAILABLE'}) from None
