from copy import deepcopy
import pytest
from app.experimental.store import ExperimentalStore,TEAM_LIFECYCLE,TEAM_COLLECTION
from app.creative.project_store import CreativeProjectStore

SCOPE={'mode':'collaboration','novel_id':'book','workspace_id':'w','storyline_id':'s','branch_id':'b'}

def seed(tmp_path):
    (tmp_path/'novels/book').mkdir(parents=True)
    store=ExperimentalStore(tmp_path);CreativeProjectStore(store).incarnation('book')
    with store.transaction('book',SCOPE) as d:
        d['collections'][TEAM_COLLECTION]={'x':{'id':'x','status':'QUEUED'}}
    return store


def capture(s):return s.capture_committed_collection('book',SCOPE,TEAM_COLLECTION)


@pytest.mark.parametrize('kind',['aba','recreate','other','rollback','reserved_null','reserved_drop'])
def test_original_team_boundary(tmp_path,kind):
    s=seed(tmp_path);first=capture(s);row=deepcopy(first['rows'][0]);before=s.path('book',SCOPE).read_bytes()
    if kind in {'reserved_null','reserved_drop'}:
        with pytest.raises(ValueError):
            with s.transaction('book',SCOPE) as d:
                if kind=='reserved_null':d[TEAM_LIFECYCLE]=None
                else:d.pop(TEAM_LIFECYCLE)
        assert s.path('book',SCOPE).read_bytes()==before
    elif kind=='rollback':
        with pytest.raises(RuntimeError):
            with s.transaction('book',SCOPE) as d:
                d['collections'][TEAM_COLLECTION]['x']['status']='RUNNING';raise RuntimeError()
        assert capture(s)==first
    elif kind=='other':
        with s.transaction('book',SCOPE) as d:d['collections']['other']={'z':{'private':'change'}}
        assert capture(s)==first
    else:
        with s.transaction('book',SCOPE) as d:
            if kind=='recreate':del d['collections'][TEAM_COLLECTION]['x']
            else:d['collections'][TEAM_COLLECTION]['x']['status']='RUNNING'
        with s.transaction('book',SCOPE) as d:d['collections'][TEAM_COLLECTION]['x']=row
        assert capture(s)['rows']==first['rows']
        assert capture(s)['row_lifecycles']!=first['row_lifecycles']


def test_uncommitted_never_observed(tmp_path):
    s=seed(tmp_path);before=capture(s)
    with s.transaction('book',SCOPE) as d:
        d['collections'][TEAM_COLLECTION]['x']['status']='RUNNING'
        assert capture(s)==before
    assert capture(s)!=before


def test_reserved_null_into_missing_and_legacy(tmp_path):
    s=ExperimentalStore(tmp_path)
    for legacy in (False,True):
        if legacy:
            s.path('book',SCOPE).parent.mkdir(parents=True,exist_ok=True)
            import json
            s.path('book',SCOPE).write_text(json.dumps(s.empty('book',SCOPE)))
        before=s.path('book',SCOPE).read_bytes() if legacy else None
        with pytest.raises(ValueError):
            with s.transaction('book',SCOPE) as d:d[TEAM_LIFECYCLE]=None
        assert (s.path('book',SCOPE).read_bytes() if s.path('book',SCOPE).exists() else None)==before
