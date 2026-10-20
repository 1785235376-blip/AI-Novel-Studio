"""Current-artifact Ink target INK_2_3_2_CURRENT_ARTIFACT_V1.

The contract resolves app.experimental.ink_export for this target; that module
re-exports the frozen DESCRIPTOR/compatibility/build surface implemented here.
"""
from .current_artifact import build, compatibility
from .descriptor import DESCRIPTOR

__all__ = ['DESCRIPTOR', 'build', 'compatibility']
