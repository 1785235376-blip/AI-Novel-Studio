"""R3-I — the adoption route and its closed request DTO.

One POST. It is deliberately **not** a generic `{owner}` write surface: the target is a
storyboard document and a named shot, and nothing else. The request carries only what a user
is entitled to decide — which Prompt revision to adopt, and the target version they were
looking at. Every provenance field is decided by the server.
"""
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .prompt_adoption import PromptAdoptionService

MAX_ID = 240

#: A digest is a lowercase 64-character hex SHA-256 and nothing else. The previous bound was
#: merely "1 to 128 characters", which let malformed digests reach the business layer.
SHA256_HEX = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]

#: P3 (write-time source consistency between the Prompt read and the Creative commit) has NOT
#: been verified: the read and the commit are two different owner operations with no proven
#: unified lock order. The route is reachable, but a reachable write whose cross-owner
#: consistency is unproven would be exactly the unsafe surface the directive forbids, so the
#: write is FAIL-CLOSED here rather than merely reported as blocked. GET stays available.
PROMPT_ADOPTION_WRITE_ENABLED = False


class PromptAdoptionIn(BaseModel):
    """Closed: an unknown key is a 422, so a client cannot inject provenance."""
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)

    shot_id: Annotated[str, Field(min_length=1, max_length=MAX_ID, strict=True)]
    family_id: Annotated[str, Field(min_length=1, max_length=MAX_ID, strict=True)]
    asset_id: Annotated[str, Field(min_length=1, max_length=MAX_ID, strict=True)]
    revision: Annotated[int, Field(ge=1, le=100000, strict=True)]
    #: The digest the user was shown. Checked against the server's own read; never trusted.
    #: Lowercase 64-char hex SHA-256 only; a malformed digest is a 422, not a business error.
    expected_digest: SHA256_HEX
    #: The document version/digest the user was looking at — real CAS.
    expected_version: Annotated[int, Field(ge=1, strict=True)]
    expected_digest_target: SHA256_HEX
    #: Fixed request identity, so a lost response is replayable rather than duplicated.
    request_id: Annotated[str, Field(min_length=1, max_length=MAX_ID, strict=True)]


def create_prompt_adoption_router(adoption: PromptAdoptionService, invoke):
    router = APIRouter(tags=["Studio prompt adoption"])

    @router.post("/projects/{nid}/studio/documents/{document_id}/shots/{shot_id}/prompt-adoption")
    def adopt_prompt(nid: str, document_id: str, shot_id: str, body: PromptAdoptionIn,
                     x_session_token: str | None = Header(None),
                     x_branch_id: str | None = Header(None)):
        """Adopt one verified Prompt revision into one storyboard shot.

        Starts no job, calls no model, and does not approve the shot.

        FAIL-CLOSED: refuses with 503 until write-time source consistency is proven. The
        refusal is a real behaviour with a regression test, not a note in a report.
        """
        def refuse(actor, scope, guard):
            # Authorization has already run inside `invoke`, so an anonymous caller gets the
            # owner's own 401 and a missing project its own 404. Raising the closed-state
            # refusal BEFORE authorization would answer "feature exists but is off" to a
            # caller who is not entitled to learn anything about the project at all.
            raise HTTPException(503, {"code": "PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED",
                                      "message": "采用写入在跨 owner 来源一致性验证完成前关闭。"})

        if not PROMPT_ADOPTION_WRITE_ENABLED:
            return invoke(nid, x_session_token, x_branch_id, "domain.write", refuse)
        # The official write entry point is the ATOMIC path. The old `adopt()` left a window
        # between verifying the source and committing the document, so it must no longer be
        # reachable over HTTP now that adopt_atomic exists.
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: adoption.adopt_atomic(
                          nid, scope, actor, document_id, shot_id, body, guard))

    @router.get("/projects/{nid}/studio/documents/{document_id}/prompt-adoption")
    def read_adoptions(nid: str, document_id: str,
                       x_session_token: str | None = Header(None),
                       x_branch_id: str | None = Header(None)):
        """The pinned adoptions recorded on this document, with drift and readability."""
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: adoption.read(nid, scope, document_id, actor))

    return router
