"""Advisory budget and bounded plans over the original portable cache owner.

No paths, filesystem scan, automatic eviction, export admission or new cache
registry. The caller supplies only its already verified reproducible candidates.
"""
from pydantic import Field

from .planning import StrictModel

MAX_SAFE_BYTES = 2**53 - 1
MAX_PLAN_RECORDS = 100  # Original CleanupIn request limit.


class CachePolicyInput(StrictModel):
    expected_version: int = Field(ge=0, strict=True)
    limit_bytes: int | None = Field(ge=0, le=MAX_SAFE_BYTES, strict=True)


class CachePolicyView(StrictModel):
    version: int = Field(ge=0, strict=True)
    limit_bytes: int | None = Field(ge=0, le=MAX_SAFE_BYTES, strict=True)


def policy_view(row=None):
    value = {'version': row['version'], 'limit_bytes': row['limit_bytes']} if row else {'version': 0, 'limit_bytes': None}
    return CachePolicyView.model_validate(value).model_dump()


def cache_budget(policy, candidates, unmeasured_records):
    """Oldest verified candidates first, with no partial/unknown-as-zero claim."""
    known = sum(row['bytes'] for row in candidates)
    measured = not unmeasured_records
    limit = policy['limit_bytes']
    excess = max(0, known - limit) if measured and limit is not None else None
    selected, reclaimed = [], 0
    if excess:
        for row in candidates:
            if reclaimed >= excess or len(selected) >= MAX_PLAN_RECORDS:
                break
            selected.append(row['id']); reclaimed += row['bytes']
    return {
        'policy': policy,
        'scope': 'CURRENT_AUTHOR_SCOPE_REPRODUCIBLE_PORTABLE_EXPORTS_ONLY',
        'advisory_only': True, 'automatic_cleanup': False,
        'measurement': {'state': 'MEASURED' if measured else 'UNKNOWN', 'bytes': known if measured else None,
                        'verified_reproducible_bytes': known, 'unmeasured_records': unmeasured_records},
        'state': 'UNCONFIGURED' if limit is None else 'UNKNOWN' if not measured else 'OVER_BUDGET' if excess else 'WITHIN_BUDGET',
        'excess_bytes': excess,
        'plan': {'record_ids': selected, 'reclaim_bytes': reclaimed,
                 'remaining_excess_bytes': max(0, excess - reclaimed) if excess is not None else None,
                 'complete': excess is not None and reclaimed >= excess,
                 'reason': 'POLICY_NOT_CONFIGURED' if limit is None else 'OCCUPANCY_UNKNOWN' if not measured
                           else 'EXCESS_VERIFIED_CACHE' if excess else 'WITHIN_BUDGET'},
    }
