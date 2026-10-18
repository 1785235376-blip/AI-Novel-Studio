import base64, copy, hashlib, json, os, subprocess, sys, types
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tests'))
from test_v2_audio_editing_pipeline import cpu_video
from test_v2_audio_only_timeline import tone
from app.services.studio_timeline_render import render_studio_timeline, normalize_studio_timeline, timeline_digest
root = Path(os.environ['NOVEL_DATA_PATH'])
root.mkdir(parents=True, exist_ok=True)
video = cpu_video(root / 'original-blue.mp4')
audio = tone(440, 1000)
assets = {}
for kind, data in [('video', video), ('audio', audio)]:
    pin = {'id': 'original-' + kind, 'kind': 'ASSET', 'asset_kind': kind, 'version': 1, 'digest': hashlib.sha256(data).hexdigest()}
    assets[pin['id']] = {'snapshot': pin, 'data': data, 'row': {'id': pin['id'], 'version': 1, 'sha256': pin['digest'], 'kind': kind}}
def source_guard(snapshot):
    assert assets[snapshot['id']]['snapshot'] == snapshot
    return copy.deepcopy(assets[snapshot['id']])
baseline_ref = '91a3f328eec5b7a9076595a5640932aa3b77987c'
old_text = subprocess.check_output(['git', 'show', baseline_ref + ':app/services/studio_timeline_render.py'], text=True)
old = types.ModuleType('app.services.legacy_timeline_probe'); old.__package__ = 'app.services'
exec(compile(old_text, 'original-frozen-renderer', 'exec'), old.__dict__)
proofs = []
for version in (1, 2):
    value = {'duration_ms': 1000, 'width': 64, 'height': 64, 'fps': 10, 'tracks': [
        {'id': kind, 'kind': kind.upper(), 'order': i, 'clips': [{'id': kind+'-clip', 'source_snapshot': assets['original-'+kind]['snapshot'], 'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]}
        for i, kind in enumerate(('video', 'audio'))], 'captions': []}
    if version == 2: value['schema_version'] = 2
    before, after = old.normalize_studio_timeline(value), normalize_studio_timeline(value)
    assert before == after and old.timeline_digest(before) == timeline_digest(after)
    old_data, old_measure = old.render_studio_timeline(value, source_guard=source_guard, guard=lambda: None, max_bytes=25*1024*1024)
    new_data, new_measure = render_studio_timeline(value, source_guard=source_guard, guard=lambda: None, max_bytes=25*1024*1024)
    assert old_data == new_data and old_measure == new_measure
    proofs.append({'schema': version, 'timeline_digest': timeline_digest(after), 'output_sha256': hashlib.sha256(new_data).hexdigest(), 'output_bytes': len(new_data), 'normalized_equal': True, 'actual_output_bytes_equal': True, 'measurement_equal': True})
print(json.dumps({'baseline_commit': baseline_ref, 'proofs': proofs}, indent=2))
