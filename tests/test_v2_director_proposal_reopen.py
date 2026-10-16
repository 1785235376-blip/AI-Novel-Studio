"""Ordinary rule-assisted adoption and original File-owner reopen; no model calls.

Use run_v2_checks.py with -m file_backend_only and an owned basetemp.
No authorization, session lifecycle, provider, or browser behavior is changed.
"""
from copy import deepcopy

import pytest

from test_v2_creative_foundation import rig


def accept(rig):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, {
        "mode": "SCREENPLAY", "title": "Synthetic human screenplay",
        "source_independent": True, "source_chapter_ids": [],
        "scenes": [{"id": "scene", "sequence": 1, "heading": "INT. ROOM",
                    "action": "A person pauses before opening the window."}],
    })
    proposal = rig.service.proposals.create(rig.nid, rig.scope, rig.actor, {
        "source_document_id": source["id"], "expected_source_version": source["version"],
    })
    notes = deepcopy(proposal["director_notes"])
    notes[0]["performance"] = "Explicit human review: pause, then turn."
    accepted = rig.service.proposals.review(rig.nid, rig.scope, rig.actor, proposal["id"], {
        "expected_version": proposal["version"], "reviewed_output_digest": proposal["output_digest"],
        "title": "Reviewed original director draft", "director_notes": notes,
    })
    return source, accepted


def reopen(rig):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    return CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)


def test_accepted_proposal_reopens_same_original_draft_after_owner_restart(rig):
    source, accepted = accept(rig)
    original_proposal, original_draft = accepted["proposal"], accepted["document"]
    service = reopen(rig)
    proposal = service.proposals.get(rig.nid, rig.scope, rig.actor, original_proposal["id"])
    draft = service.get(rig.nid, rig.scope, proposal["document_id"])
    assert proposal == original_proposal
    assert proposal["status"] == "APPROVED" and proposal["document_id"] == original_draft["id"]
    assert draft == original_draft and draft["status"] == "DRAFT"
    assert draft["director_notes"][0]["performance"] == "Explicit human review: pause, then turn."
    assert draft["provenance"]["proposal_id"] == proposal["id"]
    assert draft["provenance"]["model_called"] is False
    assert draft["source_documents"] == {source["id"]: {
        "version": proposal["source_version"], "digest": proposal["source_digest"]}}
    assert len(service.list(rig.nid, rig.scope)) == 2
    assert service.get(rig.nid, rig.scope, source["id"]) == source
    assert reopen(rig).proposals.list(rig.nid, rig.scope, rig.actor) == [proposal]


def test_accepted_proposal_and_draft_keep_source_update_checks_after_restart(rig):
    from app.creative.models import CreativeProductionDocumentIn
    from app.experimental.common import StaleSourceError
    source, accepted = accept(rig)
    changed = {key: deepcopy(source[key]) for key in CreativeProductionDocumentIn.model_fields if key in source}
    changed["scenes"][0]["action"] = "A different human-authored scene."
    rig.service.update(rig.nid, rig.scope, rig.actor, source["id"], source["version"], changed)
    service = reopen(rig)
    with pytest.raises(StaleSourceError, match="CREATIVE_PROPOSAL_SOURCE_CHANGED"):
        service.proposals.get(rig.nid, rig.scope, rig.actor, accepted["proposal"]["id"])
    with pytest.raises(StaleSourceError, match="CREATIVE_SOURCE_DOCUMENT_CHANGED"):
        service.get(rig.nid, rig.scope, accepted["document"]["id"])
    assert service.proposals.list(rig.nid, rig.scope, rig.actor) == []
    assert [row["id"] for row in service.list(rig.nid, rig.scope)] == [source["id"]]
    # The stored acceptance remains attributable; failure never silently rebinds it.
    stored = service.store.read(rig.nid, rig.scope)["collections"]
    assert stored[service.proposals.COLLECTION][accepted["proposal"]["id"]]["document_id"] == accepted["document"]["id"]
    assert stored[service.COLLECTION][accepted["document"]["id"]]["source_documents"] == accepted["document"]["source_documents"]
