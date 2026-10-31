"""Passive storage foundation only: real File owner lifecycle, no API activation."""
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative.project_store import CreativeProjectStore
from app.repository import FileRepository
from app.repositories.generation_repository import GenerationRepository, GenerationProjectIdentityError, graph_job_binding
from app.services.generation_project_binding import FIELD, IDENTITY_FIELDS

pytestmark = pytest.mark.file_backend_only


def record(incarnation):
    item = dict(id=str(uuid4()), novel_id="ordinary-owner", chapter_id="ordinary-owner:1",
                operation="continue", actor_id=None, workspace_id=None, scope=None,
                scope_type=None, scope_id=None, experimental_origin=None, status="QUEUED", output="", request={"instruction": "Continue"})
    item[FIELD] = dict(schema_version=1, project_incarnation=incarnation,
                       job_id=item["id"], project_id=item["novel_id"],
                       **{key: deepcopy(item[key]) for key in IDENTITY_FIELDS})
    return item


@pytest.fixture
def owner(tmp_path):
    novels = FileRepository(tmp_path)
    novels.create_novel(dict(id="ordinary-owner", title="Original"))
    novels.create_chapter("ordinary-owner", dict(title="First", content="Original source"))
    store = CreativeProjectStore(SimpleNamespace(backend="file", root=tmp_path))
    incarnation = store.incarnation("ordinary-owner")
    return SimpleNamespace(root=tmp_path, novels=novels, store=store,
                           repository=GenerationRepository(tmp_path), item=record(incarnation))


def test_cold_reopen_preserves_passive_identity_and_updates(owner):
    owner.repository.save(owner.item)
    reopened = GenerationRepository(owner.root)
    assert reopened.get(owner.item["id"]) == owner.item
    assert reopened.load_all() == [owner.item]
    changed = deepcopy(owner.item)
    changed.update(status="COMPLETED", output="A draft")
    reopened.save(changed)
    assert GenerationRepository(owner.root).get(changed["id"]) == changed


def test_original_owner_delete_recreate_rejects_retained_record(owner):
    owner.repository.save(owner.item)
    owner.novels.delete_novel("ordinary-owner")
    owner.novels.create_novel(dict(id="ordinary-owner", title="Replacement"))
    chapter = owner.novels.create_chapter("ordinary-owner", dict(title="First", content="Replacement"))
    assert chapter["id"] == owner.item["chapter_id"]
    replacement = owner.store.incarnation("ordinary-owner")
    assert replacement != owner.item[FIELD]["project_incarnation"]
    reopened = GenerationRepository(owner.root)
    with pytest.raises(KeyError): reopened.get(owner.item["id"])
    assert reopened.load_all() == []
    with pytest.raises(GenerationProjectIdentityError): reopened.save(owner.item)
    # The original saved job is retained; this is not a migration/deletion.
    assert json.loads(reopened._job_path(owner.item["id"]).read_text()) == owner.item


def test_missing_marker_never_provisioned_on_save_get_or_load(owner):
    owner.repository.save(owner.item)
    marker = owner.root / "novels/ordinary-owner/creative_project_v2.json"
    marker.unlink()
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(owner.item)
    with pytest.raises(KeyError): owner.repository.get(owner.item["id"])
    assert owner.repository.load_all() == []
    assert not marker.exists()


@pytest.mark.parametrize("mutation", [
    lambda item: item.__setitem__(FIELD, None),
    lambda item: item.__setitem__(FIELD, []),
    lambda item: item[FIELD].__setitem__("schema_version", 2),
    lambda item: item[FIELD].__setitem__("schema_version", True),
    lambda item: item[FIELD].__setitem__("unknown", "value"),
    lambda item: item[FIELD].pop("actor_id"),
    lambda item: item.pop("actor_id"),
    lambda item: item[FIELD].__setitem__("job_id", str(uuid4())),
    lambda item: item[FIELD].__setitem__("project_incarnation", "file:" + str(uuid4()).upper()),
    lambda item: item.__setitem__("operation", "graph_text"),
    lambda item: item.__setitem__("experimental_origin", "creative_graph_model"),
] + [lambda item, key=key: item.__setitem__(key, None) for key in (
    "graph_binding", "adaptation_binding", "creative_director_binding", "director_image_binding", "research_ocr_binding",
    "research_ocr_output_evidence", "_creative_director_terminal_evidence", "director_image_terminal_v3")])
