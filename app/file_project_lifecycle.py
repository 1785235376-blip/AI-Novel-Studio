"""Coordinate participating File project operations with project deletion.

The lock lives at the data root, never inside the removable project. It is
shared by repository instances and processes and reentrant for nested calls.
This is not a filesystem sandbox: direct-path writers must opt in as well.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from pathlib import Path


@contextmanager
def project_operation(data: Path, novel_id: str, *, require_exists=True):
    # Public project identifiers are one path component. Validate before even
    # deriving a lock key or checking existence outside the novels directory.
    # Generic dot directories remain valid legacy projects; only traversal
    # components and actual separators/control terminators are rejected.
    if (not isinstance(novel_id, str) or not novel_id or novel_id in {".", ".."}
            or any(character in novel_id for character in ("/", "\\", "\x00"))):
        raise FileNotFoundError(novel_id)
    # Import lazily: app.repositories imports FileRepository during startup.
    from .repositories.file.mutation_coordinator import workspace_mutation

    root = data / "novels" / novel_id
    with workspace_mutation(data, f"project-lifecycle:{root.resolve()}"):
        if require_exists and not root.is_dir():
            raise FileNotFoundError(novel_id)
        yield


def guard_project(id_argument, *, chapter=False):
    """Hold the lifecycle guard for a method whose first argument is an ID."""
    def decorate(method):
        @wraps(method)
        def guarded(repository, *args, **kwargs):
            if not args and id_argument not in kwargs:
                return method(repository, *args, **kwargs)
            identifier = args[0] if args else kwargs[id_argument]
            novel_id = identifier.rsplit(":", 1)[0] if chapter else identifier
            backend = getattr(repository, "backend", repository)
            with project_operation(backend.data, novel_id):
                return method(repository, *args, **kwargs)
        return guarded
    return decorate
