from copy import deepcopy
import pytest
from app.source_privacy import content_digest, effective_source_privacy, source_privacy_status, review_source_privacy


def test_hash_bound_source_review_survives_restart_and_denies_changes(tmp_path):
    chapter={"id":"n:1","novel_id":"n","version":1,"content":"SYNTHETIC_PRIVATE_MARKER"}
    assert effective_source_privacy(chapter, "a", tmp_path)=="LOCAL_ONLY"
    review_source_privacy(chapter,"a","server-actor","CLOUD_ALLOWED",1,content_digest(chapter),tmp_path)
    assert effective_source_privacy(chapter,"a",tmp_path)=="CLOUD_ALLOWED"
    assert effective_source_privacy(chapter,"b",tmp_path)=="LOCAL_ONLY"
    assert effective_source_privacy({**chapter,"version":2},"a",tmp_path)=="LOCAL_ONLY"
    assert effective_source_privacy({**chapter,"content":"changed without version"},"a",tmp_path)=="LOCAL_ONLY"
    assert effective_source_privacy({**chapter,"novel_id":"other"},"a",tmp_path)=="LOCAL_ONLY"
    text=(tmp_path/'v1_capabilities/source_privacy.json').read_text()
    assert chapter['content'] not in text and 'server-actor' in text
    review_source_privacy(chapter,"a","server-actor","LOCAL_ONLY",1,content_digest(chapter),tmp_path)
    assert effective_source_privacy(chapter,"a",tmp_path)=="LOCAL_ONLY"


def test_stale_review_and_explicit_lower_level_restrictions_cannot_be_waived(tmp_path):
    chapter={"id":"n:1","novel_id":"n","version":2,"content":"current","privacy_level":"LOCAL_ONLY"}
    with pytest.raises(ValueError,match="chapter changed"):
        review_source_privacy(chapter,None,"actor","CLOUD_ALLOWED",1,content_digest(chapter),tmp_path)
    review_source_privacy(chapter,None,"actor","CLOUD_ALLOWED",2,content_digest(chapter),tmp_path)
    assert effective_source_privacy(chapter,None,tmp_path)=="LOCAL_ONLY"
    path=tmp_path/'v1_capabilities/source_privacy.json'
    path.write_text('broken')
    assert effective_source_privacy(chapter,None,tmp_path)=="LOCAL_ONLY"
    with pytest.raises(ValueError):
        review_source_privacy(chapter,None,"actor","CLOUD_ALLOWED",2,content_digest(chapter),tmp_path)
    assert path.read_text()=='broken'


def test_explicit_allow_flag_without_review_is_not_an_egress_grant(tmp_path):
    chapter={"id":"n:1","novel_id":"n","version":1,"content":"synthetic","privacy_level":"CLOUD_ALLOWED"}
    assert effective_source_privacy(chapter,root=tmp_path)=="LOCAL_ONLY"
