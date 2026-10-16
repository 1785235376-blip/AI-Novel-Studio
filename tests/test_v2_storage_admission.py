"""Bounded M1 storage admission over the real asset owner, File and PostgreSQL."""
import errno
from uuid import UUID
from types import SimpleNamespace

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace import rig, decoders, upload, import_asset, asset_files, png_bytes
from test_v2_independent_workspace_api import client, upload_body


def disk(monkeypatch, rig, free):
    import app.creative.storage_admission as module
    seen = []
    def measure(path):
        seen.append(path)
        assert path == rig.assets.root
        return SimpleNamespace(free=free)
    monkeypatch.setattr(module.shutil, "disk_usage", measure)
    return seen


def test_admission_measures_only_original_asset_filesystem_and_exposes_no_paths(rig, monkeypatch):
    reserve = rig.service.storage_admission.RESERVE_BYTES
    seen = disk(monkeypatch, rig, reserve + 1000)
    result = rig.service.storage(rig.nid, rig.scope)
    admission = result["admission"]
    assert seen == [rig.assets.root]
    assert admission["state"] == "READY" and admission["available_import_bytes"] == 1000
    assert admission["reserve_bytes"] == reserve
    assert not admission["external_model_scan"] and not admission["automatic_cleanup"] and not admission["automatic_migration"]
    assert str(rig.root) not in str(result)
    monkeypatch.setattr(rig.service, "MAX_PROJECT_BYTES", 13)
    assert rig.service.storage(rig.nid, rig.scope)["admission"]["available_import_bytes"] == 13


@pytest.mark.parametrize("free", [0, 1, 64 * 1024 * 1024])
def test_low_disk_rejects_before_any_binary_or_metadata_write(rig, decoders, monkeypatch, free):
    from app.creative.storage_admission import StudioStorageCapacityError
    unrelated = rig.root / "model-reference.gguf"
    unrelated.write_bytes(b"owned untouched reference fixture")
    before = asset_files(rig)
    disk(monkeypatch, rig, free)
    with pytest.raises(StudioStorageCapacityError, match="CREATIVE_STORAGE_LOW_SPACE"):
        import_asset(rig)
    assert asset_files(rig) == before
    assert unrelated.read_bytes() == b"owned untouched reference fixture"
    assert rig.chapters.list(rig.nid) == []


def test_disk_exhaustion_after_staging_cleans_only_new_uncommitted_binary(rig, decoders, monkeypatch):
    import app.creative.storage_admission as module
    from app.creative.storage_admission import StudioStorageCapacityError
    existing = import_asset(rig)
    before = asset_files(rig)
    remaining = iter([module.StudioStorageAdmission.RESERVE_BYTES + 1000,
                      module.StudioStorageAdmission.RESERVE_BYTES])
    calls = []
    def measure(path):
        calls.append(path)
        if len(calls) == 2:
            assert len(list(rig.assets.root.glob("*.tmp"))) == 1
        return SimpleNamespace(free=next(remaining))
    monkeypatch.setattr(module.shutil, "disk_usage", measure)
    with pytest.raises(StudioStorageCapacityError, match="CREATIVE_STORAGE_LOW_SPACE"):
        import_asset(rig)
    assert len(calls) == 2 and asset_files(rig) == before
    assert rig.service.download(rig.nid, rig.scope, existing["id"])[1] == png_bytes()


def test_committed_idempotent_retry_requires_no_new_disk_allocation(rig, decoders, monkeypatch):
    import app.creative.storage_admission as module
    value = upload(key="repeat-committed")
    first = rig.service.import_asset(rig.nid, rig.scope, rig.actor, value)
    before = asset_files(rig)
    def forbidden(path):
        pytest.fail("A committed idempotent return must not allocate or require new disk space")
    monkeypatch.setattr(module.shutil, "disk_usage", forbidden)
    assert rig.service.import_asset(rig.nid, rig.scope, rig.actor, value) == first
    assert asset_files(rig) == before


@pytest.mark.parametrize("failure", [OSError("private volume unavailable"), SimpleNamespace(free=-1), SimpleNamespace(free=True)])
def test_unavailable_disk_fails_closed_without_private_filesystem_details(rig, monkeypatch, failure):
    import app.creative.storage_admission as module
    from app.creative.storage_admission import StudioStorageCapacityError
    def measure(path):
        if isinstance(failure, Exception):
            raise failure
        return failure
    monkeypatch.setattr(module.shutil, "disk_usage", measure)
    admission = rig.service.storage(rig.nid, rig.scope)["admission"]
    assert admission["state"] == "UNAVAILABLE" and admission["available_import_bytes"] is None
    with pytest.raises(StudioStorageCapacityError, match="^CREATIVE_STORAGE_UNAVAILABLE$"):
        rig.service.storage_admission.require(1)


def test_real_enospc_metadata_failure_preserves_existing_owner_assets(rig, decoders, monkeypatch):
    from app.creative.storage_admission import StudioStorageCapacityError
    first = import_asset(rig)
    before = asset_files(rig)
    def exhausted(row):
        raise OSError(errno.ENOSPC, "private device detail")
    monkeypatch.setattr(rig.assets, "_write_meta", exhausted)
    with pytest.raises(StudioStorageCapacityError, match="^CREATIVE_STORAGE_LOW_SPACE$"):
        import_asset(rig)
    assert asset_files(rig) == before
    assert rig.service.download(rig.nid, rig.scope, first["id"])[1] == png_bytes()


def test_mounted_low_space_is_507_no_private_path_or_partial_import(client, monkeypatch):
    import app.creative.storage_admission as module
    e = client
    monkeypatch.setattr(module.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    response = e.client.post(e.studio_base + "/assets", json=upload_body())
    assert response.status_code == 507
    payload = response.json()
    assert set(payload) == {"detail", "code", "details", "message", "request_id"}
    assert payload["detail"] == payload["details"] == {"code": "CREATIVE_STORAGE_LOW_SPACE"}
    assert payload["code"] == payload["message"] == "CREATIVE_STORAGE_LOW_SPACE"
    assert str(UUID(payload["request_id"])) == payload["request_id"]
    assert response.headers["cache-control"] == "no-store"
    assert list(e.assets.root.glob("*.json")) == list(e.assets.root.glob("*.bin")) == []
    assert checked(e.client.get(e.studio_base + "/storage"))["admission"]["state"] == "LOW_SPACE_OR_QUOTA"


def test_late_storage_error_rechecks_revoke_instead_of_disclosing_capacity(client, monkeypatch):
    import app.creative.storage_admission as module
    e = scoped(client, monkeypatch)
    def revoke(path):
        e.sessions.revoke(e.lead)
        return SimpleNamespace(free=0)
    monkeypatch.setattr(module.shutil, "disk_usage", revoke)
    response = e.client.post(e.studio_base + "/assets", headers=e.headers, json=upload_body())
    assert response.status_code == 401 and "CREATIVE_STORAGE" not in response.text
    assert list(e.assets.root.glob("*.json")) == list(e.assets.root.glob("*.bin")) == []
