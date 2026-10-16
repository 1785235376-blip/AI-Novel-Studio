"""Opt-in mounted adaptation scenario for the existing owned CPU harness.

Synthetic project/session authority only; the provider output is genuine and is
never replaced, repaired or retried. This does not certify literary quality.
"""
import hashlib
import time

SOURCE = "A visitor pauses at the doorway. A lamp lights the empty study."


def archive_authority(proposal, job):
    # Adaptation authority belongs to the original typed binding. The generic
    # Job actor/scope fields can legitimately be absent on this author path.
    binding = job.adaptation_binding
    assert (binding["proposal_id"] == proposal["id"] and binding["project_id"] == proposal["novel_id"]
        and binding["scope"] == proposal["scope"] and binding["actor_id"] == proposal["created_by"])
    return binding["scope"], binding["actor_id"]


def run(root, api, client, headers, nid, route, outcome):
    from app.dependencies import asset_library_service
    from app.experimental.api import independent_workspace_service
    from app.jobs import jobs
    from scripts.run_v2_real_text_check import write_json
    prefix = f"/api/novels/{nid}"
    chapter = api("POST", prefix + "/chapters", {"title": "Saved synthetic source", "content": SOURCE}, 201)
    original = api("GET", f'/api/chapters/{chapter["id"]}')
    base = prefix + "/experimental/creative"
    proposal = api("POST", base + "/adaptation-proposals", {
        "chapter_id": chapter["id"], "expected_source_version": original["version"],
        "title": "Owned real CPU adaptation", "instruction": "Use one short scene and one VISUALIZATION change. Return only JSON, no fences."}, 201)
    path = base + "/adaptation-proposals/" + proposal["id"]
    preview = api("POST", path + "/preview", {"expected_version": proposal["version"],
        "route_id": route["route_id"], "allow_synthetic": False})
    assert preview["model_preview"]["execution_available"] and not jobs.jobs
    assert preview["model_preview"]["asset_archive"]["mandatory"]
    payload = {"expected_version": preview["version"],
        "reviewed_preview_digest": preview["model_preview"]["preview_digest"]}
    started = time.monotonic()
    outcome["real_inference"] = "DISPATCH_ATTEMPTED_OUTCOME_UNCONFIRMED"
    running = api("POST", path + "/dispatch", payload)
    job_id = running["model_execution"]["job_id"]
    assert api("POST", path + "/dispatch", payload)["model_execution"]["job_id"] == job_id
    job = jobs.get(job_id)
    deadline = started + 180
    while time.monotonic() < deadline:
        result = api("GET", path)
        if job.status in jobs.terminal and job.terminal_hook_status is not None:
            # Original GET converges archive safely; a second observed read may
            # be needed if the worker crossed terminal publication mid-read.
            if result.get("asset_output", {}).get("asset_id") or job.status != "COMPLETED":
                break
        time.sleep(.2)
    else:
        raise AssertionError("ORIGINAL_180_SECOND_EXECUTION_BOUND_EXCEEDED")
    write_json(root / "original-job.json", job.public())
    assert job.execution_mode == "real" and job.status == "COMPLETED" and job.output.strip(), job.public()
    outcome["real_inference"] = "PASS"
    assert job.terminal_hook_status == "COMPLETED" and len(jobs.jobs) == 1
    draft = result["asset_output"]
    assert draft["state"] == "DRAFT" and draft["version"] == 1, result
    receipt = draft["execution_receipt"]
    assert receipt["execution_mode"] == "real" and receipt["quality_verification"] == "NOT_RUN"
    scope, actor = archive_authority(result, job)
    with independent_workspace_service._asset_scope(nid, scope):
        content = asset_library_service.content(draft["asset_id"], actor_id=actor)
        assert len(asset_library_service.list(nid, actor_id=actor)) == 1
    assert content == job.output.encode()
    (root / "actual-model-output.txt").write_bytes(content)
    write_json(root / "draft-asset.json", draft)
    write_json(root / "adaptation-result.json", result)
    outcome["real_adaptation_archive"] = {"state": "PASS", "asset_id": draft["asset_id"],
        "raw_sha256": hashlib.sha256(content).hexdigest(), "proposal_status": result["status"],
        "source_unchanged": api("GET", f'/api/chapters/{chapter["id"]}') == original,
        "automatic_replay": False, "elapsed_seconds": time.monotonic() - started}
    assert outcome["real_adaptation_archive"]["source_unchanged"]
    assert not api("GET", base + "/documents")["items"]
    # Preserve invalid genuine JSON as a private draft, never synthesize scenes.
    assert result["status"] == "NEEDS_REVIEW", "REAL_MODEL_STRUCTURED_OUTPUT_REJECTED; original raw draft retained"
    for _ in range(2):
        assert api("GET", path)["asset_output"] == draft
    assert len(jobs.jobs) == 1
    # This is an explicit test-client review operation, not human quality approval.
    reviewed = api("POST", path + "/review", {"expected_version": result["version"],
        "reviewed_output_digest": result["output_digest"], "title": result["title"], "output": result["output"]})
    approved = reviewed["proposal"]["asset_output"]
    assert approved["asset_id"] == draft["asset_id"] and approved["version"] == 2 and approved["state"] == "APPROVED"
    assert reviewed["document"]["mode"] == "SCREENPLAY" and reviewed["document"]["version"] == 1
    assert api("GET", f'/api/chapters/{chapter["id"]}') == original and len(jobs.jobs) == 1
    write_json(root / "approved-asset.json", approved)
    return {"project_id": nid, "proposal_id": proposal["id"], "job_id": job_id,
        "asset_id": draft["asset_id"], "asset_versions": [1, 2], "document_id": reviewed["document"]["id"],
        "execution_mode": "real", "automatic_replay": False, "manuscript_changed": False,
        "review_authority": "EXPLICIT_TEST_CLIENT_OPERATION_NOT_HUMAN_QUALITY_REVIEW",
        "quality_verification": "NOT_RUN", "browser": "NOT_RUN", "project_data_retained": True}
