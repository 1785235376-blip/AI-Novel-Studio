"""Synthetic browser fixture: real queue/HTTP/storage, synthetic auth authority.

Never launch this fixture against user data or expose it beyond loopback.
"""
from pathlib import Path
from types import SimpleNamespace
import os

from fastapi import FastAPI
import app.api as api
from app.services.export_job_service import ExportJobService
from app.services.novel_service import NovelService


class Source:
    def get(self, nid):
        if nid != "synthetic-project": raise FileNotFoundError(nid)
        return {"id": nid, "title": "Synthetic export recovery"}
    def list(self, nid):
        self.get(nid)
        return [{"id": "chapter-synthetic", "title": "Synthetic chapter", "content": "Original immutable prose", "version": 1}]
    def get_data_set(self, nid, name): return []
    def get_outline(self, nid): return {}
    def list_screenplays(self, nid):
        return [{"id": "script-synthetic", "title": "Synthetic screenplay", "branch_id": "branch-a", "revision": 7,
                 "scenes": [{"id": "scene-1", "location": "ROOM", "action": "THE DOOR\nIt opens slowly.",
                             "dialogue": [{"character": "小明Alex", "text": "First line.\n\nSecond line."}]}]}]


class Sessions:
    def resolve(self, token):
        if token not in {"session-owner", "session-other"}: raise KeyError(token)
        return SimpleNamespace(actor_id=token, workspace_id="synthetic-workspace")


class Scopes:
    def __init__(self): self.repository = self
    def project_workspace(self, project): return "synthetic-workspace" if project == "synthetic-project" else None
    def get(self, collection, branch):
        if branch not in {"branch-a", "branch-b"}: raise KeyError(branch)
        return {"project_id": "synthetic-project", "workspace_id": "synthetic-workspace", "storyline_id": "synthetic-story"}
    def validate_scope(self, scope): return scope


source = Source()
api.novel_service = NovelService(source, source)
api.export_job_service = ExportJobService(Path(os.environ["NOVEL_DATA_PATH"]) / "browser-export-fixture", api.novel_service.export, api.novel_service.export_snapshot)
api.settings = SimpleNamespace(enable_collaboration_runtime=True)
api.trusted_session_resolver = Sessions()
api.collaboration_scope_service = Scopes()
api.membership_authorization_service = SimpleNamespace(require=lambda *args: None)
app = FastAPI()
app.include_router(api.router, prefix="/api")


@app.get("/health")
def health(): return {"status": "synthetic-fixture-ready"}
