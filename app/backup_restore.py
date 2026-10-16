"""Offline, verified, non-overwriting backup/recovery for File and PostgreSQL.

No credentials are accepted in CLI arguments or written into manifests. The caller
must stop application writers so filesystem sidecars and the DB represent one state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

FORMAT_VERSION = "0.2.0"
ROOTS = ("novel_data", "prompts", "workflows", "config", "database/migrations")
SECRET_KEYS = frozenset({"api_key", "apikey", "access_token", "refresh_token", "password", "client_secret", "secret_key", "private_key"})
SECRET_NAMES = frozenset({"credentials", "credential_vault", "vault", "keyring", ".ssh", ".aws"})


class BackupError(ValueError):
    pass


def _hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _secret_file(relative: Path) -> bool:
    return (any(part.lower() in SECRET_NAMES or part.lower().startswith(".env") for part in relative.parts)
            or relative.suffix.lower() in {".pem", ".key", ".p12", ".pfx"})


def _has_credential(value) -> bool:
    if isinstance(value, dict):
        return any((str(key).lower() in SECRET_KEYS and item not in (None, "", False)) or _has_credential(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_has_credential(item) for item in value)
    return False


def _inventory(root: Path, *, selected: bool) -> dict[str, Path]:
    output: dict[str, Path] = {}
    sources = [root / relative for relative in ROOTS] if selected else [root]
    for source in sources:
        if not source.exists():
            continue
        # Path.rglob does not follow directory symlinks; reject them explicitly.
        for path in [source, *sorted(source.rglob("*"))]:
            relative = path.relative_to(root)
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
                raise BackupError(f"Symlink is not a portable backup member: {relative}")
            if not path.is_file():
                continue
            if selected and _secret_file(relative):
                continue
            output[relative.as_posix()] = path
    return output


def _source_inventory(source: Path, data_directory: Path | None) -> dict[str, Path]:
    files = _inventory(source, selected=True)
    if data_directory is not None:
        if not data_directory.is_dir() or data_directory.is_symlink():
            raise BackupError("Data directory is missing or linked")
        files = {relative: path for relative, path in files.items() if not relative.startswith("novel_data/")}
        files.update({"novel_data/" + relative: path for relative, path in _inventory(data_directory, selected=False).items()
                      if not _secret_file(Path(relative))})
    return files


def _check_json_credentials(path: Path, relative: str) -> None:
    if path.suffix.lower() != ".json":
        return
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BackupError(f"Invalid JSON in backup source: {relative}") from exc
    if _has_credential(value):
        raise BackupError(f"Plaintext credential field found; move it to the OS vault before backup: {relative}")


def _connection(url: str) -> dict[str, str]:
    parsed = urlsplit(url.replace("postgresql+psycopg://", "postgresql://", 1))
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname or not parsed.path.strip("/"):
        raise BackupError("A PostgreSQL URL with explicit host and database is required")
    # Disallow arbitrary libpq service/options passthrough.
    if parsed.query or parsed.fragment:
        raise BackupError("Use an explicit PostgreSQL URL without query options")
    return {"host": parsed.hostname, "port": str(parsed.port or 5432),
            "user": unquote(parsed.username or "postgres"), "password": unquote(parsed.password or ""),
            "dbname": unquote(parsed.path.lstrip("/"))}


def _pg_environment(url: str) -> dict[str, str]:
    conn = _connection(url)
    result = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    result.update({"PGHOST": conn["host"], "PGPORT": conn["port"], "PGUSER": conn["user"],
                   "PGPASSWORD": conn["password"], "PGDATABASE": conn["dbname"]})
    return result


def _pg_run(command: list[str], url: str) -> None:
    try:
        subprocess.run(command, env=_pg_environment(url), capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        # libpq stderr can contain connection details. Do not log it or the URL.
        raise BackupError(f"{command[0]} failed; the backup/restore is incomplete") from exc


def backup_directory(source: Path, destination: Path, *, app_version: str,
                     offline_confirmed: bool, database_url: str | None = None,
                     data_directory: Path | None = None) -> dict:
    if not offline_confirmed:
        raise BackupError("Stop all application writers and confirm offline mode")
    source, destination = source.resolve(), destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise BackupError("Backup destination must not already exist")
    if destination.resolve().is_relative_to(source):
        raise BackupError("Backup must be outside the source directory")
    if data_directory is not None and destination.resolve().is_relative_to(data_directory.resolve()):
        raise BackupError("Backup must be outside the data directory")
    files = _source_inventory(source, data_directory)
    if not files:
        raise BackupError("Source contains no supported backup data")
    for relative, path in files.items():
        _check_json_credentials(path, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(mode=0o700)  # exclusive reservation, never merge/overwrite
    incomplete = destination / ".incomplete"
    incomplete.write_text("Backup incomplete. Do not restore.\n", encoding="utf-8")
    checksums = []
    for relative, path in files.items():
        before = _hash(path)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        os.chmod(target, 0o600)
        if before != _hash(target) or before != _hash(path):
            raise BackupError(f"Source changed during backup: {relative}")
        checksums.append({"path": relative, "sha256": before, "size": target.stat().st_size})
    if set(_source_inventory(source, data_directory)) != set(files):
        raise BackupError("Source file inventory changed during backup")
    if database_url:
        dump = destination / "database.dump"
        _pg_run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(dump)], database_url)
        os.chmod(dump, 0o600)
        checksums.append({"path":"database.dump", "sha256":_hash(dump), "size":dump.stat().st_size})
    manifest = {"backup_version": FORMAT_VERSION, "app_version": app_version,
                "created_at": datetime.now(timezone.utc).isoformat(), "offline_confirmed": True,
                "database_included": bool(database_url), "file_count": len(checksums),
                "excluded": ["OS credential vault", "environment files", "private-key files", "model blobs"],
                "checksum": checksums}
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    incomplete.unlink()
    verify_backup(destination)
    return manifest


def _member(relative: str) -> PurePosixPath:
    path = PurePosixPath(relative)
    if (not relative or "\\" in relative or ":" in relative or path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise BackupError("Unsafe manifest path")
    if relative == "database.dump":
        return path
    if not any(relative.startswith(root + "/") for root in ROOTS):
        raise BackupError("Manifest includes an unsupported root")
    if _secret_file(Path(relative)):
        raise BackupError("Manifest includes a forbidden credential member")
    return path


def verify_backup(backup: Path) -> dict:
    backup = backup.absolute()
    if backup.is_symlink() or not backup.is_dir() or (backup / ".incomplete").exists():
        raise BackupError("Backup is missing, linked, or incomplete")
    try:
        if (backup / "manifest.json").is_symlink():
            raise BackupError("Manifest cannot be a symlink")
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise BackupError("Backup manifest is missing or invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("backup_version") != FORMAT_VERSION:
        raise BackupError("Unsupported backup format; legacy backups require manual review")
    entries = manifest.get("checksum")
    if not isinstance(entries, list) or not entries or manifest.get("file_count") != len(entries):
        raise BackupError("Invalid manifest file inventory")
    actual = _inventory(backup, selected=False)
    expected = {"manifest.json"}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise BackupError("Invalid manifest entry")
        relative = item["path"]
        _member(relative)
        if relative in expected:
            raise BackupError("Duplicate manifest path")
        expected.add(relative)
        path = backup / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(backup.resolve()):
            raise BackupError("Backup member missing or unsafe")
        if (not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])
                or path.stat().st_size != item.get("size") or _hash(path) != item["sha256"]):
            raise BackupError(f"Backup integrity mismatch: {relative}")
        _check_json_credentials(path, relative)
    if set(actual) != expected:
        raise BackupError("Backup has unlisted or missing files")
    if bool(manifest.get("database_included")) != ("database.dump" in expected):
        raise BackupError("Database presence does not match the manifest")
    return manifest


def _restore_database(backup: Path, database_url: str) -> None:
    import psycopg
    from psycopg import sql
    conn = _connection(database_url)
    database_name = conn["dbname"]
    if database_name in {"postgres", "template0", "template1"}:
        raise BackupError("Restore requires a new, dedicated database name")
    try:
        with psycopg.connect(**{**conn, "dbname":"postgres"}, autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database_name,)).fetchone():
                raise BackupError("Restore database already exists; refusing to overwrite it")
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database_name)))
    except psycopg.Error as exc:
        raise BackupError("Could not create the new recovery database; existing databases were not modified") from exc
    # On failure the new empty DB is left for review. No automatic DROP/--clean.
    _pg_run(["pg_restore", "--single-transaction", "--exit-on-error", "--no-owner", "--no-acl",
             "--dbname", database_name, str(backup / "database.dump")], database_url)


def restore_directory(backup: Path, destination: Path, *, database_url: str | None = None) -> dict:
    manifest = verify_backup(backup)
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise BackupError("Restore destination must not already exist")
    if bool(database_url) != bool(manifest["database_included"]):
        raise BackupError("A database backup requires a new PostgreSQL target; File backups must not specify one")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(mode=0o700)
    incomplete = destination / ".restore-incomplete"
    incomplete.write_text("Restore incomplete. Do not start the application.\n", encoding="utf-8")
    for item in manifest["checksum"]:
        if item["path"] == "database.dump":
            continue
        source = backup / item["path"]
        target = destination / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        os.chmod(target, 0o600)
        if _hash(target) != item["sha256"]:
            raise BackupError("Backup changed during restore")
    # Recheck before importing a dump if another process edited the backup.
    verify_backup(backup)
    if database_url:
        _restore_database(backup, database_url)
    receipt = {"backup_version":FORMAT_VERSION, "app_version":manifest["app_version"],
               "file_count":manifest["file_count"], "database_restored":bool(database_url),
               "restored_at":datetime.now(timezone.utc).isoformat()}
    (destination / "restore-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    incomplete.unlink()
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--source", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True)
    backup.add_argument("--app-version", required=True)
    backup.add_argument("--offline-confirmed", action="store_true")
    backup.add_argument("--data-directory", type=Path, help="Actual NovelData/NOVEL_DATA_PATH root, including assets and sidecars")
    restore = commands.add_parser("restore")
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--backup", type=Path, required=True)
    for command in (backup, restore):
        command.add_argument("--database-url-env", help="Name of an environment variable containing the DB URL")
    args = parser.parse_args()
    try:
        database_url = None
        if getattr(args, "database_url_env", None):
            database_url = os.environ.get(args.database_url_env)
            if not database_url:
                raise BackupError("The selected database URL environment variable is empty")
        if args.command == "backup":
            result = backup_directory(args.source, args.destination, app_version=args.app_version,
                                      offline_confirmed=args.offline_confirmed, database_url=database_url,
                                      data_directory=args.data_directory)
        elif args.command == "restore":
            result = restore_directory(args.backup, args.destination, database_url=database_url)
        else:
            result = verify_backup(args.backup)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except BackupError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
