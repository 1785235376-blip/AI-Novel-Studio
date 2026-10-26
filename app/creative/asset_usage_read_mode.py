"""Explicit saved-usage mode over the original coordinator capability."""
from contextlib import contextmanager

from ..repositories.file.mutation_coordinator import (
    ReadOnlyCoordinationUnavailable, existing_coordination_only,
)


@contextmanager
def usage_coordination(request):
    # Enter before original admission, so a strict request cannot initialize a
    # lock before query validation. Values are validated after original auth.
    requested = any(key == 'strict_read_only' for key, _ in request.query_params.multi_items())
    with existing_coordination_only(requested):
        yield
