"""Host-owned isolated bootstrap for the Phase 2A test worker.

This file is the only worker entrypoint the supervisor may spawn. It is not a
plugin, not a generic runner, and accepts no module/script/command argument.

Spawned as: ``python -I -S -u <absolute-path-to-this-file>``.

``-I`` ignores inherited PYTHON* variables, user site, and unsafe path
injection. ``-S`` skips the ``site`` module so sitecustomize / usercustomize /
``.pth`` import hooks do not run. This file then inserts only the Host-owned
application root onto ``sys.path`` and imports the fixed worker module.
"""

from __future__ import annotations

import sys
from pathlib import Path

EXIT_CODE_ORIGIN_INVALID = 12


def _bootstrap_path() -> Path:
    return Path(__file__).resolve()


def _host_root() -> Path:
    bootstrap = _bootstrap_path()
    app_dir = bootstrap.parent
    root = app_dir.parent
    if bootstrap.name != "plugin_test_worker_bootstrap.py" or app_dir.name != "app":
        raise SystemExit(EXIT_CODE_ORIGIN_INVALID)
    if not (root / "app" / "plugin_test_worker.py").is_file():
        raise SystemExit(EXIT_CODE_ORIGIN_INVALID)
    if not (root / "app" / "plugin_worker_protocol.py").is_file():
        raise SystemExit(EXIT_CODE_ORIGIN_INVALID)
    return root


def _is_within(path: Path, root: Path) -> bool:
    """Component-aware ancestry. ``/repo-evil`` is not inside ``/repo``."""
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def _install_host_sys_path(root: Path) -> None:
    root_s = str(root.resolve())
    try:
        cwd_s = str(Path.cwd().resolve())
    except OSError:
        cwd_s = ""
    script_dir_s = str(_bootstrap_path().parent)
    filtered: list[str] = []
    seen = {root_s}
    for entry in sys.path:
        if entry in ("", "."):
            continue
        try:
            resolved = str(Path(entry).resolve())
        except OSError:
            filtered.append(entry)
            continue
        if resolved in {cwd_s, script_dir_s}:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        filtered.append(entry)
    sys.path[:] = [root_s, *filtered]


def _assert_host_origin(module: object, root: Path) -> None:
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise SystemExit(EXIT_CODE_ORIGIN_INVALID)
    if not _is_within(Path(raw), root):
        raise SystemExit(EXIT_CODE_ORIGIN_INVALID)


def main() -> int:
    root = _host_root()
    _install_host_sys_path(root)
    import app.plugin_test_worker as worker
    import app.plugin_worker_protocol as protocol

    _assert_host_origin(worker, root)
    _assert_host_origin(protocol, root)
    return int(worker.main())


if __name__ == "__main__":
    raise SystemExit(main())
