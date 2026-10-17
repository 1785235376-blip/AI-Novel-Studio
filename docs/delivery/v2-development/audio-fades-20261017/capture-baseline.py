"""Data-only pre-edit serialization capture: no queue, native process, or provider."""
import hashlib, importlib.machinery, json, os, pathlib, subprocess, sys
root = pathlib.Path(os.environ['PROJECT_ROOT']).resolve()
assert pathlib.Path.cwd() == root
assert not any(n == 'app' or n.startswith('app.') for n in sys.modules)
assert importlib.machinery.PathFinder.find_spec('app', sys.path).origin == str(root / 'app/__init__.py')
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
from app.creative.production_execution import ProductionExecutionService, digest
from app.creative.production_execution_models import MediaCommand
from app.creative.graph_media_binding import make_graph_binding_digest
from app.experimental.store import canonical
from app.services.studio_audio_execution import _body, _binding, _digest, StudioAudioExecution
origins = {n: str(pathlib.Path(m.__file__).resolve()) for n, m in sys.modules.items() if n.startswith('app.') and getattr(m, '__file__', None)}
assert all(pathlib.Path(p).is_relative_to(root) for p in origins.values())
service = object.__new__(ProductionExecutionService)
base = {'actor': 'author', 'scope_key': 'a' * 64, 'incarnation': 'file:legacy-fixture'}
service._base = lambda *args: dict(base)
service._binding = lambda command: None
service._sources_current = lambda nid, scope, context, guard: [{'snapshot': s, 'measured': {'duration_ms': 1000, 'sample_rate': 8000, 'channels': 1}} for s in context['sources']]
service._egress = lambda *args: None
source = {'kind': 'ASSET', 'asset_kind': 'audio', 'id': 'source-a', 'version': 1, 'digest': 'b' * 64}
controls = {'gain_db': -6.020599913279624, 'sample_rate': 22050, 'channels': 1}
variants = {'wav_omitted': {}, 'wav_controls': controls, 'flac': {**controls, 'output_format': 'FLAC'}, 'mp3': {**controls, 'output_format': 'MP3'}, 'graph_trim': {}}
result = {'source_commit': head, 'capture_exit': 0, 'capture_kind': 'DATA_ONLY_SERIALIZATION_NO_EXECUTION', 'variants': {}}
for name, parameters in variants.items():
    command = {'operation_id': 'm8.audio.trim', 'request_id': 'legacy-trim', 'provider_id': None, 'model_id': None, 'prompt': '', 'parameters': {'in_ms': 100, 'out_ms': 800, **parameters}, 'allow_cloud': False, 'source_snapshots': [source], 'license_note': ''}
    if name == 'mp3': command['audio_profile'] = 'studio-audio-mp3/1'
    graph = None
    if name == 'graph_trim':
        graph = {'contract': 'creative-graph-media-binding/1', 'run_id': 'run-one', 'node_id': 'Trim', 'graph_id': 'graph-one', 'graph_version': 1, 'graph_digest': 'c'*64, 'run_request_digest': 'd'*64, 'input_digest': 'e'*64, 'preview_run_version': 1, 'command_digest': digest(MediaCommand.model_validate(command).model_dump())}
        graph['attempt_digest'] = make_graph_binding_digest(graph, base)
    preview, context, parsed = service.preview('project', {}, 'author', command, lambda: None, graph_binding=graph)
    context['command'] = parsed.model_dump()
    payload = parsed.model_dump(exclude={'source_snapshots', 'allow_cloud', 'license_note', 'request_id'})
    payload['parameters'] = parsed.parameters.model_dump(exclude_none=True)
    payload['source_snapshots'] = context['sources']
    body = _body(payload)
    assert _binding(context, body) == context
    request_sha = _digest({'body': body, 'context': context})
    receipt = {'id': 'audio-one', 'version': 1, 'request_digest': context['request_digest'], 'status': 'QUEUED', 'attempt': 0, 'dispatch_state': 'NOT_SENT', 'publication_state': 'NOT_STARTED', 'review_state': 'NOT_READY'}
    StudioAudioExecution._receipt(receipt)
    objects = {'command': parsed.model_dump(), 'preview': preview, 'context': context, 'recipe': preview['execution_recipe'], 'body': body, 'receipt': receipt}
    result['variants'][name] = {'input': command, 'graph_binding': graph, 'objects': objects, 'canonical': {k: canonical(v) for k,v in objects.items()}, 'sha256': {k: digest(v) for k,v in objects.items()}, 'model_dump_json': parsed.model_dump_json(), 'request_sha256': request_sha, 'source_sha256': hashlib.sha256(b'').hexdigest()}
path = root / '.runtime/v2-checks/audio-fades-baseline-capture/baseline.json'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'fixture': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'head': head, 'product_module_origins': origins, 'variant_hashes': {k:v['sha256'] for k,v in result['variants'].items()}}, indent=2))
