"""Exact multi-chapter adaptation on the original synthetic executor only."""
import copy
import json

import pytest

from test_v2_source_adaptation import (mounted, prefix, broker_app, creative_model,
    checked, route, action, dispatch, settle, review)
from test_v2_adaptation_archive import archived, raw, read, reopen


def chapters(e, text="The second visitor closes the gate."):
    other = e.chapters.create(e.nid, {"title": "Second", "content": text})
    return [e.chapters.get(e.chapter["id"]), e.chapters.get(other["id"])]


def create_ordered(e, sources):
    return checked(e.client.post(e.creative_base + "/adaptation-proposals", headers=e.headers, json={
        "sources": [{"chapter_id": source["id"], "expected_source_version": source["version"]} for source in sources],
        "title": "Ordered screenplay"}), 201)


def result(sources):
    return {"scenes": [{"id": f"s{i}", "sequence": i, "source_ordinal": i, "heading": "EXT. GATE - DAY",
                         "action": "The visitor moves."} for i, source in enumerate(sources, 1)],
        "report": {"summary": "Synthetic transformation for review.", "changes": [
            {"id": f"c{i}", "kind": "VISUALIZATION", "source_ordinal": i,
             "source_quote": source["content"], "scene_ids": [f"s{i}"], "note": "Review this transformation."}
            for i, source in enumerate(sources, 1)]}}


def prepared(e, monkeypatch, sources=None, output=None):
    from app.runtime import runtime
    sources = sources or chapters(e)
    calls = []
    def stream(prompt, model, **kwargs):
        calls.append(prompt)
        yield json.dumps(output or result(sources))
    monkeypatch.setattr(runtime.providers["mock"], "stream", stream)
    row = create_ordered(e, sources)
    row = action(e, row, "preview", route_id=route(e)["route_id"], allow_synthetic=True)
    return row, calls, sources


def test_ordered_exact_preview_execute_archive_review_and_reopen(creative_model, monkeypatch):
    e = creative_model
    selected = list(reversed(chapters(e)))
    unrelated = e.chapters.create(e.nid, {"title": "Unselected", "content": "UNSELECTED_PRIVATE_SENTINEL"})
    unrelated_before = e.chapters.get(unrelated["id"])
    row, calls, sources = prepared(e, monkeypatch, selected)
    preview = row["model_preview"]
    assert not calls and preview["input_digest"] == row["ordered_sources_digest"]
    assert preview["author"]["source"] == ""
    assert preview["author"]["request_scope"]["source_mode"] == "NONE"
    assert preview["broker"]["request"]["chapter_ids"] == [source["id"] for source in sources]
    context = preview["request"]["context"]
    assert list(context) == ["explicit_sources"]
    assert [item["text"] for item in context["explicit_sources"]["items"]] == [source["content"] for source in sources]
    assert all(item["truncated"] is False for item in context["explicit_sources"]["items"])
    assert "UNSELECTED_PRIVATE_SENTINEL" not in preview["request"]["prompt"]
    completed = settle(e, dispatch(e, row))
    assert completed["status"] == "NEEDS_REVIEW", completed
    asset, = archived(e, completed)
    assert asset["_text_result_origin"]["schema_version"] == 2
    assert asset["_text_execution_receipt"]["schema_version"] == 2
    original = raw(e, completed, asset)
    reopen(e, monkeypatch)
    reopened = read(e, completed)
    assert reopened["asset_output"]["state"] == "DRAFT" and len(calls) == 1
    adopted = checked(review(e, reopened))
    doc = adopted["document"]
    assert doc["source_chapter_ids"] == [source["id"] for source in sources]
    assert [scene["source_chapter_id"] for scene in doc["scenes"]] == doc["source_chapter_ids"]
    assert all("source_ordinal" not in scene for scene in doc["scenes"])
    assert doc["provenance"]["ordered_sources_digest"] == row["ordered_sources_digest"]
    assert raw(e, completed, archived(e, completed)[0]) == original
    assert [e.chapters.get(source["id"]) for source in sources] == sources
    assert e.chapters.get(unrelated["id"]) == unrelated_before


@pytest.mark.parametrize("when", ["preview", "dispatch", "review", "reopen"])
def test_second_chapter_change_blocks_every_boundary(creative_model, monkeypatch, when):
    e = creative_model
    sources = chapters(e)
    if when == "preview":
        row, calls = create_ordered(e, sources), []
    else:
        row, calls, _ = prepared(e, monkeypatch, sources)
    if when in {"review", "reopen"}:
        row = settle(e, dispatch(e, row))
    e.chapters.save(sources[1]["id"], {"version": sources[1]["version"], "content": "A changed second source."})
    if when == "reopen":
        reopen(e, monkeypatch)
        response = e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers)
    else:
        body = {"expected_version": row["version"]}
        if when == "preview": body.update(route_id=route(e)["route_id"], allow_synthetic=True)
        if when == "dispatch": body["reviewed_preview_digest"] = row["model_preview"]["preview_digest"]
        if when == "review": body.update(reviewed_output_digest=row["output_digest"], title="Review", output=row["output"])
        response = e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/{when}', headers=e.headers, json=body)
    assert response.status_code == 409, response.text
    assert len(calls) == (1 if when in {"review", "reopen"} else 0)
    assert not e.creative.list(e.nid, row["scope"])


