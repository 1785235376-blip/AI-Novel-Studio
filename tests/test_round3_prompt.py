"""Round 3 — Prompt Intelligence: Prompt Asset, version chain, binding, context.

The properties that matter beyond the individual cases:

* **no second asset, version or review system** — a prompt is an existing asset
  (`kind="prompt"`) with its payload in the allow-listed `parameters` dict, its
  version chain in the existing lineage, and its review in `promote_owned`; a test
  asserts the projection module defines no model, imports no application model, and
  exposes no write path;
* **history cannot be lost** — a revised prompt is a new immutable asset, so every
  prior revision stays readable and each carries its change note and reason;
* **a binding is shown only when the target really exists** — an unresolvable
  character/scene is `UNKNOWN`, never dropped and never assumed;
* **the context panel assembles sources, not text** — `composes_prompt_text` is
  `False` and user confirmation is required (Round 3 §10).

Pure projection tests run anywhere. Route tests need the isolated runner
(`scripts/run_v2_checks.py`), which sets `PROJECT_ROOT`; without it they skip rather
than report a pass they did not earn.
"""
from __future__ import annotations

import base64
import inspect
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative import prompt_asset as prompt

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"


# --------------------------------------------------------------- fixtures --

def payload(**overrides):
    base = dict(family_id="fam-1", revision=1, purpose="IMAGE", origin="MANUAL",
                negative_prompt="low quality", model_reference="flux-1", parameters={"steps": 28},
                seed=7, reference_asset_ids=["a1"], character_ids=["c1"], scene_ids=["l1"],
                change_note="初稿", change_reason="第一版")
    base.update(overrides)
    return prompt.build_payload(**base)


def asset(asset_id: str, body, *, version=2, status="DRAFT", approved=False, kind="prompt"):
    return {"id": asset_id, "kind": kind, "version": version, "review_status": status,
            "approved_at": "2026-10-15T00:00:00Z" if approved else None,
            "parameters": {"prompt": body}}


BIBLE = {"character_ids": ["c1"], "location_ids": ["l1"], "asset_ids": ["a1", "out1"],
         "shot_ids": ["s1"],
         "characters": [{"character_id": "c1", "dimensions": [
             {"field": "appearance", "value": "瘦高", "authored": True, "state": "KNOWN",
              "source": "world_records.CHARACTER_VISUAL.appearance"}]}],
         "locations": [{"location_id": "l1", "dimensions": [
             {"field": "architecture", "value": "老式砖楼", "authored": True, "state": "KNOWN",
              "source": "world_records.SCENE_VISUAL.architecture"}]}]}


def library(assets, **kwargs):
    return prompt.project_prompt_library(assets, bible=kwargs.pop("bible", BIBLE),
                                         asset_text=kwargs.pop("asset_text", {}), **kwargs)


# ------------------------------------------------------ required surfaces --

def test_the_eleven_prompt_fields_are_the_required_set():
    assert prompt.PROMPT_FIELDS == (
        "text", "negative_prompt", "model_reference", "parameters", "seed",
        "reference_assets", "output_assets", "purpose", "origin", "binding", "version")


def test_purpose_origin_and_binding_vocabularies_are_frozen():
    assert prompt.PURPOSES == ("IMAGE", "VIDEO", "AUDIO", "TEXT")
    assert prompt.ORIGINS == ("MANUAL", "AI_GENERATED", "IMPORTED")
    assert prompt.BINDING_KINDS == ("CHARACTER", "SCENE", "SHOT", "ASSET")


# -------------------------------------------- no second system, no writes --

def test_projection_module_defines_no_model_and_imports_no_app_model():
    source = inspect.getsource(prompt)
    for forbidden in ("from app", "import app", "class Asset(", "class Prompt(",
                      "class Version(", "class Review(", "class Project("):
        assert forbidden not in source, f"prompts must reuse the asset owner, not {forbidden}"


def test_projection_module_has_no_write_path():
    source = inspect.getsource(prompt)
    for forbidden in ("def create", "def update", "def write", "def save", "def commit", "def delete"):
        assert forbidden not in source, f"the prompt projection is read-only, not {forbidden}"


