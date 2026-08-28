from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[2]
DATABASE_PREFIX = "ai_novel_studio_e2e_"
DATABASE_NAME = re.compile(r"ai_novel_studio_e2e_[a-z0-9_-]{1,42}")
CLI_ACTIONS = ("prepare", "cleanup", "probe")


class E2EDatabaseContractError(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class E2EDatabaseTarget:
    database_name: str
    target_url: str
    maintenance_url: str


def _contract_error(code: str) -> None:
    raise E2EDatabaseContractError(code)


def load_database_url(*, require_confirmation: bool = True) -> E2EDatabaseTarget:
    value = os.getenv("E2E_DATABASE_URL", "")
    if not value:
        _contract_error("E2E_DATABASE_URL_REQUIRED")
    try:
        parsed = urlsplit(value)
        parsed.port
    except (TypeError, ValueError, UnicodeError):
        _contract_error("E2E_DATABASE_URL_INVALID")
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"}:
        _contract_error("E2E_DATABASE_SCHEME_UNSUPPORTED")
    if not parsed.hostname or parsed.fragment:
        _contract_error("E2E_DATABASE_URL_INVALID")
    if not parsed.path.startswith("/") or "/" in parsed.path[1:] or "%" in parsed.path:
        _contract_error("E2E_DATABASE_NAME_UNSAFE")
    database_name = parsed.path[1:]
    if not DATABASE_NAME.fullmatch(database_name) or database_name == DATABASE_PREFIX[:-1]:
        _contract_error("E2E_DATABASE_NAME_UNSAFE")
    if require_confirmation:
        confirmation = os.getenv("E2E_DATABASE_CONFIRM_DROP", "")
        if not confirmation:
            _contract_error("E2E_DATABASE_CONFIRM_REQUIRED")
        if confirmation != database_name:
            _contract_error("E2E_DATABASE_CONFIRM_MISMATCH")
    scheme = "postgresql"
    target_url = urlunsplit((scheme, parsed.netloc, f"/{database_name}", parsed.query, ""))
    maintenance_url = urlunsplit((scheme, parsed.netloc, "/postgres", parsed.query, ""))
    return E2EDatabaseTarget(database_name, target_url, maintenance_url)


def _terminate(connection, database_name: str) -> None:
    connection.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (database_name,),
    )


def prepare() -> None:
    target = load_database_url()
    with psycopg.connect(target.maintenance_url, autocommit=True) as connection:
        _terminate(connection, target.database_name)
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(target.database_name)))
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target.database_name)))
    with psycopg.connect(target.target_url, autocommit=True) as connection:
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
    target = load_database_url()
    with psycopg.connect(target.maintenance_url, autocommit=True) as connection:
        _terminate(connection, target.database_name)
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(target.database_name)))


def probe(slug: str) -> None:
    target = load_database_url(require_confirmation=False)
    with psycopg.connect(target.target_url) as connection:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=CLI_ACTIONS)
    parser.add_argument("--slug", default="")
    args = parser.parse_args(argv)
    try:
        if args.action == "prepare":
            prepare()
        elif args.action == "cleanup":
            cleanup()
        else:
            probe(args.slug)
    except E2EDatabaseContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception:
        code = f"E2E_DATABASE_{args.action.upper()}_FAILED"
        print(code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
