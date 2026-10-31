"""Coordinate participating File project operations with project deletion.

The lock lives at the data root, never inside the removable project. It is
shared by repository instances and processes and reentrant for nested calls.
This is not a filesystem sandbox: direct-path writers must opt in as well.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from pathlib import Path, PureWindowsPath


@contextmanager
def project_operation(data: Path, novel_id: str, *, require_exists=True, expected_incarnation=None, expected_root=None):
    # Public project identifiers are one path component. Validate before even
    # deriving a lock key or checking existence outside the novels directory.
    # Generic dot directories remain valid legacy projects. Drive-qualified
    # Windows components can alias a parent/project even when not absolute.
    if (not isinstance(novel_id, str) or not novel_id or novel_id in {".", ".."}
            or any(character in novel_id for character in ("/", "\\", "\x00"))
            or PureWindowsPath(novel_id).drive):
        raise FileNotFoundError(novel_id)
    # Import lazily: app.repositories imports FileRepository during startup.
    from .repositories.file.mutation_coordinator import workspace_mutation

    if expected_root is not None and Path(data).resolve() != Path(expected_root).resolve():
        raise ValueError("GENERATION_REVIEW_FILE_PORT_MISMATCH")
    root = data / "novels" / novel_id
    with workspace_mutation(data, f"project-lifecycle:{root.resolve()}"):
        if require_exists and not root.is_dir():
            raise FileNotFoundError(novel_id)
        if expected_incarnation is not None:
            from .creative.project_store import _marker_file_identity, _read_marker
            marker = _read_marker(root / "creative_project_v2.json")
            if _marker_file_identity(marker) != expected_incarnation:
                raise ValueError("GENERATION_REVIEW_PROJECT_OWNER_CHANGED")
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
            from .services.ordinary_writer_ports import current_writer_ports, require_writer_ports, suspend_writer_ports
            writer = kwargs.pop("_file_writer", None)
            current_writer = current_writer_ports()
            from .services.ordinary_writer_ports import _FileReviewPorts, _FileWriterPorts
            source_port = method.__name__ in {"get", "_paths", "chapter", "get_context_sources", "get_outline", "get_data_set"}
            review_port = type(current_writer) is _FileReviewPorts and method.__name__ == "save_chapter"
            if writer is None and (source_port or review_port):
                writer = current_writer
            if writer is not None:
                writer = require_writer_ports(writer, repository)
                if chapter and type(writer) is _FileWriterPorts and identifier != writer.binding['chapter_id']:
                    raise ValueError("GENERATION_WRITER_SOURCE_CHANGED")
                incarnation = kwargs.pop("_project_incarnation", None)
                expected_root = kwargs.pop("_project_root", None)
                if (kwargs.get("_file_memory") is not None
                        or (incarnation is not None and incarnation != writer.binding['project_incarnation'])
                        or (expected_root is not None and Path(expected_root).resolve() != writer.root)):
                    raise ValueError("GENERATION_WRITER_FILE_PORT_MISMATCH")
                # Reenter the original method only after validating the actual
                # nested owner; the scoped expectation covers its own callees.
                with writer.guard(repository, novel_id):
                    return method(repository, *args, **kwargs)
            memory = kwargs.pop("_file_memory", None)
            if memory is not None:
                from .lore.file_memory_ports import require_memory_ports
                memory = require_memory_ports(memory, repository)
                if novel_id != memory.binding['project_id']:
                    raise ValueError("MEMORY_BOUND_WRITE_IDENTITY_MISMATCH")
                kwargs['_project_incarnation'] = memory.binding['project_incarnation']
                kwargs['_project_root'] = memory.root
            incarnation = kwargs.pop("_project_incarnation", None)
            expected_root = kwargs.pop("_project_root", None)
            if expected_root is not None and Path(backend.novels).resolve() != Path(expected_root).resolve()/"novels":
                raise ValueError("GENERATION_REVIEW_FILE_PORT_MISMATCH")
            with project_operation(backend.data, novel_id, expected_incarnation=incarnation, expected_root=expected_root):
                # Independent lifecycle mutations do not inherit a writer
                # read expectation into their own nested source calls.
                with suspend_writer_ports():
                    return method(repository, *args, **kwargs)
        return guarded
    return decorate