def test_a_prompt_is_an_existing_asset_kind_not_a_new_owner():
    """The payload lives in the asset owner's allow-listed `parameters` dict."""
    assert prompt.PROMPT_KIND == "prompt"
    assert prompt.PAYLOAD_KEY == "prompt"
    from app.services.asset_library_service import AssetLibraryService

    code = inspect.getsource(AssetLibraryService.update_metadata)
    assert "parameters" in code, "the asset owner must already accept a parameters dict"
    # And the projection must not ask for any new metadata field.
    assert "negative_prompt" not in inspect.getsource(AssetLibraryService.update_metadata)


# ------------------------------------------------------------- the payload --

def test_payload_builder_validates_purpose_origin_revision_seed_and_family():
    with pytest.raises(ValueError, match="PROMPT_PURPOSE_INVALID"):
        payload(purpose="HOLOGRAM")
    with pytest.raises(ValueError, match="PROMPT_ORIGIN_INVALID"):
        payload(origin="DREAMT")
    with pytest.raises(ValueError, match="PROMPT_REVISION_INVALID"):
        payload(revision=0)
    with pytest.raises(ValueError, match="PROMPT_SEED_INVALID"):
        payload(seed=-1)
    with pytest.raises(ValueError, match="PROMPT_FAMILY_REQUIRED"):
        payload(family_id="   ")


def test_payload_records_adoption_source_without_copying_the_old_owner():
    built = payload(source={"owner": "ShotCard.frame_prompt", "field": "frame_prompt", "digest": "a" * 64})
    assert built["adopted_from"] == {"owner": "ShotCard.frame_prompt", "field": "frame_prompt",
                                     "digest": "a" * 64}
    # Adoption records where the value came from; it does not embed the source record.
    assert "frame_prompt" not in {key for key in built if key != "adopted_from"}


def test_payload_readability_gate():
    assert prompt.payload_is_readable(payload()) is True
    assert prompt.payload_is_readable({}) is False
    assert prompt.payload_is_readable({**payload(), "contract": "other/1"}) is False
    assert prompt.payload_is_readable({**payload(), "purpose": "NOPE"}) is False
    assert prompt.payload_is_readable({**payload(), "revision": "1"}) is False


# ------------------------------------------------------- version chain -----

def test_revisions_group_into_one_family_newest_first():
    projection = library([
        asset("A1", payload(revision=1)),
        asset("A2", payload(revision=2, change_note="提高步数", change_reason="细节不足",
                            previous_asset_id="A1")),
    ])
    assert projection["prompt_count"] == 1
    assert projection["revision_count"] == 2
    entry = projection["entries"][0]
    assert entry["family_id"] == "fam-1"
    assert entry["head_asset_id"] == "A2"
    assert entry["revision"] == 2


def test_every_revision_is_retained_with_its_change_note_and_reason():
    projection = library([
        asset("A1", payload(revision=1, change_note="初稿", change_reason="第一版")),
        asset("A2", payload(revision=2, change_note="提高步数", change_reason="细节不足")),
        asset("A3", payload(revision=3, change_note="换模型", change_reason="风格不符")),
    ])
    versions = projection["entries"][0]["versions"]
    assert [row["revision"] for row in versions] == [1, 2, 3]
    assert [row["change_note"] for row in versions] == ["初稿", "提高步数", "换模型"]
    assert [row["change_reason"] for row in versions] == ["第一版", "细节不足", "风格不符"]
    assert [row["asset_id"] for row in versions] == ["A1", "A2", "A3"]


def test_a_revision_points_at_its_predecessor():
    projection = library([asset("A1", payload(revision=1)),
                          asset("A2", payload(revision=2, previous_asset_id="A1"))])
    assert projection["entries"][0]["versions"][1]["previous_asset_id"] == "A1"


def test_two_families_are_never_merged():
    projection = library([asset("A1", payload(family_id="fam-1")),
                          asset("B1", payload(family_id="fam-2"))])
    assert projection["prompt_count"] == 2
    assert {row["family_id"] for row in projection["entries"]} == {"fam-1", "fam-2"}


def test_detail_reports_the_family_with_complete_history():
    detail = prompt.project_prompt_detail(
        "fam-1", [asset("A1", payload(revision=1)), asset("A2", payload(revision=2))], bible=BIBLE)
    assert detail["contract"] == "studio-prompt-detail/1"
    assert detail["history_complete"] is True
    assert len(detail["versions"]) == 2
    with pytest.raises(FileNotFoundError):
        prompt.project_prompt_detail("nope", [asset("A1", payload())], bible=BIBLE)


