"""Original asset owner, closed adaptation receipts and exact byte admission.

Only synthetic passive evidence is used; no model, router dispatch or provider
network runs. Use scripts/run_v2_checks.py for the original isolated fixtures.
"""
import copy
import hashlib
import json

import pytest

from app.creative import adaptation_receipt as contract
from app.experimental.store import canonical
from app.services.asset_library_service import AssetLibraryService
from test_v2_creative_foundation import rig
from test_v2_text_asset_owner import lease, source as graph_source

TEXT = "Raw screenplay proposal.\n原始文本。"
STAMP = "2026-10-10T10:00:00+00:00"
DEADLINE = "2026-10-10T10:03:00+00:00"


def source(text=TEXT):
    return {"schema_version": 1, "contract": contract.ASSET_CONTRACT, "proposal_id": "proposal-1",
        "source_proposal_version": 3, "chapter_id": "chapter-1", "source_version": 2,
        "source_digest": "a" * 64, "selection_digest": "b" * 64, "job_id": "job-1",
        "output_digest": hashlib.sha256(text.encode()).hexdigest(), "preview_digest": "c" * 64,
        "produced_at": STAMP}


def request(prompt="Adapt this exact saved source.\n原文。"):
    return {"provider_id": "local.provider", "model_id": "local-model", "prompt": prompt,
        "system_instruction": None, "context": {}, "metadata": {"purpose": "brainstorm"},
        "structured_output_schema": None,
        "parameters": {"temperature": None, "max_output_tokens": None, "stop_sequences": []}}


def route():
    identity = {"provider_id": "local.provider", "model_id": "local-model", "cloud": False,
        "synthetic": True, "model_version": "synthetic-protocol-v1", "runtime_hash": None,
        "runtime_version": "python-test", "license_confirmed": True}
    return {"provider_id": identity["provider_id"], "model_id": identity["model_id"], "identity": identity,
        "fingerprint": hashlib.sha256(canonical(identity).encode()).hexdigest(),
        "route_id": hashlib.sha256(canonical([identity["provider_id"], identity["model_id"]]).encode()).hexdigest()}


def receipt(origin=None, payload=None, chosen=None):
    origin, payload, chosen = origin or source(), payload or request(), chosen or route()
    publication = {"schema_version": 1, "contract": contract.PUBLICATION_CONTRACT, "job_id": origin["job_id"],
        "request_digest": "d" * 64, "output_digest": origin["output_digest"]}
    return contract.receipt_payload(payload, chosen, origin, execution_mode="mock_standin",
        request_digest="d" * 64, settlement_id="reservation-1", settlement_version=3,
        generation_bounds={"max_output_bytes": contract.MAX_OUTPUT_BYTES, "deadline": DEADLINE},
        final_publication=publication)


def metadata(text=TEXT, payload=None):
    payload = payload or request()
    origin = source(text)
    return AssetLibraryService.text_result_metadata(source_receipt=origin, source_job_id=origin["job_id"],
        provider_id=payload["provider_id"], model_id=payload["model_id"],
        parameters=contract.asset_parameters(payload, route()), execution_receipt=receipt(origin, payload))


@pytest.fixture
def owner(rig, monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(contract.FEATURES))
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    rig.assets = AssetLibraryService(rig.root)
    return rig


def create(owner, text=TEXT, **changes):
    initial = metadata(text)
    kwargs = {"novel_id": owner.nid, "filename": "adaptation-proposal-1.txt", "text": text,
        "source_receipt": initial["_text_result_origin"], "provider_id": initial["provider_id"],
        "model_id": initial["model_id"], "source_job_id": initial["source_job_id"],
        "parameters": initial["parameters"], "execution_receipt": initial[contract.PRIVATE_FIELD],
        "idempotency_key": "adaptation-text:proposal-1", "branch_id": None, "owner_actor_id": owner.actor,
        "required_features": tuple(contract.FEATURES), "guard": lambda: None}
    kwargs.update(changes)
    return owner.assets.create_text_result(**kwargs)


def review_receipt(actor):
    return {"contract": contract.REVIEW_CONTRACT, "proposal_id": "proposal-1", "proposal_version": 7,
        "output_digest": source()["output_digest"], "generated_output_digest": "e" * 64,
        "reviewed_output_digest": "f" * 64, "document_id": "screenplay-1", "document_version": 1,
        "reviewed_by": actor, "reviewed_at": STAMP}


