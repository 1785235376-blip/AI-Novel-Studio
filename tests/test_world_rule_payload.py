import pytest

from app.api import normalize_world_rule_payload, world_rule_violations


def test_world_rule_payload_normalizes_terms():
    payload = normalize_world_rule_payload({"statement": "能力有代价", "forbidden": "永生, 永生,无需代价"})
    assert payload["forbidden_terms"] == ["永生", "无需代价"]
    assert "forbidden" not in payload


def test_world_rule_payload_rejects_too_many_terms():
    with pytest.raises(ValueError, match="at most 100"):
        normalize_world_rule_payload({"statement": "规则", "forbidden_terms": [str(i) for i in range(101)]})


@pytest.mark.parametrize("field", ["forbidden", "forbidden_terms"])
@pytest.mark.parametrize("separator", [",", "，", "\n", "\r\n"])
def test_world_rule_string_terms_match_editor_delimiters(field, separator):
    original = {"statement": "能力有代价", field: separator.join([" 永生 ", "永生", "无需代价", ""])}
    result = normalize_world_rule_payload(original)
    assert result == {"statement": "能力有代价", "forbidden_terms": ["永生", "无需代价"]}
    assert original[field].endswith(separator)


def test_world_rule_explicit_list_preserves_literal_commas_and_precedence():
    result = normalize_world_rule_payload({
        "statement": "规则", "forbidden": "ignored,legacy",
        "forbidden_terms": ["one,two", " one,two ", "three，four", ""],
    })
    assert result == {"statement": "规则", "forbidden_terms": ["one,two", "three，four"]}


@pytest.mark.parametrize("field", ["forbidden", "forbidden_terms"])
def test_world_rule_string_limit_applies_after_splitting(field):
    with pytest.raises(ValueError, match="at most 100"):
        normalize_world_rule_payload({"statement": "规则", field: ",".join(str(i) for i in range(101))})


def test_normalized_world_rule_detects_individual_forbidden_terms():
    payload = normalize_world_rule_payload({"statement": "能力有代价", "forbidden": "永生,无需代价"})
    findings = world_rule_violations("novel-1", "他获得了永生。", [{"id": "rule-1", "payload": payload}])
    assert len(findings) == 1
    assert findings[0]["finding_type"] == "WORLD_RULE_VIOLATION"
    assert findings[0]["evidence_ids"] == ["永生"]


@pytest.mark.parametrize("terms", ["", " \t ", ",，\n\r\n", []])
def test_world_rule_empty_terms_are_omitted(terms):
    assert normalize_world_rule_payload({"statement": "规则", "forbidden_terms": terms}) == {"statement": "规则"}


@pytest.mark.parametrize("terms", [None, True, 42, {"term": "永生"}, ("永生",)])
def test_world_rule_invalid_term_containers_are_rejected(terms):
    with pytest.raises(ValueError, match="at most 100"):
        normalize_world_rule_payload({"statement": "规则", "forbidden_terms": terms})


def test_world_rule_normalization_preserves_metadata_without_mutating_input():
    original = {"statement": "规则", "forbidden": "one,two", "description": "Author's explanation"}
    assert normalize_world_rule_payload(original) == {
        "statement": "规则", "forbidden_terms": ["one", "two"], "description": "Author's explanation",
    }
    assert original == {"statement": "规则", "forbidden": "one,two", "description": "Author's explanation"}
