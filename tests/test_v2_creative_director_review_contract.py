"""Pure exact-shot review contracts; no execution or model-quality claim."""
from copy import deepcopy
import json

import pytest

from app.creative.storyboard_model import (STORYBOARD_CONTRACT, DirectorStoryboardModelOutput,
    _parse_director_output, _storyboard_prompt_data)
from app.creative.proposals import director_output_digest


def pair():
    source = {"id": "board-1", "version": 4, "mode": "STORYBOARD", "title": "Saved board",
        "source_chapter_ids": [], "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "INT. ROOM",
                    "action": "A visitor waits.", "dialogue": [{"speaker": "Visitor", "text": "Hello."}]},
                   {"id": "scene-2", "sequence": 2, "heading": "EXT. DOOR", "action": "A door opens."}],
        "shots": [{"id": "shot-2", "number": 2, "scene_id": "scene-2", "action": "Door"},
                  {"id": "shot-1", "number": 1, "scene_id": "scene-1", "action": "Wait"}]}
    associations = [{"source_shot_id": shot["id"], "source_number": shot["number"],
                     "scene_id": shot["scene_id"], "note_id": "note-" + str(shot["number"]),
                     "source_shot": deepcopy(shot)} for shot in sorted(source["shots"], key=lambda x: x["number"])]
    row = {"title": "Review", "source_digest": "a" * 64, "provenance": {"source_shots": associations}}
    notes = [{"id": item["note_id"], "source_shot_id": item["source_shot_id"],
              "scene_id": item["scene_id"], "number": item["source_number"],
              "planning": {"rationale": "Hold the reaction", "sequence_reason": "Continue the action",
                  "duration_reason": "Estimated beat", "uncertainty": "Geometry unknown",
                  "assumptions": ["Camera placement is speculative"], "evidence": [], "alternatives": []}}
             for item in associations]
    output = {"source_contract": STORYBOARD_CONTRACT, "source_document_id": source["id"],
              "source_version": source["version"], "source_digest": row["source_digest"], "director_notes": notes}
    return row, source, output


def parse(row, source, output, bound=128000):
    text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
    return _parse_director_output(row, source, text, max_output_bytes=bound)


def test_pure_prompt_has_original_schema_exact_mapping_and_detached_source():
    row, source, output = pair()
    row["visual_target"] = {"style": "Quiet"}
    before = deepcopy((row, source))
    data = _storyboard_prompt_data(row, source)
    assert data["output_schema"] == DirectorStoryboardModelOutput.model_json_schema()
    assert data["contract"] == STORYBOARD_CONTRACT
    assert data["source_document_id"] == source["id"]
    assert data["source_version"] == source["version"] and data["source_digest"] == row["source_digest"]
    assert data["source_mapping"] == [{"source_shot_id": n["source_shot_id"], "note_id": n["id"],
        "scene_id": n["scene_id"], "source_number": n["number"]} for n in output["director_notes"]]
    assert [shot["id"] for shot in data["storyboard"]["shots"]] == ["shot-1", "shot-2"]
    assert data["planning_contract"] == "SCENE_EVIDENCED_CANDIDATES_V1"
    data["storyboard"]["scenes"][0]["action"] = "Mutated return"
    data["visual_target"]["style"] = "Changed"
    assert (row, source) == before


def test_pure_parse_has_stable_notes_digest_and_does_not_mutate_inputs():
    row, source, output = pair()
    before = deepcopy((row, source, output))
    notes = parse(row, source, output)
    assert [n["id"] for n in notes] == ["note-1", "note-2"]
    assert all("source_shot_id" not in n for n in notes)
    assert all(n["planning"]["uncertainty"] == "Geometry unknown" for n in notes)
    assert director_output_digest(notes) == director_output_digest(parse(row, source, output))
    notes[0]["planning"]["rationale"] = "Explicit human change"
    assert director_output_digest(notes) != director_output_digest(parse(row, source, output))
    assert (row, source, output) == before


@pytest.mark.parametrize("field,value", [("source_contract", "DIRECTOR_NOTES_V1"),
    ("source_document_id", "other"), ("source_version", 5), ("source_version", True),
    ("source_version", "4"), ("source_digest", "b" * 64), ("unexpected", "extra")])