def review(owner, row, **changes):
    kwargs = {"actor_id": owner.actor, "branch_id": None, "expected_version": row["version"],
        "output_digest": row["sha256"], "status": "APPROVED", "review_receipt": review_receipt(owner.actor),
        "guard": lambda: None, "execution_receipt": receipt()}
    kwargs.update(changes)
    return owner.assets.review_text_result(row["id"], **kwargs)


def test_complete_private_draft_first_commit_and_once_only_review(owner, monkeypatch):
    writes = []
    original = owner.assets._write_meta
    def capture(meta):
        writes.append(copy.deepcopy(meta))
        original(meta)
    monkeypatch.setattr(owner.assets, "_write_meta", capture)
    with lease(owner):
        draft = create(owner)
        assert draft == create(owner)
        assert draft["version"] == 1 and draft["_text_result_review"] == {"status": "DRAFT", "receipt": None, "history": []}
        assert draft[contract.PRIVATE_FIELD] == receipt()
        assert set(draft["_required_features"]) == contract.FEATURES
        assert "ai_execution_v2" not in draft["_required_features"]
        adopted = review(owner, draft)
        assert adopted["version"] == 2 and review(owner, draft) == adopted and create(owner) == adopted
        assert adopted["_text_result_review"]["receipt"] == review_receipt(owner.actor)
        assert adopted["_text_result_review"]["history"] == [{"status": "DRAFT", "asset_version": 1}]
        assert adopted["_text_result_origin"] == draft["_text_result_origin"]
        assert adopted["parameters"]["temperature"] is None
        assert adopted["parameters"]["max_output_tokens"] is None
        assert owner.assets.content(adopted["id"], actor_id=owner.actor) == TEXT.encode()
        assert owner.assets.list(owner.nid) == []
        for actor in (None, "other"):
            with pytest.raises(FileNotFoundError):
                owner.assets.content(adopted["id"], actor_id=actor)
        public = owner.assets.public({"nested": [adopted]})["nested"][0]
        assert not {contract.PRIVATE_FIELD, "_text_result_origin", "_text_result_review", "_owner_actor_id"} & public.keys()
        assert "route_identity" not in contract.public_receipt(receipt())
    assert len(writes) == 2
    assert writes[0][contract.PRIVATE_FIELD] == receipt()


