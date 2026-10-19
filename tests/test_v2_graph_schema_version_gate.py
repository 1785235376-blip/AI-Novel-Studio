"""The `schema_version` gate on `validate_output_ports`.

Audit behind this file. `validate_output_ports(..., schema_version=None)` looked like
an unguarded default, so it was traced rather than assumed:

* `definition_for(id, schema_version=None)` returns exactly the same definition as
  `schema_version=1` — only 5 and 3 change anything — so `None` is a *de facto* v1.
* `parse_graph` establishes the real version set: 6→GraphLocalSubgraphInput,
  5→GraphVideoInput, 4→GraphImageInput,
  3→GraphMediaInput, 2→GraphModelInput, otherwise the frozen v1 `GraphInput`.
  Schema6 explicitly admits only pure local output kinds; schemas1–5 remain frozen.
* The callers that omit the version (`ai_execution`, `text_assets`) are the legacy v1
  text paths, and `tests/test_v2_ai_execution_contracts.py` pins that behaviour.

So `None` is a **deliberate compatibility default**, and it is fail-closed: every
schema-specific port type refuses to validate under a version it does not belong to.
What was genuinely missing is that an *illegal* version never raised — `0`, `7`, `-1`,
`"4"`, `2.0` or `True` fell through every `not in {3,4,5}` style gate and were silently
validated as v1. These tests pin the compatibility behaviour (old rows stay readable,
no forced upgrade) and the new refusal.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.creative.graph_models import (
    DEFINITIONS,
    LEGACY_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    normalise_schema_version,
    validate_output_ports,
)

LEGACY_DRAFT = {"draft": {"text": "Proposed", "origin": "MODEL_PROPOSAL"}}
ILLEGAL_VERSIONS = [0, 7, -1, 99, 1.0, 2.0, "4", "1", True, False, [1], {"version": 4}, object()]


def outcome(call):
    try:
        return ("OK", call())
    except Exception as exc:  # noqa: BLE001 - the classification is the assertion
        return (type(exc).__name__, str(exc))


# --- the version set itself -------------------------------------------------

def test_supported_versions_match_parse_graph():
    assert SUPPORTED_SCHEMA_VERSIONS == {1, 2, 3, 4, 5, 6}
    assert LEGACY_SCHEMA_VERSION == 1


# --- schema_version present -------------------------------------------------

@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_an_explicit_supported_version_is_accepted(version):
    assert validate_output_ports("text_generate", LEGACY_DRAFT, schema_version=version) == LEGACY_DRAFT


def test_schema6_is_explicitly_pure_and_does_not_inherit_model_or_media_ports():
    assert normalise_schema_version(6) == 6
    assert validate_output_ports("text_reference", {"text": "Author"}, schema_version=6) == {"text": "Author"}
    assert validate_output_ports("local_subgraph", {"draft": {"text": "Author", "origin": "MANUAL"}}, schema_version=6) == {"draft": {"text": "Author", "origin": "MANUAL"}}
    for kind, payload in [("text_generate", LEGACY_DRAFT), ("asset_reference", {"asset": {}}), ("video_generate", {"candidate": {}})]:
        with pytest.raises(ValueError, match="LOCAL_SUBGRAPH_SCHEMA_REQUIRED"):
            validate_output_ports(kind, payload, schema_version=6)
    with pytest.raises(ValueError, match="LOCAL_SUBGRAPH_SCHEMA_REQUIRED"):
        validate_output_ports("local_subgraph", {"draft": {"text": "Author", "origin": "MANUAL"}}, schema_version=1)


def test_version_three_really_exposes_the_reviewed_draft():
    """The v3-only port proves the version is doing real work, not decoration."""
    assert validate_output_ports(
        "human_review", {"reviewed_draft": LEGACY_DRAFT["draft"]}, schema_version=3
    ) == {"reviewed_draft": LEGACY_DRAFT["draft"]}


# --- schema_version missing (legacy compatibility) --------------------------

def test_missing_version_is_legacy_v1():
    assert normalise_schema_version(None) == LEGACY_SCHEMA_VERSION
    assert validate_output_ports("text_generate", LEGACY_DRAFT) == LEGACY_DRAFT


@pytest.mark.parametrize("definition_id", sorted(DEFINITIONS))
def test_missing_version_behaves_exactly_like_v1(definition_id):
    """No third mode: omitting the version may not be looser or stricter than v1."""
    for payload in ({}, {"draft": {"text": "x", "origin": "MODEL_PROPOSAL"}},
                    {"reviewed_draft": {"text": "x", "origin": "MODEL_PROPOSAL"}}):
        assert (outcome(lambda: validate_output_ports(definition_id, payload)) ==
                outcome(lambda: validate_output_ports(definition_id, payload, schema_version=1))), definition_id


def test_missing_version_is_not_silently_a_newer_schema():
    """Omitting the version must stay fail-closed, never act like v3.

    The legacy `human_review` definition has no outputs at all, so the structural
    check refuses the v3-only port before any pydantic model is reached.
    """
    with pytest.raises(ValueError, match="CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID"):
        validate_output_ports("human_review", {"reviewed_draft": LEGACY_DRAFT["draft"]})


def test_legacy_rows_are_still_readable_without_being_upgraded():
    """The point of the default: an old receipt keeps validating as it always did."""
    old_receipt = {"draft": {"text": "旧稿", "origin": "MODEL_PROPOSAL"}}
    assert validate_output_ports("text_generate", old_receipt) == old_receipt


# --- illegal versions -------------------------------------------------------

@pytest.mark.parametrize("illegal", ILLEGAL_VERSIONS, ids=lambda value: 'opaque-object' if type(value) is object else repr(value))
def test_illegal_version_is_refused(illegal):
    with pytest.raises(ValueError, match="CREATIVE_GRAPH_SCHEMA_VERSION_INVALID"):
        normalise_schema_version(illegal)
    with pytest.raises(ValueError, match="CREATIVE_GRAPH_SCHEMA_VERSION_INVALID"):
        validate_output_ports("text_generate", LEGACY_DRAFT, schema_version=illegal)


def test_boolean_is_refused_even_though_true_equals_one():
    """`True == 1` in Python, so the check must be exact on type."""
    assert True == 1
    with pytest.raises(ValueError, match="CREATIVE_GRAPH_SCHEMA_VERSION_INVALID"):
        normalise_schema_version(True)


# --- schema-specific types stay gated ---------------------------------------

@pytest.mark.parametrize("version", [None, 1, 2, 3])
def test_planning_ports_refuse_under_versions_that_do_not_own_them(version):
    with pytest.raises(ValueError, match="CREATIVE_GRAPH_PLANNING_SCHEMA_REQUIRED"):
        validate_output_ports("director_plan", {"direction": {}}, schema_version=version)


@pytest.mark.parametrize("version", [None, 1, 2, 3, 5])
def test_image_prompt_refuses_outside_schema_four(version):
    with pytest.raises(ValueError, match="CREATIVE_GRAPH_IMAGE_PROMPT_INVALID"):
        validate_output_ports("image_prompt", {"prompt": {}}, schema_version=version)


@pytest.mark.parametrize("version", [None, 1, 2, 3, 4])
def test_storyboard_shot_refuses_outside_schema_five(version):
    with pytest.raises(ValueError, match="CREATIVE_GRAPH_VIDEO_SCHEMA_REQUIRED"):
        validate_output_ports("storyboard_shot", {"shot": {}}, schema_version=version)
