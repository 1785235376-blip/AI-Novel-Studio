from __future__ import annotations

import json
import hashlib
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .paths import WindowsPackagingPaths
from .runtime_identity import (
    ProcessIdentity,
    RuntimeIdentity,
    RuntimeRole,
    validate_process_ownership,
)
from .versioning import load_release_version
from .static_frontend import validate_frontend_dist
from .postgres_migrations import PackagedPostgresMigrationRunner
from .database_bootstrap import PackagedDatabaseBootstrap
from .control_pipe import encode_ping
from .host_uplink import parse_host_credential, encode_backend_credential


RUNTIME_INCOMPLETE = "应用运行组件不完整，请重新安装 AI-Novel-Studio。"
DATABASE_INVALID = "本地数据库无法安全启动。你的作品数据未被删除，请使用恢复工具检查数据。"

# Provider secrets are accepted only through the ephemeral DesktopHost control
# channel. Never inherit developer/user API-key environment variables into
# the packaged backend. The backend persists only values explicitly handed
# off by DesktopHost, using the operating-system vault with no memory fallback.
PACKAGED_PROVIDER_SECRET_ENV_VARS = frozenset({
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "DDSHUB_API_KEY",
    "CUSTOM_API_KEY",
})


@dataclass(frozen=True)
class PackagedRuntimeLayout:
    application: Path
    python: Path
    backend: Path
    postgres: Path
    release_version: Path
    migrations: Path
    frontend_dist: Path

    @classmethod
    def resolve(cls, application: Path) -> "PackagedRuntimeLayout":
        root = application.resolve(strict=False)
        value = cls(
            application=root,
            python=root / "Runtime" / "Python" / "python.exe",
            backend=root / "Backend",
            postgres=root / "PostgreSQL",
            release_version=root / "release" / "version.json",
            migrations=root / "Database" / "Migrations",
            frontend_dist=root / "Frontend" / "dist",
        )
        value.validate()
        return value

    @property
    def postgres_bin(self) -> Path:
        return self.postgres / "bin"

    def validate(self) -> None:
        required = (
            self.python,
            self.backend / "app" / "main.py",
            self.release_version,
            *(self.postgres_bin / name for name in (
                "initdb.exe", "postgres.exe", "pg_ctl.exe", "pg_isready.exe",
                "pg_dump.exe", "pg_restore.exe", "psql.exe", "createdb.exe",
            )),
        )
        if any(not path.is_file() for path in required):
            raise RuntimeError(RUNTIME_INCOMPLETE)
        validate_frontend_dist(self.frontend_dist)
        version = _run([self.python, "-I", "-c", "import sys;print(sys.version_info[:2])"])
        if "(3, 12)" not in version.stdout:
            raise RuntimeError(RUNTIME_INCOMPLETE)
        postgres = _run([self.postgres_bin / "postgres.exe", "--version"])
        if " 16." not in postgres.stdout:
            raise RuntimeError(RUNTIME_INCOMPLETE)


