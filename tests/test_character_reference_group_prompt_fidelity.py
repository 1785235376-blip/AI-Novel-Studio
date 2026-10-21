"""Raw original-Job prompt fidelity; no trimming, coercion or source-equality bypass."""
from copy import deepcopy
import unicodedata

import pytest
from pydantic import ValidationError

from app.creative.production_execution_models import MediaCommand
from app.experimental.planning import collection
from app.experimental.world import CharacterReferenceView, WorldService
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client
from test_character_reference_group_review_fixes import setup_visual, approved_views, group_body


def model_view(prompt):
    return CharacterReferenceView.model_validate({
        "view": "FRONT", "asset_id": "asset", "asset_version": 2,
        "asset_sha256": "a" * 64, "request_id": "request",
        "provider_id": "provider", "model_id": "model", "prompt": prompt,
    })


def original_command(prompt):
    return MediaCommand.model_validate({
        "operation_id": "m5.image.t2i", "request_id": "request",
        "provider_id": "provider", "model_id": "model", "prompt": prompt,
        "parameters": {"width": 64, "height": 64}, "source_snapshots": [],
        "allow_cloud": False,
    })


@pytest.mark.parametrize("value", [
    pytest.param("plain", id="plain"),
    pytest.param(" \tFRONT\r\n ", id="ascii-boundary"),
    pytest.param("\u00a0SIDE\u3000", id="unicode-boundary"),
    pytest.param(" e\u0301 ", id="combining-unmodified"),
    pytest.param("", id="empty-metadata"),
    pytest.param(" \t\r\n", id="whitespace-metadata"),
    pytest.param("x" * 16000, id="raw-limit"),
    pytest.param(" " + "x" * 15998 + " ", id="raw-limit-with-edges"),
])
def test_model_prompt_matches_original_string_and_json_roundtrip(value):
    if value.strip():
        assert original_command(value).prompt == value
    else:
        with pytest.raises(ValidationError, match="STUDIO_EXPLICIT_PROVIDER_MODEL_PROMPT_REQUIRED"):
            original_command(value)
    view = model_view(value)
    assert view.prompt == value
    assert view.model_dump()["prompt"] == value
    assert CharacterReferenceView.model_validate_json(view.model_dump_json()).prompt == value


@pytest.mark.parametrize("value", [None, True, 1, 1.25, [], {}, b"prompt", bytearray(b"prompt")],
                         ids=["null", "bool", "int", "float", "list", "dict", "bytes", "bytearray"])
def test_model_prompt_rejects_non_string_like_original_command(value):
    for parse in [model_view, original_command]:
        with pytest.raises(ValidationError) as caught:
            parse(value)
        assert any(error["loc"] == ("prompt",) for error in caught.value.errors())


@pytest.mark.parametrize("value", ["x" * 16001, " " * 16001, "\t" + "x" * 16000],
                         ids=["raw-too-long", "spaces-too-long", "edge-too-long"])
def test_model_prompt_limit_counts_raw_input_before_any_normalization(value):
    for parse in [model_view, original_command]:
        with pytest.raises(ValidationError) as caught:
            parse(value)
        assert any(error["loc"] == ("prompt",) for error in caught.value.errors())


def test_model_default_prompt_remains_empty():
    body = model_view("").model_dump()
    del body["prompt"]
    assert CharacterReferenceView.model_validate(body).prompt == ""


def test_model_other_world_identifiers_keep_existing_whitespace_policy():
    body = model_view(" exact \n").model_dump()
    body["asset_id"] = " asset "
    body["provider_id"] = " provider "
    value = CharacterReferenceView.model_validate(body)
    assert value.asset_id == "asset" and value.provider_id == "provider"
    assert value.prompt == " exact \n"


def generic(body):
    return {"kind": "CHARACTER_REFERENCE_GROUP", "title": body["title"],
            "data": {key: deepcopy(value) for key, value in body.items() if key != "title"}}


def create(e, base, body, mode):
    return e.client.post(base + ("/character-reference-groups" if mode == "dedicated" else "/records"),
                         headers=e.headers, json=body if mode == "dedicated" else generic(body))


def edit_body(row, data=None):
    return {"kind": row["kind"], "title": row["title"] + " edited", "chapter_id": row["chapter_id"],
            "event_order": row["event_order"], "data": deepcopy(row["data"] if data is None else data),
            "expected_version": row["version"]}


