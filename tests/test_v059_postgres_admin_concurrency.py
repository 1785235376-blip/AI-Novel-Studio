from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv

from app.repositories.postgres.identity import PostgresIdentityRepository
from app.repositories.postgres.scope import PostgresAuthorizationRepository,PostgresScopeRepository


load_dotenv()
URL = (os.getenv("TEST_POSTGRES_DATABASE_URL") or os.getenv("DATABASE_URL") or "").replace(
    "postgresql+psycopg://", "postgresql://"
)
pytestmark = [pytest.mark.postgres_backend_only, pytest.mark.skipif(not URL, reason="real PostgreSQL URL is unavailable")]


def connection():
    return psycopg.connect(URL, options="-c timezone=UTC -c lock_timeout=5000")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scope(workspace_id: str) -> dict:
    return {"kind": "WORKSPACE", "workspace_id": workspace_id, "project_id": None, "storyline_id": None, "branch_id": None}


def role(item_id: str, user_id: str, workspace_id: str) -> dict:
    return {"id": item_id, "principal_id": user_id, "role": "ADMIN", "domain": "NOVEL", "scope": scope(workspace_id), "created_by": "owner", "created_at": now()}


def permission(item_id: str, user_id: str, workspace_id: str) -> dict:
    return {"id": item_id, "principal_id": user_id, "permission": "domain.write", "domain": "NOVEL", "scope": scope(workspace_id), "created_by": "owner", "created_at": now()}


def audit(item_id: str, workspace_id: str, action: str) -> dict:
    return {"id": item_id, "actor_id": "owner", "action": action, "target_type": "assignment", "target_id": item_id, "scope": scope(workspace_id), "timestamp": now(), "metadata": {}}


@pytest.fixture
def seeded_workspace():
    suffix = uuid4().hex
    workspace_id = f"v059-e-{suffix}"
    users = [f"v059-admin-a-{suffix}", f"v059-admin-b-{suffix}", f"v059-member-{suffix}"]
    with connection() as database:
        database.execute("INSERT INTO workspaces(id,payload) VALUES (%s,%s::jsonb)", (workspace_id, '{"name":"E"}'))
        for user_id in users:
            database.execute("INSERT INTO users(id,display_name,status,created_at,updated_at,metadata) VALUES (%s,%s,'ACTIVE',now(),now(),NULL)", (user_id, user_id))
            database.execute("INSERT INTO workspace_memberships(id,user_id,workspace_id,status,created_at,updated_at,metadata) VALUES (%s,%s,%s,'ACTIVE',now(),now(),NULL)", (f"membership:{user_id}", user_id, workspace_id))
        database.commit()
    yield workspace_id, users
    with connection() as database:
        database.execute("DELETE FROM authorization_audit_events WHERE payload->'scope'->>'workspace_id'=%s", (workspace_id,))
        database.execute("DELETE FROM permission_assignments WHERE payload->'scope'->>'workspace_id'=%s", (workspace_id,))
        database.execute("DELETE FROM domain_role_assignments WHERE payload->'scope'->>'workspace_id'=%s", (workspace_id,))
        database.execute("DELETE FROM workspace_memberships WHERE workspace_id=%s", (workspace_id,))
        database.execute("DELETE FROM users WHERE id=ANY(%s)", (users,))
        database.execute("DELETE FROM workspaces WHERE id=%s", (workspace_id,))
        database.commit()


def race(left, right):
    barrier = Barrier(2)
    def run(operation):
        barrier.wait(timeout=5)
        try:
            operation()
            return "committed"
        except ValueError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        return [future.result(timeout=10) for future in (pool.submit(run, left), pool.submit(run, right))]


def test_independent_sessions_concurrent_final_admin_revokes(seeded_workspace):
    workspace_id, users = seeded_workspace
    repository = PostgresAuthorizationRepository(connection)
    assignments = [role(f"role-{user_id}", user_id, workspace_id) for user_id in users[:2]]
    for item in assignments:
        repository.save_role_assignment_with_audit(item, audit(f"grant-{item['id']}", workspace_id, "grant"))
    results = race(*[
        lambda item=item: PostgresAuthorizationRepository(connection).revoke_role_assignment_with_audit(item["id"], audit(f"revoke-{item['id']}", workspace_id, "revoke"), True)
        for item in assignments
    ])
    assert sorted(results) == ["LAST_ACTIVE_ADMIN", "committed"]
    assert len([item for item in repository.list_role_assignments() if item["scope"]["workspace_id"] == workspace_id]) == 1
    assert len([event for event in repository.list_audit_events() if event["action"] == "revoke"]) == 1


def test_independent_sessions_member_remove_vs_admin_revoke(seeded_workspace):
    workspace_id, users = seeded_workspace
    authorization = PostgresAuthorizationRepository(connection)
    assignments = [role(f"role-{user_id}", user_id, workspace_id) for user_id in users[:2]]
    for item in assignments:
        authorization.save_role_assignment_with_audit(item, audit(f"grant-{item['id']}", workspace_id, "grant"))
    results = race(
        lambda: PostgresIdentityRepository(connection).remove_membership_with_audit(users[0], workspace_id, audit("remove-member", workspace_id, "remove"), True),
        lambda: PostgresAuthorizationRepository(connection).revoke_role_assignment_with_audit(assignments[1]["id"], audit("revoke-role", workspace_id, "revoke"), True),
    )
    assert sorted(results) == ["LAST_ACTIVE_ADMIN", "committed"]
    with connection() as database:
        active_admins = database.execute("SELECT COUNT(DISTINCT r.payload->>'principal_id') FROM domain_role_assignments r JOIN workspace_memberships m ON m.user_id=r.payload->>'principal_id' AND m.workspace_id=%s AND m.status='ACTIVE' WHERE r.payload->>'role'='ADMIN' AND r.payload->'scope'->>'workspace_id'=%s", (workspace_id, workspace_id)).fetchone()[0]
    assert active_admins == 1


