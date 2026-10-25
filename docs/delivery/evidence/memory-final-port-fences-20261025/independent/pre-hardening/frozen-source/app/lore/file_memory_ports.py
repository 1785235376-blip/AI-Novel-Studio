"""Private expected original File ports passed to memory's existing mutations.

This is transient composition data, not another owner, queue or authorization
callback. Final original ports validate it beneath their existing lifecycle lock.
"""
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, init=False)
class _FileMemoryPorts:
    runner: object
    binding: object
    root: object
    ports: tuple
    def __init__(self, runner, binding):
        object.__setattr__(self, 'runner', runner)
        object.__setattr__(self, 'binding', MappingProxyType(deepcopy(binding)))
        object.__setattr__(self, 'root', runner._bound_data)
        object.__setattr__(self, 'ports', runner._bound_ports)

    def check(self, target=None):
        from .memory_agent import MemoryAgentRunner
        from app.repositories.generation_repository import GenerationProjectIdentityError
        if target is not None and not any(target is port for port in self.ports):
            raise GenerationProjectIdentityError('MEMORY_BOUND_FILE_STORE_MISMATCH')
        # Call the original validation method, not an injected facade callback.
        MemoryAgentRunner._bound_check(self.runner, self.binding)

    @contextmanager
    def guard(self, target, project_id=None):
        from app.file_project_lifecycle import project_operation
        self.check(target)
        nid = self.binding['project_id']
        if project_id is not None and project_id != nid:
            raise ValueError('MEMORY_BOUND_WRITE_IDENTITY_MISMATCH')
        with project_operation(self.root, nid, expected_root=self.root,
                               expected_incarnation=self.binding['project_incarnation']):
            self.check(target)
            yield


def require_memory_ports(value, target):
    if type(value) is not _FileMemoryPorts:
        raise ValueError('MEMORY_BOUND_FILE_PORTS_REQUIRED')
    value.check(target)
    return value


def memory_file_port(method):
    """Final optional fence on original File Lore service/repository ports."""
    @wraps(method)
    def call(owner, *args, **kwargs):
        expected = kwargs.get('_file_memory')
        if expected is None:
            return method(owner, *args, **kwargs)
        expected = require_memory_ports(expected, owner)
        nid = args[0].get('novel_id') if args and isinstance(args[0], dict) else None
        with expected.guard(owner, nid):
            return method(owner, *args, **kwargs)
    return call
