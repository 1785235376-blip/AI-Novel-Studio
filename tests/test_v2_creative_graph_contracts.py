"""Pure typed-graph contracts; run with the owned run_v2_checks.py profile.

These tests never create projects, execute nodes, or contact a provider. The
owned runner is still required to isolate the repository's autouse fixtures.
"""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.creative import graph_models as models
from app.experimental.store import canonical


DIGEST = "0123456789abcdef" * 4
DEFINITION_IDS = {
    "text_input", "text_reference", "draft_prepare", "manual_transform",
    "director_note", "human_review", "asset_reference",
}
ASSET = {"asset_id": "asset-one", "version": 1, "digest": DIGEST, "kind": "image"}


def node(node_id="source", definition_id="text_input", **changes):
    value = {"id": node_id, "definition_id": definition_id}
    if definition_id == "asset_reference":
        value["parameters"] = deepcopy(ASSET)
    value.update(changes)
    return value


def edge(edge_id="edge", source="source", target="target", source_port="text", target_port="text"):
    return {"id": edge_id, "source_node_id": source, "source_port": source_port,
            "target_node_id": target, "target_port": target_port}


def connected():
    return {"title": "Graph", "nodes": [node(), node("target", "text_reference")],
            "edges": [edge()]}


def test_catalog_has_exactly_seven_fixed_versioned_definitions():
    definitions = models.catalog_definitions()
    assert len(definitions) == 7
    assert {item["id"] for item in definitions} == DEFINITION_IDS
    expected = {
        "text_input": ([], [("text", "TEXT", False)]),
        "text_reference": ([("text", "TEXT", True)], [("text", "TEXT", False)]),
        "draft_prepare": ([("text", "TEXT", True), ("direction", "DIRECTOR_NOTES", False)],
                          [("draft", "DRAFT", False)]),
        "manual_transform": ([("text", "TEXT", True), ("direction", "DIRECTOR_NOTES", False)],
                             [("draft", "DRAFT", False)]),
        "director_note": ([], [("direction", "DIRECTOR_NOTES", False)]),
        "human_review": ([("draft", "DRAFT", True)], []),
        "asset_reference": ([], [("asset", "ASSET_REF", False)]),
    }
    for item in definitions:
        assert type(item["version"]) is int and item["version"] == 1
        assert item["model_called"] is False
        assert item["executable"] is (item["id"] != "asset_reference")
        assert item["blockers"] == (["CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED"]
                                    if item["id"] == "asset_reference" else [])
        for direction, ports in zip(("inputs", "outputs"), expected[item["id"]]):
            assert item[direction] == [
                {"id": name, "type": kind, "required": required, "multiple": False}
                for name, kind, required in ports
            ]


def test_catalog_is_detached_from_trusted_definition_objects():
    before = models.catalog_definitions()
    changed = models.catalog_definitions()
    for item in changed:
        item["inputs"].append({"id": "forged"})
        item["outputs"].clear()
        item["parameters_schema"]["properties"]["forged"] = {"type": "string"}
        item["blockers"].append("forged")
        if item["default_parameters"] is not None:
            item["default_parameters"]["forged"] = True
    assert models.catalog_definitions() == before


def test_empty_and_disconnected_graphs_are_valid_editable_drafts():
    empty = models.GraphInput(title="Empty draft")
    assert empty.nodes == empty.edges == []
    assert empty.schema_version == 1
    assert empty.viewport.model_dump() == {"x": 0, "y": 0, "zoom": 1}
    disconnected = models.GraphInput.model_validate({
        "title": "Disconnected draft",
        "nodes": [node(f"n{index}", definition) for index, definition in enumerate(sorted(DEFINITION_IDS))],
    })
    assert {item.definition_id for item in disconnected.nodes} == DEFINITION_IDS
    assert disconnected.edges == []


