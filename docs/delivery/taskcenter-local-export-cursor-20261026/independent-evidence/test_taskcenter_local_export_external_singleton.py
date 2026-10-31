from copy import copy,deepcopy
from test_taskcenter_local_export_external import rig,export_rig,get
from test_taskcenter_local_export_external_cases import token,update


def test_actual_singleton_replacement_same_root_cannot_reuse_cursor(export_rig,monkeypatch):
    e=export_rig;t=token(e)
    replacement=copy(e.source) # Original class/methods, no constructor/recovery.
    monkeypatch.setattr(e.legacy,'export_job_service',replacement)
    r=get(e,{'cursor':t});assert r.status_code==409,r.text


def test_private_aba_inside_original_reader_aborts_first_page(export_rig,monkeypatch):
    e=export_rig;original=e.source.list;rid=e.ids[0];row=deepcopy(e.source._read()[rid])
    def changed(*a,**kw):
        result=original(*a,**kw)
        update(e,lambda rows:rows[rid].update(snapshot={'private':'mid-reader-private'}))
        update(e,lambda rows:rows.__setitem__(rid,row))
        return result
    monkeypatch.setattr(e.source,'list',changed)
    r=get(e);assert r.status_code==501,r.text
    assert 'mid-reader-private' not in r.text and 'items' not in r.json()
