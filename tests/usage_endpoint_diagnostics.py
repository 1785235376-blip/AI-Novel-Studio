"""Opt-in test-only exception-chain observer; never part of application routes.

No paths, identifiers, request bodies, tokens or arbitrary exception messages
are recorded. Observations do not replace uninstrumented acceptance.
"""
from functools import wraps
from pathlib import Path
import time
import traceback

# Static application codes relevant to this diagnosis, never arbitrary text.
_CODES = frozenset({
    'STUDIO_ASSET_USAGE_UNAVAILABLE', 'STUDIO_USAGE_RESOURCE_UNAVAILABLE',
    'STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE', 'STUDIO_USAGE_RESTART_REQUIRED',
    'STUDIO_USAGE_SOURCE_UNAVAILABLE', 'STUDIO_USAGE_AUTHORITY_CHANGED',
    'STUDIO_USAGE_OWNER_IDENTITY_INVALID', 'STUDIO_USAGE_QUERY_INVALID',
})


def _code(exc):
    value = str(exc)
    if value in _CODES:
        return value
    detail = getattr(exc, 'detail', None)
    value = detail.get('code') if isinstance(detail, dict) else None
    return value if isinstance(value, str) and value in _CODES else None


def observe_endpoint(original, emit, budget_getter, clock=time.monotonic):
    @wraps(original)
    def observed(*args, **kwargs):
        try:
            started = clock()
        except BaseException:
            started = None
        outcome = {'event': 'asset_usage_endpoint', 'errors': []}
        try:
            return original(*args, **kwargs)
        except BaseException as error:
            try:
                seen = set()
                current = error
                while current is not None and id(current) not in seen and len(seen) < 12:
                    seen.add(id(current))
                    outcome['errors'].append({'type': type(current).__name__, 'code': _code(current),
                        'status': getattr(current, 'status_code', None),
                        'frames': [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}
                                   for f in traceback.extract_tb(current.__traceback__)[-32:]]})
                    current = current.__cause__ or current.__context__
            except BaseException:
                outcome['observation_failed'] = True
            raise
        finally:
            # Logging failure must neither hide nor replace the original outcome.
            try:
                budget = budget_getter()
                now = clock()
                outcome.update(elapsed=None if started is None else now-started,
                    budget_elapsed=None if budget is None else budget.MAX_SECONDS+now-budget.deadline,
                    budget=None if budget is None else budget.snapshot())
                emit(outcome)
            except BaseException:
                pass
    return observed


def install_endpoint_observers(router, wrap):
    """Support both flat FastAPI routes and lazy included routers, once each."""
    seen_routers, seen_routes = set(), set()
    def visit(owner):
        if id(owner) in seen_routers:
            return 0
        seen_routers.add(id(owner))
        count = 0
        for route in owner.routes:
            child = getattr(route, 'original_router', None)
            if child is not None:
                count += visit(child)
            dependant = getattr(route, 'dependant', None)
            if (dependant is not None and id(route) not in seen_routes
                    and getattr(dependant.call, '__name__', '') == 'saved_asset_usages'):
                seen_routes.add(id(route))
                wrapped = wrap(dependant.call)
                dependant.call = wrapped
                route.endpoint = wrapped
                count += 1
        return count
    return visit(router)