@pytest.mark.parametrize("definition,parameters", [
    ("text_input", {"text": ""}), ("text_reference", {}), ("draft_prepare", {}),
    ("manual_transform", {"result": ""}), ("director_note", {"note": ""}),
    ("human_review", {}), ("asset_reference", ASSET),
])
def test_each_fixed_definition_validates_and_normalizes_its_own_parameters(definition, parameters):
    value = models.NodeInstance.model_validate(node(definition_id=definition))
    assert value.parameters == parameters
    assert value.enabled is True
    assert value.definition_version == 1
    assert value.position.model_dump() == {"x": 0, "y": 0}


def test_valid_typed_dag_supports_fanout_and_optional_direction_inputs():
    graph = models.GraphInput.model_validate({
        "title": "Human-owned draft",
        "nodes": [node(), node("reference", "text_reference"), node("prepare", "draft_prepare"),
                  node("manual", "manual_transform"), node("direction", "director_note"),
                  node("review", "human_review"), node("asset", "asset_reference")],
        "edges": [edge("e1", target="reference"), edge("e2", "reference", "prepare"),
                  edge("e3", target="manual"),
                  edge("e4", "direction", "prepare", "direction", "direction"),
                  edge("e5", "direction", "manual", "direction", "direction"),
                  edge("e6", "prepare", "review", "draft", "draft")],
    })
    assert len(graph.nodes) == 7 and len(graph.edges) == 6
    assert graph.model_dump() == models.GraphInput.model_validate_json(graph.model_dump_json()).model_dump()


def test_defaults_and_caller_owned_payloads_do_not_alias():
    raw = connected()
    before = deepcopy(raw)
    first = models.GraphInput.model_validate(raw)
    second = models.GraphInput.model_validate(raw)
    first.nodes[0].parameters["text"] = "Changed"
    first.nodes[0].position.x = 25
    first.viewport.zoom = 2
    first.edges.clear()
    assert raw == before
    assert second.nodes[0].parameters == {"text": ""}
    assert second.nodes[0].position.x == 0
    assert second.viewport.zoom == 1 and len(second.edges) == 1
    a, b = models.GraphInput(title="A"), models.GraphInput(title="B")
    a.nodes.append(models.NodeInstance.model_validate(node()))
    assert b.nodes == []


@pytest.mark.parametrize("version", [True, False, 1.0, "1", None, 0, 2])
def test_definition_version_is_exact_integer_one(version):
    with pytest.raises(ValidationError):
        models.NodeInstance.model_validate(node(definition_version=version))


@pytest.mark.parametrize("version", [True, False, 1.0, "1", None, 0, 2])
def test_schema_version_is_exact_integer_one(version):
    with pytest.raises(ValidationError):
        models.GraphInput(title="Graph", schema_version=version)


@pytest.mark.parametrize("version", [True, False, 0.0, "0", None, -1, 1])
def test_create_expected_version_is_exact_integer_zero(version):
    with pytest.raises(ValidationError):
        models.GraphCreate(request_id="request", expected_version=version, definition={"title": "Graph"})


@pytest.mark.parametrize("enabled", [0, 1, "true", "false", None, [], {}])
def test_enabled_is_a_strict_boolean(enabled):
    with pytest.raises(ValidationError):
        models.NodeInstance.model_validate(node(enabled=enabled))


@pytest.mark.parametrize("enabled", [True, False])
def test_enabled_accepts_actual_booleans(enabled):
    assert models.NodeInstance.model_validate(node(enabled=enabled)).enabled is enabled


@pytest.mark.parametrize("definition", ["provider", "python", "TEXT_INPUT", "text_input@1", "", None, 7])
def test_unregistered_definitions_are_rejected(definition):
    with pytest.raises(ValidationError):
        models.NodeInstance.model_validate(node(definition_id=definition))


@pytest.mark.parametrize("identifier", ["", "1node", "_node", "-node", "a b", "a/b", "é", "a" * 65, 1, True])
def test_node_and_edge_identifiers_are_strict_bounded_ascii_ids(identifier):
    with pytest.raises(ValidationError):
        models.NodeInstance.model_validate(node(node_id=identifier))
    for field in ("id", "source_node_id", "source_port", "target_node_id", "target_port"):
        value = edge()
        value[field] = identifier
        with pytest.raises(ValidationError):
            models.TypedEdge.model_validate(value)


