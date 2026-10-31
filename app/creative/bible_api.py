"""Closed route for the read-only Character/Scene Bible projection.

One GET. Authority is resolved on every call through the shared studio invoker.
It starts no model, opens no job, mutates no asset, promotes no canon and creates
no character, location or profile record.
"""
from fastapi import APIRouter, Header


def create_bible_router(bible, invoke):
    router = APIRouter(tags=["Studio character and scene bible"])

    @router.get("/projects/{nid}/studio/bible")
    def bible_projection(nid: str, x_session_token: str | None = Header(None),
                         x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: bible.projection(nid, scope))

    return router