def valid_origin(e, monkeypatch):
    base, visual, pin = setup_visual(e, monkeypatch)
    prompts = ("\t FRONT e\u0301 \r\n", "\u00a0SIDE\u3000", "  BACK  ")
    views, jobs = approved_views(e, prompts=prompts)
    assert [view["prompt"] for view in views] == list(prompts)
    assert [job["command"]["prompt"] for job, _, _ in jobs] == list(prompts)
    return base, group_body(e, base, visual, pin, views), jobs, prompts


@pytest.mark.parametrize("mode", ["dedicated", "generic"])
def test_api_raw_original_prompts_survive_create_generic_edit_and_approve(image_client, monkeypatch, mode):
    e = image_client
    base, body, jobs, prompts = valid_origin(e, monkeypatch)
    row = checked(create(e, base, body, mode), 201)
    assert [view["prompt"] for view in row["data"]["views"]] == list(prompts)
    row = checked(e.client.put(base + "/records/" + row["id"], headers=e.headers, json=edit_body(row)))
    assert [view["prompt"] for view in row["data"]["views"]] == list(prompts)
    row = checked(e.client.post(base + f"/records/{row['id']}/approve", headers=e.headers,
                               json={"expected_version": row["version"]}))
    assert row["status"] == "APPROVED" and row["canon_state"] == "CANON"
    assert [view["prompt"] for view in row["data"]["views"]] == list(prompts)
    assert any(item["source_record_id"] == row["id"]
               for item in checked(e.client.get(base + "/canon", headers=e.headers))["items"])
    for index, (original, _, _) in enumerate(jobs):
        current = checked(e.client.get(e.base + "/jobs/image/" + original["id"], headers=e.headers))
        for key in ["command", "request_id", "request_digest", "approved_asset_version", "output_candidate", "provider", "sources"]:
            assert current[key] == original[key]
        assert current["command"]["prompt"] == prompts[index]


def test_api_prompt_params_provider_and_source_detachment_still_rejects_at_every_write(image_client, monkeypatch):
    e = image_client
    base, body, jobs, prompts = valid_origin(e, monkeypatch)
    row = checked(create(e, base, body, "dedicated"), 201)
    for change in ["trim-prompt", "normalize-prompt", "blank-prompt", "whitespace-only-prompt", "parameters", "provider_id", "model_id", "reference_asset_ids"]:
        bad = deepcopy(body)
        view = bad["views"][0]
        if change == "trim-prompt": view["prompt"] = view["prompt"].strip()
        elif change == "normalize-prompt": view["prompt"] = unicodedata.normalize("NFC", view["prompt"])
        elif change == "blank-prompt": view["prompt"] = ""
        elif change == "whitespace-only-prompt": view["prompt"] = " \t\r\n"
        elif change == "parameters": view["parameters"]["seed"] = view["parameters"].get("seed", 0) + 1
        elif change == "reference_asset_ids": view[change] = ["not-the-original-reference"]
        else: view[change] += "-other"
        for mode in ["dedicated", "generic"]:
            response = create(e, base, bad, mode)
            assert response.status_code == 422, response.text
            assert "BINDING_CHANGED" in response.text
        response = e.client.put(base + "/records/" + row["id"], headers=e.headers,
                                json=edit_body(row, generic(bad)["data"]))
        assert response.status_code == 422, response.text
        assert "BINDING_CHANGED" in response.text
        unchanged = checked(e.client.get(base + "/records/" + row["id"], headers=e.headers))
        assert unchanged["version"] == row["version"] and unchanged["data"] == row["data"]
    # A corrupted stored declaration must not be repaired by trimming or approved.
    scope = {"mode": "local", "novel_id": e.nid}
    world = e.experimental.world_service
    with world.store.transaction(e.nid, scope) as state:
        stored = collection(state, WorldService.RECORDS)[row["id"]]
        stored["data"]["views"][0]["prompt"] = prompts[0].strip()
    response = e.client.post(base + f"/records/{row['id']}/approve", headers=e.headers,
                             json={"expected_version": row["version"]})
    assert response.status_code == 422, response.text
    assert "BINDING_CHANGED" in response.text
    assert checked(e.client.get(base + "/records/" + row["id"], headers=e.headers))["status"] == "REVIEW"
    assert not any(item.get("source_record_id") == row["id"]
                   for item in checked(e.client.get(base + "/canon", headers=e.headers))["items"])