@pytest.mark.parametrize("identifier", ["a", "Z09_-", "a" * 64])
def test_identifier_boundaries_are_supported(identifier):
    assert models.NodeInstance.model_validate(node(node_id=identifier)).id == identifier
    assert models.TypedEdge.model_validate(edge(edge_id=identifier)).id == identifier


@pytest.mark.parametrize("title", ["", " ", "\n\t", "a" * 161, None, 1, True])
def test_titles_require_nonblank_bounded_strings(title):
    with pytest.raises(ValidationError):
        models.GraphInput(title=title)


def test_title_boundary_and_unicode_are_preserved():
    title = "界" * 160
    assert models.GraphInput(title=title).title == title


@pytest.mark.parametrize("where", ["graph", "node", "edge", "position", "viewport", "parameters"])
def test_unknown_properties_are_rejected_at_every_graph_layer(where):
    raw = connected()
    if where == "graph":
        target = raw
    elif where == "node":
        target = raw["nodes"][0]
    elif where == "edge":
        target = raw["edges"][0]
    elif where == "position":
        target = raw["nodes"][0].setdefault("position", {})
    elif where == "viewport":
        target = raw.setdefault("viewport", {})
    else:
        target = raw["nodes"][0].setdefault("parameters", {})
    target["provider_code"] = "untrusted"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        models.GraphInput.model_validate(raw)


@pytest.mark.parametrize("definition", sorted(DEFINITION_IDS))
def test_each_definition_rejects_arbitrary_parameter_properties(definition):
    raw = node(definition_id=definition)
    raw.setdefault("parameters", {})["execute"] = "arbitrary-code"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        models.NodeInstance.model_validate(raw)


@pytest.mark.parametrize("definition,field,limit", [
    ("text_input", "text", 8_000), ("manual_transform", "result", 8_000),
    ("director_note", "note", 4_000),
])
def test_text_parameter_bounds_and_strict_string_types(definition, field, limit):
    assert models.NodeInstance.model_validate(node(definition_id=definition, parameters={field: "x" * limit})).parameters[field] == "x" * limit
    for invalid in ("x" * (limit + 1), 1, True, None, [], {}):
        with pytest.raises(ValidationError):
            models.NodeInstance.model_validate(node(definition_id=definition, parameters={field: invalid}))


@pytest.mark.parametrize("parameters", [[], "text", 1, True, None])
def test_parameters_require_an_object(parameters):
    with pytest.raises(ValidationError):
        models.NodeInstance.model_validate(node(parameters=parameters))


@pytest.mark.parametrize("field", ["asset_id", "version", "digest", "kind"])
def test_asset_reference_requires_every_pinned_identity_field(field):
    parameters = deepcopy(ASSET)
    del parameters[field]
    with pytest.raises(ValidationError):
        models.NodeInstance.model_validate(node(definition_id="asset_reference", parameters=parameters))


@pytest.mark.parametrize("kind", ["image", "video", "audio"])
def test_asset_reference_accepts_only_supported_kinds(kind):
    assert models.AssetParameters(**{**ASSET, "kind": kind}).kind == kind


@pytest.mark.parametrize("field,value", [
    ("asset_id", ""), ("asset_id", "x" * 241), ("asset_id", 1),
    ("version", True), ("version", False), ("version", "1"), ("version", 1.0),
    ("version", 0), ("version", -1), ("kind", "text"), ("kind", "IMAGE"),
    ("digest", "a" * 63), ("digest", "a" * 65), ("digest", "A" * 64),
    ("digest", "g" * 64), ("digest", 1),
])
def test_asset_reference_rejects_unpinned_or_malformed_values(field, value):
    with pytest.raises(ValidationError):
        models.AssetParameters(**{**ASSET, field: value})


@pytest.mark.parametrize("field", ["source_node_id", "target_node_id"])
def test_edges_cannot_reference_unknown_nodes(field):
    raw = connected()
    raw["edges"][0][field] = "missing"
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_UNKNOWN_NODE"):
        models.GraphInput.model_validate(raw)


