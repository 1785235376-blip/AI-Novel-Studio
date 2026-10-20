"""Ren'Py 8.5.4 runnable-project target internals (B07 line B).

Pure conversion helpers consumed by app/experimental/interactive_renpy_export.py.
They read only the authorized story snapshot, never open arbitrary files, never
write outside the returned in-memory payload, never bundle or launch the engine
and never execute target code.
"""
from .project import (
    ADAPTER_REVISION,
    FORMAT_VERSION,
    NO_CHOICE_MESSAGE,
    PROJECT_SCHEMA,
    RENPY_MINIMUM_VERSION,
    SCREENS_RPY,
    STEP_CAP_MESSAGE,
    STORY_FILENAME,
    TARGET_ID,
    WITNESS_PATH,
    comment_text,
    encode_json,
    projection,
    render_options,
    render_readme,
    render_script,
)
from .witness import WITNESS_SCHEMA, build_acceptance_witness

__all__ = [
    'ADAPTER_REVISION', 'FORMAT_VERSION', 'NO_CHOICE_MESSAGE', 'PROJECT_SCHEMA', 'RENPY_MINIMUM_VERSION',
    'SCREENS_RPY', 'STEP_CAP_MESSAGE', 'STORY_FILENAME', 'TARGET_ID', 'WITNESS_PATH', 'WITNESS_SCHEMA',
    'build_acceptance_witness', 'comment_text', 'encode_json', 'projection', 'render_options',
    'render_readme', 'render_script',
]
