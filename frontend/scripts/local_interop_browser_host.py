"""Explicit MOCK_ONLY isolated Studio browser fixture; never a product entry point."""
from __future__ import annotations
import os
from pathlib import Path
import sys

if os.getenv("LOCAL_INTEROP_BROWSER_FIXTURE") != "MOCK_ONLY":
    raise RuntimeError("This synthetic browser fixture requires explicit MOCK_ONLY mode")
if not all(os.getenv(name) for name in ("NOVEL_DATA_PATH", "HOME", "XDG_DATA_HOME")):
    raise RuntimeError("Isolated fixture data/home directories are mandatory")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.collaboration import Branch, Storyline, Workspace
from app.identity import User, WorkspaceMembership
from app import dependencies as d

project_id = "interop-browser-book"
d.repositories.novels.create({"id": project_id, "title": "Local Interop browser (MOCK_ONLY)", "genre": "Synthetic"})
d.repositories.chapters.backend.create_chapter(project_id, {"title": "合成😀选区（MOCK_ONLY）", "content": "合成😀选区与上下文。\nThis is synthetic manuscript data only."})
d.collaboration_scope_service.create_workspace(Workspace("interop-browser-workspace", "MOCK_ONLY workspace"))
d.collaboration_scope_service.link_project("interop-browser-workspace", project_id)
d.collaboration_scope_service.create_storyline(Storyline("interop-browser-story", "interop-browser-workspace", project_id, "Main"))
d.collaboration_scope_service.create_branch(Branch("interop-browser-branch", "interop-browser-workspace", project_id, "interop-browser-story", "Main"))
d.identity_service.create_user(User("interop-browser-author", "MOCK_ONLY Author"))
d.identity_service.add_membership(WorkspaceMembership("interop-browser-membership", "interop-browser-author", "interop-browser-workspace"))
d.trusted_session_resolver.register("interop-browser-mock-session", SessionContext("interop-browser-session", "interop-browser-client", "interop-browser-author", "interop-browser-workspace"))
d.authorization_service.assign_role(DomainRoleAssignment("interop-browser-role", "interop-browser-author", DomainRole.ADMIN, ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.WORKSPACE, "interop-browser-workspace"), "interop-browser-author"))

from app.main import app
import uvicorn
uvicorn.run(app, host="127.0.0.1", port=8051, access_log=False, log_level="warning", proxy_headers=False)