@pytest.mark.parametrize("field", ["source_port", "target_port"])
@pytest.mark.parametrize("port", ["missing", "TEXT"])
def test_ports_must_exist_with_exact_case_in_the_correct_direction(field, port):
    raw = connected()
    raw["edges"][0][field] = port
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_UNKNOWN_PORT"):
        models.GraphInput.model_validate(raw)


@pytest.mark.parametrize("source_definition,target_definition,source_port,target_port", [
    ("human_review", "human_review", "draft", "draft"),
    ("text_reference", "text_input", "text", "text"),
    ("draft_prepare", "director_note", "draft", "direction"),
])
def test_input_ports_cannot_be_sources_and_output_ports_cannot_be_targets(
    source_definition, target_definition, source_port, target_port,
):
    raw = {"title": "Invalid direction", "nodes": [node("source", source_definition), node("target", target_definition)],
           "edges": [edge(source_port=source_port, target_port=target_port)]}
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_UNKNOWN_PORT"):
        models.GraphInput.model_validate(raw)


@pytest.mark.parametrize("source_definition,target_definition,source_port,target_port", [
    ("text_input", "human_review", "text", "draft"),
    ("director_note", "text_reference", "direction", "text"),
    ("asset_reference", "text_reference", "asset", "text"),
    ("draft_prepare", "draft_prepare", "draft", "direction"),
])
def test_existing_ports_require_compatible_types(source_definition, target_definition, source_port, target_port):
    raw = {"title": "Type mismatch", "nodes": [node("source", source_definition), node("target", target_definition)],
           "edges": [edge(source_port=source_port, target_port=target_port)]}
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_PORT_TYPE_MISMATCH"):
        models.GraphInput.model_validate(raw)


def test_duplicate_node_ids_are_rejected():
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_DUPLICATE_ID"):
        models.GraphInput(title="Duplicate", nodes=[node(), node(definition_id="director_note")])


def test_duplicate_edge_ids_are_rejected_even_when_endpoints_differ():
    raw = connected()
    raw["nodes"].append(node("other", "text_reference"))
    raw["edges"].append(edge(target="other"))
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_DUPLICATE_ID"):
        models.GraphInput.model_validate(raw)


def test_duplicate_edge_endpoints_are_rejected_even_when_ids_differ():
    raw = connected()
    raw["edges"].append(edge(edge_id="different"))
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_DUPLICATE_EDGE"):
        models.GraphInput.model_validate(raw)


def test_single_input_cardinality_rejects_two_distinct_sources():
    raw = connected()
    raw["nodes"].append(node("other"))
    raw["edges"].append(edge(edge_id="different", source="other"))
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_PORT_CARDINALITY"):
        models.GraphInput.model_validate(raw)


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("size", [1, 2, 3])
def test_self_loops_and_cycles_fail_even_for_disabled_nodes(enabled, size):
    raw = {"title": "Cyclic", "nodes": [node(f"n{i}", "text_reference", enabled=enabled) for i in range(size)],
           "edges": [edge(f"e{i}", f"n{i}", f"n{(i + 1) % size}") for i in range(size)]}
    message = "cannot depend on itself" if size == 1 else "must be acyclic"
    with pytest.raises(ValidationError, match=message):
        models.GraphInput.model_validate(raw)


def test_disabling_a_node_does_not_bypass_port_validation():
    raw = connected()
    raw["nodes"][0]["enabled"] = False
    raw["edges"][0]["source_port"] = "forged"
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_UNKNOWN_PORT"):
        models.GraphInput.model_validate(raw)


@pytest.mark.parametrize("model,field", [
    (models.Position, "x"), (models.Position, "y"),
    (models.Viewport, "x"), (models.Viewport, "y"), (models.Viewport, "zoom"),
])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "1", True, None])
def test_geometry_is_finite_and_does_not_coerce_strings_or_booleans(model, field, value):
    with pytest.raises(ValidationError):
        model(**{field: value})


