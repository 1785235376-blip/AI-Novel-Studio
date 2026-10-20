import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
import pytest
from app.experimental.interactive_story import StorySpec, play, parse_condition
from app.experimental.ink_export import InkExportAdapter, ink_literal, expression


def story():
    return StorySpec.model_validate({'title':'Ink fixture','graph_id':'graph','graph_version':1,'entry_node_id':'a', 'max_steps':8,
      'variables':[{'name':'flag','type':'bool','initial':False}, {'name':'count','type':'int','initial':-10000,'minimum':-10000,'maximum':10000}],
      'nodes':[
        {'node_id':'a','node_version':1,'title':'Gate','dialogue':'INCLUDE secret.ink\nEXTERNAL bad()\n-> evil #tag {bad()} [choice] " \\ // /* */ <>',
         'choices':[{'id':'again','label':'Again # {x} [y] " ->','target':'a','assignments':{'flag':True,'count':10000}},
                    {'id':'finish','label':'Finish','target':'b','condition':'flag and count == 10000'},
                    {'id':'other','label':'Other','target':'c','condition':'not flag and count < 0'}]},
        {'node_id':'b','node_version':1,'title':'End','ending':'Good'},
        {'node_id':'c','node_version':1,'title':'Other','choices':[{'id':'finish','label':'Converge','target':'b','assignments':{'count':0}}]}]}).model_dump()


def test_ink_pure_contract_and_rejections():
    s=story(); a=InkExportAdapter(); files=a.files(s,{})
    assert b'+ {' in files['ink/story.ink']
    m=json.loads(files['ink/validation.json']); assert m['artifact_runtime']=='NOT_RUN'
    assert m['source_map']['nodes']=={'a':'ans_node_0','b':'ans_node_1','c':'ans_node_2'}
    assert m['implementation']=='COMMUNITY_JAVASCRIPT_PORT_NOT_NATIVE_CSHARP'
    for prefix in m['witnesses']:
        for i,state in enumerate(prefix['states']):
            original=play(s,prefix['choices'][:i]); assert state['node_id']==original['node']['node_id']
            assert state['variables']==original['variables'] and state['steps']==original['steps']
    for value in ['bad\nINCLUDE secret', 'bad\tchoice']:
        bad=deepcopy(s);bad['nodes'][0]['choices'][0]['label']=value
        assert not a.validate(bad)['can_review']
        with pytest.raises(ValueError): a.files(bad,{})
    with pytest.raises(ValueError): ink_literal('bad\nnext')
    with pytest.raises(ValueError):
        bad=deepcopy(s);bad['variables'][1]['initial']=2**53; a.files(bad,{})
    assert expression(parse_condition('not flag or count >= -10000'), {'flag':'ans_var_0','count':'ans_var_1'})=='((not ans_var_0) or (ans_var_1 >= -10000))'


def test_actual_pinned_inkjs_compiler_runtime_replay_and_persistence():
    root=os.environ.get('POEMSEED_INKJS_ROOT'); node=os.environ.get('POEMSEED_NODE')
    if not root or not node: pytest.skip('pinned inkjs 2.3.2 runtime opt-in required')
    s=story(); paths=[[],['again'],['again','again','finish'],['other','finish'],['again']*8]
    cases=[]; expected=[]
    for path in paths:
        files=InkExportAdapter().files(s,{}); indices=[]
        for i,cid in enumerate(path):
            p=play(s,path[:i]); indices.append([c['id'] for c in p['choices'] if c['enabled']].index(cid))
        cases.append({'source':files['ink/story.ink'].decode(),'variables':['ans_var_0','ans_var_1'],'indices':indices})
        expected.append([play(s,path[:i]) for i in range(len(path)+1)])
    result=subprocess.run([node,str(Path(__file__).parents[1]/'scripts/verify_ink_runtime.cjs')],input=json.dumps(cases),text=True,encoding='utf-8',capture_output=True,timeout=30,check=False)
    assert result.returncode == 0, result.stderr[-5000:]
    results=json.loads(result.stdout)
    assert len(results)==len(expected)==len(cases)
    for actual,states in zip(results,expected):
        assert len(actual['snapshots'])==len(states)
        assert actual['fileCalls']==0 and not actual['errors']
        for got,want in zip(actual['snapshots'],states):
            assert got['node']==['a','b','c'].index(want['node']['node_id'])
            assert got['steps']==want['steps']
            assert ['PLAYING','ENDING','STEP_CAP_REACHED','NO_EXIT'][got['status']]==want['status']
            assert got['values']=={'ans_var_0':want['variables']['flag'],'ans_var_1':want['variables']['count']}
            assert all(type(got['values'][k]) is type(v) for k,v in {'ans_var_0':want['variables']['flag'],'ans_var_1':want['variables']['count']}.items())
            assert got['choices']==([c['label'] for c in want['choices'] if c['enabled']] if want['status']=='PLAYING' else [])
        assert actual['snapshots'][0]['output']==s['nodes'][0]['dialogue']+'\n'

