"""Provider cost attestation: trusted only when bound to one exact completed job."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from test_studio_backend_integration_v2 import execute, queue, request, studio
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


def create_job(e):
    prepared = request(e)
    row, _ = queue(e, prepared)
    row = execute(e, row)
    return row


def attestation(row, **overrides):
    provider = row["provider"]
    value = {
        "contract": "studio-provider-cost-attestation/1",
        "job_id": row["id"],
        "owner": "image",
        "request_digest": row["request_digest"],
        "provider_id": provider["provider_id"],
        "model_id": provider["model_id"],
        "currency": "USD",
        "actual_microusd": 12345,
        "usage": [{"name": "images", "value": 1}, {"name": "gpu_ms", "value": 500}],
        "pricing_version": "synthetic-price-v1",
        "source": "PROVIDER_ADAPTER",
        "attested_at": datetime.now(timezone.utc).isoformat(),
    }
    value.update(overrides)
    return value


def view(e, row):
    return e.production.get(e.nid, e.scope, e.actor, "image", row["id"], lambda: None)


def sidecar(e, job_id):
    return Path(e.workspace.store.root) / "runtime" / "provider-cost-attestations" / "image" / (job_id + ".json")


def test_attested_cost_is_trusted_and_bound_to_exact_job(studio):
    e = studio
    row = create_job(e)
    assert view(e, row)["cost"]["state"] == "UNKNOWN"
    assert view(e, row)["cost"]["trusted"] is False
    receipt = e.production.record_cost_attestation(
        e.nid, e.scope, e.actor, "image", row["id"], attestation(row), lambda: None)
    assert receipt["contract"] == "studio-provider-cost-attestation-receipt/1"
    assert receipt["trusted"] is True
    cost = view(e, row)["cost"]
    assert cost["contract"] == "studio-job-cost/1"
    assert cost["state"] == "ATTESTED" and cost["trusted"] is True
    assert cost["currency"] == "USD" and cost["actual_microusd"] == 12345
    assert cost["linkage"] == "PROVIDER_ADAPTER"
    assert cost["estimated_microusd"] is None and cost["accounted_microusd"] is None
    assert cost["fabricated"] is False and cost["decision_required"] is False
    assert cost["pricing_version"] == "synthetic-price-v1"
    assert {entry["name"]: entry["value"] for entry in cost["usage"]} == {"images": 1, "gpu_ms": 500}


def test_attestation_mismatches_and_invalid_values_are_rejected(studio):
    e = studio
    row = create_job(e)
    with pytest.raises(ValueError, match="STUDIO_COST_ATTESTATION_REQUEST_MISMATCH"):
        e.production.record_cost_attestation(
            e.nid, e.scope, e.actor, "image", row["id"],
            attestation(row, request_digest="a" * 64), lambda: None)
    with pytest.raises(ValueError, match="STUDIO_COST_ATTESTATION_PROVIDER_MISMATCH"):
        e.production.record_cost_attestation(
            e.nid, e.scope, e.actor, "image", row["id"],
            attestation(row, provider_id="other-provider"), lambda: None)
    with pytest.raises(ValidationError):
        e.production.record_cost_attestation(
            e.nid, e.scope, e.actor, "image", row["id"],
            attestation(row, actual_microusd=-1), lambda: None)
    with pytest.raises(ValidationError):
        e.production.record_cost_attestation(
            e.nid, e.scope, e.actor, "image", row["id"],
            attestation(row, source="HTTP_CLIENT_CLAIM"), lambda: None)
    with pytest.raises(ValueError, match="STUDIO_COST_ATTESTATION_AUTHORITY_REQUIRED"):
        e.production.record_cost_attestation(
            e.nid, e.scope, "", "image", row["id"], attestation(row), lambda: None)
    assert view(e, row)["cost"]["state"] == "UNKNOWN"
    assert not sidecar(e, row["id"]).exists()


def test_corrupt_or_orphan_sidecar_never_claims_trusted_cost(studio):
    e = studio
    row = create_job(e)
    e.production.record_cost_attestation(
        e.nid, e.scope, e.actor, "image", row["id"], attestation(row), lambda: None)
    assert view(e, row)["cost"]["state"] == "ATTESTED"
    path = sidecar(e, row["id"])
    assert path.exists()
    path.write_text("{not-json", encoding="utf-8")
    assert view(e, row)["cost"]["state"] == "UNKNOWN"
    assert view(e, row)["cost"]["trusted"] is False
    path.write_text("x" * (16 * 1024 + 1), encoding="utf-8")
    assert view(e, row)["cost"]["state"] == "UNKNOWN"
    path.unlink()
    # A sidecar for another job never affects this job.
    other_path = sidecar(e, "some-other-job")
    other_path.parent.mkdir(parents=True, exist_ok=True)
    other_path.write_text("{}", encoding="utf-8")
    assert view(e, row)["cost"]["state"] == "UNKNOWN"


def usage_attestation(row, **overrides):
    provider = row["provider"]
    value = {
        "contract": "studio-provider-usage-attestation/1",
        "job_id": row["id"],
        "owner": "image",
        "request_digest": row["request_digest"],
        "provider_id": provider["provider_id"],
        "model_id": provider["model_id"],
        "usage": [{"name": "images", "value": 2}, {"name": "gpu_ms", "value": 900}],
        "source": "PROVIDER_ADAPTER",
        "attested_at": datetime.now(timezone.utc).isoformat(),
    }
    value.update(overrides)
    return value


def test_usage_only_attestation_keeps_price_unknown(studio):
    e = studio
    row = create_job(e)
    receipt = e.production.record_usage_attestation(
        e.nid, e.scope, e.actor, "image", row["id"], usage_attestation(row), lambda: None)
    assert receipt["contract"] == "studio-provider-usage-attestation/1"
    assert receipt["trusted"] is True and receipt["pricing"] == "UNKNOWN"
    cost = view(e, row)["cost"]
    assert cost["state"] == "USAGE_ATTESTED" and cost["trusted"] is True
    assert cost["currency"] is None and cost["actual_microusd"] is None
    assert cost["estimated_microusd"] is None and cost["accounted_microusd"] is None
    assert cost["linkage"] == "PROVIDER_ADAPTER"
    assert cost["reason"] == "PROVIDER_USAGE_ATTESTED_PRICING_UNKNOWN"
    assert cost["decision_required"] is True
    assert {entry["name"]: entry["value"] for entry in cost["usage"]} == {"images": 2, "gpu_ms": 900}
    assert cost["pricing_version"] is None
    # A priced attestation supersedes the usage-only record.
    e.production.record_cost_attestation(
        e.nid, e.scope, e.actor, "image", row["id"], attestation(row), lambda: None)
    priced = view(e, row)["cost"]
    assert priced["state"] == "ATTESTED" and priced["actual_microusd"] == 12345


def test_usage_attestation_mismatches_are_rejected(studio):
    e = studio
    row = create_job(e)
    with pytest.raises(ValueError, match="STUDIO_USAGE_ATTESTATION_REQUEST_MISMATCH"):
        e.production.record_usage_attestation(
            e.nid, e.scope, e.actor, "image", row["id"],
            usage_attestation(row, request_digest="b" * 64), lambda: None)
    with pytest.raises(ValueError, match="STUDIO_USAGE_ATTESTATION_PROVIDER_MISMATCH"):
        e.production.record_usage_attestation(
            e.nid, e.scope, e.actor, "image", row["id"],
            usage_attestation(row, provider_id="other-provider"), lambda: None)
    with pytest.raises(ValueError, match="STUDIO_USAGE_ATTESTATION_USAGE_REQUIRED"):
        e.production.record_usage_attestation(
            e.nid, e.scope, e.actor, "image", row["id"],
            usage_attestation(row, usage=[]), lambda: None)
    assert view(e, row)["cost"]["state"] == "UNKNOWN"

