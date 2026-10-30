"""Restricted local, read-only shared-index capacity diagnosis.

This does not calculate project usage, authenticate index contents, reserve
space, or provide an HTTP endpoint. Collaboration and PostgreSQL remain
unsupported because a project administrator is not an administrator of the
shared index across all workspaces.
"""
from __future__ import annotations

from ..config import settings
from ..repositories.file.mutation_coordinator import existing_coordination_only
from ..services.asset_query_index import FileAssetQueryIndex
from .project_quota_management_authority import project_management_lease
from .workspace import IndependentWorkspaceService


class AudioIndexCapacityDiagnosticUnavailable(ValueError):
    def __init__(self):
        super().__init__('AUDIO_INDEX_CAPACITY_DIAGNOSTIC_UNAVAILABLE')


def inspect_local_shared_index_capacity(workspace, nid, token=None):
    """Observe coarse name classes without proving ownership or admission.

    Caller is the original local project administrator. The original existing
    locks and identity are mandatory; no missing facility is provisioned. The
    result contains neither file names, counts, sizes, project identifiers nor
    content. It must not be exposed as a project quota or admission decision.
    """
    if (type(workspace) is not IndependentWorkspaceService
            or workspace.store.backend != 'file'
            or settings.enable_collaboration_runtime):
        raise AudioIndexCapacityDiagnosticUnavailable()
    with existing_coordination_only(), workspace.store.existing_owner_only():
        with project_management_lease(workspace, nid, token):
            observed = FileAssetQueryIndex(workspace.assets.root)._observe_unverified_capacity_names()
    # Names are sampled; uncooperative concurrent writers can change directory
    # entries even while the original cooperating-owner lock is held. Never
    # present these categories as a complete inventory or a storage snapshot.
    return {**observed, 'complete_inventory': False,
            'ownership': 'UNKNOWN', 'project_charge_known': False,
            'capacity_exempt': False, 'write_admission_proven': False,
            'scope': 'SHARED_INDEX_ONLY'}
