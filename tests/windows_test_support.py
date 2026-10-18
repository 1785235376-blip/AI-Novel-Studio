"""Windows test portability helpers for platform limitations.

The hosted Linux CI has the privileges and POSIX semantics these contracts rely on.
A default Windows developer session does not (symlink creation requires Developer Mode or
SeCreateSymbolicLinkPrivilege). Production code must still reject links when they exist; these
helpers only skip the *construction* of the fixture when the platform denies it.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REASON_SYMLINK = (
    "WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE: hosted Linux CI covers the symlink contract"
)


def _skip_if_denied(error: OSError) -> None:
    if getattr(error, "winerror", None) == 1314 or getattr(error, "errno", None) in (1, 22):
        pytest.skip(REASON_SYMLINK)
    raise error


def symlink_or_skip(source: str | os.PathLike[str], target: str | os.PathLike[str],
                    *, target_is_directory: bool = False) -> None:
    """Create a symlink at *source* pointing to *target*, or skip when Windows denies it."""
    try:
        Path(source).symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        _skip_if_denied(error)


def os_symlink_or_skip(source: str | os.PathLike[str], target: str | os.PathLike[str],
                       *, target_is_directory: bool = False) -> None:
    """os.symlink wrapper with the same explicit Windows skip contract."""
    try:
        os.symlink(target, source, target_is_directory=target_is_directory)
    except OSError as error:
        _skip_if_denied(error)