# -------------------------------------------------------------- bindings --

def test_a_binding_is_known_only_when_the_target_really_exists():
    entry = library([asset("A1", payload(character_ids=["c1", "c-missing"],
                                         scene_ids=["l1", "l-missing"]))])["entries"][0]
    characters = {row["id"]: row["resolution"] for row in entry["bindings"]["characters"]}
    scenes = {row["id"]: row["resolution"] for row in entry["bindings"]["scenes"]}
    assert characters == {"c1": "KNOWN", "c-missing": "UNKNOWN"}
    assert scenes == {"l1": "KNOWN", "l-missing": "UNKNOWN"}
    assert set(entry["unresolved_bindings"]) == {"c-missing", "l-missing"}


def test_without_a_bible_index_every_binding_is_unknown_and_says_why():
    projection = prompt.project_prompt_library([asset("A1", payload())], bible=None)
    entry = projection["entries"][0]
    assert projection["bible_index_supplied"] is False
    assert all(row["resolution"] == "UNKNOWN" for row in entry["bindings"]["characters"])
    assert all(row["verification"] == "NO_INDEX_SUPPLIED" for row in entry["bindings"]["characters"])
    assert projection["entries"][0]["fields"][-1]["field"] == "version"


def test_reference_and_output_assets_are_resolved_against_the_asset_index():
    entry = library([asset("A1", payload(reference_asset_ids=["a1", "a-missing"],
                                         output_asset_ids=["out1"]))])["entries"][0]
    resolutions = {row["id"]: row["resolution"] for row in entry["bindings"]["assets"]}
    assert resolutions == {"a1": "KNOWN", "a-missing": "UNKNOWN", "out1": "KNOWN"}


# --------------------------------------------------------------- fields --

def test_prompt_text_comes_from_the_asset_bytes():
    entry = library([asset("A1", payload())], asset_text={"A1": "a tall figure in the rain"})["entries"][0]
    assert [row["value"] for row in entry["fields"] if row["field"] == "text"] == ["a tall figure in the rain"]


def test_unauthored_fields_are_the_explicit_unknown_value():
    entry = library([asset("A1", payload(negative_prompt="", model_reference="", seed=None,
                                         parameters=None, output_asset_ids=[]))])["entries"][0]
    fields = {row["field"]: row for row in entry["fields"]}
    for name in ("negative_prompt", "model_reference", "parameters", "seed", "output_assets"):
        assert fields[name]["authored"] is False, name
        assert fields[name]["state"] == prompt.UNKNOWN, name
    assert fields[name]["value"] == prompt.UNKNOWN


def test_redacted_mode_projects_digests_instead_of_text():
    entry = library([asset("A1", payload(redacted=True))], asset_text={"A1": "secret prompt"})["entries"][0]
    fields = {row["field"]: row for row in entry["fields"]}
    assert entry["redacted"] is True
    assert fields["text"]["value"] == prompt.digest("secret prompt")
    assert "secret prompt" not in str(entry)


def test_review_status_is_carried_through_not_invented():
    approved = library([asset("A1", payload(), status="APPROVED", approved=True)])["entries"][0]
    draft = library([asset("A1", payload())])["entries"][0]
    assert approved["review_status"] == "APPROVED" and approved["approved"] is True
    assert draft["review_status"] == "DRAFT" and draft["approved"] is False


# ------------------------------------------------------- robustness ------

def test_non_prompt_assets_are_ignored():
    projection = library([asset("IMG", {}, kind="image"), asset("A1", payload())])
    assert projection["prompt_count"] == 1
    assert projection["entries"][0]["head_asset_id"] == "A1"


def test_a_prompt_asset_with_an_unreadable_payload_is_reported_not_guessed():
    projection = library([asset("A1", {"contract": "other/1", "purpose": "IMAGE"})])
    assert projection["prompt_count"] == 0
    # Reason refined by R3-R-07: the validator now names the specific violation rather
    # than one generic code. The refusal itself is unchanged and still reported.
    assert projection["malformed"] == [{"asset_id": "A1", "family_id": "A1",
                                        "reason": "PROMPT_PAYLOAD_CONTRACT_INVALID"}]