def test_malformed_unknown_and_mixed_binding_fail_closed(owner, mutation):
    item = deepcopy(owner.item)
    mutation(item)
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(item)
    # Corrupt durable input must never fall back to ordinary legacy on read.
    owner.repository._job_path(item["id"]).write_text(json.dumps(item))
    with pytest.raises((GenerationProjectIdentityError, KeyError)): owner.repository.get(item["id"])
    assert owner.repository.load_all() == []


@pytest.mark.parametrize("field,value", [
    ("project_incarnation", "file:" + str(uuid4())), ("chapter_id", "ordinary-owner:2"),
    ("operation", "rewrite"), ("actor_id", "actor"), ("workspace_id", "workspace"),
    ("scope_type", "PROJECT"), ("scope_id", "ordinary-owner"),
])
def test_bound_identity_cannot_change(owner, field, value):
    owner.repository.save(owner.item)
    item = deepcopy(owner.item)
    item[FIELD][field] = value
    if field in item: item[field] = value
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(item)
    assert owner.repository.get(owner.item["id"]) == owner.item


def test_binding_cannot_be_removed_or_added_to_existing_legacy(owner):
    owner.repository.save(owner.item)
    item = deepcopy(owner.item)
    del item[FIELD]
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(item)
    legacy = deepcopy(item)
    legacy["id"] = "legacy-job"
    owner.repository.save(legacy)
    legacy["output"] = "legacy compatibility"
    owner.repository.save(legacy)
    assert owner.repository.get("legacy-job") == legacy
    # A canonical legacy ID also cannot be adopted by adding a valid binding.
    legacy = deepcopy(item)
    legacy["id"] = str(uuid4())
    owner.repository.save(legacy)
    legacy[FIELD] = deepcopy(owner.item[FIELD])
    legacy[FIELD]["job_id"] = legacy["id"]
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(legacy)


def test_collaboration_exact_scope_identity(owner):
    item = deepcopy(owner.item)
    item.update(actor_id="actor", workspace_id="workspace", scope_type="BRANCH", scope_id="branch", experimental_origin="branch_manuscript",
                scope=dict(kind="BRANCH", workspace_id="workspace", project_id="ordinary-owner",
                           storyline_id="storyline", branch_id="branch"))
    item[FIELD].update({key: deepcopy(item[key]) for key in IDENTITY_FIELDS})
    owner.repository.save(item)
    assert owner.repository.get(item["id"]) == item
    changed = deepcopy(item)
    changed["scope"]["branch_id"] = "replacement"
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(changed)
    changed[FIELD]["scope"]["branch_id"] = "replacement"
    changed["scope_id"] = changed[FIELD]["scope_id"] = "replacement"
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(changed)


def test_all_ordinary_operations_are_passive(owner):
    for operation in ("continue", "rewrite", "polish", "brainstorm", "review"):
        item = record(owner.item[FIELD]["project_incarnation"])
        item["operation"] = item[FIELD]["operation"] = operation
        owner.repository.save(item)
        assert graph_job_binding(owner.repository.get(item["id"])) == item[FIELD]


def test_bound_filename_alias_is_not_readable(owner):
    owner.repository.save(owner.item)
    alias = str(uuid4())
    owner.repository._job_path(alias).write_text(json.dumps(owner.item))
    with pytest.raises(KeyError): owner.repository.get(alias)
    assert owner.repository.load_all() == [owner.item]


