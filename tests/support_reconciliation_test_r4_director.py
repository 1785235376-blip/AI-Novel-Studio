"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

def screenplay(rig):
    row = rig.screenplays.create(rig.nid)
    row = rig.screenplays.approve(rig.nid, row['id'], row['edit_version'])
    return rig.screenplays.plan_shots(rig.nid, row['id'], row['edit_version'])
