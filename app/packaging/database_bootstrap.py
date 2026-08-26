from __future__ import annotations

"""Idempotent ownership-safe bootstrap for the packaged PostgreSQL cluster."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class DatabaseBootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class PackagedDatabaseBootstrap:
    postgres_bin: Path
    port: int
    database_name: str
    database_user: str
    run: Callable[..., object]

    def ensure_ready(self) -> None:
        """Ensure the application principal and database exist without touching contents."""
        administrator = self._find_administrator()
        self._execute(administrator, "postgres", self._ensure_role_sql())
        self._ensure_database(administrator)
        self._execute(self.database_user, self.database_name, "SELECT 1")

    def _find_administrator(self) -> str:
        # New clusters use database_user as initdb's superuser.  Older packaged
        # clusters can have the conventional postgres administrative role.
        for candidate in (self.database_user, "postgres"):
            result = self._run_psql(candidate, "postgres", "SELECT 1", check=False)
            if getattr(result, "returncode", 1) == 0:
                return candidate
        raise DatabaseBootstrapError("无法连接本地 PostgreSQL 管理数据库")

    def _ensure_role_sql(self) -> str:
        role = self.database_user.replace("'", "''")
        identifier = self.database_user.replace('"', '""')
        return (
            "DO $bootstrap$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN "
            f'CREATE ROLE "{identifier}" LOGIN SUPERUSER; '
            "END IF; END $bootstrap$;"
        )

    def _ensure_database(self, administrator: str) -> None:
        database = self.database_name.replace("'", "''")
        result = self._run_psql(
            administrator, "postgres",
            f"SELECT 1 FROM pg_database WHERE datname='{database}'", check=False,
        )
        if getattr(result, "returncode", 1) != 0:
            raise DatabaseBootstrapError("无法检查本地 PostgreSQL 数据库")
        if result.stdout.strip() == "1":
            return
        result = self.run([
            self.postgres_bin / "createdb.exe", "-h", "127.0.0.1", "-p", str(self.port),
            "-U", administrator, "-O", self.database_user, self.database_name,
        ], check=False)
        if getattr(result, "returncode", 1) != 0:
            raise DatabaseBootstrapError("本地 PostgreSQL 数据库初始化失败")

    def _execute(self, user: str, database: str, sql: str) -> None:
        result = self._run_psql(user, database, sql, check=False)
        if getattr(result, "returncode", 1) != 0:
            raise DatabaseBootstrapError("本地 PostgreSQL 数据库初始化失败")

    def _run_psql(self, user: str, database: str, sql: str, *, check: bool):
        return self.run([
            self.postgres_bin / "psql.exe", "-h", "127.0.0.1", "-p", str(self.port),
            "-U", user, "-d", database, "-v", "ON_ERROR_STOP=1", "-X", "-tAc", sql,
        ], check=check)
