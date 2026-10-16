"""Use the existing cross-process File coordinator for shared finding documents."""
from functools import wraps
from .mutation_coordinator import workspace_mutation


def narrative_write(fn):
    @wraps(fn)
    def locked(self, project, *args, **kwargs):
        with workspace_mutation(self.root, 'narrative:' + project):
            return fn(self, project, *args, **kwargs)
    return locked


def continuity_write(fn):
    @wraps(fn)
    def locked(self, *args, **kwargs):
        with workspace_mutation(self.root, 'continuity'):
            return fn(self, *args, **kwargs)
    return locked
