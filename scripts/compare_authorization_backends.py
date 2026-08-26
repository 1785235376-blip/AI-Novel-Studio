"""Compare Scope/Authorization business semantics on File and real PostgreSQL.

The script deliberately fails when DATABASE_URL is missing or PostgreSQL cannot be
reached.  It is a runtime verification tool, not a unit-test substitute.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable

import psycopg
from dotenv import load_dotenv

from app.authorization import (
    AuthorizationScope,
    DomainRole,
    DomainRoleAssignment,
    ModalityDomain,
    PermissionAssignment,
    ScopeKind,
)
from app.collaboration import Branch, Storyline, Workspace
from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
from app.repositories.postgres.scope import (
    PostgresAuthorizationRepository,
    PostgresScopeRepository,
)
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService


STAMP = "2026-08-10T00:00:00+00:00"


class Novels:
    def get(self, project_id: str) -> dict[str, str]:
        return {"id": project_id}


def exception_name(action: Callable[[], Any]) -> str | None:
    try:
        action()
    except Exception as exc:  # parity includes the public exception category
        return type(exc).__name__
    return None


def execute(scope_repository: Any, authorization_repository: Any, run: str) -> dict[str, Any]:
    scopes = CollaborationScopeService(scope_repository, Novels())
    auth = AuthorizationService(authorization_repository, scopes)

    wa, wb = f"w-a-{run}", f"w-b-{run}"
    pa, pb = f"p-a-{run}", f"p-b-{run}"
    sa, sb = f"s-a-{run}", f"s-b-{run}"
    ba, bb = f"b-a-{run}", f"b-b-{run}"

    workspace_a = Workspace(wa, "Workspace A", STAMP, STAMP)
    workspace_b = Workspace(wb, "Workspace B", STAMP, STAMP)
    storyline_a = Storyline(sa, wa, pa, "Storyline A", "", STAMP, STAMP)
    storyline_b = Storyline(sb, wb, pb, "Storyline B", "", STAMP, STAMP)
    branch_a = Branch(ba, wa, pa, sa, "Branch A", None, STAMP, STAMP)
    branch_b = Branch(bb, wb, pb, sb, "Branch B", None, STAMP, STAMP)

    scopes.create_workspace(workspace_a)
    scopes.create_workspace(workspace_b)
    scopes.link_project(wa, pa)
    scopes.link_project(wb, pb)
    scopes.create_storyline(storyline_a)
    scopes.create_storyline(storyline_b)
    scopes.create_branch(branch_a)
    scopes.create_branch(branch_b)

    workspace_a_scope = AuthorizationScope(ScopeKind.WORKSPACE, wa)
    project_a_scope = AuthorizationScope(ScopeKind.PROJECT, wa, pa)
    storyline_a_scope = AuthorizationScope(ScopeKind.STORYLINE, wa, pa, sa)
    branch_a_scope = AuthorizationScope(ScopeKind.BRANCH, wa, pa, sa, ba)
    branch_b_scope = AuthorizationScope(ScopeKind.BRANCH, wb, pb, sb, bb)

    auth.assign_role(DomainRoleAssignment(f"admin-{run}", "admin", DomainRole.ADMIN, ModalityDomain.VIDEO, workspace_a_scope, "owner", STAMP))
    auth.assign_role(DomainRoleAssignment(f"lead-{run}", "lead", DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, project_a_scope, "owner", STAMP))
    auth.assign_permission(PermissionAssignment(f"explicit-{run}", "explicit", "asset.read", ModalityDomain.IMAGE, storyline_a_scope, "owner", STAMP))
    # One principal with independent NOVEL/IMAGE/VIDEO grants verifies the model's
    # multi-domain behavior without implying that media generation exists.
    auth.assign_role(DomainRoleAssignment(f"multi-novel-{run}", "multi", DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, project_a_scope, "owner", STAMP))
    auth.assign_permission(PermissionAssignment(f"multi-image-{run}", "multi", "asset.read", ModalityDomain.IMAGE, project_a_scope, "owner", STAMP))
    auth.assign_permission(PermissionAssignment(f"multi-video-{run}", "multi", "asset.read", ModalityDomain.VIDEO, branch_a_scope, "owner", STAMP))

    return {
        "scope": {
            "workspace_create_read": scopes.get_workspace(wa) == workspace_a.__dict__,
            "project_scope": scope_repository.project_workspace(pa) == wa,
            "storyline_scope": scopes.list_storylines(wa, pa) == [storyline_a.__dict__],
            "branch_scope": scopes.list_branches(wa, pa, sa) == [{**branch_a.__dict__, "revision": 0}],
        },
        "authorization": {
            "admin_descendant_cross_domain": auth.is_allowed("admin", "anything", ModalityDomain.IMAGE, branch_a_scope),
            "admin_cross_scope_denied": not auth.is_allowed("admin", "anything", ModalityDomain.IMAGE, branch_b_scope),
            "domain_lead_descendant": auth.is_allowed("lead", "domain.write", ModalityDomain.NOVEL, branch_a_scope),
            "domain_lead_cross_domain_denied": not auth.is_allowed("lead", "domain.write", ModalityDomain.IMAGE, branch_a_scope),
            "domain_lead_cross_scope_denied": not auth.is_allowed("lead", "domain.write", ModalityDomain.NOVEL, branch_b_scope),
            "explicit_permission_descendant": auth.is_allowed("explicit", "asset.read", ModalityDomain.IMAGE, branch_a_scope),
            "explicit_permission_other_denied": not auth.is_allowed("explicit", "asset.write", ModalityDomain.IMAGE, branch_a_scope),
            "missing_assignment_denied": not auth.is_allowed("missing", "domain.read", ModalityDomain.NOVEL, branch_a_scope),
            "multi_novel": auth.is_allowed("multi", "domain.write", ModalityDomain.NOVEL, branch_a_scope),
            "multi_image": auth.is_allowed("multi", "asset.read", ModalityDomain.IMAGE, branch_a_scope),
            "multi_video": auth.is_allowed("multi", "asset.read", ModalityDomain.VIDEO, branch_a_scope),
        },
        "errors": {
            "incomplete_declared_scope": exception_name(lambda: AuthorizationScope(ScopeKind.WORKSPACE, wa, pa)),
            "missing_project_scope": exception_name(lambda: auth.is_allowed("lead", "domain.read", ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.PROJECT, wa, "missing"))),
            "cross_workspace_project": exception_name(lambda: auth.is_allowed("lead", "domain.read", ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.PROJECT, wb, pa))),
        },
        "persistence": {
            "role_assignment_count": len([x for x in authorization_repository.list_role_assignments() if x["id"].endswith(run)]),
            "permission_assignment_count": len([x for x in authorization_repository.list_permission_assignments() if x["id"].endswith(run)]),
            "audit_count": len([x for x in authorization_repository.list_audit_events() if x["target_id"].endswith(run)]),
        },
    }


def main() -> None:
    load_dotenv()
    raw_url = os.getenv("TEST_POSTGRES_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw_url:
        raise SystemExit("POSTGRESQL REAL VERIFICATION BLOCKED: DATABASE_URL is not configured")
    url = raw_url.replace("postgresql+psycopg://", "postgresql://")
    run = uuid.uuid4().hex
    project_ids = (f"p-a-{run}", f"p-b-{run}")

    # A successful real connection and server_version query are part of the proof.
    def connect() -> psycopg.Connection[Any]:
        return psycopg.connect(url, connect_timeout=5)

    try:
        with connect() as connection:
            server_version = connection.execute("SHOW server_version").fetchone()[0]
            for project_id in project_ids:
                connection.execute(
                    "INSERT INTO novels(slug,title,metadata,created_at,updated_at) VALUES (%s,%s,'{}',now(),now())",
                    (project_id, "Authorization Parity"),
                )
            connection.commit()
    except psycopg.OperationalError as exc:
        raise SystemExit(
            f"POSTGRESQL REAL VERIFICATION BLOCKED: {type(exc).__name__}"
        ) from None

    postgres = execute(
        PostgresScopeRepository(connect),
        PostgresAuthorizationRepository(connect),
        run,
    )
    with tempfile.TemporaryDirectory(prefix="authorization-parity-") as directory:
        file_result = execute(
            FileScopeRepository(Path(directory)),
            FileAuthorizationRepository(Path(directory)),
            run,
        )

    matches = postgres == file_result
    artifact = {
        "postgresql_real_verified": True,
        "postgresql_server_version": server_version,
        "file_postgres_parity": "MATCH" if matches else "MISMATCH",
        "file": file_result,
        "postgresql": postgres,
    }
    print(json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2))
    if not matches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