@pytest.mark.parametrize("bad", ["duplicate", "single", "too_many", "oversize", "total", "mixed"])
def test_ordered_admission_limits(creative_model, bad):
    e = creative_model
    sources = chapters(e, "x" * 8001 if bad == "oversize" else "Second source")
    if bad == "duplicate": sources[1] = sources[0]
    if bad == "single": sources = sources[:1]
    if bad in {"too_many", "total"}:
        count = 17 if bad == "too_many" else 5
        sources = [e.chapters.get(e.chapters.create(e.nid, {"title": f"Source {i}", "content": "x" * (6500 if bad == "total" else 10)})["id"]) for i in range(count)]
    body = {"title": "Rejected", "sources": [{"chapter_id": source["id"], "expected_source_version": source["version"]} for source in sources]}
    if bad == "mixed": body.update(chapter_id=sources[0]["id"], expected_source_version=sources[0]["version"])
    response = e.client.post(e.creative_base + "/adaptation-proposals", headers=e.headers, json=body)
    assert response.status_code in {400, 422}, response.text
    assert not e.manager.jobs


@pytest.mark.parametrize("bad", ["foreign_quote", "unknown_ordinal", "cross_source", "missing_ordinal"])
def test_ordered_output_attribution_is_closed(creative_model, monkeypatch, bad):
    e = creative_model
    sources = chapters(e)
    output = result(sources)
    if bad == "foreign_quote": output["report"]["changes"][0]["source_quote"] = sources[1]["content"]
    if bad == "unknown_ordinal": output["scenes"][0]["source_ordinal"] = 3
    if bad == "cross_source": output["report"]["changes"][0]["scene_ids"] = ["s2"]
    if bad == "missing_ordinal": output["scenes"][0].pop("source_ordinal")
    row, calls, _ = prepared(e, monkeypatch, sources, output)
    completed = settle(e, dispatch(e, row))
    assert completed["status"] == "MODEL_UNAVAILABLE", completed
    assert completed["model_execution"]["failure_code"] == "ADAPTATION_INVALID_OUTPUT"
    assert len(calls) == 1 and not e.creative.list(e.nid, row["scope"])


@pytest.mark.parametrize("change", ["privacy", "archive", "hidden", "reorder", "cost"])
def test_nonanchor_revocation_or_changed_consent_blocks_admission(creative_model, monkeypatch, change):
    from app.creative.proposals import digest
    e = creative_model
    row, calls, sources = prepared(e, monkeypatch)
    if change == "privacy":
        from app.source_privacy import review_source_privacy, content_digest
        review_source_privacy(sources[1], None, "test-owner", "LOCAL_ONLY", sources[1]["version"],
            content_digest(sources[1]), root=e.creative.store.root)
    elif change == "archive":
        e.chapters.archive(sources[1]["id"], sources[1]["version"])
    elif change == "hidden":
        original = e.chapters.get
        monkeypatch.setattr(e.chapters, "get", lambda cid: {**original(cid), **({"hidden": True} if cid == sources[1]["id"] else {})})
    elif change == "reorder":
        with e.creative.store.transaction(e.nid, row["scope"]) as state:
            stored = state["collections"][e.creative.adaptations.COLLECTION][row["id"]]
            stored["sources"].reverse()
            for ordinal, source in enumerate(stored["sources"], 1): source["ordinal"] = ordinal
            stored["ordered_sources_digest"] = digest(stored["sources"])
            for key in ("chapter_id", "source_version", "source_digest", "selected_text", "selection_digest"):
                stored[key] = stored["sources"][0][key]
    else:
        monkeypatch.setattr(e.creative.adaptations.generation, "_policy", lambda *_: (_ for _ in ()).throw(ValueError("PRICE_CHANGED")))
    response = e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/dispatch', headers=e.headers,
        json={"expected_version": row["version"], "reviewed_preview_digest": row["model_preview"]["preview_digest"]})
    assert response.status_code in {400, 404, 409, 422}, response.text
    assert calls == [] and not e.manager.jobs


@pytest.mark.parametrize("change", ["second_source", "cancel", "binding"])
def test_ordered_late_output_never_crosses_changed_authority(creative_model, monkeypatch, change):
    from threading import Event
    import time
    from app.runtime import runtime
    e = creative_model
    row, calls, sources = prepared(e, monkeypatch)
    entered, release = Event(), Event()
    def delayed(prompt, model, **kwargs):
        entered.set()
        assert release.wait(15)
        yield json.dumps(result(sources))
    monkeypatch.setattr(runtime.providers["mock"], "stream", delayed)
    try:
        running = dispatch(e, row)
        assert entered.wait(5)
        job = e.manager.get(running["model_execution"]["job_id"])
        if change == "second_source":
            e.chapters.save(sources[1]["id"], {"version": sources[1]["version"], "content": "Changed while running."})
        elif change == "cancel":
            action(e, running, "cancel")
        else:
            job.adaptation_binding["ordered_sources_digest"] = "f" * 64
    finally:
        release.set()
    deadline = time.monotonic() + 20
    with job.condition:
        while job.terminal_hook_status is None:
            remaining = deadline - time.monotonic()
            assert remaining > 0
            job.condition.wait(min(remaining, .05))
    assert job.status in {"FAILED", "CANCELLED"} and not job.output
    assert not e.creative.list(e.nid, row["scope"])
    assert e.client.get(e.prefix + "/generation/" + job.id, headers=e.headers).status_code == 404
