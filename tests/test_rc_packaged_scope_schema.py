"""Packaged chapter startup must prepare its existing scope-document schema."""
from pathlib import Path
from types import SimpleNamespace

from app.packaging.packaged_processes import PackagedProcessFactory
from app.packaging.postgres_migrations import PackagedPostgresMigrationRunner


ROOT = Path(__file__).resolve().parents[1]
SCOPE_ID = "0003_experimental_scope_documents"


def test_packaged_owner_prepares_branch_schema_without_launcher_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("EXPERIMENTAL_FEATURES", raising=False)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    commands = []

    def run(command, **kwargs):
        commands.append([str(value) for value in command])
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("app.packaging.packaged_processes._run", run)
    config = SimpleNamespace(
        layout=SimpleNamespace(migrations=ROOT / "database/migrations", postgres=tmp_path / "postgres"),
        paths=SimpleNamespace(logs=tmp_path / "logs"),
        database_name="isolated-acceptance", database_user="novel_studio",
    )
    factory = PackagedProcessFactory(config, SimpleNamespace())
    factory._run_packaged_migrations(54321)
    sql = [command[command.index("-c") + 1] for command in commands]
    scope_sql = next(statement for statement in sql if "CREATE TABLE IF NOT EXISTS experimental_scope_documents" in statement)
    identity_sql = next(statement for statement in sql if "CREATE TABLE IF NOT EXISTS chapter_identities" in statement)
    assert SCOPE_ID in scope_sql
    assert sql.index(scope_sql) < sql.index(identity_sql)
    assert "0002_context_privacy" in scope_sql
    assert SCOPE_ID in sql[-1]
    assert "packaged migration schema ready" in (tmp_path / "logs/migration.log").read_text(encoding="utf-8")
    assert all("isolated-acceptance" in command for command in commands)


def test_explicit_schema_dependency_does_not_enable_runtime_features(monkeypatch):
    monkeypatch.delenv("EXPERIMENTAL_FEATURES", raising=False)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    from app.experimental.flags import enabled_flags

    runner = PackagedPostgresMigrationRunner(
        migrations_path=ROOT / "database/migrations", execute_sql=lambda sql: None,
        include_experimental=True,
    )
    assert SCOPE_ID in [row.migration_id for row in runner.migrations]
    assert enabled_flags() == frozenset()
    default = PackagedPostgresMigrationRunner(
        migrations_path=ROOT / "database/migrations", execute_sql=lambda sql: None,
    )
    assert SCOPE_ID not in [row.migration_id for row in default.migrations]
