"""Motion-frame remote reference and cloud approval trust-boundary tests.

Evidence for the "motion frame remote reference" concern on the current
candidate: this backend never fetches a remote frame URL itself. Local/IP
destinations are validated with the shared outbound-destination guard (including
DNS-rebinding rejection); arbitrary public hostnames remain opaque references
that are only forwarded to the configured server-side video provider. The cloud
approval digest binds provider endpoint, provider/model ids, prompt, frames,
constraints and media owner, so an endpoint/model change after review fails
closed before the provider boundary.

Residual risk is explicitly not claimed as an exploit: provider-side fetching of
a client-supplied URL is outside this backend's network/credential boundary.
"""
from __future__ import annotations

import hashlib
import socket

import pytest

from app.media_files import OutboundURLRejected, media_destination
from app.services.screenplay_service import ScreenplayService
from app.media_frames import provider_is_local, resolve_motion_frame
from types import SimpleNamespace


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_remote_frame_reference_is_opaque_and_performs_no_dns_or_fetch(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the backend must not resolve or fetch a remote frame reference")
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    value, source = resolve_motion_frame(
        "https://example.com/frames/f-1.png",
        {"shots": [], "storyboard": []}, "novel", SimpleNamespace(endpoint="https://cloud.example"), None)
    assert value == "https://example.com/frames/f-1.png"
    assert source == {"kind": "REMOTE_REFERENCE", "content_verified": False}
    assert set(source) == {"kind", "content_verified"}


@pytest.mark.parametrize("url", [
    "https://user:pass@example.com/f.png",
    "https://example.com/f.png#fragment",
    "https:///no-host.png",
])
def test_remote_frame_rejects_credentials_fragments_and_missing_host(url):
    with pytest.raises(ValueError):
        resolve_motion_frame(url, {"shots": [], "storyboard": []}, "novel",
                             SimpleNamespace(endpoint="https://cloud.example"), None)


def test_loopback_remote_frame_must_match_configured_local_provider(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 0))])
    local = SimpleNamespace(endpoint="http://127.0.0.1:8188")
    value, source = resolve_motion_frame("http://127.0.0.1:8188/frame.png",
                                         {"shots": [], "storyboard": []}, "novel", local, None)
    assert value == "http://127.0.0.1:8188/frame.png" and source["kind"] == "REMOTE_REFERENCE"
    # Another loopback port is still a different origin: no piggybacking on the
    # configured local provider's trust.
    with pytest.raises(OutboundURLRejected):
        resolve_motion_frame("http://127.0.0.1:9999/frame.png",
                             {"shots": [], "storyboard": []}, "novel", local, None)


def test_outbound_destination_rejects_dns_rebinding_to_private_addresses(monkeypatch):
    # Public-looking hostname resolves to a private address after the check
    # starts: the resolved addresses decide, so rebinding fails closed.
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *args, **kwargs: [(2, 1, 6, "", ("10.0.0.9", 0))])
    with pytest.raises(OutboundURLRejected):
        media_destination("https://public.example/frame.png", None)
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))])
    parsed, origin, address = media_destination("https://public.example/frame.png", None)
    assert parsed.hostname == "public.example" and address == "93.184.216.34"


def test_local_provider_is_not_mistaken_for_cloud():
    assert provider_is_local(SimpleNamespace(endpoint="http://127.0.0.1:8188"))
    assert provider_is_local(SimpleNamespace(endpoint="http://localhost:8188"))
    assert provider_is_local(SimpleNamespace(endpoint="http://192.168.1.20:8188"))
    assert not provider_is_local(SimpleNamespace(endpoint="https://cloud.example"))
    assert not provider_is_local(SimpleNamespace(endpoint="http://169.254.169.254"))


def screenplay_doc():
    return {"id": "sp-1", "novel_id": "novel-1", "branch_id": None, "actor_id": "author",
            "owner_actor_id": "author", "workspace_id": "ws", "owner": {"kind": "local"},
            "privacy_level": "CLOUD_ALLOWED", "scenes": [], "shots": [], "storyboard": [],
            "transitions": []}


