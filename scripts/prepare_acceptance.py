from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
DB_NAME = "ai_novel_studio_acceptance"
NS = uuid.UUID("1e36e9f7-99c5-5a26-b3e8-8af38173fc28")


def acceptance_url(value: str) -> str:
    if not value:
        raise RuntimeError("DATABASE_URL is required")
    parsed = urlsplit(value.replace("postgresql+psycopg://", "postgresql://", 1))
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{DB_NAME}", parsed.query, parsed.fragment))


def ensure_database(url: str) -> None:
    parsed = urlsplit(url)
    admin = urlunsplit((parsed.scheme, parsed.netloc, "/postgres", parsed.query, parsed.fragment))
    with psycopg.connect(admin, autocommit=True) as connection:
        exists = connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,)).fetchone()
        if not exists:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))


def ensure_schema(url: str) -> None:
    with psycopg.connect(url, autocommit=True) as connection:
        ready = connection.execute("SELECT to_regclass('public.schema_versions')").fetchone()[0]
        if not ready:
            for migration in sorted((ROOT / "database" / "migrations").glob("*.sql")):
                connection.execute(migration.read_text(encoding="utf-8"))
        required = {"workspaces", "novels", "chapters", "workspace_memberships", "domain_role_assignments"}
        found = {row[0] for row in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
        missing = required - found
        if missing:
            raise RuntimeError(f"acceptance database is missing tables: {sorted(missing)}")


def stable(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def seed(url: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    workspaces = [
        ("acceptance-alpha", "Workspace Alpha"),
        ("acceptance-beta", "Workspace Beta"),
        ("acceptance-empty", "Workspace Empty"),
    ]
    users = [
        ("acceptance-admin", "Acceptance Admin"),
        ("acceptance-lead", "Acceptance Domain Lead"),
        ("acceptance-member", "Acceptance Member"),
    ]
    scope = lambda workspace: {"kind": "WORKSPACE", "workspace_id": workspace, "project_id": None, "storyline_id": None, "branch_id": None}
    with psycopg.connect(url) as connection:
        for workspace_id, name in workspaces:
            payload = {"id": workspace_id, "name": name, "created_at": now, "updated_at": now, "acceptance_seed": True}
            connection.execute("INSERT INTO workspaces(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO NOTHING", (workspace_id, json.dumps(payload)))
        for user_id, display_name in users:
            connection.execute("INSERT INTO users(id,display_name,status,created_at,updated_at,metadata) VALUES (%s,%s,'ACTIVE',%s,%s,%s::jsonb) ON CONFLICT(id) DO NOTHING", (user_id, display_name, now, now, json.dumps({"acceptance_seed": True})))
        for workspace_id, _ in workspaces:
            for user_id, _ in users:
                membership_id = f"acceptance-membership:{workspace_id}:{user_id}"
                connection.execute("INSERT INTO workspace_memberships(id,user_id,workspace_id,status,created_at,updated_at,metadata) VALUES (%s,%s,%s,'ACTIVE',%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (membership_id, user_id, workspace_id, now, now, json.dumps({"acceptance_seed": True})))
            role = {"id": f"acceptance-admin:{workspace_id}", "principal_id": "acceptance-admin", "role": "ADMIN", "domain": "NOVEL", "scope": scope(workspace_id), "created_by": "acceptance-seed", "created_at": now}
            connection.execute("INSERT INTO domain_role_assignments(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO NOTHING", (role["id"], json.dumps(role)))
        lead = {"id": "acceptance-lead:alpha", "principal_id": "acceptance-lead", "role": "DOMAIN_LEAD", "domain": "NOVEL", "scope": scope("acceptance-alpha"), "created_by": "acceptance-seed", "created_at": now}
        permission = {"id": "acceptance-member:alpha:read", "principal_id": "acceptance-member", "permission": "domain.read", "domain": "NOVEL", "scope": scope("acceptance-alpha"), "created_by": "acceptance-seed", "created_at": now}
        connection.execute("INSERT INTO domain_role_assignments(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO NOTHING", (lead["id"], json.dumps(lead)))
        connection.execute("INSERT INTO permission_assignments(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO NOTHING", (permission["id"], json.dumps(permission)))

        for key, workspace in (("alpha", "acceptance-alpha"), ("beta", "acceptance-beta")):
            novel_slug = f"acceptance-{key}-novel"
            novel_uuid = stable(f"novel:{key}")
            title = f"Acceptance Novel {key.title()}"
            metadata = {"genre": "Acceptance", "status": "Writing", "style_profile": {}, "acceptance_seed": True}
            connection.execute("INSERT INTO novels(id,slug,title,metadata,workspace_id,created_at,updated_at) VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s) ON CONFLICT(slug) DO NOTHING", (novel_uuid, novel_slug, title, json.dumps(metadata), workspace, now, now))
            connection.execute("INSERT INTO project_workspaces(project_id,workspace_id) VALUES (%s,%s) ON CONFLICT(project_id) DO NOTHING", (novel_slug, workspace))
            storyline_id = f"acceptance-{key}-storyline"
            branch_id = f"acceptance-{key}-main"
            storyline = {"id": storyline_id, "workspace_id": workspace, "project_id": novel_slug, "name": f"{key.title()} Storyline", "description": "Acceptance storyline", "created_at": now, "updated_at": now}
            branch = {"id": branch_id, "workspace_id": workspace, "project_id": novel_slug, "storyline_id": storyline_id, "name": "main", "parent_branch_id": None, "created_at": now, "updated_at": now}
            connection.execute("INSERT INTO storylines(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO NOTHING", (storyline_id, json.dumps(storyline)))
            connection.execute("INSERT INTO storyline_branches(id,payload,revision) VALUES (%s,%s::jsonb,0) ON CONFLICT(id) DO NOTHING", (branch_id, json.dumps(branch)))
            old_doc = {"type": "doc", "content": [{"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Acceptance Chapter"}]}, {"type": "paragraph", "content": [{"type": "text", "text": "This is the preserved first revision."}]}]}
            current_doc = {"type": "doc", "content": [{"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Acceptance Chapter"}]}, {"type": "paragraph", "content": [{"type": "text", "text": f"Stable acceptance text for Workspace {key.title()}."}]}]}
            chapter_uuid = stable(f"chapter:{key}:1")
            connection.execute("INSERT INTO chapters(id,novel_id,chapter_number,title,markdown_path,content_hash,workflow_status,document,version,created_at,updated_at) VALUES (%s,%s,1,'Acceptance Chapter',%s,%s,'DRAFT',%s::jsonb,2,%s,%s) ON CONFLICT(novel_id,chapter_number) DO NOTHING", (chapter_uuid, novel_uuid, f"chapters/{key}-0001.md", stable(f"hash:{key}"), json.dumps(current_doc), now, now))
            connection.execute("INSERT INTO chapter_versions(id,chapter_id,version,document,created_at,operator,source,actor_id,session_id,scope_type,scope_id,metadata,reason) VALUES (%s,%s,1,%s::jsonb,%s,'acceptance-seed','USER','acceptance-admin','acceptance-seed','BRANCH',%s,%s::jsonb,'MANUAL_SAVE') ON CONFLICT(chapter_id,version) DO NOTHING", (stable(f"version:{key}:1"), chapter_uuid, json.dumps(old_doc), now, branch_id, json.dumps({"acceptance_seed": True})))
        connection.commit()


def main() -> None:
    url = acceptance_url(os.environ.get("DATABASE_URL", ""))
    if len(sys.argv) > 1 and sys.argv[1] == "url":
        print(url)
        return
    ensure_database(url)
    ensure_schema(url)
    seed(url)
    print("ACCEPTANCE_DATA_READY")


if __name__ == "__main__":
    main()