@pytest.mark.parametrize("field", ["x", "y"])
def test_canvas_coordinate_boundaries(field):
    for boundary in (-100_000.0, 100_000.0):
        assert getattr(models.Position(**{field: boundary}), field) == boundary
    for invalid in (-100_000.01, 100_000.01):
        with pytest.raises(ValidationError):
            models.Position(**{field: invalid})


def test_zoom_boundaries():
    for boundary in (0.35, 2.5):
        assert models.Viewport(zoom=boundary).zoom == boundary
    for invalid in (0, -1, 0.349, 2.501):
        with pytest.raises(ValidationError):
            models.Viewport(zoom=invalid)


def test_node_and_edge_list_budgets_are_bounded_before_graph_evaluation():
    assert models.MAX_NODES == 16 and models.MAX_EDGES == 40
    raw = {"title": "Bounded", "nodes": [node(f"n{i}") for i in range(models.MAX_NODES)]}
    assert len(models.GraphInput.model_validate(raw).nodes) == models.MAX_NODES
    raw["nodes"].append(node("overflow"))
    with pytest.raises(ValidationError) as error:
        models.GraphInput.model_validate(raw)
    assert any(item["loc"] == ("nodes",) and item["type"] == "too_long" for item in error.value.errors())
    raw = connected()
    raw["edges"] = [edge(f"e{i}") for i in range(models.MAX_EDGES + 1)]
    with pytest.raises(ValidationError) as error:
        models.GraphInput.model_validate(raw)
    assert any(item["loc"] == ("edges",) and item["type"] == "too_long" for item in error.value.errors())


def test_definition_byte_budget_accepts_exact_limit_and_rejects_one_extra_byte():
    assert models.MAX_DEFINITION_BYTES == 96_000
    raw = models.GraphInput.model_validate({
        "title": "Capacity", "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.0},
        "nodes": [node(f"n{i}", position={"x": 0.0, "y": 0.0}) for i in range(models.MAX_NODES)],
    }).model_dump()
    remaining = models.MAX_DEFINITION_BYTES - len(canonical(raw).encode("utf-8"))
    for item in raw["nodes"]:
        length = min(remaining, 8_000)
        item["parameters"]["text"] = "x" * length
        remaining -= length
    assert remaining == 0
    assert len(canonical(raw).encode("utf-8")) == models.MAX_DEFINITION_BYTES
    accepted = models.GraphInput.model_validate(raw)
    assert len(canonical(accepted.model_dump()).encode("utf-8")) == models.MAX_DEFINITION_BYTES
    raw["nodes"][-1]["parameters"]["text"] += "x"
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_DEFINITION_CAPACITY"):
        models.GraphInput.model_validate(raw)


def test_definition_budget_counts_utf8_bytes_rather_than_characters():
    raw = {"title": "Unicode capacity", "nodes": [
        node(f"n{i}", parameters={"text": "界" * 4_000}) for i in range(8)
    ]}
    assert len(canonical(raw)) < models.MAX_DEFINITION_BYTES
    assert len(canonical(raw).encode("utf-8")) > models.MAX_DEFINITION_BYTES
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_DEFINITION_CAPACITY"):
        models.GraphInput.model_validate(raw)


ENVELOPES = [
    (models.GraphCreate, {"request_id": "request", "definition": {"title": "Graph"}}),
    (models.GraphSave, {"expected_version": 1, "definition": {"title": "Graph"}}),
    (models.GraphPreflight, {"expected_version": 1}),
    (models.GraphRunCreate, {"expected_graph_version": 1, "reviewed_preflight_digest": DIGEST, "request_id": "request"}),
    (models.GraphAction, {"expected_version": 1}),
]


@pytest.mark.parametrize("model,payload", ENVELOPES)
def test_transport_envelopes_accept_documented_fields_and_reject_extras(model, payload):
    assert model.model_validate(deepcopy(payload))
    with pytest.raises(ValidationError, match="extra_forbidden"):
        model.model_validate({**deepcopy(payload), "provider": "untrusted"})


