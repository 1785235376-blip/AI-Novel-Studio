"""Finite, launcher-owned packaged profiles; never request authority or tokens.

The default profile retains the original package contract. V2 selects existing
storage owners under a separate root, with the original WebView cache shape.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import stat
from time import monotonic

from .paths import WindowsPackagingPaths
from ..packaged_profile import DEFAULT_PROFILE, V2_PROFILE, PROFILE_ENV, PROFILES, validate_profile


V2_DIRECTORY = "AI-Novel-Studio-V2"
MAX_V2_STATE_ENTRIES = 100_000
MAX_V2_STATE_DEPTH = 64
MAX_V2_STATE_SCAN_SECONDS = 10.0
V2_FEATURES = (
    "branch_manuscript_v1", "narrative_production_v2", "ai_execution_v2",
    "model_broker_v2", "author_context_inspector_v2",
)


def _reject_link_entry(path: Path) -> None:
    try:
        facts = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(facts.st_mode) or getattr(facts, "st_file_attributes", 0) & 0x400:
        raise ValueError("PACKAGED_V2_LINKED_PATH")
    if stat.S_ISREG(facts.st_mode) and getattr(facts, "st_nlink", 1) > 1:
        raise ValueError("PACKAGED_V2_MULTILINK_FILE")


def _reject_links(path: Path) -> None:
    # Existing aliases are rejected; these pathname checks are not an atomic
    # filesystem sandbox against a concurrent writer with the same OS identity.
    for item in (path, *path.parents):
        _reject_link_entry(item)


def _is_owned_postgres_junction(path: Path, allowed) -> bool:
    if allowed is None or path != allowed[0]:
        return False
    is_junction = getattr(os.path, "isjunction", lambda _path: False)
    return is_junction(path) and path.resolve() == allowed[1]


def _reject_tree_links(root: Path, budget: dict, allowed_postgres_junction=None) -> None:
    _reject_links(root)
    # Existing V2 state may contain linked individual files, not just a linked
    # owner root. Stream entries so a huge single directory is also bounded.
    pending = [(root, 0)]
    while pending:
        directory, depth = pending.pop()
        if depth > MAX_V2_STATE_DEPTH or monotonic() - budget["started"] > MAX_V2_STATE_SCAN_SECONDS:
            raise ValueError("PACKAGED_V2_STATE_SCAN_LIMIT")
        try:
            entries = os.scandir(directory)
        except FileNotFoundError:
            if directory == root:
                continue
            raise ValueError("PACKAGED_V2_STATE_CHANGED") from None
        with entries:
            for entry in entries:
                budget["entries"] += 1
                if (budget["entries"] > MAX_V2_STATE_ENTRIES
                        or monotonic() - budget["started"] > MAX_V2_STATE_SCAN_SECONDS):
                    raise ValueError("PACKAGED_V2_STATE_SCAN_LIMIT")
                candidate = Path(entry.path)
                if _is_owned_postgres_junction(candidate, allowed_postgres_junction):
                    # Exact original executable-only Unicode workaround.
                    continue
                _reject_link_entry(candidate)
                if entry.is_dir(follow_symlinks=False):
                    pending.append((candidate, depth + 1))


def resolve_profile_paths(
    profile: str = DEFAULT_PROFILE, *, local_app_data=None, user_profile=None,
) -> WindowsPackagingPaths:
    validate_profile(profile)
    if profile == DEFAULT_PROFILE:
        return WindowsPackagingPaths.resolve(local_app_data=local_app_data, user_profile=user_profile)
    bases = []
    for value, name in ((local_app_data, "LOCALAPPDATA"), (user_profile, "USERPROFILE")):
        raw = os.fspath(value) if value is not None else os.environ.get(name, "")
        if not raw or not Path(raw).is_absolute() or any(mark in raw for mark in ("%", "$", "~")):
            raise ValueError("PACKAGED_V2_ABSOLUTE_ROOT_REQUIRED")
        owned = Path(raw) / V2_DIRECTORY
        _reject_links(owned)
        bases.append(owned)
    paths = WindowsPackagingPaths.resolve(local_app_data=bases[0], user_profile=bases[1])
    _profile_path_owners(paths)
    return paths


def _profile_path_owners(paths: WindowsPackagingPaths):
    paths.validate()
    local = paths.user_data.parent.parent
    profile_root = paths.backups.parents[2]
    if local.name != V2_DIRECTORY or profile_root.name != V2_DIRECTORY:
        raise ValueError("PACKAGED_V2_ISOLATED_ROOT_REQUIRED")
    expected = WindowsPackagingPaths.resolve(local_app_data=local, user_profile=profile_root)
    if paths != expected:
        raise ValueError("PACKAGED_V2_PATH_OWNER_MISMATCH")
    for path in asdict(paths).values():
        _reject_links(path)
    return local, profile_root


def validate_profile_paths(profile: str, paths: WindowsPackagingPaths, *, postgres_root: Path | None = None) -> None:
    validate_profile(profile)
    if profile == DEFAULT_PROFILE:
        return
    local, profile_root = _profile_path_owners(paths)
    allowed_junction = None
    if postgres_root is not None:
        target = postgres_root.resolve()
        if not target.as_posix().isascii():
            digest = hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:12]
            allowed_junction = (paths.runtime / f"PostgreSQL-{digest}", target)
    budget = {"entries": 0, "started": monotonic()}
    roots = tuple(dict.fromkeys((local, profile_root)))
    for root in roots:
        if not any(other in root.parents for other in roots):
            _reject_tree_links(root, budget, allowed_junction)


def v2_backend_environment(paths: WindowsPackagingPaths, *, postgres_root: Path) -> dict[str, str]:
    validate_profile_paths(V2_PROFILE, paths, postgres_root=postgres_root)
    # Original identity and provider sidecars have their own existing owners.
    # Bind those owners explicitly too; NOVEL_DATA_PATH alone does not move them.
    return {
        PROFILE_ENV: V2_PROFILE,
        "EXPERIMENTAL_FEATURES": ",".join(V2_FEATURES),
        "LOCALAPPDATA": str(paths.user_data.parent.parent),
        "ASSET_PROVIDER_CONFIG_PATH": str(paths.config / "asset-providers.json"),
        "AUDIO_PROVIDER_CONFIG_PATH": str(paths.config / "audio-providers.json"),
        "ASSET_WORKER_CONFIG_PATH": str(paths.config / "asset-worker.json"),
        "ENABLE_CLOUD": "false",
        "CREATION_PROFILE": "LOCAL_ONLY",
        "MOCK_PROVIDER": "false",
    }
