"""Read-only Character/Scene Bible service over the existing Studio owners.

This service introduces no character, location, asset, project or task owner. It
reads what already exists — the project's `characters`/`locations` records, the
`WorldService` semantic records, the asset index and the creative documents — and
projects them through `bible_projection`.

There is no mutation here: no profile write, no reference resolution write, no
canon promotion. Authoring a visual profile still goes through the existing
`WorldService` record route with its own review, version and CAS contract.
"""
from __future__ import annotations

from ..experimental.common import now
from .bible_projection import BIBLE_CONTRACT, project_bible


class BibleWorkspaceService:
    """Project the existing owners as one Character + Scene Bible."""

    CONTRACT = BIBLE_CONTRACT

    def __init__(self, workspace, world=None):
        self.workspace, self.world = workspace, world

    @staticmethod
    def _scoped(rows, scope):
        """Only rows visible in this branch; unscoped rows belong to every branch."""
        branch = scope.get("branch_id")
        return [row for row in rows if not row.get("branch_id") or row.get("branch_id") == branch]

    @staticmethod
    def _scope_view(nid, scope):
        view = {"mode": scope.get("mode", "local"), "novel_id": nid}
        for key in ("workspace_id", "project_id", "storyline_id", "branch_id"):
            if key in scope:
                view[key] = scope[key]
        return view

    def projection(self, nid, scope):
        """Read the original owners; write nothing."""
        self.workspace.store.key(nid, scope)
        project = self.workspace.novels.get(nid)
        characters = self._scoped(self.workspace.novels.data_set(nid, "characters"), scope)
        locations = self._scoped(self.workspace.novels.data_set(nid, "locations"), scope)
        records = self.world.records(nid, scope) if self.world is not None else []
        projected = project_bible(
            characters=characters, locations=locations, world_records=records,
            assets=self.workspace.asset_index(nid, scope),
            documents=self.workspace.creative.list(nid, scope),
        )
        projected.update(
            project_id=nid,
            scope=self._scope_view(nid, scope),
            generated_at=now(),
            project_context={
                "title": str(project.get("title", "") or ""),
                "genre": str(project.get("genre", "") or ""),
                "inherited_not_authored": True,
            },
            visual_owner="WorldService records (CHARACTER_VISUAL / SCENE_VISUAL)",
            world_owner_available=self.world is not None,
        )
        return projected
