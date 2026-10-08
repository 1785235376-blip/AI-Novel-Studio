"""RC regression: stricter model request grammar, unchanged host acceptance.

Synthetic outputs here are negative/dispatch contracts; live-model evidence is
collected separately and must never be inferred from this test suite.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError as SchemaValidationError, validate
from pydantic import ValidationError as HostValidationError

from app.model_center.discovery_bridge import _llama_grammar_schema
from app.services.ai_planning_service import StartupPlanningOutput, startup_output_schema
from test_full_recovery_core_chain import core, record, queued, ready  # noqa: F401


@pytest.mark.parametrize("kind", ["WORLD", "CHARACTERS", "OUTLINE"])
def test_kind_specific_contract_accepts_original_valid_payload(kind):
    value = {"candidates": [{"record": record(kind)}]}
    validate(value, startup_output_schema(kind, 1))
    assert StartupPlanningOutput.model_validate(value).candidates[0].record.kind == kind


@pytest.mark.parametrize("requested,other", [("WORLD", "CHARACTERS"), ("CHARACTERS", "OUTLINE"), ("OUTLINE", "WORLD")])
def test_actual_wire_contract_no_longer_permits_a_different_kind(requested, other):
    value = {"candidates": [{"record": record(other)}]}
    # This was syntactically permitted by the old grammar, then failed only
    # after spending inference tokens at the host's requested-kind check.
    validate(value, _llama_grammar_schema(StartupPlanningOutput.model_json_schema()))
    with pytest.raises(SchemaValidationError):
        validate(value, _llama_grammar_schema(startup_output_schema(requested, 1)))


@pytest.mark.parametrize("kind,missing", [("WORLD", "world_summary"), ("WORLD", "world_rules"), ("WORLD", "locations"), ("CHARACTERS", "characters"), ("OUTLINE", "outline")])
def test_required_payload_survives_the_existing_llama_grammar_projection(kind, missing):
    value = {"candidates": [{"record": record(kind)}]}
    value["candidates"][0]["record"].pop(missing)
    validate(value, _llama_grammar_schema(StartupPlanningOutput.model_json_schema()))
    with pytest.raises(SchemaValidationError):
        validate(value, _llama_grammar_schema(startup_output_schema(kind, 1)))


def test_dispatch_uses_narrow_contract_but_existing_host_still_rejects_empty_world(core):
    core.runtime.model_registry = SimpleNamespace(resolve=lambda *_: SimpleNamespace(structured_output=True))
    payload = record("WORLD")
    payload["world_rules"] = []
    core.runtime.output = json.dumps({"candidates":[{"record":payload}]})
    row = queued(core,"WORLD")
    result = core.planning.execute(core.nid,core.scope,row["id"])
    assert result["status"] == "FAILED"
    assert result["error_code"] == "PLANNING_VALIDATION_FAILED"
    assert result["validation_issues"] == [{"loc":["candidates",0,"record"],"type":"value_error"}]
    assert not core.novels.get(core.nid).get("world_summary")
    sent = core.runtime.calls[0].structured_output_schema
    assert sent["$defs"]["WorkbenchRecordIn"]["properties"]["kind"]["enum"] == ["WORLD"]
    assert len(core.runtime.calls)==1  # No implicit retry or fabricated repair.


def test_validation_diagnostics_do_not_disclose_model_values_or_unknown_keys(core):
    secret = "private-provider-token-http://secret.example"
    payload = record("WORLD")
    payload[secret] = secret
    core.runtime.output = json.dumps({"candidates":[{"record":payload}]})
    row = queued(core,"WORLD")
    result = core.planning.execute(core.nid,core.scope,row["id"])
    assert result["status"] == "FAILED"
    assert result["validation_issues"] == [{"loc":["candidates",0,"record","<field>"],"type":"extra_forbidden"}]
    assert secret not in json.dumps(result)
    assert not core.novels.get(core.nid).get("world_summary")


def test_real_old_world_response_mixed_payload_is_prevented_by_new_wire_contract():
    # Exact public-fiction model output from old-schema-attempt2 (Qwen/llama.cpp),
    # retained as a regression fixture. This test itself is not live inference.
    value=json.loads((Path(__file__).parent/'fixtures/rc_world_mixed_payload.json').read_text(encoding='utf8'))
    record=value['candidates'][0]['record']
    assert record['kind']=='WORLD' and record['characters'] and record['outline']
    validate(value,_llama_grammar_schema(StartupPlanningOutput.model_json_schema()))
    with pytest.raises(HostValidationError,match='character payload is only allowed for CHARACTERS'):
        StartupPlanningOutput.model_validate(value)
    wire=_llama_grammar_schema(startup_output_schema('WORLD',1))
    properties=wire['$defs']['WorkbenchRecordIn']['properties']
    assert 'characters' not in properties and 'outline' not in properties
    assert wire['$defs']['WorkbenchRecordIn']['additionalProperties'] is False
    with pytest.raises(SchemaValidationError,match='Additional properties'):
        validate(value,wire)