from test_r5_interactive_story import interactive_env, create, approve, spec
from test_r4_revision_intelligence import revision_env
import base64
import io
import zipfile
from app.experimental.common import StaleSourceError


def test_original_export_owner_ink_receipt_and_source_drift(interactive_env):
    e=interactive_env; row=approve(e,create(e)); value={'expected_version':row['version']}
    preview=e.service.export_preview(e.nid,e.scope,'author',row['id'],value)
    assert preview['can_export'] and preview['ink_target']['version']=='2.3.2'
    assert any(a['target']=='INKJS_2_3_2_TYPED_TEXT_SUBSET' for a in preview['engine_adapters'])
    out=e.service.export(e.nid,e.scope,'author',row['id'],{**value,'preview_digest':preview['preview_digest']})
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(out['content_base64']))) as z:
        prefix='interactive-story-'+row['id']+'/'
        manifest=json.loads(z.read(prefix+'ink/validation.json'))
        exported_script=z.read(prefix+'ink/story.ink').decode()
        receipt=json.loads(z.read(prefix+'source-receipt.json'))
        assert receipt['adaptation_version']==row['version']
        assert receipt['export_preview_digest']==preview['preview_digest']
        assert manifest['artifact_runtime']=='NOT_RUN'
        assert 'ink/story.ink' in json.loads(z.read(prefix+'checksums.json'))
    if os.environ.get('POEMSEED_INKJS_ROOT') and os.environ.get('POEMSEED_NODE'):
        cases=[]; expected=[]
        for witness in row['analysis']['endings']:
            path=witness['choices']; states=[play(row['spec'],path[:i]) for i in range(len(path)+1)]
            indices=[[c['id'] for c in state['choices'] if c['enabled']].index(cid) for state,cid in zip(states,path)]
            cases.append({'source':exported_script,'variables':['ans_var_0','ans_var_1'],'indices':indices}); expected.append(states)
        run=subprocess.run([os.environ['POEMSEED_NODE'],str(Path(__file__).parents[1]/'scripts/verify_ink_runtime.cjs')],input=json.dumps(cases),text=True,encoding='utf-8',capture_output=True,timeout=30)
        assert run.returncode==0,run.stderr[-3000:]
        runtime_results=json.loads(run.stdout)
        assert len(runtime_results)==len(expected)==len(cases)
        for actual,states in zip(runtime_results,expected):
            assert len(actual['snapshots'])==len(states)
            assert actual['fileCalls']==0
            for got,want in zip(actual['snapshots'],states):
                assert got['values']=={'ans_var_0':want['variables']['courage'],'ans_var_1':want['variables']['trusted']}
                assert got['choices']==[c['label'] for c in want['choices'] if c['enabled']]
                assert got['node']==[n['node_id'] for n in row['spec']['nodes']].index(want['node']['node_id'])
                assert got['steps']==want['steps']
            assert 'Alice' in actual['snapshots'][0]['output'] and '🙂é' in actual['snapshots'][0]['output']
    with pytest.raises(FileNotFoundError): e.service.export_preview(e.nid,e.scope,'other',row['id'],value)
    e.chapters.save(e.cid,{'version':e.chapter['version'],'content':'changed'})
    with pytest.raises(StaleSourceError): e.service.export(e.nid,e.scope,'author',row['id'],{**value,'preview_digest':preview['preview_digest']})