def test_a_payload_missing_its_required_family_id_is_reported_not_silently_accepted():
    """`family_id` is required by the payload contract.

    A silent fallback to the asset id would let a corrupt payload masquerade as a
    valid single-revision prompt, so it is reported as malformed instead.
    """
    bare = payload()
    bare.pop("family_id")
    projection = library([asset("A1", bare), asset("A2", bare)])
    assert projection["prompt_count"] == 0
    assert {row["reason"] for row in projection["malformed"]} == {"PROMPT_PAYLOAD_FIELD_MISSING"}
    assert len(projection["malformed"]) == 2


def test_a_project_without_any_prompt_asset_still_projects_cleanly():
    """Round 3 §12: an old project with no prompt assets must keep working."""
    projection = library([])
    assert projection["prompt_count"] == 0
    assert projection["entries"] == []
    assert projection["revision_count"] == 0
    assert projection["malformed"] == []
    assert projection["required_fields"] == list(prompt.PROMPT_FIELDS)


def test_library_grants_nothing_and_declares_unknown():
    projection = library([])
    assert projection["advisory_only"] is True
    assert projection["execution_authority"] is False
    assert projection["auto_modify"] is False
    assert projection["unknown_is_explicit"] is True


def test_projection_never_mutates_its_inputs():
    rows = [asset("A1", payload())]
    before = repr(rows)
    library(rows, asset_text={"A1": "x"})
    assert repr(rows) == before


# ------------------------------------------------------- context assembly --

def test_context_assembles_sources_and_never_composes_the_prompt():
    context = prompt.project_prompt_context(character_ids=["c1"], location_ids=["l1"], bible=BIBLE)
    assert context["contract"] == "studio-prompt-context/1"
    assert context["composes_prompt_text"] is False
    assert context["requires_user_confirmation"] is True
    assert [source["kind"] for source in context["sources"]] == ["CHARACTER_BIBLE", "SCENE_BIBLE"]
    assert context["sources"][0]["dimensions"][0]["value"] == "瘦高"


def test_context_reports_an_unresolvable_source_as_unknown():
    context = prompt.project_prompt_context(character_ids=["c-missing"], bible=BIBLE)
    assert context["sources"][0]["resolution"] == "UNKNOWN"


def test_context_reports_what_is_still_unauthored():
    bare = {"characters": [{"character_id": "c1", "dimensions": [
        {"field": "clothing", "value": "UNKNOWN", "authored": False, "state": "UNKNOWN", "source": "s"}]}],
        "location_ids": [], "character_ids": ["c1"], "asset_ids": [], "shot_ids": []}
    context = prompt.project_prompt_context(character_ids=["c1"], bible=bare)
    assert context["unauthored"] == [{"kind": "CHARACTER_BIBLE", "id": "c1", "field": "clothing"}]


# ------------------------------------------------------- route admission --

def test_only_get_reaches_the_prompt_paths():
    from app.creative.workspace_api import is_independent_studio_route

    for path in ("/api/projects/P1/studio/prompts", "/api/projects/P1/studio/prompts/fam1",
                 "/api/projects/P1/studio/prompts/context"):
        assert is_independent_studio_route("GET", path), path
    # Authoring is a deliberate, separately-admitted write surface (R3-W); the read
    # routes themselves remain GET-only. Undeclared methods and shapes stay refused.
    for method, path in (("PUT", "/api/projects/P1/studio/prompts"),
                         ("DELETE", "/api/projects/P1/studio/prompts"),
                         ("POST", "/api/projects/P1/studio/prompts/fam1"),
                         ("PUT", "/api/projects/P1/studio/prompts/fam1"),
                         ("DELETE", "/api/projects/P1/studio/prompts/fam1"),
                         ("GET", "/api/projects/P1/studio/prompts/a/b")):
        assert not is_independent_studio_route(method, path), (method, path)


# ------------------------------------------------------ route integration ---

