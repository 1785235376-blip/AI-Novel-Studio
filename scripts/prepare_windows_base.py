"""Materialize a fresh Windows x64 base from reviewed, hash-locked official inputs.

This is a build helper, not an installer: no services, user databases, credentials,
WebView2 install, or downloaded executable is run. A build-machine pip only
unpacks the pinned wheels. Native smoke verification is a separate Windows step.
"""
from __future__ import annotations

import argparse
import email
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "packaging/windows-runtime-inputs.json"
ALLOWED_HOSTS = frozenset({"www.python.org", "get.enterprisedb.com", "files.pythonhosted.org"})
POSTGRES_TREES = frozenset({"bin", "lib", "share", "doc"})
REQUIRED_POSTGRES = (
    "bin/postgres.exe", "bin/initdb.exe", "bin/pg_ctl.exe", "bin/pg_isready.exe",
    "bin/pg_dump.exe", "bin/pg_restore.exe", "bin/psql.exe", "bin/createdb.exe",
    "lib/pgcrypto.dll", "share/extension/pgcrypto.control", "share/postgres.bki",
    "bin/libcrypto-3-x64.dll", "bin/libssl-3-x64.dll", "bin/zlib1.dll",
    "server_license.txt", "commandlinetools_3rd_party_licenses.txt",
)
CRT_REQUIRED = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
REDIST_SOURCE = "https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution"
PTH_CONTENT = "python312.zip\n.\nLib\\site-packages\n..\\..\\Backend\nimport site\n"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or (item.exists() and getattr(item.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"Links/reparse points are not accepted: {item}")


def checked_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment:
        raise ValueError("Input URL must use HTTPS on a reviewed official origin")
    return url


class OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(item: dict, cache: Path) -> Path:
    name = item["filename"]
    if Path(name).name != name or not re.fullmatch(r"[A-Za-z0-9_.+-]+", name):
        raise ValueError("Unsafe input filename")
    if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
        raise ValueError("Input requires an exact SHA256")
    checked_url(item["url"])
    target = cache / name
    reject_links(target)
    if not target.exists():
        temporary = target.with_suffix(target.suffix + ".part")
        reject_links(temporary)
        if temporary.exists():
            raise ValueError(f"Remove/review interrupted input before retrying: {temporary}")
        opener = urllib.request.build_opener(OfficialRedirects())
        try:
            with opener.open(item["url"], timeout=90) as response, temporary.open("xb") as output:
                checked_url(response.url)
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > item["size"]:
                        raise ValueError(f"Unexpected input length: {name}")
                    output.write(chunk)
            if temporary.stat().st_size != item["size"] or sha256(temporary) != item["sha256"]:
                raise ValueError(f"Input digest/length mismatch: {name}")
            temporary.rename(target)
        finally:
            if temporary.exists():
                temporary.unlink()
    if target.stat().st_size != item["size"] or sha256(target) != item["sha256"]:
        raise ValueError(f"Cached input digest/length mismatch: {name}")
    return target


def safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    seen: set[str] = set()
    total = 0
    for member in archive.infolist():
        name = member.filename
        parts = name.rstrip("/").split("/")
        # ZipInfo normalizes Windows separators in filename while preserving
        # orig_filename. Enforce the same raw-entry policy on both platforms.
        if (not name or "\\" in name or "\\" in member.orig_filename or name.startswith("/") or
                any(part in ("", "..", ".") or ":" in part or part.endswith((" ", ".")) for part in parts) or
                any(re.fullmatch(r"(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part) for part in parts)):
            raise ValueError(f"Unsafe archive path: {name}")
        kind = stat.S_IFMT(member.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or member.flag_bits & 1:
            raise ValueError(f"Link/special/encrypted archive member: {name}")
        key = name.rstrip("/").casefold()
        if key in seen:
            raise ValueError(f"Duplicate/case-colliding archive member: {name}")
        seen.add(key)
        total += member.file_size
        if total > 2_000_000_000:
            raise ValueError("Archive expands beyond the reviewed size limit")
    return archive.infolist()


def extract(archive_path: Path, destination: Path, *, postgres: bool = False) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        members = safe_members(archive)  # validate all paths before the first write
        for member in members:
            parts = PurePosixPath(member.filename).parts
            if postgres:
                if parts[0] != "pgsql":
                    raise ValueError("PostgreSQL archive has an unexpected root")
                parts = parts[1:]
                if not parts or not (parts[0] in POSTGRES_TREES or (len(parts) == 1 and "license" in parts[0].lower())):
                    continue
            target = destination.joinpath(*parts)
            reject_links(target)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)


def inventory(root: Path) -> list[dict]:
    result = []
    for path in sorted(root.rglob("*")):
        reject_links(path)
        if path.is_file():
            result.append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": sha256(path)})
    return result


def find_vc_redist(explicit: Path | None) -> Path | None:
    # Redistribution eligibility must be established by the caller. Merely
    # finding Visual Studio on a hosted runner does not establish that right.
    if explicit is None:
        return None
    candidates = [explicit]
    valid = []
    for candidate in candidates:
        if candidate is None:
            continue
        candidate = candidate.absolute()
        reject_links(candidate)
        # Only the documented release redistributable tree; never System32,
        # Debug_NonRedist, or an arbitrary machine's runtime folder.
        if not re.search(r"/VC/Redist/MSVC/[0-9.]+/x64/Microsoft\.VC143\.CRT$", candidate.as_posix(), re.I):
            raise ValueError("VC runtime input must be an installed Visual Studio release REDIST directory")
        if all((candidate / name).is_file() for name in CRT_REQUIRED):
            valid.append(candidate)
    if not valid:
        raise ValueError("Visual Studio 2022 x64 release CRT redistributables are required; supply --vc-redist-directory")
    return max(valid, key=lambda p: tuple(int(n) for n in p.parts[-3].split(".")))


def validate_dependency_closure(lock: dict) -> None:
    # pip is already the build-time wheel unpacker; its vendored parser avoids
    # adding a production packaging dependency. Evaluate Windows markers even
    # when materializing the input tree on a Linux build machine.
    from pip._vendor.packaging.markers import default_environment
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.utils import canonicalize_name
    from pip._vendor.packaging.specifiers import SpecifierSet
    environment = default_environment()
    environment.update({"sys_platform": "win32", "os_name": "nt", "platform_system": "Windows",
                        "platform_machine": "AMD64", "python_version": "3.12", "python_full_version": "3.12.9",
                        "implementation_name": "cpython", "platform_python_implementation": "CPython"})
    versions = {canonicalize_name(item["name"]): item["version"] for item in lock["wheels"]}
    for item in lock["wheels"]:
        if item.get("requires_python") and not SpecifierSet(item["requires_python"]).contains("3.12.9"):
            raise ValueError(f"Wheel does not support the embedded Python: {item['name']}")
        extras = ("", "binary") if canonicalize_name(item["name"]) == "psycopg" else ("",)
        for raw in item.get("requires_dist", []):
            requirement = Requirement(raw)
            if requirement.marker and not any(requirement.marker.evaluate({**environment, "extra": extra}) for extra in extras):
                continue
            version = versions.get(canonicalize_name(requirement.name))
            if version is None or not requirement.specifier.contains(version):
                raise ValueError(f"Windows dependency closure missing/incompatible: {item['name']} requires {raw}")


def prepare(output: Path, cache: Path, vc_redist_directory: Path | None) -> dict:
    output = output.absolute()
    cache = cache.absolute()
    reject_links(output)
    reject_links(cache)
    if output.exists():
        raise ValueError("Base output must be fresh; refusing to overwrite an existing application")
    if cache == output or cache.is_relative_to(output) or output.is_relative_to(cache):
        raise ValueError("Base output and download cache must be separate trees")
    crt = find_vc_redist(vc_redist_directory)
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock["schema_version"] != 1 or lock["target"] != "cp312-win_amd64":
        raise ValueError("Unsupported input manifest")
    validate_dependency_closure(lock)
    cache.mkdir(parents=True, exist_ok=True)
    paths = {item["name"]: download(item, cache) for item in lock["runtime_inputs"]}
    wheel_cache = cache / "wheels"
    wheel_cache.mkdir(exist_ok=True)
    for item in lock["wheels"]:
        wheel = download(item, wheel_cache)
        with zipfile.ZipFile(wheel) as archive:
            safe_members(archive)
            if not item["license_files"] or any(name not in archive.namelist() for name in item["license_files"]):
                raise ValueError(f"Required wheel license is missing: {item['name']}")
            metadata_paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1:
                raise ValueError(f"Wheel metadata is ambiguous: {item['name']}")
            metadata = email.message_from_bytes(archive.read(metadata_paths[0]))
            if (metadata["Name"] != item["name"] or metadata["Version"] != item["version"] or
                    metadata.get_all("Requires-Dist", []) != item["requires_dist"] or
                    metadata.get("Requires-Python") != item["requires_python"]):
                raise ValueError(f"Wheel metadata differs from reviewed dependency lock: {item['name']}")
    output.mkdir()
    python = output / "Runtime/Python"
    postgres = output / "PostgreSQL"
    extract(paths["CPython"], python)
    extract(paths["PostgreSQL"], postgres, postgres=True)
    for name in REQUIRED_POSTGRES:
        if not (postgres / name).is_file():
            raise ValueError(f"PostgreSQL input is incomplete: {name}")
    crt_inventory = inventory(crt) if crt else []
    if crt:
        for path in crt.glob("*.dll"):
            shutil.copyfile(path, postgres / "bin" / path.name)
    # Vendoring is CPython's supported embed-distribution model; pip itself is
    # never installed into the embedded runtime or run by the user's app.
    subprocess.run([
        sys.executable, "-m", "pip", "--isolated", "install", "--no-index", "--no-deps",
        "--no-compile", "--only-binary=:all:", "--platform", "win_amd64",
        "--python-version", "3.12", "--implementation", "cp", "--abi", "cp312",
        "--require-hashes", "--find-links", str(wheel_cache), "--target", str(python / "Lib/site-packages"),
        "-r", str(ROOT / "packaging/requirements-windows.lock.txt"),
    ], check=True)
    (python / "python312._pth").write_text(PTH_CONTENT, encoding="ascii")
    licenses = output / "Licenses"
    licenses.mkdir()
    shutil.copyfile(python / "LICENSE.txt", licenses / "CPython-LICENSE.txt")
    for path in postgres.glob("*license*.txt"):
        shutil.copyfile(path, licenses / ("PostgreSQL-" + path.name))
    # Existing VS installation is the licensed build input. No installer or
    # agreement is accepted here; eligibility to redistribute is not invented.
    (licenses / "MSVC-REDISTRIBUTION.txt").write_text(
        "CRT mode: " + ("caller-supplied licensed release REDIST input" if crt else "external system prerequisite; no files copied") + "\n"
        "Redistribution is subject to the existing Visual Studio license and its REDIST list:\n"
        + REDIST_SOURCE + "\nSource: " + str(crt) + "\n", encoding="utf-8")
    (licenses / "PYTHON-WHEEL-LICENSES.txt").write_text(
        "Full wheel notices are retained in Runtime/Python/Lib/site-packages/*.dist-info.\n"
        + "\n".join(item["filename"] + ": " + ", ".join(item["license_files"]) for item in lock["wheels"]) + "\n", encoding="utf-8")
    (output / "PREREQUISITES.txt").write_text(
        "Internal Windows x64 acceptance payload. Not a public release.\n"
        "Requires an installed Microsoft Edge WebView2 Evergreen Runtime.\n"
        + ("Requires Microsoft Visual C++ 2015-2022 x64 Redistributable (MSVCP140.dll / VCRUNTIME140.dll).\n" if not crt else "App-local release CRT input supplied by the caller; see Licenses.\n") +
        "This package does not download/install WebView2 or accept new runtime terms.\n"
        "Official user-controlled installation: https://developer.microsoft.com/en-us/microsoft-edge/webview2/\n"
        "Native interactive launch, IME, signing and user acceptance remain separate gates.\n", encoding="utf-8")
    manifest = {
        "schema_version": 1, "kind": "fresh-windows-base-inputs", "public_release": False,
        "native_runtime_verification": "NOT_RUN", "interactive_acceptance": "NOT_RUN",
        "input_manifest_sha256": sha256(LOCK), "inputs": lock,
        "vc_redist": {"mode": "caller-supplied-licensed-redist" if crt else "external-system-prerequisite", "source": str(crt) if crt else None, "license_source": REDIST_SOURCE, "files": crt_inventory},
        "files": inventory(output),
    }
    (output / "base-input-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--vc-redist-directory", type=Path)
    args = parser.parse_args()
    result = prepare(args.output, args.cache, args.vc_redist_directory)
    print(json.dumps({"base_application": str(args.output.absolute()), "files": len(result["files"]), "native_runtime_verification": "NOT_RUN"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
