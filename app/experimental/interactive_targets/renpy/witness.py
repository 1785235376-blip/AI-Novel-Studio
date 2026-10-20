"""Acceptance witness for the generated Ren'Py 8.5.4 project target.

The witness is derived from the story authority only: the discovered endings come
from the approved bounded analysis, and every expected state is computed by the
authority play() replay for each prefix of a discovered ending path. It records
the current node, variables, enabled/menu choices and playback status so the
target environment (or a human) can check the running project step by step.

The witness is bounded: one path per discovered ending, a bounded number of
states and bytes, and a truncated flag when those limits are reached. It is not
a proof over every possible path and it is not target-runtime acceptance.
"""
from __future__ import annotations

from ...interactive_story import play
from .project import (
    ADAPTER_REVISION,
    FORMAT_VERSION,
    PROJECT_SCHEMA,
    RENPY_MINIMUM_VERSION,
    TARGET_ID,
    WITNESS_PATH,
    encode_json,
)

WITNESS_SCHEMA = "poemseed-renpy-acceptance-witness/1"
WITNESS_STATE_LIMIT = 2048
WITNESS_BYTE_LIMIT = 4 * 1024 * 1024

EXPECTED_RUNTIME_BEHAVIOR = [
    "A new game (or replay) starts at the approved entry node with ans_steps = 0 and every approved variable at its initial value.",
    "Each choice increments the step counter, applies its approved bool/int assignments and jumps to the approved target node.",
    "Only choices whose approved typed condition is true at that state are enabled; disabled choices are not selectable.",
    "An ending node displays the approved ending text and returns to the Ren'Py main menu.",
    "The step-cap guard stops playback at the approved max_steps instead of exceeding it.",
    "Target runtime execution is NOT claimed by this witness unless TARGET_RUNTIME_EXECUTED is PASS.",
]


def _state(project, path):
    """One expected state from the authority bounded replay for a choice prefix."""
    result = play(project["spec"], list(path))
    node = result["node"]
    node_id = node["node_id"]
    return {
        "index": len(path),
        "node_id": node_id,
        "node_label": project["labels"][node_id],
        "node_title": node["title"],
        "steps": result["steps"],
        "max_steps": result["max_steps"],
        "status": result["status"],
        "variables": result["variables"],
        "enabled_choice_ids": [choice["id"] for choice in result["choices"] if choice["enabled"]],
        "choices": [{"id": choice["id"], "label": choice["label"], "enabled": choice["enabled"]} for choice in result["choices"]],
    }


def build_acceptance_witness(project, analysis, meta, media_references, runtime_evidence, script_path):
    """Build the deterministic acceptance/witness.json document for one export."""
    spec = project["spec"]
    witnesses = []
    state_count = 0
    byte_count = 2
    truncated = False
    for ending in analysis.get("endings") or []:
        choices = list(ending.get("choices") or [])
        if state_count + len(choices) + 1 > WITNESS_STATE_LIMIT:
            truncated = True
            break
        states = [_state(project, choices[:index]) for index in range(len(choices) + 1)]
        witness = {"ending_node_id": ending["node_id"], "ending": ending.get("ending", ""),
                   "choices": choices, "states": states}
        size = len(encode_json(witness))
        if byte_count + size > WITNESS_BYTE_LIMIT:
            truncated = True
            break
        witnesses.append(witness)
        state_count += len(states)
        byte_count += size
    variables = [{"name": variable["name"], "type": variable["type"], "initial": variable["initial"],
                  "generated_name": project["names"][variable["name"]]} for variable in spec["variables"]]
    media = [{
        "asset_id": str(item.get("asset_id")),
        "kind": str(item.get("kind")),
        "version": item.get("version"),
        "missing": bool(item.get("missing")),
        "packaged": False,
    } for item in media_references]
    evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    return {
        "schema": WITNESS_SCHEMA,
        "target_id": TARGET_ID,
        "target_format_version": FORMAT_VERSION,
        "adapter_revision": ADAPTER_REVISION,
        "project": {
            "schema": PROJECT_SCHEMA,
            "script": script_path,
            "options": "game/options.rpy",
            "screens": "game/screens.rpy",
            "witness": WITNESS_PATH,
            "engine_bundled": False,
            "engine_minimum_version": RENPY_MINIMUM_VERSION,
        },
        "story": {
            "story_id": meta.get("story_id"),
            "revision": meta.get("revision"),
            "title": meta.get("title"),
            "spec_digest": meta.get("spec_digest"),
            "source_digest": meta.get("source_digest"),
            "review_receipt": meta.get("review_receipt"),
            "entry_node_id": spec["entry_node_id"],
            "entry_node_label": project["labels"][spec["entry_node_id"]],
            "max_steps": spec["max_steps"],
            "node_count": len(spec["nodes"]),
            "ending_count": len(analysis.get("endings") or []),
            "variables": variables,
        },
        "how_to_use": [
            "Extract the exported ZIP into a new empty directory and open the extracted project folder with the Ren'Py " + RENPY_MINIMUM_VERSION + " launcher (see README.txt).",
            "Start the game, then follow one witness choices path. After each choice compare the running node, variables, enabled choices and ending display with the recorded states.",
            "States are indexed by the number of choices already taken; index 0 is the state right after the first node is entered.",
            "The main menu itself is not story state: states assume the game was started (Start pressed) and describe the bounded story playback.",
            "Save/load is native Ren'Py behavior and is not part of this witness state sequence.",
        ],
        "coverage": "ONE_WITNESS_PER_DISCOVERED_ENDING_WITH_PER_STEP_PLAY_STATES_NOT_ALL_PATHS",
        "witnesses": witnesses,
        "witness_count": len(witnesses),
        "state_count": state_count,
        "truncated": truncated,
        "state_limit": WITNESS_STATE_LIMIT,
        "byte_limit": WITNESS_BYTE_LIMIT,
        "expected_runtime_behavior": list(EXPECTED_RUNTIME_BEHAVIOR),
        "runtime_evidence": {str(level): str(status) for level, status in sorted(evidence.items())},
        "media_references": media,
    }