@dataclass(frozen=True)
class PackagedProcessConfig:
    layout: PackagedRuntimeLayout
    paths: WindowsPackagingPaths
    version: str
    database_name: str = "ai_novel_studio"
    database_user: str = "novel_studio"

    @classmethod
    def create(cls, application: Path, paths: WindowsPackagingPaths) -> "PackagedProcessConfig":
        layout = PackagedRuntimeLayout.resolve(application)
        release = load_release_version(layout.release_version)
        return cls(layout=layout, paths=paths, version=release.version)

    def environment(
        self, *, database_port: int, backend_port: int,
        runtime_instance_id: str | None = None, bootstrap_secret: str | None = None,
    ) -> dict[str, str]:
        value = {
            "APP_VERSION": self.version,
            "PROJECT_ROOT": str(self.layout.backend),
            "NOVEL_DATA_PATH": str(self.paths.novel_data),
            "PROMPT_PATH": str(self.layout.backend / "prompts"),
            "WORKFLOW_PATH": str(self.layout.backend / "workflows"),
            "STORAGE_BACKEND": "postgres",
            "DATABASE_URL": f"postgresql://{self.database_user}@127.0.0.1:{database_port}/{self.database_name}",
            "FRONTEND_ORIGIN": f"http://127.0.0.1:{backend_port}",
            "ENABLE_PACKAGED_RUNTIME": "true",
            "ENABLE_COLLABORATION_RUNTIME": "true",
            "COLLABORATION_DEV_SESSIONS_JSON": "",
            "ENABLE_PROVIDER_FALLBACK": "false",
            "PACKAGED_WINDOWS_MODE": "true",
            "PACKAGED_FRONTEND_DIST": str(self.layout.frontend_dist),
            "PYTHONUTF8": "1",
            "PYTHONNOUSERSITE": "1",
        }
        if runtime_instance_id is not None and bootstrap_secret is not None:
            value["PACKAGED_RUNTIME_INSTANCE_ID"] = runtime_instance_id
            value["PACKAGED_BOOTSTRAP_SECRET"] = bootstrap_secret
        return value

    def public_runtime_metadata(self, *, database_port: int, backend_port: int) -> dict[str, object]:
        return {
            "application_version": self.version,
            "packaged_windows_mode": True,
            "user_data_root": str(self.paths.user_data),
            "postgresql_data_root": str(self.paths.database),
            "logs_root": str(self.paths.logs),
            "runtime_root": str(self.paths.runtime),
            "database_port": database_port,
            "backend_port": backend_port,
        }


