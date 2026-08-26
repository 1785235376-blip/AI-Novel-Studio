import os
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv

from app.collaboration import Workspace
from app.identity import User, WorkspaceMembership
from app.repositories.postgres.identity import PostgresIdentityRepository
from app.repositories.postgres.scope import PostgresScopeRepository
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.identity_service import IdentityService


class Novels:
    def get(self, item):
        return {"id": item}


@pytest.mark.postgres_backend_only
def test_real_postgres_identity_membership_round_trip_and_cardinality():
    load_dotenv()
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        pytest.skip("DATABASE_URL is not configured")
    url = raw_url.replace("postgresql+psycopg://", "postgresql://")
    connection = lambda: psycopg.connect(url, options="-c timezone=UTC")
    suffix = uuid4().hex
    workspace_one, workspace_two = f"identity-w1-{suffix}", f"identity-w2-{suffix}"
    alice, bob = f"alice-{suffix}", f"bob-{suffix}"
    scopes = CollaborationScopeService(PostgresScopeRepository(connection), Novels())
    identity = IdentityService(PostgresIdentityRepository(connection), scopes)
    try:
        scopes.create_workspace(Workspace(workspace_one, "One"))
        scopes.create_workspace(Workspace(workspace_two, "Two"))
        identity.create_user(User(alice, "Alice"))
        identity.create_user(User(bob, "Bob"))
        identity.add_membership(WorkspaceMembership(f"m1-{suffix}", alice, workspace_one))
        identity.add_membership(WorkspaceMembership(f"m2-{suffix}", alice, workspace_two))
        identity.add_membership(WorkspaceMembership(f"m3-{suffix}", bob, workspace_one))
        assert identity.get_membership(alice, workspace_one).user_id == alice
        assert len(identity.repository.list_memberships(user_id=alice)) == 2
        assert len(identity.repository.list_memberships(workspace_id=workspace_one)) == 2
    finally:
        with connection() as database:
            database.execute("DELETE FROM workspace_memberships WHERE user_id IN (%s,%s)", (alice, bob))
            database.execute("DELETE FROM users WHERE id IN (%s,%s)", (alice, bob))
            database.execute("DELETE FROM workspaces WHERE id IN (%s,%s)", (workspace_one, workspace_two))
            database.commit()
