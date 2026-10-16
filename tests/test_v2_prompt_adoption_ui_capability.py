"""Additive adoption UI capability through original mounted File/PG owners.

Only the process-local module switch is patched. Real identity, membership,
authorization, Asset review, CreativeDocument CAS and persistence stay intact.
"""
from copy import deepcopy

import pytest

from test_round3i_http_authorized import _chain
from test_v2_private_prompt_lifecycle import checked, mounted, prefix, prompts, retirement


@pytest.fixture(autouse=True)
def current_original_phase_owner(prompts, monkeypatch):
    # The mounted fixture rebinds the singleton workspace to a fresh real store
    # for every case. Drop only the lazily cached phase adapter from the prior
    # fixture; its original factory must bind this case's actual owner instead.
    monkeypatch.setattr(prompts.experimental.studio_prompt_adoption_service, "_inputs", None)


def flow(e):
    return _chain(e, e.prefix, e.activate(e.lead, branch=e.branch))


def headers(e, actor=None, **extra):
    return {**e.activate(actor or e.lead, branch=e.branch), **extra}


def stored(e):
    return {"scope": deepcopy(e.store.read(e.nid, e.scope)),
            "assets": {path.name: path.read_bytes() for path in e.assets.root.iterdir()
                       if path.is_file() and path.suffix in {".json", ".bin"}}}


def exact_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["detail"]["code"] == code, response.text


@pytest.mark.parametrize("enabled", [False, True])
def test_get_projects_only_current_process_capability_without_owner_mutation(prompts, monkeypatch, enabled):
    from app.creative import prompt_adoption_api
    e = prompts
    f = flow(e)
    before = stored(e)
    with monkeypatch.context() as patch:
        patch.setattr(prompt_adoption_api, "PROMPT_ADOPTION_WRITE_ENABLED", enabled)
        projection = checked(e.client.get(f["read_url"], headers=headers(e)))
        assert projection["write_enabled"] is enabled
        assert type(projection["write_enabled"]) is bool
        assert projection["contract"] == "prompt-adoption/1"
        assert projection["document_id"] == f["board"]["id"]
        assert projection["version"] == f["target"]["version"]
        assert projection["digest"] == f["target"]["digest"]
        assert projection["adoptions"] == []
        assert stored(e) == before
    assert prompt_adoption_api.PROMPT_ADOPTION_WRITE_ENABLED is False


def test_client_fields_query_and_headers_cannot_open_closed_adoption(prompts):
    from app.creative import prompt_adoption_api
    e = prompts
    assert prompt_adoption_api.PROMPT_ADOPTION_WRITE_ENABLED is False
    f = flow(e)
    before = stored(e)
    claimed = headers(e, **{"X-Prompt-Adoption-Write-Enabled": "true", "X-Write-Enabled": "true"})
    projection = checked(e.client.get(f["read_url"], headers=claimed, params={"write_enabled": "true"}))
    assert projection["write_enabled"] is False
    refused = e.client.post(f["adopt_url"], headers=claimed,
                            params={"write_enabled": "true"}, json=f["dto"])
    exact_error(refused, 503, "PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED")
    extra = e.client.post(f["adopt_url"], headers=claimed, json={**f["dto"], "write_enabled": True})
    assert extra.status_code == 422, extra.text
    assert any(row["loc"] == ["body", "write_enabled"] and row["type"] == "extra_forbidden"
               for row in extra.json()["detail"])
    assert stored(e) == before
    assert prompt_adoption_api.PROMPT_ADOPTION_WRITE_ENABLED is False


@pytest.mark.parametrize("enabled", [False, True])
def test_original_read_and_write_authorization_precedes_capability(prompts, monkeypatch, enabled):
    from app.creative import prompt_adoption_api
    e = prompts
    f = flow(e)
    before = stored(e)
    with monkeypatch.context() as patch:
        patch.setattr(prompt_adoption_api, "PROMPT_ADOPTION_WRITE_ENABLED", enabled)
        exact_error(e.client.get(f["read_url"]), 401, "SESSION_REQUIRED")
        exact_error(e.client.post(f["adopt_url"], json=f["dto"]), 401, "SESSION_REQUIRED")
        viewer = checked(e.client.get(f["read_url"], headers=headers(e, e.viewer)))
        assert viewer["write_enabled"] is enabled
        # The global capability is not a new permission grant to this reader.
        exact_error(e.client.post(f["adopt_url"], headers=headers(e, e.viewer), json=f["dto"]),
                    403, "PROJECT_SCOPE_FORBIDDEN")
        exact_error(e.client.get(f["read_url"], headers=headers(e, e.new_actor)),
                    403, "PROJECT_SCOPE_FORBIDDEN")
        exact_error(e.client.post(f["adopt_url"], headers=headers(e, e.new_actor), json=f["dto"]),
                    403, "PROJECT_SCOPE_FORBIDDEN")
        assert stored(e) == before
    assert prompt_adoption_api.PROMPT_ADOPTION_WRITE_ENABLED is False


def test_explicit_process_enable_uses_original_commit_and_exact_replay(prompts, monkeypatch):
    from app.creative import prompt_adoption_api
    e = prompts
    f = flow(e)
    with monkeypatch.context() as patch:
        patch.setattr(prompt_adoption_api, "PROMPT_ADOPTION_WRITE_ENABLED", True)
        assert checked(e.client.get(f["read_url"], headers=headers(e)))["write_enabled"] is True
        result = checked(e.client.post(f["adopt_url"], headers=headers(e), json=f["dto"]))
        assert result["committed"] is True and result["replayed"] is False
        assert result["version"] == f["target"]["version"] + 1
        proof = result["adoption"]
        assert proof["target_version"] == f["target"]["version"]
        assert proof["target_digest"] == f["target"]["digest"]
        assert proof["result_version"] == result["version"]
        assert (proof["family_id"], proof["asset_id"], proof["revision"], proof["digest"]) == (
            f["prompt"]["family_id"], f["prompt"]["asset_id"], f["prompt"]["revision"], f["source"]["digest"])
        assert proof["source_bindings_verified"] is True
        document = checked(e.client.get(f["creative"] + "/documents/" + f["board"]["id"], headers=headers(e)))
        assert next(row for row in document["shots"] if row["id"] == f["shot_id"])["frame_prompt"] == f["source"]["value"]
        projected = checked(e.client.get(f["read_url"], headers=headers(e)))
        assert projected["write_enabled"] is True
        assert projected["version"] == result["version"] and projected["digest"] == result["digest"]
        assert len(projected["adoptions"]) == 1 and projected["adoptions"][0]["still_applied"] is True
        committed = stored(e)
        replay = checked(e.client.post(f["adopt_url"], headers=headers(e), json=f["dto"]))
        assert replay["committed"] is True and replay["replayed"] is True
        assert replay["version"] == result["version"] and replay["adoption"] == proof
        assert stored(e) == committed
    assert prompt_adoption_api.PROMPT_ADOPTION_WRITE_ENABLED is False
    assert checked(e.client.get(f["read_url"], headers=headers(e)))["write_enabled"] is False
    exact_error(e.client.post(f["adopt_url"], headers=headers(e), json=f["dto"]),
                503, "PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED")
    assert stored(e) == committed
