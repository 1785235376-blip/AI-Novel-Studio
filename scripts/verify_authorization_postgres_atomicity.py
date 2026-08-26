"""Real PostgreSQL verification for authorization assignment/audit atomicity.

This script intentionally queries the database after each repository operation;
repository reads alone are not accepted as transaction evidence.
"""

from __future__ import annotations

import json
import os
import uuid

import psycopg
from dotenv import load_dotenv

from app.repositories.postgres.scope import PostgresAuthorizationRepository


load_dotenv()
database_url = os.environ["DATABASE_URL"].replace(
    "postgresql+psycopg://", "postgresql://"
)
run_id = uuid.uuid4().hex
repository = PostgresAuthorizationRepository(lambda: psycopg.connect(database_url))


def payload(identifier: str, principal: str) -> dict[str, object]:
    return {
        "id": identifier,
        "principal_id": principal,
        "role": "DOMAIN_LEAD",
        "domain": "NOVEL",
        "scope": {"kind": "WORKSPACE", "workspace_id": f"workspace-{run_id}"},
        "created_by": "atomicity-verifier",
        "created_at": "2026-08-10T00:00:00+00:00",
    }


def audit(identifier: str, target_id: str, action: str = "ROLE_ASSIGNED") -> dict[str, object]:
    return {
        "id": identifier,
        "actor_id": "atomicity-verifier",
        "action": action,
        "target_type": "DomainRoleAssignment",
        "target_id": target_id,
        "scope": {"kind": "WORKSPACE", "workspace_id": f"workspace-{run_id}"},
        "timestamp": "2026-08-10T00:00:00+00:00",
        "metadata": {},
    }


commit_assignment = payload(f"atomic-commit-assignment-{run_id}", "commit-principal")
commit_audit = audit(f"atomic-commit-audit-{run_id}", commit_assignment["id"])
repository.save_role_assignment_with_audit(commit_assignment, commit_audit)

with psycopg.connect(database_url) as connection:
    committed_assignment = connection.execute(
        "SELECT payload FROM domain_role_assignments WHERE id=%s",
        (commit_assignment["id"],),
    ).fetchone()
    committed_audit = connection.execute(
        "SELECT payload FROM authorization_audit_events WHERE id=%s",
        (commit_audit["id"],),
    ).fetchone()

commit_verified = (
    committed_assignment is not None
    and committed_assignment[0] == commit_assignment
    and committed_audit is not None
    and committed_audit[0] == commit_audit
)

rollback_assignment = payload(f"atomic-rollback-assignment-{run_id}", "rollback-principal")
rollback_audit_id = f"atomic-rollback-audit-{run_id}"
existing_audit = audit(rollback_audit_id, "preexisting-target", "PREEXISTING")
conflicting_audit = audit(rollback_audit_id, rollback_assignment["id"])

with psycopg.connect(database_url) as connection:
    connection.execute(
        "INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb)",
        (rollback_audit_id, json.dumps(existing_audit)),
    )
    connection.commit()

forced_failure = False
try:
    repository.save_role_assignment_with_audit(rollback_assignment, conflicting_audit)
except ValueError as error:
    forced_failure = "audit id already exists" in str(error)

with psycopg.connect(database_url) as connection:
    residual_assignment = connection.execute(
        "SELECT payload FROM domain_role_assignments WHERE id=%s",
        (rollback_assignment["id"],),
    ).fetchone()
    preserved_audit = connection.execute(
        "SELECT payload FROM authorization_audit_events WHERE id=%s",
        (rollback_audit_id,),
    ).fetchone()

rollback_verified = (
    forced_failure
    and residual_assignment is None
    and preserved_audit is not None
    and preserved_audit[0] == existing_audit
)

artifact = {
    "postgres_assignment_and_audit_commit": "PASS" if commit_verified else "FAIL",
    "postgres_forced_audit_failure": "OBSERVED" if forced_failure else "NOT_OBSERVED",
    "postgres_assignment_rollback": "PASS" if rollback_verified else "FAIL",
    "rollback_assignment_residual": "NONE" if residual_assignment is None else "FOUND",
    "preexisting_audit_preserved": preserved_audit is not None and preserved_audit[0] == existing_audit,
}
print(json.dumps(artifact, sort_keys=True))

if not commit_verified or not rollback_verified:
    raise SystemExit(1)
