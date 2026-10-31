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
import stat
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


def _check_json_credentials(path: Path, relative: str, *, max_json_bytes: int | None = None) -> None:
    if path.suffix.lower() != ".json":
        return
    try:
        value = (json.loads(path.read_text(encoding="utf-8-sig")) if max_json_bytes is None
                 else _restored_json(path, max_json_bytes))
    except BackupError:
        raise
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
    return _verify_backup_manifest(backup, manifest)


def _verify_backup_manifest(backup: Path, manifest: dict, *, max_json_bytes: int | None = None) -> dict:
    """Shared original integrity checks, including credential and membership guards."""
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
        _check_json_credentials(path, relative, max_json_bytes=max_json_bytes)
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


RESTORED_MAX_ENTRIES = 100_000
RESTORED_MAX_DEPTH = 64
RESTORED_MAX_PATH_CHARS = 4096
RESTORED_MANIFEST_BYTES = 16 * 1024 * 1024
RESTORED_RECEIPT_BYTES = 64 * 1024
RESTORED_JSON_BYTES = 16 * 1024 * 1024


def _restored_root(path: Path) -> Path:
    """Check lexical ancestors before resolving; trusted, quiescent trees only."""
    path = path.absolute()
    if ".." in path.parts:
        raise BackupError("RESTORED_UNSAFE_ROOT")
    for ancestor in reversed((path, *path.parents)):
        if not stat.S_ISDIR(ancestor.lstat().st_mode):
            raise BackupError("RESTORED_UNSAFE_ROOT")
    return path


