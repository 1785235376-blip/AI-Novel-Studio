"""V2 owner deletion/recreation, with real File and PostgreSQL repositories.

The slug/title is intentionally identical across incarnations. Old scope bytes
remain present: filtering or cleanup in a test fixture must not fix this defect.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from test_v2_creative_foundation import TEST_URL, client, payload, public


TITLE = "V2 identical title lifecycle"


@pytest.fixture(params=[pytest.param("file", marks=pytest.mark.file_backend_only),
                       pytest.param("postgres", marks=pytest.mark.postgres_backend_only)])
def rig(request, tmp_path):
    from types import SimpleNamespace
    from app.config import Settings
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService

    backend = request.param
    url = TEST_URL if backend == "postgres" else ""
    bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=url, novel_data=tmp_path), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    # The title-derived slug is constant even across separate test cases. It is
    # not randomized to conceal incomplete deletion or reincarnation leakage.
    nid = novels.create({"title": TITLE})["id"]
    store = ExperimentalStore(tmp_path, backend, url)
    value = SimpleNamespace(nid=nid, scope={"mode": "local", "novel_id": nid}, actor="local-author",
        novels=novels, chapters=chapters, store=store, service=CreativeService(store, novels, chapters),
        root=tmp_path, backend=backend, url=url)
    try:
        yield value
    finally:
        # Every incarnation has the same captured nid. Only this fixture's
        # owned synthetic scopes and owner may be removed after assertions.
        if backend == "postgres":
            try:
                with store._connect() as connection:
                    connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))
                if any(row["id"] == nid for row in novels.list()):
                    novels.delete(nid)
                with store._connect() as connection:
                    assert connection.execute("SELECT count(*) FROM novels WHERE slug = %s", (nid,)).fetchone()[0] == 0
                    assert connection.execute("SELECT count(*) FROM experimental_scope_documents WHERE novel_id = %s", (nid,)).fetchone()[0] == 0
            finally:
                bundle.novels.database.engine.dispose()


def recreate(rig):
    rig.novels.delete(rig.nid)
    novel = rig.novels.create({"title": TITLE})
    rig.nid = novel["id"]
    rig.scope = {"mode": "local", "novel_id": rig.nid}
    chapter = rig.chapters.create(rig.nid, {"title": "One", "content": "A visitor remembers the ruined city."})
    rig.chapter = rig.chapters.get(chapter["id"])
    return novel


def independent(title="Private synthetic draft"):
    return {"mode": "SCREENPLAY", "title": title, "source_independent": True}


def test_same_title_recreate_preserves_history_but_never_revives_it(rig, monkeypatch):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    import app.creative.service as module

    recreate(rig)
    assert rig.nid == "v2-identical-title-lifecycle"
    identities = set()
    old_documents, old_proposals = {}, {}
    # Old records must not consume the new owner's two-document quota.
    monkeypatch.setattr(module, "MAX_DOCUMENTS", 2)
    for generation in range(3):
        assert rig.service.list(rig.nid, rig.scope) == []
        assert rig.service.proposals.list(rig.nid, rig.scope, rig.actor) == []
        source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
        standalone = rig.service.create(rig.nid, rig.scope, rig.actor, independent())
        proposal = rig.service.proposals.create(rig.nid, rig.scope, rig.actor,
            {"source_document_id": source["id"], "expected_source_version": 1})
        identity = source["project_incarnation"]
        assert identity not in identities
        identities.add(identity)
        assert standalone["project_incarnation"] == proposal["project_incarnation"] == identity
        assert len(rig.service.list(rig.nid, rig.scope)) == 2
        reopened = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
        assert reopened.get(rig.nid, rig.scope, source["id"]) == source
        old_documents.update({source["id"]: source, standalone["id"]: standalone})
        raw = rig.store.read(rig.nid, rig.scope)["collections"]
        old_proposals[proposal["id"]] = copy.deepcopy(raw[rig.service.proposals.COLLECTION][proposal["id"]])
        assert raw[rig.service.COLLECTION] == old_documents
        assert raw[rig.service.proposals.COLLECTION] == old_proposals
        recreate(rig)
        # Reusing the exact title, chapter number and content is not identity.
        assert rig.nid == "v2-identical-title-lifecycle"
        assert reopened.list(rig.nid, rig.scope) == []
        assert reopened.proposals.list(rig.nid, rig.scope, rig.actor) == []
        for row in (source, standalone):
            for operation in (
                lambda: reopened.get(rig.nid, rig.scope, row["id"]),
                lambda: reopened.history(rig.nid, rig.scope, row["id"]),
                lambda: reopened.export(rig.nid, rig.scope, row["id"]),
                lambda: reopened.update(rig.nid, rig.scope, rig.actor, row["id"], 1, public(row)),
                lambda: reopened.archive(rig.nid, rig.scope, rig.actor, row["id"], 1),
                lambda: reopened.restore(rig.nid, rig.scope, rig.actor, row["id"], 1, 1),
            ):
                with pytest.raises(FileNotFoundError):
                    operation()
        with pytest.raises(FileNotFoundError):
            reopened.proposals.cancel(rig.nid, rig.scope, rig.actor, proposal["id"], {"expected_version": 1})
        retained = rig.store.read(rig.nid, rig.scope)["collections"]
        assert retained[rig.service.COLLECTION] == old_documents
        assert retained[rig.service.proposals.COLLECTION] == old_proposals


def test_recreation_is_project_and_branch_bounded_with_unrelated_data_intact(rig):
    recreate(rig)
    unrelated = rig.novels.create({"title": "V2 retained unrelated lifecycle"})["id"]
    other_scope = {"mode": "local", "novel_id": unrelated}
    branch = {"mode": "collaboration", "novel_id": rig.nid, "workspace_id": "w",
              "storyline_id": "s", "branch_id": "b"}
    try:
        untouched = rig.service.create(unrelated, other_scope, rig.actor, independent("Unrelated"))
        before_other = rig.store.read(unrelated, other_scope)
        local = rig.service.create(rig.nid, rig.scope, rig.actor, independent("Local"))
        branch_row = rig.service.create(rig.nid, branch, rig.actor, independent("Branch"))
        assert rig.service.list(rig.nid, branch) == [branch_row]
        assert rig.service.list(rig.nid, rig.scope) == [local]
        with rig.store.transaction(rig.nid, rig.scope) as state:
            state["collections"]["unrelated_existing_domain"] = {"sentinel": {"private": "retained"}}
        branch_before = rig.store.read(rig.nid, branch)
        recreate(rig)
        assert rig.service.list(rig.nid, rig.scope) == []
        assert rig.service.list(rig.nid, branch) == []
        assert rig.store.read(rig.nid, branch) == branch_before
        current = rig.service.create(rig.nid, rig.scope, rig.actor, independent("New"))
        assert rig.service.list(rig.nid, rig.scope) == [current]
        assert rig.service.get(unrelated, other_scope, untouched["id"]) == untouched
        assert rig.store.read(unrelated, other_scope) == before_other
        assert rig.store.read(rig.nid, rig.scope)["collections"]["unrelated_existing_domain"] == {
            "sentinel": {"private": "retained"}}
    finally:
        if rig.backend == "postgres":
            with rig.store._connect() as connection:
                connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (unrelated,))
        rig.novels.delete(unrelated)


def test_unbound_pre_incarnation_rows_are_preserved_and_fail_closed(rig):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent())
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][rig.service.COLLECTION][row["id"]].pop("project_incarnation")
    before = rig.store.read(rig.nid, rig.scope)
    assert rig.service.list(rig.nid, rig.scope) == []
    with pytest.raises(FileNotFoundError):
        rig.service.get(rig.nid, rig.scope, row["id"])
    assert rig.store.read(rig.nid, rig.scope) == before
    new = rig.service.create(rig.nid, rig.scope, rig.actor, independent("Bound"))
    assert rig.service.list(rig.nid, rig.scope) == [new]
    assert rig.store.read(rig.nid, rig.scope)["collections"][rig.service.COLLECTION][row["id"]] == (
        before["collections"][rig.service.COLLECTION][row["id"]])


def test_delete_waits_for_inflight_commit_then_recreated_owner_is_empty(rig):
    recreate(rig)
    entered, release, deleting, deleted = Event(), Event(), Event(), Event()
    def pause():
        if not entered.is_set():
            entered.set()
            assert release.wait(10)
    def delete():
        deleting.set()
        rig.novels.delete(rig.nid)
        deleted.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(rig.service.create, rig.nid, rig.scope, rig.actor, independent(), reauthorize=pause)
        try:
            assert entered.wait(5)
            deleter = pool.submit(delete)
            assert deleting.wait(5)
            assert not deleted.wait(.2)
        finally:
            release.set()
        old = writer.result(timeout=10)
        deleter.result(timeout=10)
    assert rig.novels.create({"title": TITLE})["id"] == rig.nid
    assert rig.service.list(rig.nid, rig.scope) == []
    assert rig.store.read(rig.nid, rig.scope)["collections"][rig.service.COLLECTION][old["id"]] == old
    current = rig.service.create(rig.nid, rig.scope, rig.actor, independent("New owner"))
    assert current["project_incarnation"] != old["project_incarnation"]


def test_recreated_api_cannot_read_or_mutate_old_assets_or_bypass_authority(rig, client):
    recreate(rig)
    base = f"/api/novels/{rig.nid}/experimental/creative"
    owner, reader = {"X-Session-Token": "owner"}, {"X-Session-Token": "reader"}
    created = client.post(base + "/documents", json=independent("PRIVATE_OLD_OWNER"), headers=owner)
    assert created.status_code == 201, created.text
    old = created.json()
    recreate(rig)
    assert client.get(base + "/documents", headers=owner).json() == {"items": []}
    assert client.get(base + "/documents", headers=reader).json() == {"items": []}
    assert client.get(base + "/documents").status_code == 401
    url = base + "/documents/" + old["id"]
    for headers in (owner, reader, {**owner, "X-Branch-ID": "other"}):
        response = client.get(url, headers=headers)
        assert response.status_code == 404
        assert "PRIVATE_OLD_OWNER" not in response.text
    body = {**public(old), "expected_version": 1}
    assert client.put(url, json=body, headers=owner).status_code == 404
    assert client.put(url, json=body, headers=reader).status_code == 403
    assert client.post(base + "/documents", json=independent(), headers=reader).status_code == 403
    new = client.post(base + "/documents", json=independent("Current owner"), headers=owner)
    assert new.status_code == 201, new.text
    assert client.get(base + "/documents", headers=reader).json() == {"items": [new.json()]}


def test_durable_identity_survives_process_restart_and_repeated_creation_timestamp(rig):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    from app.storage import atomic_write

    recreate(rig)
    first = rig.service.create(rig.nid, rig.scope, rig.actor, independent())
    stamp = rig.novels.get(rig.nid)["created_at"]
    rig.novels.update(rig.nid, {"title": "Renamed owner"})
    script = """import json,os,sys
