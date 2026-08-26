from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[2]
E2E_DATABASE = "ai_novel_studio_e2e"


def load_database_url() -> str:
    value = os.getenv("DATABASE_URL", "")
    if not value:
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                value = line.split("=", 1)[1].strip()
                break
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def database_url(name: str) -> str:
    base = load_database_url()
    return base.rsplit("/", 1)[0] + "/" + name


def prepare() -> None:
    admin_url = database_url("postgres")
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (E2E_DATABASE,),
        )
        connection.execute(f'DROP DATABASE IF EXISTS "{E2E_DATABASE}"')
        connection.execute(f'CREATE DATABASE "{E2E_DATABASE}"')
    with psycopg.connect(database_url(E2E_DATABASE), autocommit=True) as connection:
        for migration in sorted((ROOT / "database" / "migrations").glob("*.sql")):
            connection.execute(migration.read_text(encoding="utf-8"))
        connection.execute("INSERT INTO workspaces(id,payload) VALUES ('e2e-workspace-a','{\"id\":\"e2e-workspace-a\",\"name\":\"E2E Workspace A\"}'::jsonb),('e2e-workspace-b','{\"id\":\"e2e-workspace-b\",\"name\":\"E2E Empty Workspace B\"}'::jsonb)")
        connection.execute("INSERT INTO project_workspaces(project_id,workspace_id) VALUES ('e2e-project-a','e2e-workspace-a')")
        connection.execute("INSERT INTO storylines(id,payload) VALUES ('e2e-story-a','{\"id\":\"e2e-story-a\",\"workspace_id\":\"e2e-workspace-a\",\"project_id\":\"e2e-project-a\",\"name\":\"E2E Story\"}'::jsonb)")
        connection.execute("INSERT INTO storyline_branches(id,payload,revision) VALUES ('e2e-branch-a','{\"id\":\"e2e-branch-a\",\"workspace_id\":\"e2e-workspace-a\",\"project_id\":\"e2e-project-a\",\"storyline_id\":\"e2e-story-a\",\"name\":\"main\"}'::jsonb,0)")
        connection.execute("INSERT INTO users(id,display_name,status,created_at,updated_at,metadata) VALUES ('e2e-admin','E2E Admin','ACTIVE',now(),now(),NULL),('e2e-member','E2E Member','ACTIVE',now(),now(),NULL),('e2e-candidate','E2E Candidate','ACTIVE',now(),now(),NULL)")
        connection.execute("INSERT INTO workspace_memberships(id,user_id,workspace_id,status,created_at,updated_at,metadata) VALUES ('membership:e2e-a-admin','e2e-admin','e2e-workspace-a','ACTIVE',now(),now(),NULL),('membership:e2e-a-member','e2e-member','e2e-workspace-a','ACTIVE',now(),now(),NULL),('membership:e2e-b-admin','e2e-admin','e2e-workspace-b','ACTIVE',now(),now(),NULL)")
        connection.execute("INSERT INTO domain_role_assignments(id,payload) VALUES ('role:e2e-a-admin','{\"id\":\"role:e2e-a-admin\",\"principal_id\":\"e2e-admin\",\"role\":\"ADMIN\",\"domain\":\"NOVEL\",\"scope\":{\"kind\":\"WORKSPACE\",\"workspace_id\":\"e2e-workspace-a\",\"project_id\":null,\"storyline_id\":null,\"branch_id\":null},\"created_by\":\"fixture\"}'::jsonb),('role:e2e-b-admin','{\"id\":\"role:e2e-b-admin\",\"principal_id\":\"e2e-admin\",\"role\":\"ADMIN\",\"domain\":\"NOVEL\",\"scope\":{\"kind\":\"WORKSPACE\",\"workspace_id\":\"e2e-workspace-b\",\"project_id\":null,\"storyline_id\":null,\"branch_id\":null},\"created_by\":\"fixture\"}'::jsonb)")


def cleanup() -> None:
    with psycopg.connect(database_url(E2E_DATABASE), autocommit=True) as connection:
        connection.execute("TRUNCATE TABLE novels CASCADE")


def probe(slug: str) -> None:
    with psycopg.connect(database_url(E2E_DATABASE)) as connection:
        row = connection.execute(
            """
            SELECT n.slug,
                   count(DISTINCT c.id) AS chapters,
                   count(DISTINCT v.id) AS versions,
                   count(DISTINCT g.id) AS jobs,
                   count(DISTINCT p.id) FILTER (WHERE p.status = 'APPROVED') AS approved,
                   count(DISTINCT ce.id) AS canon
            FROM novels n
            LEFT JOIN chapters c ON c.novel_id = n.id
            LEFT JOIN chapter_versions v ON v.chapter_id = c.id
            LEFT JOIN generation_jobs g ON g.novel_id = n.id
            LEFT JOIN pending_canon p ON p.novel_id = n.id
            LEFT JOIN canon_entries ce ON ce.novel_id = n.id
            WHERE n.slug = %s
            GROUP BY n.slug
            """,
            (slug,),
        ).fetchone()
    if not row:
        raise SystemExit("novel_missing")
    print("|".join(str(value) for value in row))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "cleanup", "url", "probe"))
    parser.add_argument("--slug", default="")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "cleanup":
        cleanup()
    elif args.action == "url":
        print(database_url(E2E_DATABASE))
    else:
        probe(args.slug)
