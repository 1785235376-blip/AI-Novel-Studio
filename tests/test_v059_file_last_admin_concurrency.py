from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.repositories.file.identity import FileIdentityRepository
from app.repositories.file.scope import FileAuthorizationRepository


def _seed(tmp_path):
    identity = FileIdentityRepository(tmp_path)
    authorization = FileAuthorizationRepository(tmp_path)
    for user_id in ("admin-a", "admin-b"):
        identity.save_membership({
            "id": f"membership:{user_id}", "user_id": user_id,
            "workspace_id": "workspace", "status": "ACTIVE",
            "created_at": "t0", "updated_at": "t0", "metadata": None,
        })
        authorization.save_role_assignment({
            "id": f"role:{user_id}", "principal_id": user_id,
            "role": "ADMIN", "domain": "NOVEL",
            "scope": {"kind": "WORKSPACE", "workspace_id": "workspace"},
            "granted_by": "bootstrap", "created_at": "t0", "metadata": None,
        })
    return identity, authorization


def _run_race(*operations):
    barrier = Barrier(len(operations))

    def run(operation):
        barrier.wait()
        try:
            operation()
            return "COMMITTED"
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(run, operations))


def _active_admins(identity, authorization):
    active = {row["user_id"] for row in identity.list_memberships(workspace_id="workspace", status="ACTIVE")}
    admins = {
        row["principal_id"] for row in authorization.list_role_assignments()
        if row["role"] == "ADMIN" and row["scope"]["workspace_id"] == "workspace"
    }
    return active & admins


def test_concurrent_admin_revokes_retain_one_active_admin(tmp_path):
    identity, authorization = _seed(tmp_path)

    results = _run_race(
        lambda: authorization.revoke_role_assignment_with_audit(
            "role:admin-a", {"id": "audit:revoke-a", "scope": {"kind": "WORKSPACE", "workspace_id": "workspace"}}, True
        ),
        lambda: authorization.revoke_role_assignment_with_audit(
            "role:admin-b", {"id": "audit:revoke-b", "scope": {"kind": "WORKSPACE", "workspace_id": "workspace"}}, True
        ),
    )

    assert sorted(results) == ["COMMITTED", "LAST_ACTIVE_ADMIN"]
    assert len(_active_admins(identity, authorization)) == 1


def test_concurrent_member_disable_and_admin_revoke_retain_one_active_admin(tmp_path):
    identity, authorization = _seed(tmp_path)

    results = _run_race(
        lambda: identity.update_membership_status_with_audit(
            "admin-a", "workspace", "INACTIVE", "t1",
            {"id": "audit:disable-a", "scope": {"kind": "WORKSPACE", "workspace_id": "workspace"}}, True
        ),
        lambda: authorization.revoke_role_assignment_with_audit(
            "role:admin-b", {"id": "audit:revoke-b", "scope": {"kind": "WORKSPACE", "workspace_id": "workspace"}}, True
        ),
    )

    assert sorted(results) == ["COMMITTED", "LAST_ACTIVE_ADMIN"]
    assert len(_active_admins(identity, authorization)) == 1
