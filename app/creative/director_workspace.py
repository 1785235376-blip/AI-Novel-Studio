"""Read-only Director Workspace service over the existing Studio owners.

This service introduces no document, project, asset, shot or task owner. It reads
the creative document the existing `CreativeService` already stores and projects it
through `director_intent`, adding only the project context a director surface needs
to orient itself.

There is exactly no mutation here: no intent write, no shot write, no continuity
correction. Authoring a Director Intent still goes through the existing
`PUT /api/projects/{nid}/studio/creative/documents/{rid}` owner path, which already
writes `visual_target` and `director_notes`; nothing about those writes changes.
"""
from __future__ import annotations

from ..experimental.common import now
from .director_intent import DIRECTOR_WORKSPACE_CONTRACT, project_director_workspace
from .director_camera_geometry import project_camera_geometry


class DirectorWorkspaceService:
    """Project one creative document as a director decision surface."""

    CONTRACT = DIRECTOR_WORKSPACE_CONTRACT

    def __init__(self, workspace, creative):
        self.workspace, self.creative = workspace, creative

    @staticmethod
    def _scope_view(nid, scope):
        view = {"mode": scope.get("mode", "local"), "novel_id": nid}
        for key in ("workspace_id", "project_id", "storyline_id", "branch_id"):
            if key in scope:
                view[key] = scope[key]
        return view

    def projection(self, nid, scope, rid):
        """Read the original document; write nothing.

        `creative.get` is the existing owner read: it fences project incarnation,
        scope and source changes and refuses an archived document, so authority is
        resolved by the owner rather than re-implemented here.
        """
        self.workspace.store.key(nid, scope)
        project = self.workspace.novels.get(nid)
        document = self.creative.get(nid, scope, rid)
        projected = project_director_workspace(document)
        geometry = project_camera_geometry(document, self.creative.document_digest(document))
        if geometry is not None:
            projected["camera_geometry"] = geometry
        projected.update(
            project_id=nid,
            scope=self._scope_view(nid, scope),
            generated_at=now(),
            # The project's own genre is inherited context, shown separately from
            # the director's authored intent. It is read, never copied into the
            # document and never used to overwrite what the director authored.
            project_context={
                "title": str(project.get("title", "") or ""),
                "genre": str(project.get("genre", "") or ""),
                "inherited_not_authored": True,
            },
        )
        return projected
