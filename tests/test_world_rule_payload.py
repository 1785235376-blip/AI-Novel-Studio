import pytest

from app.api import normalize_world_rule_payload


def test_world_rule_payload_normalizes_terms():
    payload = normalize_world_rule_payload({"statement": "能力有代价", "forbidden": "永生, 永生,无需代价"})
    assert payload["forbidden_terms"] == ["永生", "无需代价"]
    assert "forbidden" not in payload


def test_world_rule_payload_rejects_too_many_terms():
    with pytest.raises(ValueError, match="at most 100"):
        normalize_world_rule_payload({"statement": "规则", "forbidden_terms": [str(i) for i in range(101)]})
