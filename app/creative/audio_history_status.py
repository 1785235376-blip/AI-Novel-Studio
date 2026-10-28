"""Strict observation of an uncaptured legacy audio asset.

This deliberately does not read or implement the published history format.
In particular, a head or restoration marker is not evidence of an empty chain.
"""
from fastapi import HTTPException


def uncaptured_audio_status(workspace, nid, scope, actor, aid, guard):
    guard()
    with workspace._asset_scope(nid, scope):
        row = workspace._row(nid, scope, aid, actor_id=actor)
        if row.get("kind") != "audio":
            raise FileNotFoundError(aid)
        if "_audio_history_head" in row or "_audio_history_restore_origin" in row:
            raise HTTPException(409, {"code": "AUDIO_HISTORY_FORMAT_NOT_INTEGRATED"})
        # Content is verified by the original owner. No missing or damaged
        # current binary may be represented as a usable history baseline.
        try:
            workspace.assets.content(aid, branch_id=scope.get("branch_id"), actor_id=actor,
                                     max_bytes=workspace.assets.MAX_BYTES, guard=guard)
        except (OSError, ValueError):
            guard()
            raise HTTPException(409, {"code": "AUDIO_HISTORY_CONTENT_UNAVAILABLE"}) from None
        guard()
        return {"asset_id": aid, "current_version": row["version"], "head": None,
                "coverage": "UNCAPTURED", "items": [], "next_cursor": None}