def test_exact_strict_source_envelope(field, value):
    row, source, output = pair()
    output[field] = value
    with pytest.raises(ValueError):
        parse(row, source, output)


@pytest.mark.parametrize("change", ["reorder", "omit", "duplicate", "id", "scene", "number", "shot", "snapshot"])
def test_exact_association_and_source_snapshot(change):
    row, source, output = pair()
    if change == "reorder": output["director_notes"].reverse()
    elif change == "omit": output["director_notes"].pop()
    elif change == "duplicate": output["director_notes"][1] = deepcopy(output["director_notes"][0])
    elif change == "snapshot": row["provenance"]["source_shots"][0]["source_shot"]["action"] = "Stale"
    else:
        field = {"id": "id", "scene": "scene_id", "number": "number", "shot": "source_shot_id"}[change]
        output["director_notes"][0][field] = 3 if field == "number" else "other"
    with pytest.raises(ValueError):
        parse(row, source, output)


@pytest.mark.parametrize("change", ["missing", "null", "uncertainty", "blank", "speculation", "shot_evidence",
    "foreign_scene", "invented", "dialogue_index", "excess_alternatives"])
def test_planning_and_scene_only_evidence_are_mandatory(change):
    row, source, output = pair()
    note = output["director_notes"][0]
    planning = note["planning"]
    if change == "missing": del note["planning"]
    elif change == "null": note["planning"] = None
    elif change == "uncertainty": del planning["uncertainty"]
    elif change == "blank": planning["uncertainty"] = "  "
    elif change == "speculation": planning["assumptions"] = []
    elif change == "excess_alternatives": planning["alternatives"] = [{"choice": "Wide", "tradeoff": "Distance"}] * 4
    else:
        evidence = {"scene_id": "scene-1", "field": "action", "excerpt": "visitor waits"}
        if change == "shot_evidence": evidence["field"] = "frame_prompt"
        elif change == "foreign_scene": evidence.update(scene_id="scene-2", excerpt="door opens")
        elif change == "invented": evidence["excerpt"] = "never supplied"
        elif change == "dialogue_index": evidence.update(field="dialogue", excerpt="Hello.", dialogue_index=1)
        planning["evidence"] = [evidence]
    with pytest.raises(ValueError):
        parse(row, source, output)


def test_valid_exact_scene_and_dialogue_excerpts():
    row, source, output = pair()
    output["director_notes"][0]["planning"]["evidence"] = [
        {"scene_id": "scene-1", "field": "action", "excerpt": "visitor waits"},
        {"scene_id": "scene-1", "field": "dialogue", "dialogue_index": 0, "excerpt": "Hello."}]
    assert len(parse(row, source, output)[0]["planning"]["evidence"]) == 2


@pytest.mark.parametrize("nested", [False, True])
def test_duplicate_json_keys_reject_at_every_depth(nested):
    row, source, output = pair()
    text = json.dumps(output)
    if nested:
        text = text.replace('"rationale": "Hold the reaction"', '"rationale": "First", "rationale": "Second"', 1)
    else:
        text = text.replace('{', '{"source_version": 4,', 1)
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        parse(row, source, text)


def test_utf8_byte_bound_and_invalid_utf8_reject_before_json():
    row, source, output = pair()
    output["director_notes"][0]["note"] = "镜头" * 10
    text = json.dumps(output, ensure_ascii=False)
    with pytest.raises(ValueError, match="OUTPUT_LIMIT"):
        parse(row, source, text, bound=len(text))
    assert parse(row, source, text, bound=len(text.encode("utf-8")))
    with pytest.raises(UnicodeEncodeError):
        parse(row, source, '\ud800')


def test_legacy_screenplay_parser_still_allows_optional_planning_and_sorted_notes():
    row, source, _ = pair()
    source["mode"] = "SCREENPLAY"
    output = {"director_notes": [{"id": "b", "number": 2, "scene_id": "scene-2"},
                                {"id": "a", "number": 1, "scene_id": "scene-1"}]}
    notes = parse(row, source, output)
    assert [note["id"] for note in notes] == ["a", "b"]
    assert all("planning" not in note for note in notes)
