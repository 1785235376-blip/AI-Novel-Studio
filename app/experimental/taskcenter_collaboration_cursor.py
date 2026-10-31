"""Read-only File collaboration composition using original authority owners.

Only explicit source-free agent_team windows are certified. Each owner commits
its own lifecycle in its own file; this is not a cross-file atomic snapshot.
"""
from pathlib import Path
from fastapi import HTTPException

from ..authorization import AuthorizationScope, ScopeKind, ModalityDomain
from ..collaboration import CollaborationScope
from ..repositories.file.identity import FileIdentityRepository
from ..repositories.file.scope import FileScopeRepository, FileAuthorizationRepository
from ..trusted_sessions import TrustedSessionResolver
from .taskcenter_cursor_http import TaskCenterCursorHTTPAdapter
from .taskcenter_query import cursor_not_supported
from .store import ExperimentalStore
from .teams import TeamService
from .ux import WorkspaceToolsService


class CollaborationTaskCenterCursorAdapter(TaskCenterCursorHTTPAdapter):
    def __init__(self, *args, actual_authorities, **kwargs):
        super().__init__(*args, **kwargs)
        self.actual_authorities = actual_authorities

    def _gate(self, ctx, selection):
        packaged, collaboration = self.runtime_mode()
        if (self.engine is None or packaged or not collaboration
                or ctx.scope.get('mode') != 'collaboration'
                or not ctx.token or ctx.branch != ctx.scope.get('branch_id')
                or selection.authorities != ('agent_team',)
                or type(self.service) is not WorkspaceToolsService
                or type(self.source) is not TeamService
                or type(self.source.store) is not ExperimentalStore
                or self.source.store.backend != 'file'
                or self.service.store is not self.source.store
                or [r for r in self.service.task_readers if r.name == 'agent_team'] != [self.reader]):
            cursor_not_supported()

    def _capture(self, ctx, selection, require_flag):
        require_flag('agent_team_recipes')
        try:
            return self.source.runs_observation(ctx.novel_id, ctx.scope)
        except HTTPException:
            raise
        except Exception:
            self._unavailable(selection)

    def _window(self, ctx, observation, query, failed_only):
        rows = observation['rows']
        # Original reader validates the complete scope document. Only the first
        # bounded window is projected; never inspect private tail payload here.
        for row in rows[:200]:
            if (not isinstance(row, dict) or row.get('sources') != {}
                    or row.get('execution_scope') != {
                        'project_id': ctx.novel_id,
                        'workspace_id': ctx.scope['workspace_id'],
                        'branch_id': ctx.branch, 'scope': ctx.scope}):
                raise ValueError('unsupported team source')
        visible = {**observation, 'rows': [self.source._view(ctx.novel_id, row)
                                         for row in rows[:200]] + rows[200:]}
        return super()._window(ctx, visible, query, failed_only)

    def _authority(self, ctx, selection, owner):
        try:
            resolver, membership, scopes = self.actual_authorities()
            identities = membership.identity_service.repository
            authorization = membership.authorization_service
            grants = authorization.repository
            topology = scopes.repository
            root = Path(owner.root).resolve()
            if (type(resolver) is not TrustedSessionResolver
                    or type(identities) is not FileIdentityRepository
                    or type(grants) is not FileAuthorizationRepository
                    or type(topology) is not FileScopeRepository
                    or membership.identity_service.scope_service is not scopes
                    or authorization.scope_service is not scopes
                    or any(Path(x.path).parent.resolve() != root for x in (identities, grants, topology))):
                raise ValueError('unverified authorities')
            scope = CollaborationScope(ctx.scope['workspace_id'], ctx.novel_id,
                                       ctx.scope['storyline_id'], ctx.branch)
            auth_scope = AuthorizationScope(ScopeKind.BRANCH, scope.workspace_id,
                                           scope.project_id, scope.storyline_id, scope.branch_id)
            with grants.mutation(), owner.existing_owner_only(), owner.owner_lease(ctx.novel_id):
                actor = resolver.resolve(ctx.token)
                if actor.actor_id != ctx.actor or actor.workspace_id != scope.workspace_id:
                    raise ValueError('authority mismatch')
                membership.require(actor, 'domain.read', ModalityDomain.NOVEL, auth_scope)
                return {'session': resolver.binding_observation(ctx.token),
                        'membership': identities.binding_observation(ctx.actor, scope.workspace_id),
                        'scope': topology.binding_observation(scope),
                        'grants': grants.binding_observation(authorization, ctx.actor, 'domain.read',
                                                             ModalityDomain.NOVEL, auth_scope)}
        except HTTPException:
            raise
        except Exception:
            self._unavailable(selection)

    def _checked_capture(self, ctx, selection, require_flag, owner, identity, query, failed_only):
        before = self._authority(ctx, selection, owner)
        result = super()._checked_capture(ctx, selection, require_flag, owner, identity, query, failed_only)
        after = self._authority(ctx, selection, owner)
        if before != after:
            self._unavailable(selection)
        return {**result, 'authority': after}