@pytest.mark.parametrize("size", [31_999, 32_000, 32_001, 127_999, 128_000, 128_001])
def test_raw_output_budget_is_encoded_bytes(owner, size):
    text = "文" * (size // 3) + "x" * (size % 3)
    assert len(text.encode()) == size
    with lease(owner):
        if size > contract.MAX_OUTPUT_BYTES:
            with pytest.raises(ValueError, match="CONTENT_INVALID"):
                create(owner, text)
            assert owner.assets.list(owner.nid, actor_id=owner.actor) == []
        else:
            row = create(owner, text)
            assert row["size"] == size and owner.assets.content(row["id"], actor_id=owner.actor) == text.encode()


@pytest.mark.parametrize("size", [31_999, 32_000, 32_001])
def test_original_graph_output_budget_remains_unchanged(size):
    text = "x" * size
    initial = AssetLibraryService.text_result_metadata(source_receipt=graph_source(text), provider_id="local.provider",
        model_id="local-model", source_job_id="job-1", parameters={"max_output_tokens": 512})
    if size <= 32_000:
        assert AssetLibraryService._text_initial(initial, text.encode()) == initial
    else:
        with pytest.raises(ValueError, match="CONTENT_INVALID"):
            AssetLibraryService._text_initial(initial, text.encode())


@pytest.mark.parametrize("field,value", [("contract", "unknown"), ("schema_version", True),
    ("source_proposal_version", True), ("source_proposal_version", 0), ("source_proposal_version", 2**53),
    ("source_version", 0), ("chapter_id", "../chapter"), ("job_id", ""),
    ("selection_digest", "A" * 64), ("produced_at", "2026-10-10T10:00:00")])
def test_origin_schema_never_falls_back_to_graph(field, value):
    initial = metadata()
    initial["_text_result_origin"][field] = value
    with pytest.raises(ValueError):
        AssetLibraryService._text_initial(initial, TEXT.encode())


@pytest.mark.parametrize("path,value", [
    (("contract",), "creative-graph-text-execution/1"), (("schema_version",), True),
    (("request", "parameters", "temperature"), 0), (("request", "parameters", "max_output_tokens"), 2048),
    (("request", "parameters", "stop_sequences"), ["STOP"]), (("request", "context"), {"secret": "context"}),
    (("request", "metadata", "purpose"), "creative_graph_model"), (("request", "system_instruction"), "hidden"),
    (("request", "structured_output_schema"), {}), (("request", "model_id"), "different-model"),
    (("request_payload_sha256",), "f" * 64), (("prompt_sha256",), "f" * 64),
    (("route_fingerprint",), "f" * 64), (("route_id",), "f" * 64),
    (("route_identity", "cloud"), True), (("route_identity", "synthetic"), 1),
    (("model_evidence", "kind"), "MODEL_CENTER_METADATA"), (("execution_mode",), "real"),
    (("generation_bounds", "max_output_bytes"), 32_000), (("generation_bounds", "deadline"), None),
    (("terminal", "status"), "FAILED"), (("terminal", "settled_at"), DEADLINE),
    (("terminal", "final_publication"), None), (("terminal", "final_publication", "job_id"), "other-job"),
    (("terminal", "final_publication", "request_digest"), "f" * 64),
    (("terminal", "final_publication", "output_digest"), "f" * 64),
    (("quality_verification",), "PASSED")])
def test_receipt_mutations_fail_closed(path, value):
    initial = metadata()
    node = initial[contract.PRIVATE_FIELD]
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        AssetLibraryService._text_initial(initial, TEXT.encode())


@pytest.mark.parametrize("part", ["origin", "receipt", "request", "parameters", "terminal", "marker", "bounds"])
def test_all_receipt_envelopes_are_closed(part):
    initial = metadata()
    value = initial[contract.PRIVATE_FIELD]
    node = {"origin": initial["_text_result_origin"], "receipt": value, "request": value["request"],
        "parameters": value["request"]["parameters"], "terminal": value["terminal"],
        "marker": value["terminal"]["final_publication"], "bounds": value["generation_bounds"]}[part]
    node["unexpected"] = "not accepted"
    with pytest.raises(ValueError):
        AssetLibraryService._text_initial(initial, TEXT.encode())


@pytest.mark.parametrize("mode", ["missing", "graph", "stripped-origin", "stripped-receipt"])
def test_adaptation_receipt_is_mandatory_and_tagged(mode):
    initial = metadata()
    if mode == "missing":
        initial.pop(contract.PRIVATE_FIELD)
    elif mode == "graph":
        initial[contract.PRIVATE_FIELD]["contract"] = "creative-graph-text-execution/1"
    elif mode == "stripped-origin":
        initial["_text_result_origin"].pop("contract")
    else:
        initial[contract.PRIVATE_FIELD].pop("contract")
    with pytest.raises(ValueError):
        AssetLibraryService._text_initial(initial, TEXT.encode())


@pytest.mark.parametrize("field", ["temperature", "max_output_tokens", "stop_sequences", "synthetic", "quality_verification"])
def test_asset_parameters_preserve_actual_nullable_author_contract(field):
    initial = metadata()
    initial["parameters"][field] = "invented"
    with pytest.raises(ValueError):
        AssetLibraryService._text_initial(initial, TEXT.encode())


@pytest.mark.parametrize("delta", [-1, 0, 1])
@pytest.mark.parametrize("layer", ["prompt", "request", "receipt", "metadata"])
def test_exact_encoded_budget_boundaries(monkeypatch, layer, delta):
    # Reduce each independent cap to the measured legal payload size. This
    # exercises cap-1/cap/cap+1 without inventing otherwise-invalid padding.
    initial = metadata(payload=request('汉字\\"\n\t\x01' * 15))
    value = initial[contract.PRIVATE_FIELD]
    encoded = {"prompt": value["request"]["prompt"].encode(), "request": contract.encode_receipt(value["request"]),
        "receipt": contract.encode_receipt(value), "metadata": AssetLibraryService.text_result_metadata_bytes(initial)}[layer]
    name = {"prompt": "MAX_PROMPT_BYTES", "request": "MAX_REQUEST_BYTES", "receipt": "MAX_BYTES", "metadata": "MAX_METADATA_BYTES"}[layer]
    monkeypatch.setattr(contract, name, len(encoded) - delta)
    assert contract.encode_receipt(initial) == json.dumps(initial, ensure_ascii=False, allow_nan=False).encode()
    if delta > 0:
        with pytest.raises(ValueError, match="LIMIT"):
            AssetLibraryService._text_initial(initial, TEXT.encode())
    else:
        assert AssetLibraryService._text_initial(initial, TEXT.encode()) == initial


def test_metadata_can_fail_while_receipt_fits(monkeypatch):
    initial = metadata()
    monkeypatch.setattr(contract, "MAX_METADATA_BYTES", len(AssetLibraryService.text_result_metadata_bytes(initial)) - 1)
    value = initial[contract.PRIVATE_FIELD]
    assert contract.validate_receipt(value, source=source(), provider_id="local.provider", model_id="local-model",
        parameters=initial["parameters"]) == value
    with pytest.raises(ValueError, match="METADATA_LIMIT"):
        AssetLibraryService._text_initial(initial, TEXT.encode())


@pytest.mark.parametrize("after_commit", [False, True])
@pytest.mark.parametrize("phase", ["draft", "review"])
def test_metadata_faults_recover_same_identity_and_version(owner, monkeypatch, after_commit, phase):
    original = owner.assets._write_meta
    with lease(owner):
        draft = create(owner) if phase == "review" else None
        def fail(meta):
            if after_commit:
                original(meta)
            raise OSError("synthetic metadata interruption")
        monkeypatch.setattr(owner.assets, "_write_meta", fail)
        with pytest.raises(OSError):
            review(owner, draft) if draft else create(owner)
        retained = owner.assets.list(owner.nid, actor_id=owner.actor)
        assert len(retained) == (1 if phase == "review" else int(after_commit))
        monkeypatch.setattr(owner.assets, "_write_meta", original)
        recovered = review(owner, draft) if draft else create(owner)
        assert recovered["version"] == (2 if phase == "review" else 1)
        if retained:
            assert retained[0]["id"] == recovered["id"]
        assert owner.assets.content(recovered["id"], actor_id=owner.actor) == TEXT.encode()
        assert len(owner.assets.list(owner.nid, actor_id=owner.actor)) == 1
        assert not list(owner.assets.root.glob("*.tmp"))


@pytest.mark.parametrize("field,value", [("proposal_id", "other-proposal"), ("proposal_version", 3),
    ("proposal_version", True), ("document_version", 2), ("document_version", True),
    ("reviewed_by", "different-actor"), ("output_digest", "f" * 64),
    ("generated_output_digest", "bad"), ("reviewed_output_digest", "bad"),
    ("reviewed_at", "2026-10-10T10:00:00"), ("document_id", "../document")])
def test_review_binding_is_strict(owner, field, value):
    with lease(owner):
        draft = create(owner)
        changed = review_receipt(owner.actor)
        changed[field] = value
        with pytest.raises(ValueError):
            review(owner, draft, review_receipt=changed)
        assert owner.assets.get(draft["id"], actor_id=owner.actor) == draft


def test_owner_guards_privacy_immutability_and_no_fabricated_rejection(owner):
    def denied():
        raise PermissionError("revoked")
    with lease(owner):
        with pytest.raises(PermissionError):
            create(owner, guard=denied)
        assert owner.assets.list(owner.nid, actor_id=owner.actor) == []
        draft = create(owner)
        for action in (lambda: create(owner, guard=denied), lambda: review(owner, draft, guard=denied)):
            with pytest.raises(PermissionError):
                action()
        with pytest.raises(ValueError, match="REVIEW_INVALID"):
            review(owner, draft, status="REJECTED")
        with pytest.raises(ValueError, match="RECEIPT_CHANGED"):
            review(owner, draft, execution_receipt=None)
        with pytest.raises(ValueError, match="PROVENANCE_IMMUTABLE"):
            owner.assets.update_metadata(draft["id"], {"parameters": {}}, actor_id=owner.actor, expected_version=1)
        with pytest.raises(ValueError, match="PRIVATE_OWNER_REQUIRED"):
            owner.assets.promote_owned(draft["id"], actor_id=owner.actor, branch_id=None, expected_version=1, provenance={})
        assert owner.assets.get(draft["id"], actor_id=owner.actor) == draft


def test_exact_adaptation_flags_and_legacy_graph_caps(owner, monkeypatch):
    with lease(owner):
        with pytest.raises(ValueError, match="AUTHORITY_REQUIRED|feature unavailable"):
            create(owner, required_features=tuple(contract.FEATURES | {"ai_execution_v2"}))
        row = create(owner)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    with lease(owner):
        with pytest.raises(FileNotFoundError):
            owner.assets.get(row["id"], actor_id=owner.actor)
    assert AssetLibraryService.TEXT_RESULT_MAX_BYTES == 32_000
    from app.creative.text_execution_receipt import MAX_BYTES
    assert MAX_BYTES == 64_000


@pytest.mark.parametrize("target", [127_999, 128_000, 128_001])
def test_actual_prompt_utf8_cap(target):
    prompt = "文" * (target // 3) + "x" * (target % 3)
    initial = metadata(payload=request(prompt))
    assert len(prompt.encode()) == target
    if target > contract.MAX_PROMPT_BYTES:
        with pytest.raises(ValueError, match="PROMPT_LIMIT"):
            AssetLibraryService._text_initial(initial, TEXT.encode())
    else:
        assert AssetLibraryService._text_initial(initial, TEXT.encode()) == initial


@pytest.mark.parametrize("target", [255_999, 256_000, 256_001])
def test_actual_request_cap_counts_json_control_escaping(target):
    payload = request("\x01" * 42_000)
    remaining = target - len(contract.encode_receipt(payload))
    assert remaining > 0
    payload["prompt"] += "a" * remaining
    assert len(contract.encode_receipt(payload)) == target
    assert len(payload["prompt"].encode()) <= contract.MAX_PROMPT_BYTES
    initial = metadata(payload=payload)
    if target > contract.MAX_REQUEST_BYTES:
        with pytest.raises(ValueError, match="REQUEST_LIMIT"):
            AssetLibraryService._text_initial(initial, TEXT.encode())
    else:
        assert AssetLibraryService._text_initial(initial, TEXT.encode()) == initial


def test_real_route_evidence_requires_verified_local_fingerprints_and_license():
    chosen = route()
    identity = chosen["identity"]
    identity.update(synthetic=False, model_version="a" * 64, runtime_hash="b" * 64,
        source_locality="LOCAL_VERIFIED", license_confirmed=True)
    chosen["fingerprint"] = hashlib.sha256(canonical(identity).encode()).hexdigest()
    value = receipt(chosen=chosen)
    value["execution_mode"] = "real"
    params = contract.asset_parameters(request(), chosen)
    assert contract.validate_receipt(value, source=source(), provider_id="local.provider", model_id="local-model",
        parameters=params) == value
    for field, invalid in (("source_locality", "UNKNOWN"), ("license_confirmed", False),
                           ("model_version", "synthetic-protocol-v1"), ("runtime_hash", None)):
        forged = copy.deepcopy(value)
        forged["route_identity"][field] = invalid
        forged["route_fingerprint"] = hashlib.sha256(canonical(forged["route_identity"]).encode()).hexdigest()
        forged["model_evidence"] = contract.model_evidence(forged["route_identity"])
        with pytest.raises(ValueError):
            contract.validate_receipt(forged, source=source(), provider_id="local.provider", model_id="local-model",
                parameters=params)


def test_original_graph_receipt_and_containing_metadata_keep_exact_64k_limit():
    from app.creative.text_execution_receipt import validate_receipt
    for target in (63_999, 64_000, 64_001):
        origin, chosen = graph_source("x"), route()
        value = {"schema_version": 1, "contract": "creative-graph-text-execution/1", "prompt": "\\" * 30_000,
            "prompt_sha256": "a" * 64, "provider_id": chosen["provider_id"], "model_id": chosen["model_id"],
            "route_id": chosen["route_id"], "route_fingerprint": chosen["fingerprint"],
            "route_identity": chosen["identity"], "model_evidence": contract.model_evidence(chosen["identity"]),
            "parameters": {"temperature": 0, "max_output_tokens": 512, "stop_sequences": []},
            "execution_mode": "mock_standin", "request_digest": "d" * 64, "workflow": origin,
            "terminal": {"status": "COMPLETED", "settlement_id": "reservation-1", "settled_at": STAMP},
            "quality_verification": "NOT_RUN"}
        remainder = target - len(contract.encode_receipt(value))
        value["prompt"] += "\\" * (remainder // 2) + "a" * (remainder % 2)
        value["prompt_sha256"] = hashlib.sha256(value["prompt"].encode()).hexdigest()
        assert len(value["prompt"].encode()) <= 32_000 and len(contract.encode_receipt(value)) == target
        parameters = {"temperature": 0, "max_output_tokens": 512, "synthetic": True}
        args = dict(source=origin, provider_id=chosen["provider_id"], model_id=chosen["model_id"], parameters=parameters)
        if target > 64_000:
            with pytest.raises(ValueError, match="^TEXT_EXECUTION_RECEIPT_INVALID$"):
                validate_receipt(value, **args)
        else:
            assert validate_receipt(value, **args) == value
            initial = AssetLibraryService.text_result_metadata(source_receipt=origin, source_job_id="job-1",
                provider_id=chosen["provider_id"], model_id=chosen["model_id"], parameters=parameters, execution_receipt=value)
            with pytest.raises(ValueError, match="^TEXT_RESULT_METADATA_LIMIT$"):
                AssetLibraryService._text_initial(initial, b"x")


@pytest.mark.parametrize("chapter_id", ["novel:1", "novel:~0123456789abcdef0123456789abcdef",
    "../chapter", "..\\chapter", "novel/chapter", "novel\\chapter", "novel:\x00"])
def test_chapter_reference_uses_original_identifier_without_widening_asset_ids(chapter_id):
    initial = metadata()
    initial["_text_result_origin"]["chapter_id"] = chapter_id
    initial[contract.PRIVATE_FIELD]["workflow"]["chapter_id"] = chapter_id
    if chapter_id in {"novel:1", "novel:~0123456789abcdef0123456789abcdef"}:
        assert AssetLibraryService._text_initial(initial, TEXT.encode()) == initial
        with pytest.raises(ValueError):
            AssetLibraryService._identifier(chapter_id)
    else:
        with pytest.raises(ValueError):
            AssetLibraryService._text_initial(initial, TEXT.encode())


def test_real_original_chapter_identity_archives_through_asset_owner(owner):
    origin = source()
    origin["chapter_id"] = owner.chapter["id"]
    assert ":" in origin["chapter_id"]
    with lease(owner):
        draft = create(owner, source_receipt=origin, execution_receipt=receipt(origin))
        assert draft["_text_result_origin"]["chapter_id"] == owner.chapter["id"]
        assert draft[contract.PRIVATE_FIELD]["workflow"]["chapter_id"] == owner.chapter["id"]


@pytest.mark.parametrize("version", [0, -1, True, 1.0, "3", None, 2**53])
def test_settlement_version_rejects_nonpositive_nonstrict_or_unbounded(version):
    initial = metadata()
    initial[contract.PRIVATE_FIELD]["terminal"]["settlement_version"] = version
    with pytest.raises(ValueError):
        AssetLibraryService._text_initial(initial, TEXT.encode())


@pytest.mark.parametrize("version", [1, 3, 2**53 - 1])
def test_settlement_version_is_immutable_receipt_data(version):
    initial = metadata()
    initial[contract.PRIVATE_FIELD]["terminal"]["settlement_version"] = version
    assert AssetLibraryService._text_initial(initial, TEXT.encode()) == initial
    assert contract.public_receipt(initial[contract.PRIVATE_FIELD])["terminal"]["settlement_version"] == version


def test_settlement_version_is_mandatory():
    initial = metadata()
    initial[contract.PRIVATE_FIELD]["terminal"].pop("settlement_version")
    with pytest.raises(ValueError):
        AssetLibraryService._text_initial(initial, TEXT.encode())



def find(owner, **changes):
    kwargs = {"novel_id": owner.nid, "idempotency_key": "adaptation-text:proposal-1",
        "branch_id": None, "owner_actor_id": owner.actor, "proposal_id": "proposal-1"}
    kwargs.update(changes)
    return owner.assets.find_text_result(**kwargs)


def test_server_lookup_requires_scope_and_returns_exact_existing_identity(owner):
    with pytest.raises(ValueError, match="BINDING_REQUIRED"):
        find(owner)
    with lease(owner):
        assert find(owner) is None
        original = create(owner)
        assert find(owner) == original
        assert find(owner, idempotency_key="different-key", proposal_id="different-proposal") is None
        with pytest.raises(ValueError, match="BINDING_REQUIRED"):
            find(owner, branch_id="other-branch")
        with pytest.raises(ValueError, match="BINDING_REQUIRED"):
            find(owner, novel_id="different-novel")
        assert owner.assets.list(owner.nid) == []


@pytest.mark.parametrize("change", ["other-owner", "missing-owner", "deleted", "novel", "branch", "duplicate"])
def test_server_lookup_cannot_treat_hidden_or_ambiguous_identity_as_absent(owner, change):
    from app.services.asset_library_service import AssetIdempotencyConflict
    with lease(owner):
        original = create(owner)
        changed = copy.deepcopy(original)
        if change == "other-owner": changed["_owner_actor_id"] = "different-actor"
        if change == "missing-owner": changed.pop("_owner_actor_id")
        if change == "deleted": changed["deleted_at"] = STAMP
        if change == "novel": changed["novel_id"] = "different-novel"
        if change == "branch": changed["branch_id"] = "different-branch"
        if change == "duplicate":
            changed["id"] = "duplicate-asset"
            owner.assets._bin_path(changed["id"]).write_bytes(TEXT.encode())
        owner.assets._write_meta(changed)
        with pytest.raises(AssetIdempotencyConflict, match="identity conflict"):
            find(owner)
        assert len(list(owner.assets.root.glob("*.bin"))) == (2 if change == "duplicate" else 1)


@pytest.mark.parametrize("corruption", ["json", "shape", "identifier"])
def test_server_lookup_masks_corrupt_metadata_as_integrity_failure(owner, corruption):
    from app.services.asset_library_service import AssetIntegrityError
    with lease(owner):
        create(owner)
        path = owner.assets.root / ("invalid.name.json" if corruption == "identifier" else "broken.json")
        path.write_text("{" if corruption == "json" else "{}", encoding="utf-8")
        with pytest.raises(AssetIntegrityError, match="^text result lookup integrity could not be verified$"):
            find(owner)
        assert len(list(owner.assets.root.glob("*.bin"))) == 1


def test_server_lookup_never_adopts_other_project_or_branch(owner):
    with lease(owner):
        original = create(owner)
    other_scope = {"mode": "collaboration", "novel_id": owner.nid, "workspace_id": "workspace",
        "storyline_id": "storyline", "branch_id": "other-branch"}
    with lease(owner, other_scope):
        assert find(owner, branch_id="other-branch") is None
    with lease(owner):
        changed = copy.deepcopy(original)
        changed["_project_binding"]["incarnation"] = "file:11111111-1111-4111-8111-111111111111"
        owner.assets._write_meta(changed)
        assert find(owner) is None
        assert len(list(owner.assets.root.glob("*.bin"))) == 1


@pytest.mark.parametrize("key", [None, "different-key"])
def test_server_lookup_fences_changed_key_by_original_proposal(owner, key):
    from app.services.asset_library_service import AssetIdempotencyConflict
    with lease(owner):
        original = create(owner)
        changed = copy.deepcopy(original)
        changed["idempotency_key"] = key
        owner.assets._write_meta(changed)
        with pytest.raises(AssetIdempotencyConflict, match="identity conflict"):
            find(owner)
        assert len(list(owner.assets.root.glob("*.bin"))) == 1


@pytest.mark.parametrize("actor", ["member:alice", "alice@example.test", "协作作者", "organization/alice"])
def test_review_accepts_original_opaque_actor_identity(actor):
    value = review_receipt(actor)
    assert contract.validate_review(value, source=source(), actor_id=actor, output_digest=source()["output_digest"]) == value
    with pytest.raises(ValueError, match="REVIEW_BINDING_INVALID"):
        contract.validate_review(value, source=source(), actor_id="different-actor", output_digest=source()["output_digest"])


@pytest.mark.parametrize("actor", ["", " ", "member\nadmin", "x" * 241])
def test_review_actor_remains_bounded_nonempty_control_free(actor):
    with pytest.raises(ValueError):
        contract.validate_review(review_receipt(actor), source=source(), actor_id=actor, output_digest=source()["output_digest"])


@pytest.mark.parametrize("field", ["_owner_actor_id", "_required_features", "version"])
def test_damaged_private_contract_never_falls_back_to_generic_asset_visibility(owner, field):
    with lease(owner):
        row = create(owner)
        path = owner.assets._meta_path(row["id"])
        value = json.loads(path.read_text(encoding='utf-8'))
        if field == "version": value[field] = True
        else: value.pop(field)
        path.write_text(json.dumps(value), encoding='utf-8')
        for actor in (None, owner.actor):
            assert not owner.assets.list(owner.nid, actor_id=actor)
            with pytest.raises(FileNotFoundError): owner.assets.get(row["id"], actor_id=actor)
            with pytest.raises(FileNotFoundError): owner.assets.content(row["id"], actor_id=actor)
