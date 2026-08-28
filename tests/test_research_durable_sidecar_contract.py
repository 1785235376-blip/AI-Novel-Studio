from pathlib import Path

import pytest

from app.services.v1_capability_service import (
    CapabilityVersionConflict,
    ResearchRecordIn,
    V1CapabilityService,
)


class Novels:
    def __init__(self):
        self.items = {"novel-a": {"id": "novel-a"}, "novel-b": {"id": "novel-b"}}

    def get(self, novel_id):
        if novel_id not in self.items:
            raise FileNotFoundError(novel_id)
        return self.items[novel_id]


class Assets:
    def get(self, asset_id):
        raise FileNotFoundError(asset_id)


def record(title="Archive", status="ACTIVE", source_type="ARCHIVE", tags=None):
    return ResearchRecordIn(title=title, status=status, source_type=source_type, tags=tags or ["port"], author="", citation="", url="", excerpt="", notes="", asset_ids=[])


@pytest.mark.parametrize("profile", ["file", "postgres"])
def test_research_durable_sidecar_boundary_contract(profile, tmp_path):
    root = tmp_path / profile
    service = V1CapabilityService(root, Novels(), object(), Assets())
    created = service.create_research("novel-a", record())
    assert service.storage_mode == "durable_sidecar"
    assert service.list_research("novel-a", status="ACTIVE")["total"] == 1
    assert service.list_research("novel-a", source_type="ARCHIVE")["total"] == 1
    assert service.list_research("novel-a", tag="port")["total"] == 1
    assert service.list_research("novel-b")["items"] == []
    with pytest.raises(FileNotFoundError):
        service._get("research", created["id"], "novel-b")
    updated = service.update_research("novel-a", created["id"], record("Revised"), created["version"])
    with pytest.raises(CapabilityVersionConflict):
        service.update_research("novel-a", created["id"], record("Stale"), created["version"])
    restarted = V1CapabilityService(root, Novels(), object(), Assets())
    assert restarted._get("research", created["id"], "novel-a")["title"] == "Revised"
    with pytest.raises(FileNotFoundError):
        restarted.delete_research("novel-b", created["id"], updated["version"])
    assert restarted.delete_research("novel-a", created["id"], updated["version"])["deleted"] is True
    assert restarted.list_research("novel-a")["items"] == []
    path = restarted._path("research").resolve()
    assert path.is_relative_to(root.resolve())
    with pytest.raises(ValueError):
        restarted._path("../research")
