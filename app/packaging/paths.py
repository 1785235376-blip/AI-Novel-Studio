from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


PRODUCT_DIRECTORY = "AI-Novel-Studio"


@dataclass(frozen=True)
class WindowsPackagingPaths:
    application: Path
    user_data: Path
    database: Path
    novel_data: Path
    config: Path
    logs: Path
    runtime: Path
    cache: Path
    backups: Path

    @classmethod
    def resolve(
        cls, *, local_app_data: str | os.PathLike[str] | None = None,
        user_profile: str | os.PathLike[str] | None = None,
    ) -> "WindowsPackagingPaths":
        local = _absolute_base(local_app_data or os.environ.get("LOCALAPPDATA"), "LOCALAPPDATA")
        profile = _absolute_base(user_profile or os.environ.get("USERPROFILE"), "USERPROFILE")
        product_root = local / PRODUCT_DIRECTORY
        user_data = product_root / "UserData"
        result = cls(
            application=local / "Programs" / PRODUCT_DIRECTORY,
            user_data=user_data,
            database=user_data / "PostgreSQL",
            novel_data=user_data / "NovelData",
            config=product_root / "Config",
            logs=product_root / "Logs",
            runtime=product_root / "Runtime",
            cache=product_root / "Cache",
            backups=profile / "Documents" / PRODUCT_DIRECTORY / "Backups",
        )
        result.validate()
        return result

    def validate(self) -> None:
        values = list(asdict(self).values())
        if any(not Path(value).is_absolute() for value in values):
            raise ValueError("All packaging paths must be absolute")
        if _contains(self.user_data, self.application) or _contains(self.application, self.user_data):
            raise ValueError("Application files and user data must be separated")
        for durable in (self.user_data, self.database, self.novel_data, self.config, self.logs, self.backups):
            if _contains(self.application, durable):
                raise ValueError("Durable data cannot be stored inside the application directory")

    def as_public_dict(self) -> dict[str, str]:
        """Return paths only; the contract intentionally has no credential fields."""
        return {name: str(value) for name, value in asdict(self).items()}

    @property
    def normal_uninstall_roots(self) -> tuple[Path, ...]:
        return (self.application, self.runtime, self.cache)

    @property
    def preserved_roots(self) -> tuple[Path, ...]:
        return (self.user_data, self.config, self.logs, self.backups)


def validate_destructive_target(
    target: str | os.PathLike[str], *, allowed_roots: Iterable[str | os.PathLike[str]],
    allow_root: bool = False,
) -> Path:
    raw = str(target)
    if not raw or any(marker in raw for marker in ("%", "$", "~")):
        raise ValueError("Destructive targets must not contain unresolved variables")
    candidate = Path(raw)
    if not candidate.is_absolute():
        raise ValueError("Destructive targets must be absolute")
    candidate = candidate.resolve(strict=False)
    roots = tuple(Path(root).resolve(strict=False) for root in allowed_roots)
    if not roots:
        raise ValueError("At least one explicit deletion root is required")
    for root in roots:
        if candidate == root:
            if allow_root:
                _reject_reparse_points(candidate)
                return candidate
            continue
        if _contains(root, candidate):
            _reject_reparse_points(candidate)
            return candidate
    raise ValueError("Destructive target is outside the approved roots")


def _absolute_base(value: str | os.PathLike[str] | None, name: str) -> Path:
    if value is None or not str(value).strip():
        raise RuntimeError(f"{name} is required for Windows packaging paths")
    raw = str(value)
    if any(marker in raw for marker in ("%", "$", "~")):
        raise ValueError(f"{name} contains an unresolved variable")
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError(f"{name} must be absolute")
    return path.resolve(strict=False)


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _reject_reparse_points(path: Path) -> None:
    current = path
    while True:
        if current.exists():
            stat = current.lstat()
            attributes = getattr(stat, "st_file_attributes", 0)
            if current.is_symlink() or attributes & 0x400:
                raise ValueError("Destructive targets must not traverse links or reparse points")
        if current.parent == current:
            return
        current = current.parent
