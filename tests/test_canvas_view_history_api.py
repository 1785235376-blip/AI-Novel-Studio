"""Mounted original API; shared admission patch is delivered separately."""
import pytest
from test_r3_mounted_contracts import checked, scoped, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_creative_graph_api import graph_client
from test_canvas_view_api_additive import canvas, body
from test_canvas_view_history import restore_body

def test_mounted_history_restore_and_conflict_keep_security_headers(canvas):
    e=canvas;one=checked(e.client.post(e.canvas_base,json=body()),201);path=e.canvas_base+'/'+one['id']
    checked(e.client.put(path,json={'expected_version':1,'definition':{**one['definition'],'title':'Second'}}))
    response=e.client.get(path+'/history');h=checked(response);assert h['current_version']==2 and response.headers['cache-control']=='no-store'
    value=restore_body(h);saved=checked(e.client.post(path+'/restore',json=value));assert saved['version']==3 and saved['definition']==one['definition']
    assert checked(e.client.get(path))==saved
    assert len(checked(e.client.get(path+'/history'))['items'])==3
    conflict=e.client.post(path+'/restore',json=value);assert conflict.status_code==409 and set(conflict.json()['detail']['current'])<={'version','status'}
    assert conflict.headers['x-content-type-options']=='nosniff'

def test_mounted_scoped_history_restore_rejects_other_actor_and_late_revocation(canvas,monkeypatch):
    e=scoped(canvas,monkeypatch);one=checked(e.client.post(e.canvas_base,headers=e.headers,json=body()),201);path=e.canvas_base+'/'+one['id']
    checked(e.client.put(path,headers=e.headers,json={'expected_version':1,'definition':{**one['definition'],'title':'Second'}}));h=checked(e.client.get(path+'/history',headers=e.headers))
    assert e.client.get(path+'/history',headers=e.viewer_headers).status_code==404
    assert e.client.post(path+'/restore',headers=e.viewer_headers,json=restore_body(h)).status_code==403
    original=e.graphs.canvas_views.history
    def revoked(*a,**k):
        value=original(*a,**k);e.sessions.revoke(e.lead);return value
    monkeypatch.setattr(e.graphs.canvas_views,'history',revoked)
    response=e.client.get(path+'/history',headers=e.headers);assert response.status_code==401 and one['id'] not in response.text


def test_mounted_history_restore_remain_default_off_and_redact_validation(canvas,monkeypatch):
    e=canvas;one=checked(e.client.post(e.canvas_base,json=body()),201);path=e.canvas_base+'/'+one['id']
    checked(e.client.put(path,json={'expected_version':1,'definition':{**one['definition'],'title':'Second'}}));h=checked(e.client.get(path+'/history'))
    bad={**restore_body(h),'private_extra':'never-echo-this-value'}
    response=e.client.post(path+'/restore',json=bad);assert response.status_code==422 and 'never-echo-this-value' not in response.text and response.headers['cache-control']=='no-store'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    for method,suffix,payload in [('GET','/history',None),('POST','/restore',restore_body(h))]:
        response=e.client.request(method,path+suffix,json=payload);assert response.status_code==404 and response.headers['cache-control']=='no-store'