def _restored_inventory(root: Path) -> dict[str, tuple]:
    """Metadata only: never open unexpected files or traverse linked directories."""
    result = {}
    pending = [(root, "", 0)]
    while pending:
        path, relative, depth = pending.pop()
        info = path.lstat()
        if depth > RESTORED_MAX_DEPTH or len(result) >= RESTORED_MAX_ENTRIES:
            raise BackupError("RESTORED_LIMIT_EXCEEDED")
        directory = stat.S_ISDIR(info.st_mode)
        if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
            raise BackupError("RESTORED_UNSAFE_ENTRY")
        if path.name in {".incomplete", ".restore-incomplete"}:
            raise BackupError("RESTORED_INCOMPLETE")
        result[relative] = (directory, info.st_dev, info.st_ino, info.st_mode,
                            info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if directory:
            with os.scandir(path) as children:
                for child in children:
                    if len(result) + len(pending) >= RESTORED_MAX_ENTRIES:
                        raise BackupError("RESTORED_LIMIT_EXCEEDED")
                    name = f"{relative}/{child.name}" if relative else child.name
                    pending.append((Path(child.path), name, depth + 1))
    return result


def _restored_json(path: Path, limit: int):
    # The inventory has already rejected links/special files. The bounded read
    # also limits allocation if an ordinary writer violates offline mode.
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise BackupError("RESTORED_LIMIT_EXCEEDED")
    return json.loads(raw.decode("utf-8-sig"))


def _restored_members(files: set[str]) -> set[str]:
    members = set()
    def add(name: str) -> None:
        if name not in members:
            if len(members) >= RESTORED_MAX_ENTRIES:
                raise BackupError("RESTORED_LIMIT_EXCEEDED")
            members.add(name)
    add("")
    for relative in files:
        add(relative)
        for parent in PurePosixPath(relative).parents:
            if parent.as_posix() != ".":
                add(parent.as_posix())
    return members


def verify_restored_directory(backup: Path, destination: Path, *,
                              offline_confirmed: bool = False) -> dict:
    """Read-only byte comparison, not application/database readiness or provenance.

    Caller supplies trusted roots and stops every writer for the whole operation.
    Metadata rechecks detect ordinary changes, not adversarial replacement races.
    """
    if not offline_confirmed:
        raise BackupError("RESTORED_OFFLINE_REQUIRED")
    try:
        backup, destination = _restored_root(backup), _restored_root(destination)
        if backup.is_relative_to(destination) or destination.is_relative_to(backup):
            raise BackupError("RESTORED_OVERLAPPING_ROOTS")
        backup_before = _restored_inventory(backup)
        target_before = _restored_inventory(destination)
        if "manifest.json" not in backup_before or backup_before["manifest.json"][0]:
            raise BackupError("RESTORED_BACKUP_INVALID")
        manifest = _restored_json(backup / "manifest.json", RESTORED_MANIFEST_BYTES)
        if (not isinstance(manifest, dict) or manifest.get("backup_version") != FORMAT_VERSION
                or type(manifest.get("file_count")) is not int
                or type(manifest.get("database_included")) is not bool
                or not isinstance(manifest.get("app_version"), str)
                or not isinstance(manifest.get("checksum"), list)
                or not manifest["checksum"]
                or manifest["file_count"] != len(manifest["checksum"])):
            raise BackupError("RESTORED_BACKUP_INVALID")
        if len(manifest["checksum"]) >= RESTORED_MAX_ENTRIES:
            raise BackupError("RESTORED_LIMIT_EXCEEDED")
        expected = {}
        for item in manifest["checksum"]:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise BackupError("RESTORED_BACKUP_INVALID")
            # Bound expansion before PurePosixPath constructs all ancestors.
            if (len(item["path"]) > RESTORED_MAX_PATH_CHARS
                    or item["path"].count("/") + 1 > RESTORED_MAX_DEPTH):
                raise BackupError("RESTORED_LIMIT_EXCEEDED")
            try:
                relative = _member(item["path"]).as_posix()
            except BackupError:
                raise BackupError("RESTORED_BACKUP_INVALID") from None
            if (relative in expected or type(item.get("size")) is not int or item["size"] < 0
                    or not isinstance(item.get("sha256"), str)
                    or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])):
                raise BackupError("RESTORED_BACKUP_INVALID")
            expected[relative] = item
        backup_files = {"manifest.json", *expected}
        target_files = {"restore-receipt.json", *(set(expected) - {"database.dump"})}
        for inventory, files, code in ((backup_before, backup_files, "RESTORED_BACKUP_INVALID"),
                                        (target_before, target_files, "RESTORED_MEMBERSHIP_MISMATCH")):
            if (set(inventory) != _restored_members(files)
                    or {name for name, info in inventory.items() if not info[0]} != files):
                raise BackupError(code)
        # Original verifier retains format, checksum and JSON credential guards.
        # Membership is checked first so no unexpected file body is opened.
        try:
            if _verify_backup_manifest(backup, manifest, max_json_bytes=RESTORED_JSON_BYTES) != manifest:
                raise BackupError("RESTORED_BACKUP_INVALID")
        except BackupError as exc:
            if str(exc) == "RESTORED_LIMIT_EXCEEDED":
                raise
            raise BackupError("RESTORED_BACKUP_INVALID") from None
        receipt = _restored_json(destination / "restore-receipt.json", RESTORED_RECEIPT_BYTES)
        if (not isinstance(receipt, dict) or set(receipt) != {
                "backup_version", "app_version", "file_count", "database_restored", "restored_at"}
                or receipt.get("backup_version") != FORMAT_VERSION
                or receipt.get("app_version") != manifest["app_version"]
                or type(receipt.get("file_count")) is not int
                or receipt["file_count"] != manifest["file_count"]
                or type(receipt.get("database_restored")) is not bool
                or receipt["database_restored"] != manifest["database_included"]
                or not isinstance(receipt.get("restored_at"), str)):
            raise BackupError("RESTORED_RECEIPT_INVALID")
        try:
            timestamp = datetime.fromisoformat(receipt["restored_at"])
            if timestamp.utcoffset() is None:
                raise ValueError
        except ValueError:
            raise BackupError("RESTORED_RECEIPT_INVALID") from None
        count = total = 0
        for relative, item in expected.items():
            if relative == "database.dump":
                continue
            if (target_before[relative][4] != item["size"]
                    or _hash(destination / relative) != item["sha256"]):
                raise BackupError("RESTORED_CONTENT_MISMATCH")
            count += 1
            total += item["size"]
        if (backup_before != _restored_inventory(backup)
                or target_before != _restored_inventory(destination)):
            raise BackupError("RESTORED_TREE_CHANGED")
        return {"status": "file_bytes_verified", "verified_file_count": count,
                "verified_byte_count": total, "application_compatibility": "not_verified",
                "database_validation": "unsupported" if manifest["database_included"] else "not_applicable",
                "switch_performed": False}
    except BackupError:
        raise
    except (OSError, ValueError, TypeError, RecursionError):
        raise BackupError("RESTORED_INPUT_INVALID_OR_UNREADABLE") from None


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
    restored = commands.add_parser("verify-restored")
    restored.add_argument("--backup", type=Path, required=True)
    restored.add_argument("--destination", type=Path, required=True)
    restored.add_argument("--offline-confirmed", action="store_true")
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
        elif args.command == "verify-restored":
            result = verify_restored_directory(args.backup, args.destination,
                                               offline_confirmed=args.offline_confirmed)
        else:
            result = verify_backup(args.backup)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except BackupError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
