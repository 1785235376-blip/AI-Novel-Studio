"""Bounded, read-only diagnostics for an existing File audio scope document.

The File document lifecycle is the original TaskCenter observation contract.
It does not bind ``audio_v2_mix_proposals`` rows to a project incarnation.
This snapshot therefore never claims project charge or admits a write. A caller
must supply its original authorization lease; a guard alone is not a lease.
"""
from __future__ import annotations

from ..creative.asset_usage_budget import UsageBudgetError, current_usage_budget, usage_read_budget
from ..creative.project_store import CreativeProjectStore
from ..repositories.file.mutation_coordinator import (
    ReadOnlyCoordinationUnavailable, existing_coordination_only, workspace_mutation,
)
from .audio_shared_document_measurement import MAX_DOCUMENT_BYTES, MAX_MIX_BYTES
from .store import ExperimentalStore, LIFECYCLE_MODES


class AudioScopeObservationUnavailable(ValueError):
    """A committed snapshot cannot safely be observed without initializing state."""

    def __init__(self):
        super().__init__('AUDIO_SCOPE_OBSERVATION_UNAVAILABLE')


def inspect_existing_audio_scope(project_store, nid, scope, guard):
    """Observe one File scope snapshot; all project charge remains unknown.

    ``guard`` is an original-owner reauthorization check. An eventual caller
    must retain an appropriate original authority/session lease across this
    operation; this function does not itself provide authorization. An owner
    lease does not authorize inspection of other incarnations' audio rows.
    Consequently the result contains no content-dependent observation and
    cannot be used for billing, compare-and-swap or write admission.
    No client paths, write callbacks, migration or quota admission are accepted.
    """
    if (type(project_store) is not CreativeProjectStore or not callable(guard)
            or type(project_store.store) is not ExperimentalStore
            or project_store.store.backend != 'file'):
        raise AudioScopeObservationUnavailable()
    store = project_store.store
    key = store.key(nid, scope)
    mode = scope['mode']
    lifecycle = next((name for name, pair in LIFECYCLE_MODES.items() if pair[0] == mode), None)
    if lifecycle is None:
        raise AudioScopeObservationUnavailable()
    prior_budget = current_usage_budget()
    with existing_coordination_only(), usage_read_budget() as budget, project_store.existing_owner_only():
        # Do not override an outer request's tighter cumulative limits. A new,
        # private observation permits one bounded canonical audio scope, read
        # twice for the exact original-owner snapshot comparison below.
        if prior_budget is None:
            budget.MAX_SCOPE_BYTES = MAX_DOCUMENT_BYTES
            budget.MAX_JSON_STRING_BYTES = 4 * ((MAX_MIX_BYTES + 2) // 3)
            budget.MAX_READ_BYTES = 2 * MAX_DOCUMENT_BYTES
        # Do not invoke caller authorization under the project lease: original
        # File retirement takes authorization before project. The caller must
        # already hold its original authority/session lease for this operation.
        guard()
        try:
            with workspace_mutation(store.root, f'experimental:{key}'):
                with project_store.owner_lease(nid) as incarnation:
                    raw, document = store._file_snapshot(nid, scope)
                    if raw is None or lifecycle not in document:
                        raise AudioScopeObservationUnavailable()
                    marker = document[lifecycle]
                    if marker['project_identity'] != incarnation:
                        raise AudioScopeObservationUnavailable()
                    # Compare the original owner's physical bytes twice under
                    # the same scope and project leases. No caller callback is
                    # executed while the project lease is held.
                    fresh, _ = store._file_snapshot(nid, scope)
                    if fresh is None or fresh != raw:
                        raise AudioScopeObservationUnavailable()
                    result = {'scope_snapshot': 'UNKNOWN',
                              'audio_row_binding': 'UNVERIFIED',
                              'project_charge_known': False,
                              'new_write_admission': 'CLOSED'}
        except (FileNotFoundError, ReadOnlyCoordinationUnavailable, UsageBudgetError,
                ValueError, KeyError, UnicodeError):
            raise AudioScopeObservationUnavailable() from None
        guard()
        return result
