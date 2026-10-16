"""Mounted original Host APIs and real tiny FLAC bytes, never model acceptance."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from test_v2_audio_wav_controls_api import audio_client, client, checked, command, snapshot, action, run
from test_v2_independent_workspace import rig
from test_r3_mounted_contracts import mounted, prefix


def queue_flac(e):
    e.command = command(snapshot(e.source), output_format="FLAC", sample_rate=22050, channels=1, gain_db=-6.020599913279624)
    preview = checked(e.client.post(e.base + "/preview", headers=e.headers, json=e.command))
    row = checked(e.client.post(e.base + "/jobs", headers=e.headers,
        json={"command": e.command, "reviewed_preview_digest": preview["preview_digest"]}), 201)
    return preview, row


def test_mounted_flac_proof_private_candidate_review_and_safe_capture(audio_client):
    e = audio_client; preview, queued = queue_flac(e)
    executed = checked(run(e, queued)); assert executed["status"] == "AWAITING_REVIEW", executed
    asset, measured = executed["output_candidate"], executed["media_measurement"]
    response = e.client.get(e.base + "/jobs/audio/" + queued["id"] + "/candidate", headers=e.headers)
    assert response.status_code == 200 and response.headers["content-type"].startswith("audio/flac")
    assert response.content[:4] == b"fLaC" and measured["container"] == "flac"
    assert hashlib.sha256(response.content).hexdigest() == measured["output_sha256"] == response.headers["x-asset-sha256"]
    assert len(response.content) == measured["byte_count"]
    assert response.headers["cache-control"] == "no-store" and response.headers["x-content-type-options"] == "nosniff"
    assert e.client.get(e.studio_base + "/assets/" + asset["id"], headers=e.headers).status_code == 404
    approved = checked(e.client.post(e.base + "/jobs/audio/" + queued["id"] + "/review", headers=e.headers,
        json={**action(executed), "reviewed_output_digest": asset["digest"]}))
    assert approved["status"] == "APPROVED" and approved["media_measurement"] == measured
    formal = checked(e.client.get(e.studio_base + "/assets/" + asset["id"], headers=e.headers))
    assert formal["media_type"] == "audio/flac" and formal["version"] == 2
    assert checked(e.client.get(e.base + "/jobs/audio/" + queued["id"], headers=e.headers)) == approved
    if os.environ.get("STUDIO_CAPTURE_AUDIO_FLAC"):
        root = Path(os.environ["STUDIO_CAPTURE_AUDIO_FLAC"]); root.mkdir(parents=True, exist_ok=True)
        for name, value in (("preview", preview), ("queued", queued), ("executed", executed), ("approved", approved), ("formal", formal)):
            # Original response DTO only: no Host token, paths or queue context.
            (root / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("fault", ["missing", "forged", "origin", "forwarded"])
def test_flac_keeps_original_trusted_host_boundary(audio_client, fault):
    e = audio_client
    e.command = command(snapshot(e.source), output_format="FLAC")
    headers = dict(e.headers)
    if fault == "missing": headers = {}
    elif fault == "forged": headers["X-Session-Token"] = "synthetic-untrusted"
    elif fault == "origin": headers["Origin"] = "https://untrusted.invalid"
    else: headers["X-Forwarded-For"] = "198.51.100.9"
    response = e.client.post(e.base + "/preview", headers=headers, json=e.command)
    assert response.status_code == (401 if fault in {"missing", "forged"} else 403)