@pytest.mark.parametrize("model,payload", ENVELOPES[1:])
@pytest.mark.parametrize("version", [True, False, "1", 1.0, 0, -1, None])
def test_transport_expected_versions_are_strict_positive_integers(model, payload, version):
    field = "expected_graph_version" if model is models.GraphRunCreate else "expected_version"
    with pytest.raises(ValidationError):
        model.model_validate({**deepcopy(payload), field: version})


@pytest.mark.parametrize("model,payload", [ENVELOPES[2], ENVELOPES[3]])
def test_target_selection_has_a_finite_id_budget(model, payload):
    assert model.model_validate(payload).target_node_ids == []
    targets = [f"n{i}" for i in range(models.MAX_NODES)]
    assert model.model_validate({**payload, "target_node_ids": targets}).target_node_ids == targets
    for invalid in (targets + ["overflow"], ["bad id"], [1], "source", None):
        with pytest.raises(ValidationError):
            model.model_validate({**payload, "target_node_ids": invalid})


def test_review_action_is_bounded_and_digest_fenced():
    action = models.GraphAction(expected_version=1, node_id="review", reviewed_output_digest=DIGEST, note="x" * 1_000)
    assert action.reviewed_output_digest == DIGEST
    for field, value in (("note", "x" * 1_001), ("note", 1), ("node_id", "bad id"),
                         ("reviewed_output_digest", "A" * 64), ("reviewed_output_digest", "a" * 63)):
        with pytest.raises(ValidationError):
            models.GraphAction.model_validate({"expected_version": 1, field: value})


def test_run_creation_requires_a_reviewed_preflight_digest_and_idempotency_id():
    raw = deepcopy(ENVELOPES[3][1])
    for field in ("expected_graph_version", "reviewed_preflight_digest", "request_id"):
        missing = {key: value for key, value in raw.items() if key != field}
        with pytest.raises(ValidationError):
            models.GraphRunCreate.model_validate(missing)
    for digest in ("A" * 64, "a" * 63, "a" * 65, "z" * 64, 1, None):
        with pytest.raises(ValidationError):
            models.GraphRunCreate.model_validate({**raw, "reviewed_preflight_digest": digest})


def test_generated_graph_schema_exposes_budgets_fixed_versions_and_closed_objects():
    schema = models.GraphInput.model_json_schema()
    assert schema["additionalProperties"] is False
    properties = schema["properties"]
    assert properties["schema_version"]["const"] == 1
    assert properties["nodes"]["maxItems"] == models.MAX_NODES
    assert properties["edges"]["maxItems"] == models.MAX_EDGES
    assert properties["title"]["minLength"] == 1 and properties["title"]["maxLength"] == 160
    definitions = schema["$defs"]
    for name in ("NodeInstance", "TypedEdge", "Position", "Viewport"):
        assert definitions[name]["additionalProperties"] is False
    node_schema = definitions["NodeInstance"]["properties"]
    assert set(node_schema["definition_id"]["enum"]) == DEFINITION_IDS
    assert node_schema["definition_version"]["const"] == 1
    assert node_schema["enabled"]["type"] == "boolean"
    assert definitions["Viewport"]["properties"]["zoom"]["minimum"] == 0.35
    assert definitions["Viewport"]["properties"]["zoom"]["maximum"] == 2.5


def test_catalog_parameter_schemas_match_their_validated_defaults_and_asset_pins():
    for definition in models.catalog_definitions():
        schema = definition["parameters_schema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        if definition["id"] == "asset_reference":
            assert definition["default_parameters"] is None
            assert set(schema["required"]) == {"asset_id", "version", "digest", "kind"}
            assert schema["properties"]["version"]["type"] == "integer"
            assert schema["properties"]["version"]["minimum"] == 1
            assert set(schema["properties"]["kind"]["enum"]) == {"image", "video", "audio"}
        else:
            normalized = models.NodeInstance.model_validate(node(definition_id=definition["id"]))
            assert definition["default_parameters"] == normalized.parameters
