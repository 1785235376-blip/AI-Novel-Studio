"""Reusable U16 parameters, also validated by the original B01 template catalog.

No source IDs, model selections, credentials, execution grants or budget changes
can be carried by a preset. Current user selections supply those separately.
"""
from typing import Literal
from pydantic import model_validator
from .planning import StrictModel


class BatchPreset(StrictModel):
    proof: bool = True
    export_format: Literal['txt', 'markdown', 'docx', 'epub', 'pdf'] | None = None
    skip_satisfied: bool = True

    @model_validator(mode='after')
    def useful(self):
        if not self.proof and self.export_format is None:
            raise ValueError('BATCH_PRESET_OPERATION_REQUIRED')
        return self
