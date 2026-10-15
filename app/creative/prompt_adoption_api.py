"""R3-I — the adoption route and its closed request DTO.

One POST. It is deliberately **not** a generic `{owner}` write surface: the target is a
storyboard document and a named shot, and nothing else. The request carries only what a user
is entitled to decide — which Prompt revision to adopt, and the target version they were
looking at. Every provenance field is decided by the server.
"""
from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from .prompt_adoption import PromptAdoptionService

MAX_ID = 240


class PromptAdoptionIn(BaseModel):
    """Closed: an unknown key is a 422, so a client cannot inject provenance."""
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)

    shot_id: Annotated[str, Field(min_length=1, max_length=MAX_ID, strict=True)]
    family_id: Annotated[str, Field(min_length=1, max_length=MAX_ID, strict=True)]
    asset_id: Annotated[str, Field(min_length=1, max_length=MAX_ID, strict=True)]
    revision: Annotated[int, Field(ge=1, le=100000, strict=True)]
    #: The digest the user was shown. Checked against the server's own read; never trusted.
    expected_digest: Annotated[str, Field(min_length=1, max_length=128, strict=True)]
    #: The document version/digest the user was looking at — real CAS.
    expected_version: Annotated[int, Field(ge=1, strict=True)]
    expected_digest_target: Annotated[str, Field(min_length=1, max_length=128, strict=True)]
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
        """
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: adoption.adopt(
                          nid, scope, actor, document_id, shot_id, body, guard))

    @router.get("/projects/{nid}/studio/documents/{document_id}/prompt-adoption")
    def read_adoptions(nid: str, document_id: str,
                       x_session_token: str | None = Header(None),
                       x_branch_id: str | None = Header(None)):
        """The pinned adoptions recorded on this document, with drift and readability."""
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: adoption.read(nid, scope, document_id, actor))

    return router
