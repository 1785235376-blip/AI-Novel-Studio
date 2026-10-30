"""Closed, read-only diagnosis for an unbound File audio scope.

The File document lifecycle is the original TaskCenter observation contract.
It does not bind ``audio_v2_mix_proposals`` rows to a project incarnation.
This snapshot therefore never claims project charge or admits a write. A caller
must supply its original authorization lease; a guard alone is not a lease.
"""
from __future__ import annotations

from ..creative.project_store import CreativeProjectStore
from ..repositories.file.mutation_coordinator import (
    ReadOnlyCoordinationUnavailable, existing_coordination_only, workspace_mutation,
)
from .store import ExperimentalStore, LIFECYCLE_MODES


class AudioScopeObservationUnavailable(ValueError):
    """A committed snapshot cannot safely be observed without initializing state."""

    def __init__(self):
        super().__init__('AUDIO_SCOPE_OBSERVATION_UNAVAILABLE')


def inspect_existing_audio_scope(project_store, nid, scope, guard):
    """Return UNKNOWN without observing unbound shared document contents.

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
    with existing_coordination_only(), project_store.existing_owner_only():
        # Do not invoke caller authorization under the project lease: original
        # File retirement takes authorization before project. The caller must
        # already hold its original authority/session lease for this operation.
        guard()
        try:
            with workspace_mutation(store.root, f'experimental:{key}'):
                with project_store.owner_lease(nid):
                    # Even parsing or sizing the shared document can reveal
                    # content from another project incarnation. A valid lease
                    # establishes neither document validity nor row ownership.
                    result = {'scope_snapshot': 'UNKNOWN',
                              'audio_row_binding': 'UNVERIFIED',
                              'project_charge_known': False,
                              'new_write_admission': 'CLOSED'}
        except (FileNotFoundError, ReadOnlyCoordinationUnavailable, ValueError, KeyError, UnicodeError):
            raise AudioScopeObservationUnavailable() from None
        guard()
        return result