@pytest.mark.parametrize('unsupported', ['line one\nline two', 'one\ttwo', 'one\rtwo'])
def test_original_export_preflight_surfaces_unsupported_ink_semantics(interactive_env, unsupported):
    e=interactive_env;s=spec(e);s['nodes'][0]['choices'][0]['label']=unsupported
    row=approve(e,create(e,s));value={'expected_version':row['version']}
    p=e.service.export_preview(e.nid,e.scope,'author',row['id'],value)
    assert p['can_export'] and p['ink_target']['compatibility']=='UNSUPPORTED'
    assert any('INK_UNSUPPORTED_CHOICE_WHITESPACE' in loss for loss in p['losses'])
    out=e.service.export(e.nid,e.scope,'author',row['id'],{**value,'preview_digest':p['preview_digest']})
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(out['content_base64']))) as z:
        prefix='interactive-story-'+row['id']+'/'
        assert prefix+'ink/story.ink' not in z.namelist()
        assert json.loads(z.read(prefix+'ink/validation.json'))['compatibility']=='UNSUPPORTED'
        from app.experimental.interactive_story import renpy_export
        assert z.read(prefix+'game/story.rpy').decode()==renpy_export(row['spec'],e.service._owned(e.nid,e.scope,'author',row['id'])['capture']['characters'])
        assert json.loads(z.read(prefix+'story.json'))['spec']['nodes'][0]['choices'][0]['label']==s['nodes'][0]['choices'][0]['label']

@pytest.mark.parametrize('condition', ['True','False','flag == False','flag != True','count < 0','count <= -10000',
    'count > 0','count >= -10000','not (flag or count > 0)','flag and count == 0','count != 10000'])
def test_actual_runtime_typed_operator_choices(condition):
    root=os.environ.get('POEMSEED_INKJS_ROOT'); node=os.environ.get('POEMSEED_NODE')
    if not root or not node: pytest.skip('pinned inkjs runtime opt-in required')
    s=story();s['nodes'][0]['choices'][1]['condition']=condition
    source=InkExportAdapter().files(s,{})['ink/story.ink'].decode()
    request=[{'source':source,'variables':['ans_var_0','ans_var_1'],'indices':[]}]
    result=subprocess.run([node,str(Path(__file__).parents[1]/'scripts/verify_ink_runtime.cjs')],input=json.dumps(request),text=True,capture_output=True,timeout=30)
    assert result.returncode==0, result.stderr[-3000:]
    results=json.loads(result.stdout); assert len(results)==1
    actual=results[0]; assert actual['fileCalls']==0 and len(actual['snapshots'])==1
    assert actual['snapshots'][0]['choices']==[c['label'] for c in play(s,[])['choices'] if c['enabled']]


def test_witnesses_globally_bounded_with_explicit_truncation(monkeypatch):
    import app.experimental.ink_export as module
    monkeypatch.setattr(module,'WITNESS_STATE_LIMIT',1)
    m=json.loads(InkExportAdapter().files(story(),{})['ink/validation.json'])
    assert m['witnesses_truncated'] and not m['witnesses'] and m['witness_states']==0
    monkeypatch.setattr(module,'WITNESS_STATE_LIMIT',1024)
    monkeypatch.setattr(module,'WITNESS_BYTE_LIMIT',10)
    m=json.loads(InkExportAdapter().files(story(),{})['ink/validation.json'])
    assert m['witnesses_truncated'] and not m['witnesses']

@pytest.mark.parametrize('name', ['Alice\nINCLUDE secret.ink','Alice\tname','Alice\rname'])
def test_speaker_controls_omit_only_ink_with_exact_source_location(interactive_env, name):
    e=interactive_env;e.novels.upsert_character(e.nid,'alice',{'name':name})
    row=approve(e,create(e)); value={'expected_version':row['version']}
    preview=e.service.export_preview(e.nid,e.scope,'author',row['id'],value)
    assert preview['can_export'] and preview['ink_target']['compatibility']=='UNSUPPORTED'
    assert {'code':'INK_UNSUPPORTED_SPEAKER_WHITESPACE','node_id':e.nodes[0],'character_id':'alice'} in preview['ink_issues']
    out=e.service.export(e.nid,e.scope,'author',row['id'],{**value,'preview_digest':preview['preview_digest']})
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(out['content_base64']))) as z:
        prefix='interactive-story-'+row['id']+'/'
        assert prefix+'ink/story.ink' not in z.namelist()
        assert json.loads(z.read(prefix+'ink/validation.json'))['issues']==preview['ink_issues']
        from app.experimental.interactive_story import renpy_export
        assert z.read(prefix+'game/story.rpy').decode()==renpy_export(row['spec'],{'alice':name})
