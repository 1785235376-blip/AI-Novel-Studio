"""Actual TypeScript split descriptors/results against the original File edit owner.

No mock normalizer, PostgreSQL, media render or provider calls. Bundles the current
frontend implementation into pytest's temporary directory, never a runtime source.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from app.services.studio_timeline_edit import apply_timeline_edits
from app.services.studio_timeline_render import normalize_studio_timeline

pytestmark = pytest.mark.file_backend_only
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def frontend_split(tmp_path_factory):
    folder = tmp_path_factory.mktemp('actual-selection-split')
    bundle = folder / 'split.cjs'
    entry = '''
import { selectionSplitOperations, applySelectionSplit } from './src/nle/timelineSelectionSplit';
import { readFileSync } from 'node:fs';
const input = JSON.parse(readFileSync(0, 'utf8'));
const before = JSON.stringify(input.timeline);
try {
  const operations = selectionSplitOperations(input.timeline, input.selected, input.at, input.ids);
  const result = applySelectionSplit(input.timeline, input.selected, input.at, input.ids);
  process.stdout.write(JSON.stringify({operations, result, unchanged: before === JSON.stringify(input.timeline)}));
} catch (error) {
  process.stdout.write(JSON.stringify({error: String(error), unchanged: before === JSON.stringify(input.timeline)}));
}
'''
    build = '''const esbuild = require(require.resolve('esbuild', {paths: [require.resolve('vite')]}));
esbuild.buildSync({stdin: {contents: process.argv[2], resolveDir: process.cwd(), loader: 'ts'},
 bundle: true, platform: 'node', format: 'cjs', outfile: process.argv[1]});'''
    subprocess.run(['node', '-e', build, str(bundle), entry], cwd=ROOT / 'frontend', check=True,
                   capture_output=True, text=True)

    def invoke(timeline, selected, at, ids):
        result = subprocess.run(['node', str(bundle)], input=json.dumps(dict(
            timeline=timeline, selected=selected, at=at, ids=ids)),
            capture_output=True, text=True, check=True, cwd=ROOT)
        return json.loads(result.stdout)
    return invoke


def clip(identity, kind='video', start=1000, trim_in=600, trim_out=3600, **extra):
    result = dict(id=identity, source_snapshot=dict(id='asset-' + kind, kind='ASSET',
        asset_kind=kind, version=1, digest='a' * 64), start_ms=start, in_ms=trim_in, out_ms=trim_out)
    if kind != 'audio':
        result.update(x=0, y=0, width=640, height=360)
    return {**result, **extra}


def document(clips, schema=2, kind='VIDEO'):
    result = dict(duration_ms=10000, tracks=[dict(id='main', kind=kind, order=0,
        muted=False, gain_db=0, clips=clips)])
    if schema == 3:
        result.update(schema_version=3, media_kind='AUDIO')
    else:
        result.update(width=640, height=360, fps=24, captions=[dict(start_ms=6000, end_ms=7000, text='Unchanged caption')])
        if schema == 2:
            result['schema_version'] = 2
    return normalize_studio_timeline(result)


def rows(timeline):
    return {clip['id']: clip for track in timeline['tracks'] for clip in track['clips']}


def compare(frontend, timeline, selected, at, ids):
    before = deepcopy(timeline)
    actual = frontend(timeline, selected, at, ids)
    assert 'error' not in actual, actual
    expected_ops = [dict(op='clip.split', clip_id=identity, at_ms=at, new_clip_id=ids[identity])
                    for identity in selected if identity in ids]
    assert actual['operations'] == expected_ops
    assert actual['unchanged'] and timeline == before
    backend = apply_timeline_edits(timeline, actual['operations'])
    assert actual['result'] == backend
    assert timeline == before
    return backend


@pytest.mark.parametrize('schema,kind', [(None, 'video'), (2, 'video'), (2, 'image'), (3, 'audio')])
def test_actual_descriptors_and_full_final_document(frontend_split, schema, kind):
    original = clip('selected', kind, trim_in=0 if kind == 'image' else 600)
    timeline = document([original], schema, 'AUDIO' if kind == 'audio' else 'VIDEO')
    result = compare(frontend_split, timeline, ['selected'], 2000, {'selected': 'right'})
    actual = rows(result)
    assert actual['right']['source_snapshot'] == original['source_snapshot']
    assert actual['right']['in_ms'] == (0 if kind == 'image' else 1600)
    assert actual['selected']['out_ms'] == (1000 if kind == 'image' else 1600)
    if kind == 'image':
        assert actual['right']['out_ms'] == 2600
    if schema is None:
        assert 'fade_in_ms' not in actual['right']


@pytest.mark.parametrize('kind,schema', [('video', 2), ('audio', 3)])
def test_rational_cut_fades_and_metadata(frontend_split, kind, schema):
    item = clip('selected', kind, speed_num=3, speed_den=2, fade_in_ms=200, fade_out_ms=300)
    if kind == 'video':
        item.update(include_audio=True, gain_db=-4, opacity=0.7,
                    crop=dict(x=2, y=4, width=500, height=280),
                    color_adjustment=dict(brightness=0.1, contrast=1.1, saturation=0.8))
    timeline = document([item], schema, 'AUDIO' if kind == 'audio' else 'VIDEO')
    result = rows(compare(frontend_split, timeline, ['selected'], 1800, {'selected': 'right'}))
    assert result['selected']['out_ms'] == result['right']['in_ms'] == 1800
    assert result['selected']['fade_in_ms'] == 200 and result['selected']['fade_out_ms'] == 0
    assert result['right']['fade_in_ms'] == 0 and result['right']['fade_out_ms'] == 300


def test_selected_order_skips_boundaries_and_locked_unaffected(frontend_split):
    timeline = document([clip('video')])
    timeline['tracks'].append(dict(id='sound', kind='AUDIO', order=1, muted=False, gain_db=0,
        clips=[clip('audio', 'audio'), clip('boundary', 'audio', start=2000)]))
    timeline['tracks'].append(dict(id='locked', kind='AUDIO', order=2, muted=False, gain_db=0,
        locked=True, clips=[clip('outside', 'audio', start=6000)]))
    timeline = normalize_studio_timeline(timeline)
    result = compare(frontend_split, timeline, ['outside', 'audio', 'boundary', 'video'], 2000,
                     {'audio': 'audio-right', 'video': 'video-right'})
    assert rows(result)['boundary'] == rows(timeline)['boundary']
    assert rows(result)['outside'] == rows(timeline)['outside']


def test_outgoing_transition_stays_on_right_tail(frontend_split):
    left = clip('selected', trim_in=0, trim_out=3000,
                transition_out=dict(kind='CROSS_DISSOLVE', to_clip_id='next', duration_ms=200))
    right = clip('next', start=3800, trim_in=0, trim_out=2000)
    timeline = document([left, right])
    result = rows(compare(frontend_split, timeline, ['selected'], 2000, {'selected': 'tail'}))
    assert 'transition_out' not in result['selected']
    assert result['tail']['transition_out'] == left['transition_out']


@pytest.mark.parametrize('reason', ['fractional-cut', 'fade-too-long', 'locked', 'transition-cut'])
def test_frontend_and_original_backend_reject_without_input_mutation(frontend_split, reason):
    item = clip('selected', speed_num=3, speed_den=2)
    at = 1801
    if reason == 'fade-too-long':
        item.update(fade_in_ms=900); at = 1800
    if reason == 'locked':
        at = 1800
    if reason == 'transition-cut':
        item = clip('selected', trim_in=0, trim_out=3000,
                    transition_out=dict(kind='CROSS_DISSOLVE', to_clip_id='next', duration_ms=200))
        at = 3900
    timeline = document([item] + ([clip('next', start=3800, trim_in=0, trim_out=2000)]
                                 if reason == 'transition-cut' else []))
    if reason == 'locked':
        timeline['tracks'][0]['locked'] = True
    before = deepcopy(timeline)
    actual = frontend_split(timeline, ['selected'], at, {'selected': 'right'})
    assert 'error' in actual and actual['unchanged']
    with pytest.raises(ValueError):
        apply_timeline_edits(timeline, [dict(op='clip.split', clip_id='selected', at_ms=at, new_clip_id='right')])
    assert timeline == before
