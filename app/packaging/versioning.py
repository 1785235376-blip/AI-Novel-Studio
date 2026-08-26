from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class VersionMismatch(ValueError):
    """Raised when a release consumer disagrees with the authoritative version."""


@dataclass(frozen=True)
class ReleaseVersion:
    product: str
    version: str
    channel: str
    display_version: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReleaseVersion":
        required = {"product", "version", "channel", "display_version"}
        if set(value) != required:
            missing = sorted(required - set(value))
            extra = sorted(set(value) - required)
            raise ValueError(f"Invalid release version keys; missing={missing}, extra={extra}")
        if value["product"] != "AI-Novel-Studio":
            raise ValueError("Unsupported release product")
        version = str(value["version"])
        if re.fullmatch(r"\d+\.\d+\.\d+", version) is None:
            raise ValueError("Release version must use MAJOR.MINOR.PATCH")
        if value["channel"] not in {"alpha", "beta", "stable"}:
            raise ValueError("Unsupported release channel")
        return cls(
            product=str(value["product"]), version=version,
            channel=str(value["channel"]), display_version=str(value["display_version"]),
        )


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_release_version(path: Path | None = None) -> ReleaseVersion:
    source = path or repository_root() / "release" / "version.json"
    return ReleaseVersion.from_mapping(json.loads(source.read_text(encoding="utf-8")))


def validate_manifest_version(manifest: Mapping[str, Any], release: ReleaseVersion) -> None:
    actual = manifest.get("app_version")
    if actual != release.version:
        raise VersionMismatch(
            f"manifest app_version mismatch: expected {release.version}, got {actual!r}"
        )


def _env_value(path: Path, name: str) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    return None


def validate_repository_versions(root: Path | None = None) -> dict[str, str]:
    base = (root or repository_root()).resolve()
    release = load_release_version(base / "release" / "version.json")
    actual = {
        "backend": str(tomllib.loads((base / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]),
        "backend_module": _module_version(base / "app" / "__init__.py"),
        "frontend": str(json.loads((base / "frontend" / "package.json").read_text(encoding="utf-8"))["version"]),
        "environment": str(_env_value(base / ".env.example", "APP_VERSION")),
    }
    mismatches = {name: value for name, value in actual.items() if value != release.version}
    if mismatches:
        raise VersionMismatch(f"release version mismatch: expected {release.version}, got {mismatches}")

    documentation = {
        "README.md": (base / "README.md").read_text(encoding="utf-8"),
        "docs/installation.md": (base / "docs" / "installation.md").read_text(encoding="utf-8"),
    }
    missing = [name for name, content in documentation.items() if f"V{release.version}" not in content]
    if missing:
        raise VersionMismatch(f"documentation version mismatch: {missing} do not declare V{release.version}")
    return actual


def _module_version(path: Path) -> str:
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        path.read_text(encoding="utf-8"), flags=re.MULTILINE,
    )
    if match is None:
        raise VersionMismatch("backend module does not declare __version__")
    return match.group(1)
