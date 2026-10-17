"""Capture actual unchanged legacy request builders; no invocation or authority."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
from threading import Event
from types import SimpleNamespace

ROOT = Path('/workspace/scratch/20a0022d2b33/studio-creative-binding')
EVIDENCE = ROOT / 'docs/delivery/v2-development/creative-binding-origin'
# Repeat the proven stdlib-only original-runner child origin check before imports.
probe = EVIDENCE / 'origin-probe.py'
sys.argv.append('--child')
exec(compile(probe.read_text(), str(probe), 'exec'), {'__file__': str(probe)})

def deny_external(event, arguments):
    if event in {'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system', 'sqlite3.connect'}:
        raise AssertionError('Baseline capture forbids external execution: ' + event)
sys.addaudithook(deny_external)

from app.author_request import build_author_request, request_payload, request_digest
from app.model_execution import graph_request_payload_digest
from app.model_runtime import TextGenerationRequest, TextGenerationParameters

common = dict(id='11111111-1111-4111-8111-111111111111', novel_id='baseline-project',
    actor_id='baseline-author', scope={'mode': 'local', 'novel_id': 'baseline-project'},
    profile='LOCAL_ONLY', requested_provider='mock', requested_model='mock-writer')
graph_fields = dict(common, operation='graph_text', chapter_id=None,
    graph_binding={'graph_id':'baseline-graph','graph_version':1,'run_id':'baseline-run','node_id':'text',
        'project_incarnation':'file:22222222-2222-4222-8222-222222222222',
        'input_digest':'a'*64,'reviewed_preview_digest':'b'*64,'route_fingerprint':'c'*64},
    generation_max_output_bytes=32000, generation_deadline='2030-01-02T03:04:05+00:00')
graph = SimpleNamespace(**graph_fields)
graph_request = TextGenerationRequest(provider_id='mock',model_id='mock-writer',
    prompt='Golden graph prompt: 夜色。',parameters=TextGenerationParameters(temperature=0.0,max_output_tokens=256),
    metadata={'purpose':'creative_graph_model'},job_id=graph.id)
graph_payload = request_payload(graph_request)
screenplay_fields = dict(common, chapter_id='baseline-chapter',operation='brainstorm',
    instruction='Adapt the saved selection into screenplay scenes.',source='A visitor pauses at the doorway.',
    style='',base_chapter_version=7,base_chapter_digest='d'*64,workspace_id=None,session_id=None,
    creation_records=[],request_scope={'source_mode':'SELECTION_ONLY','include_automatic_context':False,
        'include_style_reference':False,'include_plan_reference':False},author_input_digest=None,
    reviewed_variant=None,character_viewpoint=None,revision_selection_binding=None)
screenplay = SimpleNamespace(**screenplay_fields, cancelled=Event())
screenplay_request = build_author_request(screenplay, SimpleNamespace(provider='mock',model='mock-writer'),
    {'content':screenplay.source}, {})
fixture = {'schema_version':1, 'graph':{'job':graph_fields,'payload':graph_payload,'synthetic_allowed':True,
    'expected_digest':graph_request_payload_digest(graph, graph_payload, True)},
    'screenplay':{'job':screenplay_fields,'payload':request_payload(screenplay_request),'cloud':False,
    'expected_digest':request_digest(screenplay_request, screenplay, False)}}
modules = {}
for name, module in sorted(sys.modules.copy().items()):
    if not (name == 'app' or name.startswith('app.')): continue
    location = getattr(module, '__file__', None)
    if location:
        path = Path(location).resolve()
        assert path.is_relative_to(ROOT), (name, location)
        modules[name] = {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
assert 'app.jobs' not in sys.modules and 'app.runtime' not in sys.modules and 'app.dependencies' not in sys.modules
prompt = ROOT / 'prompts/plot_planner/system.md'
provenance = {'status':'PASS_ACTUAL_UNCHANGED_BUILDERS', 'root':str(ROOT), 'executable':sys.executable,
    'product_modules':modules,'prompt_path':str(prompt),'prompt_sha256':hashlib.sha256(prompt.read_bytes()).hexdigest(),
    'capture_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'authority_recreated':False,'provider_or_adapter_invoked':False,'network_or_database_used':False}
if '--verify-fixture' in sys.argv:
    path = ROOT / 'tests/fixtures/creative_binding_legacy_requests.json'
    assert json.loads(path.read_text()) == fixture, 'Frozen legacy fixture mismatch'
    provenance['frozen_fixture_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
else:
    (EVIDENCE / 'captured-legacy-requests.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
(EVIDENCE / ('fixture-verification-provenance.json' if '--verify-fixture' in sys.argv else 'capture-provenance.json')).write_text(json.dumps(provenance,indent=2)+'\n')
print(json.dumps({'status':provenance['status'],'graph_digest':fixture['graph']['expected_digest'],
    'screenplay_digest':fixture['screenplay']['expected_digest']},indent=2))
