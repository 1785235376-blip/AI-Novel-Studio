"""Mounted original trim DTO/candidate/review path with synthetic MP3 bytes."""
import hashlib

from test_v2_audio_wav_controls_api import audio_client, client, checked, command, snapshot, action, run
from test_v2_independent_workspace import rig
from test_r3_mounted_contracts import mounted, prefix


def test_mounted_mp3_candidate_and_explicit_review_keep_actual_mime(audio_client):
    e = audio_client
    e.command = command(snapshot(e.source), output_format="MP3", sample_rate=22050, channels=1)
    preview = checked(e.client.post(e.base + "/preview", headers=e.headers, json=e.command))
    assert preview["execution_recipe"]["output_profile"] == "MP3_LIBMP3LAME_22050_MONO_CBR64"
    queued = checked(e.client.post(e.base + "/jobs", headers=e.headers,
        json={"command": e.command, "reviewed_preview_digest": preview["preview_digest"]}), 201)
    executed = checked(run(e, queued)); assert executed["status"] == "AWAITING_REVIEW", executed
    asset, measured = executed["output_candidate"], executed["media_measurement"]
    response = e.client.get(e.base + "/jobs/audio/" + queued["id"] + "/candidate", headers=e.headers)
    assert response.status_code == 200 and response.headers["content-type"].startswith("audio/mpeg")
    assert measured["container"] == "mp3" and measured["profile_validation"] == "MP3_GAPLESS_PCM_VERIFIED"
    assert hashlib.sha256(response.content).hexdigest() == measured["output_sha256"] == response.headers["x-asset-sha256"]
    assert len(response.content) == measured["byte_count"]
    assert response.headers["cache-control"] == "no-store" and response.headers["x-content-type-options"] == "nosniff"
    assert e.client.get(e.studio_base + "/assets/" + asset["id"], headers=e.headers).status_code == 404
    approved = checked(e.client.post(e.base + "/jobs/audio/" + queued["id"] + "/review", headers=e.headers,
        json={**action(executed), "reviewed_output_digest": asset["digest"]}))
    assert approved["status"] == "APPROVED" and approved["media_measurement"] == measured
    formal = checked(e.client.get(e.studio_base + "/assets/" + asset["id"], headers=e.headers))
    assert formal["media_type"] == "audio/mpeg" and formal["version"] == 2
    assert checked(e.client.get(e.base + "/jobs/audio/" + queued["id"], headers=e.headers)) == approved