@pytest.mark.parametrize("kind", ["graph", "adaptation", "director", "ocr", "image"])
def test_original_specialized_file_contracts_remain_exact(owner, kind):
    incarnation = owner.item[FIELD]["project_incarnation"]
    digest = "a" * 64
    scope = dict(mode="local", novel_id="ordinary-owner")
    common = dict(project_id="ordinary-owner", project_incarnation=incarnation,
                  actor_id="actor", scope=scope)
    item = dict(id=str(uuid4()), novel_id="ordinary-owner", chapter_id=None,
                actor_id="actor", scope=scope, profile="LOCAL_ONLY", expected_request_digest=digest,
                status="QUEUED", output="")
    if kind == "graph":
        item.update(operation="graph_text", experimental_origin="creative_graph_model",
                    graph_binding=dict(graph_id="graph", graph_version=1, run_id="run", node_id="node",
                                       project_incarnation=incarnation, input_digest=digest,
                                       reviewed_preview_digest=digest, route_fingerprint=digest))
        expected = item["graph_binding"]
    elif kind == "adaptation":
        item.update(operation="brainstorm", experimental_origin="creative_adaptation_model",
                    chapter_id="ordinary-owner:1", actor_id=None, scope=None,
                    adaptation_binding=dict(contract="CREATIVE_ADAPTATION_V1", **common,
                        proposal_id="proposal", chapter_id="ordinary-owner:1", source_version=1,
                        source_digest=digest, preview_digest=digest))
        expected = item["adaptation_binding"]
    elif kind == "director":
        item.update(operation="creative_director_text", experimental_origin="creative_director_source_model",
                    creative_director_binding=dict(contract="CREATIVE_DIRECTOR_SOURCE_V1", source_kind="STORYBOARD",
                        **common, source_document_id="source", source_version=1,
                        source_digest=digest, reviewed_preview_digest=digest))
        expected = item["creative_director_binding"]
    elif kind == "ocr":
        item.update(operation="research_ocr", experimental_origin="research_ocr_model",
                    research_ocr_binding=dict(contract="RESEARCH_OCR_JOB_V1", source_kind="IMAGE", **common,
                        source_id="image", source_version=1, source_digest=digest, media_type="image/png",
                        language="en", route_digest=digest, reviewed_preview_digest=digest))
        expected = item["research_ocr_binding"]
    else:
        from app.creative.director_image_binding import ImageBinding
        image_binding = ImageBinding.model_validate(dict(source=dict(**common,
            asset=dict(asset_id="asset", version=1, sha256=digest), media_type="image/png",
            byte_count=42, width=1, height=1), target=dict(document_id="storyboard", version=1,
            digest=digest, scene_id="scene"), route_digest=digest, preview_digest=digest)).model_dump()
        item.update(operation="creative_director_image_v3", experimental_origin="creative_director_image_model_v3",
                    director_image_binding=image_binding)
        expected = common
    assert graph_job_binding(item) == expected
    owner.repository.save(item)
    assert GenerationRepository(owner.root).get(item["id"]) == item
    assert FIELD not in owner.repository.get(item["id"])
    item["status"] = "RUNNING"
    owner.repository.save(item)
    mixed = deepcopy(item)
    mixed[FIELD] = deepcopy(owner.item[FIELD])
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(mixed)
    assert owner.repository.get(item["id"]) == item


def test_save_holds_original_lifecycle_lease_through_atomic_write(owner, monkeypatch):
    import threading
    import app.repositories.generation_repository as module
    entered, release, deleted = threading.Event(), threading.Event(), threading.Event()
    errors = []
    write = module.atomic_write

    def blocking_write(path, value):
        entered.set()
        if not release.wait(10): raise TimeoutError("test writer release")
        return write(path, value)

    def save():
        try: owner.repository.save(owner.item)
        except Exception as error: errors.append(error)

    def delete():
        try: owner.novels.delete_novel("ordinary-owner")
        except Exception as error: errors.append(error)
        finally: deleted.set()

    monkeypatch.setattr(module, "atomic_write", blocking_write)
    writer = threading.Thread(target=save)
    remover = threading.Thread(target=delete)
    writer.start()
    try:
        assert entered.wait(10)
        remover.start()
        assert not deleted.wait(.1)
    finally:
        release.set()
        writer.join(10)
        if remover.ident is not None: remover.join(10)
    assert not writer.is_alive() and not remover.is_alive() and not errors
    assert deleted.is_set()
    with pytest.raises(KeyError): owner.repository.get(owner.item["id"])
