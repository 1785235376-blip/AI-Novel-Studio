from test_taskcenter_mixed_external import rig,export_rig,mixed_rig,get
from test_taskcenter_mixed_external_cases import token


def test_registry_order_change_inside_last_final_component_restarts(mixed_rig,monkeypatch):
    e=mixed_rig;t=token(e);adapter=e.api.taskcenter_cursor_adapter.mixed_adapter
    component=adapter.components['exports'];original=component._checked_capture;count=[0]
    def changed(*a,**kw):
        result=original(*a,**kw);count[0]+=1
        if count[0]==3:
            service=e.api.workspace_tools_service
            monkeypatch.setattr(service,'task_readers',tuple(reversed(service.task_readers)))
        return result
    monkeypatch.setattr(component,'_checked_capture',changed)
    r=get(e,{'cursor':t});assert count[0]==3
    assert r.status_code==409,r.text