class PackagedManagedChild:
    def __init__(
        self, *, role: RuntimeRole, process: subprocess.Popen[bytes], runtime: RuntimeIdentity,
        inspector, expected_executable: Path, ready, graceful,
    ):
        self.role = role
        self.process = process
        self.runtime = runtime
        self.inspector = inspector
        self.expected_executable = expected_executable.resolve()
        self._ready = ready
        self._graceful = graceful
        inspector.register(process.pid, role, runtime)
        actual = inspector.inspect(process.pid)
        if actual is None:
            process.terminate()
            raise RuntimeError(f"{role.value} process identity unavailable")
        if Path(actual.executable_path).resolve() != self.expected_executable:
            process.terminate()
            raise RuntimeError(f"{role.value} executable mismatch")
        self.identity = actual

    def wait_ready(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                return False
            if self._ready():
                return True
            time.sleep(0.1)
        return False

    def request_shutdown(self) -> None:
        if self.process.poll() is None:
            self._graceful()

    def wait_exited(self, timeout_seconds: float) -> bool:
        try:
            self.process.wait(timeout=timeout_seconds)
            self.inspector.unregister(self.process.pid)
            return True
        except subprocess.TimeoutExpired:
            return False

    def force_terminate(self) -> None:
        actual = self.inspector.inspect(self.process.pid)
        validate_process_ownership(self.identity, actual, self.runtime)
        self.process.terminate()

    def is_running(self) -> bool:
        return self.process.poll() is None


class PackagedProcessFactory:
    def __init__(self, config: PackagedProcessConfig, inspector):
        self.config = config
        self.inspector = inspector
        self.database_port: int | None = None
        self.backend_port: int | None = None
        self._bootstrap_secret: str | None = None
        self.postgres_runtime: Path | None = None
        self._migration_ready = False
        self.backend_control_writer = None
        self._runtime_instance_id: str | None = None

    def start(
        self, role: RuntimeRole, port: int, runtime: RuntimeIdentity,
        paths: WindowsPackagingPaths,
    ) -> PackagedManagedChild:
        if paths != self.config.paths:
            raise ValueError("packaged process paths changed after validation")
        if role is RuntimeRole.POSTGRESQL:
            self.database_port = port
            return self._start_postgres(port, runtime)
        if role is RuntimeRole.BACKEND:
            if self.database_port is None:
                raise RuntimeError("PostgreSQL must start before Backend")
            self.backend_port = port
            return self._start_backend(port, runtime)
        raise RuntimeError("Frontend proxy is not implemented in Phase 5.1")

    def _start_postgres(self, port: int, runtime: RuntimeIdentity) -> PackagedManagedChild:
        self.postgres_runtime = _postgres_execution_root(
            self.config.layout.postgres, self.config.paths.runtime,
        )
        data = self.config.paths.database
        initialize_cluster(
            self.config, data, postgres_runtime=self.postgres_runtime,
        )
        log = self.config.paths.logs / "postgresql.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        postgres_bin = self.postgres_runtime / "bin"
        executable = postgres_bin / "postgres.exe"
        stream = log.open("ab")
        process = subprocess.Popen(
            [str(executable), "-D", str(data), "-h", "127.0.0.1", "-p", str(port)],
            cwd=self.postgres_runtime, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        def ready() -> bool:
            probe = _run([
                postgres_bin / "pg_isready.exe", "-h", "127.0.0.1",
                "-p", str(port), "-U", self.config.database_user,
            ], check=False)
            if probe.returncode != 0:
                return False
            self._bootstrap_database(port)
            if not self._migration_ready:
                self._run_packaged_migrations(port)
                self._migration_ready = True
            return True
        def stop() -> None:
            _run([
                postgres_bin / "pg_ctl.exe", "stop", "-D", data,
                "-m", "fast", "-w", "-t", "15",
            ], check=False)
        return PackagedManagedChild(
            role=RuntimeRole.POSTGRESQL, process=process, runtime=runtime,
            inspector=self.inspector, expected_executable=executable, ready=ready, graceful=stop,
        )

    def _bootstrap_database(self, port: int) -> None:
        PackagedDatabaseBootstrap(
            postgres_bin=self._postgres_bin,
            port=port,
            database_name=self.config.database_name,
            database_user=self.config.database_user,
            run=_run,
        ).ensure_ready()
        # A newly created application database needs the pre-ledger schema before
        # the packaged migration runner can adopt and advance it.
        if not self._schema_exists(port):
            for migration in sorted(self.config.layout.migrations.glob("*.sql")):
                if migration.name != "017_chapter_archive_state.sql":
                    _run(self._psql(port, self.config.database_name, ["-v", "ON_ERROR_STOP=1", "-f", str(migration)]))

    def _schema_exists(self, port: int) -> bool:
        return _run(self._psql(port, self.config.database_name, ["-tAc", "SELECT to_regclass('public.novels') IS NOT NULL"]), check=False).stdout.strip() == "t"

    def _run_packaged_migrations(self, port: int) -> None:
        log_path = self.config.paths.logs / "migration.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        def log(message: str) -> None:
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(message + "\n")

        def execute(sql: str) -> None:
            result = _run(self._psql(port, self.config.database_name, ["-v", "ON_ERROR_STOP=1", "-X", "-c", sql]), check=False)
            if result.returncode != 0:
                raise RuntimeError("packaged migration SQL failed")

        PackagedPostgresMigrationRunner(
            migrations_path=self.config.layout.migrations,
            execute_sql=execute,
            log=log,
        ).run()

    def _psql(self, port: int, database: str, extra: list[str]) -> list[Path | str]:
        return [self._postgres_bin / "psql.exe", "-h", "127.0.0.1", "-p", str(port), "-U", self.config.database_user, "-d", database, *extra]

    @property
    def _postgres_bin(self) -> Path:
        return (self.postgres_runtime or self.config.layout.postgres) / "bin"

    def _start_backend(self, port: int, runtime: RuntimeIdentity) -> PackagedManagedChild:
        self._runtime_instance_id = runtime.runtime_instance_id
        log = self.config.paths.logs / "backend.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        executable = self.config.layout.python
        environment = os.environ.copy()
        self._bootstrap_secret = secrets.token_urlsafe(48)
        environment.update(self.config.environment(
            database_port=self.database_port or 0, backend_port=port,
            runtime_instance_id=runtime.runtime_instance_id,
            bootstrap_secret=self._bootstrap_secret,
        ))
        for secret_name in PACKAGED_PROVIDER_SECRET_ENV_VARS:
            environment.pop(secret_name, None)
        environment["CREDENTIAL_VAULT_BACKEND"] = "auto"
        environment["CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK"] = "false"
        stream = log.open("ab")
        process = subprocess.Popen(
            [str(executable), "-I", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
            cwd=self.config.layout.backend, env=environment, stdin=subprocess.PIPE,
            stdout=stream, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        def ready() -> bool:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    body = json.load(response)
                if response.status == 200 and body.get("version") == self.config.version:
                    if process.stdin is not None:
                        process.stdin.write(encode_ping(runtime.runtime_instance_id))
                        process.stdin.flush()
                        self.backend_control_writer = process.stdin
                    return True
                return False
            except (OSError, ValueError, urllib.error.URLError):
                return False
        def stop() -> None:
            process.send_signal(getattr(subprocess, "CTRL_BREAK_EVENT", 1))
        return PackagedManagedChild(
            role=RuntimeRole.BACKEND, process=process, runtime=runtime,
            inspector=self.inspector, expected_executable=executable, ready=ready, graceful=stop,
        )

    def take_bootstrap_secret(self) -> str:
        if self._bootstrap_secret is None:
            raise RuntimeError("packaged bootstrap is unavailable")
        value, self._bootstrap_secret = self._bootstrap_secret, None
        return value

    def forward_backend_ping(self, runtime_instance_id: str, observer=None) -> bool:
        if runtime_instance_id != self._runtime_instance_id or self.backend_control_writer is None:
            return False
        self.backend_control_writer.write(encode_ping(runtime_instance_id))
        self.backend_control_writer.flush()
        if observer is not None:
            observer("A1_PING_FORWARDED_FROM_WEBVIEW")
        return True

    def forward_backend_credential(self, host_line: str, observer=None) -> bool:
        message = parse_host_credential(host_line, self._runtime_instance_id or "")
        if message is None or self.backend_control_writer is None: return False
        self.backend_control_writer.write(encode_backend_credential(message)); self.backend_control_writer.flush()
        return True


def initialize_cluster(
    config: PackagedProcessConfig, data: Path, *, postgres_runtime: Path | None = None,
) -> bool:
    version = data / "PG_VERSION"
    if data.exists():
        if not data.is_dir() or not version.is_file():
            raise RuntimeError(DATABASE_INVALID)
        if version.read_text(encoding="ascii").strip() != "16":
            raise RuntimeError(DATABASE_INVALID)
        return False
    data.parent.mkdir(parents=True, exist_ok=True)
    postgres_bin = postgres_runtime / "bin" if postgres_runtime is not None else config.layout.postgres_bin
    _run([
        postgres_bin / "initdb.exe", "-D", data,
        "--username", config.database_user, "--encoding", "UTF8",
        "--locale", "C", "--auth-local", "trust", "--auth-host", "trust",
    ])
    with (data / "postgresql.conf").open("a", encoding="utf-8") as stream:
        stream.write("\nlisten_addresses = '127.0.0.1'\n")
    return True


def _postgres_execution_root(packaged_root: Path, runtime_root: Path) -> Path:
    target = packaged_root.resolve()
    if target.as_posix().isascii():
        return target
    digest = hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:12]
    alias = runtime_root.resolve() / f"PostgreSQL-{digest}"
    return _ensure_junction(alias, target)


def _ensure_junction(alias: Path, target: Path) -> Path:
    alias.parent.mkdir(parents=True, exist_ok=True)
    if alias.exists():
        if not getattr(os.path, "isjunction", lambda _path: False)(alias) or alias.resolve() != target:
            raise RuntimeError(RUNTIME_INCOMPLETE)
        return alias
    completed = subprocess.run(
        [os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"), "/d", "/c", "mklink", "/J", str(alias), str(target)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if (
        completed.returncode != 0 or not alias.is_dir()
        or not getattr(os.path, "isjunction", lambda _path: False)(alias)
        or alias.resolve() != target
    ):
        raise RuntimeError(RUNTIME_INCOMPLETE)
    return alias


def _run(arguments, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(value) for value in arguments], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if check and completed.returncode != 0:
        raise RuntimeError(RUNTIME_INCOMPLETE)
    return completed