@pytest.mark.parametrize("kind", ["role", "permission"])
def test_independent_sessions_reject_semantic_duplicate_assignment(seeded_workspace, kind):
    workspace_id, users = seeded_workspace
    factory = role if kind == "role" else permission
    items = [factory(f"{kind}-{index}-{uuid4().hex}", users[2], workspace_id) for index in range(2)]
    method = "save_role_assignment_with_audit" if kind == "role" else "save_permission_assignment_with_audit"
    results = race(*[
        lambda item=item: getattr(PostgresAuthorizationRepository(connection), method)(item, audit(f"grant-{item['id']}", workspace_id, "grant"))
        for item in items
    ])
    assert sorted(results) == ["committed", "duplicate semantic assignment"]
    repository = PostgresAuthorizationRepository(connection)
    stored = repository.list_role_assignments(users[2]) if kind == "role" else repository.list_permission_assignments(users[2])
    assert len(stored) == 1
    assert len([event for event in repository.list_audit_events() if event["id"].startswith("grant-")]) == 1


def test_workspace_create_and_rename_share_postgres_business_audit_transaction(seeded_workspace):
    source_workspace,users=seeded_workspace;actor=users[0];target=f"v059-b-{uuid4().hex}"
    repository=PostgresScopeRepository(connection)
    try:
        created=repository.create_workspace(target,"Created",actor)
        assert created["id"]==target
        with connection() as database:
            membership=database.execute("SELECT status FROM workspace_memberships WHERE user_id=%s AND workspace_id=%s",(actor,target)).fetchone()
            admin=database.execute("SELECT payload->>'role' FROM domain_role_assignments WHERE payload->>'principal_id'=%s AND payload->'scope'->>'workspace_id'=%s",(actor,target)).fetchone()
            create_audit=database.execute("SELECT payload->>'action' FROM authorization_audit_events WHERE payload->>'target_id'=%s",(target,)).fetchall()
        assert membership==( "ACTIVE",) and admin==("ADMIN",) and ("WORKSPACE_CREATED",) in create_audit
        renamed=repository.rename_workspace(target,"Renamed",actor)
        assert renamed["name"]=="Renamed" and repository.get("workspaces",target)["name"]=="Renamed"
        with connection() as database:
            actions={row[0] for row in database.execute("SELECT payload->>'action' FROM authorization_audit_events WHERE payload->>'target_id'=%s",(target,)).fetchall()}
        assert actions=={"WORKSPACE_CREATED","WORKSPACE_RENAMED"}
    finally:
        with connection() as database:
            database.execute("DELETE FROM authorization_audit_events WHERE payload->>'target_id'=%s",(target,))
            database.execute("DELETE FROM domain_role_assignments WHERE payload->'scope'->>'workspace_id'=%s",(target,))
            database.execute("DELETE FROM workspace_memberships WHERE workspace_id=%s",(target,))
            database.execute("DELETE FROM workspaces WHERE id=%s",(target,));database.commit()


def test_concurrent_packaged_initial_workspace_provisioning_is_idempotent():
    suffix=uuid4().hex;actor=f"packaged-local-{suffix}";target=f"packaged-workspace-{suffix}"
    barrier=Barrier(2)
    def provision():
        barrier.wait(timeout=5)
        return PostgresScopeRepository(connection).provision_initial_workspace(actor,target,"我的创作空间","本机作者")
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=[future.result(timeout=10) for future in (pool.submit(provision),pool.submit(provision))]
        assert results[0]["id"]==results[1]["id"]==target
        with connection() as database:
            assert database.execute("SELECT COUNT(*) FROM workspaces WHERE id=%s",(target,)).fetchone()[0]==1
            assert database.execute("SELECT COUNT(*) FROM workspace_memberships WHERE user_id=%s",(actor,)).fetchone()[0]==1
            assert database.execute("SELECT COUNT(*) FROM domain_role_assignments WHERE payload->>'principal_id'=%s AND payload->'scope'->>'workspace_id'=%s",(actor,target)).fetchone()[0]==1
            assert database.execute("SELECT COUNT(*) FROM authorization_audit_events WHERE payload->>'target_id'=%s AND payload->>'action'='WORKSPACE_CREATED'",(target,)).fetchone()[0]==1
    finally:
        with connection() as database:
            database.execute("DELETE FROM authorization_audit_events WHERE payload->>'target_id'=%s",(target,))
            database.execute("DELETE FROM domain_role_assignments WHERE payload->'scope'->>'workspace_id'=%s",(target,))
            database.execute("DELETE FROM workspace_memberships WHERE workspace_id=%s",(target,))
            database.execute("DELETE FROM workspaces WHERE id=%s",(target,))
            database.execute("DELETE FROM users WHERE id=%s",(actor,));database.commit()