@pytest.fixture
def rig(tmp_path, monkeypatch):
    """A real studio router over the real File store and the real asset owner."""
    root = Path(__file__).resolve().parents[1]
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.creative.bible_workspace import BibleWorkspaceService
    from app.creative.prompt_workspace import PromptWorkspaceService
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.experimental.world import WorldService
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.asset_library_service import AssetLibraryService

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "round3-prompt-" + uuid4().hex
    novels.create({"id": nid, "title": "Round3 prompts"})
    novels.upsert_character(nid, "c1", {"name": "林向晚"})
    raw = ExperimentalStore(tmp_path, "file", "")
    creative = CreativeService(raw, novels, chapters)
    assets = AssetLibraryService(tmp_path)
    workspace = IndependentWorkspaceService(
        creative, assets, ProductionLineageService(raw, novels, chapters, assets,
                                                   MediaService(raw, novels, chapters, assets)))
    bible = BibleWorkspaceService(workspace, WorldService(raw, novels, chapters))

    def authorize(project_id, token, branch, permission):
        if token != "valid-session":
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return "round3-author", {"mode": "local", "novel_id": project_id}

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("not used")),
        workspace_writer=lambda token: "round3-author",
        bible_service=bible, prompt_service=PromptWorkspaceService(workspace, bible)), prefix="/api")
    return SimpleNamespace(client=TestClient(app), nid=nid, assets=assets, workspace=workspace,
                           scope={"mode": "local", "novel_id": nid})


def _create_prompt(rig, body, text="a tall figure in the rain"):
    """Author a prompt asset through the EXISTING asset owner — no new store.

    The write happens inside the project's existing asset scope lease, because that
    lease is what installs the `_project_binding` the studio read path requires.
    Note: `ManualAssetImport.kind` is `image|video|audio` only, so there is **no
    studio HTTP route** that can create a text/prompt asset today — this helper is
    the service-level path, and that gap is reported honestly in the round report.
    """
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        created = rig.assets.create(rig.nid, "prompt.txt",
                                    base64.b64encode(text.encode()).decode(),
                                    media_type="text/plain", kind="prompt",
                                    required_features=("narrative_production_v2",))
        rig.assets.update_metadata(created["id"], {"parameters": {"prompt": body}},
                                   branch_id=rig.scope.get("branch_id"))
    return created


def test_prompt_library_route_projects_a_real_prompt_asset(rig):
    created = _create_prompt(rig, payload(character_ids=["c1"], scene_ids=["l-missing"]))
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                              headers={"x-session-token": "valid-session"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contract"] == "studio-prompt-library/1"
    assert body["advisory_only"] is True and body["execution_authority"] is False
    assert body["prompt_count"] == 1
    entry = body["entries"][0]
    assert entry["head_asset_id"] == created["id"]
    assert entry["revision"] == 1
    assert [row["value"] for row in entry["fields"] if row["field"] == "text"] == ["a tall figure in the rain"]
    characters = {row["id"]: row["resolution"] for row in entry["bindings"]["characters"]}
    assert characters == {"c1": "KNOWN"}
    assert "l-missing" in entry["unresolved_bindings"]


def test_prompt_library_is_empty_for_a_project_without_prompts(rig):
    body = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                          headers={"x-session-token": "valid-session"}).json()
    assert body["prompt_count"] == 0 and body["entries"] == []


def test_prompt_detail_route_and_unknown_family(rig):
    _create_prompt(rig, payload(family_id="fam-x"))
    ok = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts/fam-x",
                        headers={"x-session-token": "valid-session"})
    assert ok.status_code == 200 and ok.json()["contract"] == "studio-prompt-detail/1"
    missing = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts/nope",
                             headers={"x-session-token": "valid-session"})
    assert missing.status_code == 404


def test_prompt_context_route_never_composes_text(rig):
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts/context?character_id=c1",
                              headers={"x-session-token": "valid-session"})
    assert response.status_code == 200
    body = response.json()
    assert body["composes_prompt_text"] is False
    assert body["requires_user_confirmation"] is True


def test_prompt_routes_require_authority_and_are_get_only(rig):
    assert rig.client.get(f"/api/projects/{rig.nid}/studio/prompts").status_code == 403
    spec = rig.client.get("/openapi.json").json()
    assert set(spec["paths"]["/api/projects/{nid}/studio/prompts"]) == {"get"}
    assert set(spec["paths"]["/api/projects/{nid}/studio/prompts/{family_id}"]) == {"get"}
    assert set(spec["paths"]["/api/projects/{nid}/studio/prompts/context"]) == {"get"}