def cloud_task(endpoint):
    service = ScreenplayService(novels=object(), chapters=object(),
                                video_providers={"cloud": SimpleNamespace(endpoint=endpoint)})
    prompt = "synthetic motion"
    task = {"id": "task-1", "transition_id": "tr-1", "provider_id": "cloud", "model_id": "m-1",
            "prompt": prompt, "start_frame": "https://example.com/a.png",
            "end_frame": "asset:asset-1", "constraints": {"fps": 24},
            "privacy_level": "CLOUD_ALLOWED"}
    screenplay = screenplay_doc()
    task["cloud_approval_prompt_sha256"] = sha(prompt)
    task["cloud_approval_provider_id"] = "cloud"
    task["cloud_approval_model_id"] = "m-1"
    task["cloud_approval_request_sha256"] = service._motion_request_digest(task, screenplay, "novel-1")
    return service, screenplay, task


def test_cloud_review_digest_binds_provider_endpoint_frames_and_owner(monkeypatch):
    monkeypatch.setattr("app.source_privacy.assert_project_source_policies", lambda *args: None)
    service, screenplay, task = cloud_task("https://cloud.example")
    service._require_motion_review(task, service.video_providers["cloud"], screenplay, "novel-1")
    baseline = service._motion_request_digest(task, screenplay, "novel-1")
    # Endpoint changed server-side after the review: the digest no longer
    # matches and execution must be re-reviewed before the provider boundary.
    service.video_providers["cloud"] = SimpleNamespace(endpoint="https://other.example")
    assert service._motion_request_digest(task, screenplay, "novel-1") != baseline
    with pytest.raises(ValueError, match="VIDEO_CLOUD_PROMPT_REVIEW_REQUIRED"):
        service._require_motion_review(task, service.video_providers["cloud"], screenplay, "novel-1")
    # Frame, constraint and media-owner changes are also bound.
    service.video_providers["cloud"] = SimpleNamespace(endpoint="https://cloud.example")
    changed = {**task, "end_frame": "asset:asset-2"}
    assert service._motion_request_digest(changed, screenplay, "novel-1") != baseline
    changed = {**task, "constraints": {"fps": 30}}
    assert service._motion_request_digest(changed, screenplay, "novel-1") != baseline
    changed = {**task, "prompt": "other prompt"}
    assert service._motion_request_digest(changed, screenplay, "novel-1") != baseline
    other_owner = {**screenplay, "owner_actor_id": "someone-else"}
    assert service._motion_request_digest(task, other_owner, "novel-1") != baseline
    # Unrelated task status fields are not part of the approval binding.
    assert service._motion_request_digest({**task, "status": "FAILED", "error": "x"},
                                          screenplay, "novel-1") == baseline


def test_cloud_review_rejects_unapproved_or_downgraded_tasks(monkeypatch):
    monkeypatch.setattr("app.source_privacy.assert_project_source_policies", lambda *args: None)
    service, screenplay, task = cloud_task("https://cloud.example")
    provider = service.video_providers["cloud"]
    for mutated in ({**task, "privacy_level": "LOCAL_ONLY"},
                    {**task, "cloud_approval_provider_id": "other"},
                    {**task, "cloud_approval_model_id": "m-2"},
                    {**task, "cloud_approval_prompt_sha256": "0" * 64},
                    {**task, "cloud_approval_request_sha256": "0" * 64}):
        with pytest.raises(ValueError):
            service._require_motion_review(mutated, provider, screenplay, "novel-1")


def test_local_provider_skips_cloud_review_without_claiming_cloud(monkeypatch):
    service = ScreenplayService(novels=object(), chapters=object(),
                                video_providers={"local": SimpleNamespace(endpoint="http://127.0.0.1:8188")})
    screenplay = screenplay_doc()
    task = {"provider_id": "local", "model_id": "local-model", "prompt": "p",
            "privacy_level": "LOCAL_ONLY"}
    service._require_motion_review(task, service.video_providers["local"], screenplay, "novel-1")
