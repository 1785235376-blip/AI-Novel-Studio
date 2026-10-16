"""Comparator regression: canonical legacy upgrades must not conceal data loss."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

from app.compare_context_backends import _file_raw, _legacy_file_privacy_projection, differences
from app.repositories.postgres.serialization import serialize_character


def test_legacy_raw_projection_matches_migrated_policy_and_keeps_source_bytes(tmp_path):
    directory=tmp_path/"novels/book/characters";directory.mkdir(parents=True)
    path=directory/"characters.json"
    original=b'[{"id":"hero","name":"Synthetic hero","age":31,"status":"ALIVE","trait":"careful"}]\n'
    path.write_bytes(original)
    raw=_file_raw(tmp_path,"book")
    projected,upgrades=_legacy_file_privacy_projection(raw)
    pg=serialize_character(SimpleNamespace(slug="hero",name="Synthetic hero",age=31,life_status="ALIVE",privacy="LOCAL_ONLY",facts={"trait":"careful","_source_privacy_present":False}))
    assert differences(projected["characters"],[pg])==[]
    assert projected["characters"][0]["privacy_level"]==pg["privacy_level"]=="LOCAL_ONLY"
    assert projected["characters"][0]["privacy_status"]=="UNKNOWN"
    assert upgrades==[{"path":"raw.characters[0]","source_privacy_present":False,"source_privacy_level":None,"effective_privacy_level":"LOCAL_ONLY","privacy_status":"UNKNOWN"}]
    assert "privacy_level" not in raw["characters"][0]
    assert path.read_bytes()==original


def test_privacy_downgrade_missing_policy_and_nonprivacy_edits_still_fail():
    raw={"characters":[{"id":"hero","name":"Synthetic","privacy_level":"LOCAL_ONLY","detail":{"facts":["preserve this"]}}]}
    projected,_=_legacy_file_privacy_projection(raw)
    expected=projected["characters"]
    downgraded=copy.deepcopy(expected);downgraded[0]["privacy_level"]="CLOUD_ALLOWED"
    assert differences(expected,downgraded,"raw.characters")==[{"path":"raw.characters[0].privacy_level","file":"LOCAL_ONLY","postgres":"CLOUD_ALLOWED"}]
    missing=copy.deepcopy(expected);missing[0].pop("privacy_level")
    assert differences(expected,missing,"raw.characters")==[{"path":"raw.characters[0].privacy_level","file":"LOCAL_ONLY","postgres":"<missing>"}]
    corrupted=copy.deepcopy(expected);corrupted[0]["detail"]["facts"][0]="changed"
    assert differences(expected,corrupted,"raw.characters")==[{"path":"raw.characters[0].detail.facts[0]","file":"preserve this","postgres":"changed"}]


def test_invalid_legacy_policy_is_conservatively_visible_not_dropped():
    original={"foreshadowing":[{"id":"hint","privacy_level":"INVALID","title":"retain title"}]}
    unchanged=copy.deepcopy(original)
    projected,changes=_legacy_file_privacy_projection(original)
    assert projected["foreshadowing"]==[{"id":"hint","privacy_level":"LOCAL_ONLY","privacy_status":"UNKNOWN","title":"retain title"}]
    assert changes[0]["source_privacy_level"]=="INVALID"
    assert changes[0]["effective_privacy_level"]=="LOCAL_ONLY"
    assert original==unchanged


def test_explicit_policies_and_order_are_preserved_exactly():
    raw={"canon":[{"id":"second","privacy_level":"REDACT_BEFORE_CLOUD","fact":"B"},{"id":"first","privacy_level":"CLOUD_ALLOWED","fact":"A"}],"story_state":{"chapter":2}}
    projected,changes=_legacy_file_privacy_projection(raw)
    assert projected["canon"]==raw["canon"]
    assert projected["story_state"]==raw["story_state"]
    assert changes==[]
    assert differences(projected["canon"],list(reversed(projected["canon"])))
