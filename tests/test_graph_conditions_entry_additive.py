"""Original File/API conditional discovery, Save, execution and human review."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import os,json
import pytest
from test_r3_mounted_contracts import checked,mounted,prefix
from test_v2_independent_workspace_api import client
from test_v2_creative_graph_api import graph_client,scoped_graph_client
from test_v2_graph_local_conditions_api import enable,create,grant
from test_v2_graph_local_conditions import definition

def test_default_gate_and_original_catalog_list_remain_closed(scoped_graph_client,monkeypatch):
 e=scoped_graph_client;monkeypatch.delenv('CREATIVE_GRAPH_CONDITIONS_V1',raising=False)
 old=checked(e.client.get(e.graph_base+'/catalog',headers=e.headers))
 assert all(row['id']!='local_condition' for row in old['definitions'])
 for path in ['/catalog?include_local_conditions=true','?include_local_conditions=true']:
  response=e.client.get(e.graph_base+path,headers=e.headers);assert response.status_code==422,response.text
 enable(monkeypatch);row=create(e,definition(),e.headers)
 assert checked(e.client.get(e.graph_base,headers=e.headers))=={'items':[]}
 assert checked(e.client.get(e.graph_base+'?include_local_conditions=true',headers=e.headers))=={'items':[row]}
 assert checked(e.client.get(e.graph_base+'/catalog',headers=e.headers))==old
 grant(e,('domain.write',));response=e.client.get(e.graph_base+'?include_local_conditions=true',headers=e.headers);assert response.status_code==403

@pytest.mark.parametrize('predicate',[{'kind':'boolean','value':True},{'kind':'enum','value':'A','equals':'B'}])
def test_condition_entry_original_save_whole_preflight_run_review_and_reopen(scoped_graph_client,monkeypatch,predicate):
 enable(monkeypatch);e=scoped_graph_client;catalog=checked(e.client.get(e.graph_base+'/catalog?include_local_conditions=true',headers=e.headers))
 assert len(catalog['definitions'])==6 and catalog['capabilities']['whole_graph_required'] is True
 assert catalog['capabilities']['cache_mode']=='DISABLED_LOCAL_CONDITIONS_V1'
 assert e.client.get(e.graph_base+'/catalog?include_local_conditions=true&include_video=true',headers=e.headers).status_code==403  # Original protected media read takes precedence.
 value=definition(predicate)
 if predicate['kind']=='enum':value['nodes'][0]['parameters']['text']='  \ufeffPinned authored source\u0085 第二行 \u00a0'
 row=create(e,value,e.headers);saved=checked(e.client.put(e.graph_base+'/'+row['id'],headers=e.headers,json={'expected_version':row['version'],'definition':{**row['definition'],'title':'Saved bounded choice'}}))
 assert saved['version']==2;assert checked(e.client.get(e.graph_base+'/'+row['id'],headers=e.headers))==saved
 path=e.graph_base+'/'+row['id'];preflight=checked(e.client.post(path+'/preflight',headers=e.headers,json={'expected_version':saved['version'],'target_node_ids':[]}))
 assert preflight['executable'] and preflight['cache_enabled'] is False
 subset=checked(e.client.post(path+'/preflight',headers=e.headers,json={'expected_version':saved['version'],'target_node_ids':['yes_review']}));assert not subset['executable'] and any(i['code']=='CREATIVE_GRAPH_CONDITION_WHOLE_GRAPH_REQUIRED' for i in subset['issues'])
 intent={'expected_graph_version':saved['version'],'reviewed_preflight_digest':preflight['preflight_digest'],'target_node_ids':preflight['target_node_ids'],'request_id':uuid4().hex}
 queued=checked(e.client.post(path+'/runs',headers=e.headers,json=intent),201);assert checked(e.client.post(path+'/runs',headers=e.headers,json=intent),201)==queued
 run_path=e.studio_base+'/graph-runs/'+queued['id'];waiting=checked(e.client.post(run_path+'/execute',headers=e.headers,json={'expected_version':queued['version']}))
 assert waiting['status']=='WAITING_APPROVAL' and all(s['output'] is None for s in waiting['node_states'].values())
 plan=preflight['conditional_plan'];assert waiting['conditional_runtime']['plan']==plan
 assert all(waiting['node_states'][key]=={'status':'SKIPPED','reviewed':False,'output':None,'error':{'code':'CREATIVE_GRAPH_BRANCH_NOT_SELECTED'}} for key in plan['skipped_node_ids'])
 review=waiting['review'];assert review['node_id'] in plan['active_node_ids']
 assert e.client.post(run_path+'/approve',headers=e.headers,json={'expected_version':waiting['version'],'node_id':review['node_id'],'reviewed_output_digest':'0'*64}).status_code==409
 approved=checked(e.client.post(run_path+'/approve',headers=e.headers,json={'expected_version':waiting['version'],'node_id':review['node_id'],'reviewed_output_digest':review['output_digest']}))
 assert approved['status']=='SUCCEEDED' and approved['reviewed'];assert checked(e.client.get(run_path,headers=e.headers))==approved
 assert approved['cache']=={'hits':0,'misses':3,'mode':'DISABLED_LOCAL_CONDITIONS_V1'}
 assert all(approved['node_states'][key]['output'] is None for key in plan['skipped_node_ids'])
 if os.getenv('GRAPH_CONDITIONS_CAPTURE') and e.prefix=='/api':
  target=Path(__file__).resolve().parents[1]/('.runtime/conditions-wire.json' if predicate['kind']=='boolean' else '.runtime/conditions-enum-wire.json');target.parent.mkdir(exist_ok=True);target.write_text(json.dumps({'catalog':catalog,'graph':saved,'preflight':preflight,'create_body':intent,'queued':queued,'waiting':waiting,'approved':approved},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
