"""Human-reviewed IMAGE adoption contracts; no executable persisted authority."""
from typing import Literal, Annotated
from pydantic import Field, model_validator
from .director_binding import _Frozen, Digest, Identifier
from .director_image_binding import ImageTarget

class ImageAdoptionInput(_Frozen):
    contract: Literal['DIRECTOR_IMAGE_ADOPTION_INPUT_V1']
    request_id: Identifier
    expected_version: int = Field(ge=1, strict=True)
    target: ImageTarget
    reviewed_terminal_digest: Digest
    reviewed_accounting_digest: Digest
    selected_suggestions: list[Annotated[int, Field(strict=True)]] = Field(min_length=1, max_length=8)
    note: str = Field(min_length=1, max_length=8000, strict=True)
    human_review_confirmed: bool = Field(strict=True)

    @model_validator(mode='after')
    def explicit_review(self):
        if self.human_review_confirmed is not True:
            raise ValueError('DIRECTOR_IMAGE_HUMAN_REVIEW_REQUIRED')
        return self


def terminal_for(coordinator, row, binding):
    from .director_image_terminal import FIELD, validate
    saved = coordinator.manager.persistence.get(row['job_id'])
    evidence = validate(saved, saved.get(FIELD))
    if (saved['expected_request_digest'] != row['request_digest']
            or saved['director_image_binding'] != binding.model_dump()
            or evidence['accounting']['id'] != row['reservation_id']):
        raise ValueError('DIRECTOR_IMAGE_TERMINAL_CHANGED')
    return saved, evidence