from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore
store=CreativeProjectStore(ExperimentalStore(sys.argv[1],sys.argv[2],os.getenv('V2_LIFECYCLE_DATABASE_URL','')))
print(json.dumps(store.read(sys.argv[3], {'mode':'local','novel_id':sys.argv[3]})['collections']['creative_documents_v2']))
"""
    result = subprocess.run([sys.executable, "-B", "-c", script, str(rig.root), rig.backend, rig.nid],
        cwd=Path(__file__).resolve().parents[1], env={**os.environ, "V2_LIFECYCLE_DATABASE_URL": rig.url},
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {first["id"]: first}
    recreate(rig)
    # Even identical clock stamps cannot confer ownership on a recreated slug.
    if rig.backend == "file":
        path = rig.root / "novels" / rig.nid / "novel.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["created_at"] = stamp
        atomic_write(path, json.dumps(metadata))
    else:
        with rig.store._connect() as connection:
            connection.execute("UPDATE novels SET created_at = %s WHERE slug = %s", (stamp, rig.nid))
    assert rig.service.list(rig.nid, rig.scope) == []
    current = rig.service.create(rig.nid, rig.scope, rig.actor, independent())
    assert current["project_incarnation"] != first["project_incarnation"]


def test_first_access_from_independent_scopes_uses_one_identity(rig):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    from threading import Barrier

    scopes = [rig.scope, {"mode": "collaboration", "novel_id": rig.nid, "workspace_id": "w",
                         "storyline_id": "s", "branch_id": "parallel"}]
    barrier = Barrier(2)
    def write(scope):
        service = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
        barrier.wait(timeout=5)
        return service.create(rig.nid, scope, rig.actor, independent())
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(write, scopes))
    assert rows[0]["project_incarnation"] == rows[1]["project_incarnation"]
    for scope, row in zip(scopes, rows):
        assert rig.service.list(rig.nid, scope) == [row]


def test_revoked_write_does_not_adopt_or_modify_unbound_history(rig):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent())
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][rig.service.COLLECTION][row["id"]].pop("project_incarnation")
    before = rig.store.read(rig.nid, rig.scope)
    calls = []
    def revoke():
        calls.append(1)
        if len(calls) == 2:
            raise PermissionError("synthetic revoked authority")
    with pytest.raises(PermissionError):
        rig.service.create(rig.nid, rig.scope, rig.actor, independent("Rejected"), reauthorize=revoke)
    assert rig.store.read(rig.nid, rig.scope) == before
    assert rig.service.list(rig.nid, rig.scope) == []


@pytest.mark.file_backend_only
@pytest.mark.parametrize("corruption", ["invalid_json", "oversized", "invalid_uuid", "wrong_schema", "directory", "symlink"])
def test_file_corrupt_marker_fails_closed_without_reading_external_content(tmp_path, corruption):
    import json
    from pathlib import Path
    from app.creative.project_store import CreativeProjectStore
    from app.experimental.store import ExperimentalStore
    from app.repository import FileRepository

    owner = FileRepository(tmp_path).create_novel({"title": TITLE})["id"]
    scope = {"mode": "local", "novel_id": owner}
    store = CreativeProjectStore(ExperimentalStore(tmp_path))
    original = store.incarnation(owner)
    marker = tmp_path / "novels" / owner / "creative_project_v2.json"
    marker.unlink()
    if corruption == "directory":
        marker.mkdir()
    elif corruption == "symlink":
        external = tmp_path / "unrelated-private-marker.json"
        external.write_text(json.dumps({"schema_version": 1, "project_incarnation": original.split(":")[1]}))
        marker.symlink_to(external)
    else:
        marker.write_text({"invalid_json": "{", "oversized": " " * 257,
            "invalid_uuid": '{"schema_version":1,"project_incarnation":"not-a-uuid"}',
            "wrong_schema": '{"schema_version":true,"project_incarnation":"' + original.split(":")[1] + '"}'}[corruption])
    restarted = CreativeProjectStore(ExperimentalStore(tmp_path))
    with pytest.raises(ValueError, match="CREATIVE_PROJECT_IDENTITY_INVALID"):
        restarted.read(owner, scope)
    with pytest.raises(ValueError, match="CREATIVE_PROJECT_IDENTITY_INVALID"):
        with restarted.transaction(owner, scope):
            pytest.fail("corrupt identity must not enter a transaction")
    assert not (tmp_path / "experimental_v1").exists()
    if corruption == "symlink":
        assert marker.is_symlink()
        assert json.loads(external.read_text())["project_incarnation"] == original.split(":")[1]
