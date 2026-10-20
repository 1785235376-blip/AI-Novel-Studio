"""B07/DIF-10/E2E-07 Godot 4 runtime acceptance verifier (C line).

This script does NOT prove anything by generating a project. It builds the real
GODOT_4_RUNTIME_PROJECT_V1 export through the frozen contract, packages it as the
product ZIP, extracts it into a scratch directory, and executes it with the real
Godot 4 headless engine on this host. Every observable step is aligned field by field
against the authoritative Python playback (interactive_story.play).

Checks performed
----------------
1. artifact: bundle/manifest/receipt hashes, the fixed runtime template hashes, the
   typed data schema, and the acceptance cases shipped inside the ZIP;
2. engine: the real Godot executable reports a supported version;
3. alignment: for the initial state and for every recorded ending witness path, the
   runtime's per-step POEMSEED_STATE records (node, variables, enabled choices, steps,
   status, path) equal the Python playback projection exactly (bool/int aware);
4. enforcement: runtime defense fixtures (a cyclic story that must stop at the step
   cap, a conditional no-exit story, and malformed stories) fail safely, and the
   authority gate refuses to export those stories in the first place;
5. save/restore: process 1 saves mid-path, process 2 restores and continues; restored
   variables/choices/ending equal direct playback; wrong revision/spec/source digest,
   tampered variables, tampered paths, corrupt JSON and version mismatches are all
   rejected without applying the save (exit code 2);
6. path safety: user:// path traversal, absolute save paths and non-JSON result paths
   are refused and never create files outside the bounded user directory;
7. static audit: the shipped GDScript contains no eval/Expression/dynamic code,
   network, rich text or arbitrary file access beyond the documented allow-list.

Evidence levels are written honestly: only TARGET_RUNTIME_EXECUTED,
SAVE_RESTORE_VERIFIED and GENERATED_ARTIFACT_VALIDATED can become PASS here.
WINDOWS_USABILITY_VERIFIED stays NOT_RUN because headless automation is not GUI
acceptance.

Two modes:
- default (unchanged): generate the real target export through the frozen contract,
  package it, then run the checks above against that freshly generated project;
- external artifact (--artifact ZIP): verify a ZIP that the Studio journey already
  exported (E2E-07). Nothing is regenerated: expectations come from the artifact's
  data/story.json plus acceptance/cases.json, the product bundle records are recomputed
  fail-closed, and the same real Godot headless execution, per-step alignment, static
  audit and two-process save/restore checks run against the delivered project.

Usage:
  python scripts/verify_godot_interactive_runtime.py [--godot PATH] [--scratch-root DIR]
  python scripts/verify_godot_interactive_runtime.py --artifact exported.zip --report result.json [--godot PATH] [--scratch-root DIR]
Exit code 0 means every check passed; FAIL or a blocked environment is non-zero.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import app.experimental.interactive_godot_export as godot_export  # noqa: E402
import app.experimental.interactive_export_contract as contract  # noqa: E402
from app.experimental.interactive_story import StorySpec, analyze  # noqa: E402

TARGET_ID = godot_export.TARGET_ID
STORY_ID = 'b07-godot-runtime-verify-20261020'
DEFAULT_SCRATCH_ROOT = Path(r'D:\PoemSeed\Recovery\b07-scratch\godot-runtime')
EVIDENCE_JSON = REPO_ROOT / 'docs' / 'v2' / 'B07_GODOT_RUNTIME_EVIDENCE_20261020.json'
EVIDENCE_LOG = REPO_ROOT / 'docs' / 'v2' / 'B07_GODOT_RUNTIME_EVIDENCE_20261020.log'
ENGINE_HINTS = [
    r'D:\GameDev\Godot\Godot-4.7-stable\Godot_v4.7-stable_win64_console.exe',
]
ENGINE_EXECUTABLES = ['godot', 'godot.exe', 'Godot_v4.7-stable_win64_console.exe']
WATCHDOG_FRAMES = '600'
PROCESS_TIMEOUT_SECONDS = 120

CHECKS = []
COMMANDS = []
FAILURES = []


# ---------------------------------------------------------------------------
# recording helpers
# ---------------------------------------------------------------------------
def record(check: str, status: str, detail: str = '') -> None:
    CHECKS.append({'check': check, 'status': status, 'detail': detail[:2000]})
    if status != 'PASS':
        FAILURES.append({'check': check, 'detail': detail[:2000]})
    print(('PASS  ' if status == 'PASS' else status + '  ') + check + ((' :: ' + detail[:400]) if detail else ''))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


# ---------------------------------------------------------------------------
# engine discovery
# ---------------------------------------------------------------------------
def find_engine(explicit: str | None) -> tuple[str | None, str]:
    candidates = []
    if explicit:
        candidates.append(explicit)
    override = os.environ.get('POEMSEED_GODOT_BIN')
    if override:
        candidates.append(override)
    candidates.extend(ENGINE_HINTS)
    for name in ENGINE_EXECUTABLES:
        found = shutil.which(name)
        if found:
            candidates.append(found)
    if os.name == 'nt':
        local = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs'
        if local.exists():
            for path in local.rglob('Godot*_console.exe'):
                candidates.append(str(path))
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if Path(candidate).is_file():
            return candidate, 'found'
    return None, 'not found in POEMSEED_GODOT_BIN, declared search hints or PATH'


# ---------------------------------------------------------------------------
# process execution
# ---------------------------------------------------------------------------
def run_engine(engine: str, project: Path, user_args: list[str], label: str) -> dict:
    argv = [engine, '--headless', '--quit-after', WATCHDOG_FRAMES, '--path', str(project), '--', *user_args]
    started = time.monotonic()
    timed_out = False
    try:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout_bytes, stderr_bytes = process.communicate(timeout=PROCESS_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_bytes, stderr_bytes = process.communicate()
            timed_out = True
    except OSError as exc:
        return {'label': label, 'argv': argv, 'exit_code': None, 'stdout': '', 'stderr': str(exc),
                'timed_out': True, 'duration_ms': 0, 'stdout_sha256': '', 'stderr_sha256': ''}
    duration_ms = int((time.monotonic() - started) * 1000)
    stdout = stdout_bytes.decode('utf-8', 'replace')
    stderr = stderr_bytes.decode('utf-8', 'replace')
    entry = {'label': label, 'argv': argv, 'exit_code': process.returncode, 'stdout': stdout, 'stderr': stderr,
             'timed_out': timed_out, 'duration_ms': duration_ms,
             'stdout_sha256': sha256_bytes(stdout_bytes), 'stderr_sha256': sha256_bytes(stderr_bytes)}
    COMMANDS.append({key: entry[key] for key in ('label', 'argv', 'exit_code', 'timed_out', 'duration_ms',
                                                 'stdout_sha256', 'stderr_sha256')})
    return entry


def parse_records(result: dict) -> dict:
    records = {'states': [], 'story': None, 'done': None, 'error': None, 'restored': None,
               'saved': None, 'result': None, 'user_dir': None}
    for line in result['stdout'].splitlines():
        if 'POEMSEED_STATE ' in line:
            records['states'].append(json.loads(line.split('POEMSEED_STATE ', 1)[1]))
        elif 'POEMSEED_STORY ' in line:
            records['story'] = json.loads(line.split('POEMSEED_STORY ', 1)[1])
        elif 'POEMSEED_DONE ' in line:
            records['done'] = json.loads(line.split('POEMSEED_DONE ', 1)[1])
        elif 'POEMSEED_ERROR ' in line:
            records['error'] = json.loads(line.split('POEMSEED_ERROR ', 1)[1])
        elif 'POEMSEED_RESTORED ' in line:
            records['restored'] = json.loads(line.split('POEMSEED_RESTORED ', 1)[1])
        elif 'POEMSEED_SAVED ' in line:
            records['saved'] = json.loads(line.split('POEMSEED_SAVED ', 1)[1])
        elif 'POEMSEED_RESULT ' in line:
            records['result'] = json.loads(line.split('POEMSEED_RESULT ', 1)[1])
        elif 'POEMSEED_USERDIR ' in line:
            raw = line.split('POEMSEED_USERDIR ', 1)[1].strip().rstrip('/' + os.sep)
            records['user_dir'] = Path(raw)
    return records


def healthy_run(result: dict, expected_exit: int) -> tuple[bool, str]:
    if result['timed_out']:
        return False, 'process timed out'
    if result['exit_code'] != expected_exit:
        return False, 'exit code ' + str(result['exit_code']) + ' != ' + str(expected_exit)
    if 'SCRIPT ERROR' in result['stderr'] or 'Parse Error' in result['stderr']:
        return False, 'GDScript error in stderr'
    return True, ''


# ---------------------------------------------------------------------------
# typed equality: bool is never equal to int, int never equal to float
# ---------------------------------------------------------------------------
def typed_diff(expected, actual, where='$') -> list[str]:
    problems = []
    if type(expected) is not type(actual):
        return [where + ': type ' + type(expected).__name__ + ' != ' + type(actual).__name__
                + ' (expected ' + repr(expected)[:120] + ', actual ' + repr(actual)[:120] + ')']
    if isinstance(expected, dict):
        for key in expected:
            if key not in actual:
                problems.append(where + '.' + str(key) + ': missing in runtime state')
            else:
                problems.extend(typed_diff(expected[key], actual[key], where + '.' + str(key)))
        for key in actual:
            if key not in expected:
                problems.append(where + '.' + str(key) + ': unexpected in runtime state')
        return problems
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [where + ': list length ' + str(len(expected)) + ' != ' + str(len(actual))]
        for index, (left, right) in enumerate(zip(expected, actual)):
            problems.extend(typed_diff(left, right, where + '[' + str(index) + ']'))
        return problems
    if expected != actual:
        problems.append(where + ': ' + repr(expected)[:200] + ' != ' + repr(actual)[:200])
    return problems


# ---------------------------------------------------------------------------
# story fixtures
# ---------------------------------------------------------------------------
def build_story_spec() -> dict:
    raw = {
        'title': 'B07 Godot 运行时验收故事',
        'graph_id': 'b07-godot-verify-graph',
        'graph_version': 3,
        'entry_node_id': 'g1',
        'max_steps': 8,
        'graph_record_ids': [],
        'variables': [
            {'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3},
            {'name': 'trust', 'type': 'bool', 'initial': True, 'minimum': 0, 'maximum': 100},
            {'name': 'visits', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 2},
            {'name': 'score', 'type': 'int', 'initial': 0, 'minimum': -5, 'maximum': 5},
        ],
        'nodes': [
            {'node_id': 'g1', 'node_version': 1, 'title': '第一幕·门', 'character_id': 'alice',
             'dialogue': '要出发吗？\n第二行带 "引号"、反斜杠 \\ 和制表符\t结束。',
             'choices': [
                 {'id': 'c_go', 'label': '去港口', 'target': 'g2',
                  'condition': 'trust and courage <= 1', 'assignments': {'courage': 2, 'score': 1}},
                 {'id': 'c_wait', 'label': '去山里', 'target': 'g3',
                  'condition': 'not trust or courage >= 0', 'assignments': {}},
             ]},
            {'node_id': 'g2', 'node_version': 1, 'title': '第二幕·港', 'character_id': None,
             'dialogue': '海风吹过。', 'background_asset_id': 'bg-harbour',
             'choices': [
                 {'id': 'c_home', 'label': '回家', 'target': 'g4',
                  'condition': 'courage == 2 and not (visits > 0)', 'assignments': {'visits': 1}},
                 {'id': 'c_leave', 'label': '小径', 'target': 'g5',
                  'condition': 'trust or courage != 2', 'assignments': {'trust': False}},
             ]},
            {'node_id': 'g3', 'node_version': 1, 'title': '第二幕·山', 'character_id': 'alice',
             'dialogue': '山雾四起。', 'ending': '山结局 — "引号" 与 \\ 反斜杠\n第二行结局'},
            {'node_id': 'g4', 'node_version': 1, 'title': '终幕·家', 'character_id': None,
             'dialogue': '灯还亮着。', 'ending': '港口结局'},
            {'node_id': 'g5', 'node_version': 1, 'title': '第三幕·径', 'character_id': None,
             'dialogue': '岔路出现。', 'music_asset_id': 'bgm-path',
             'choices': [
                 {'id': 'c_rest', 'label': '休息', 'target': 'g6',
                  'condition': 'courage != 3', 'assignments': {'courage': 3, 'score': -2}},
                 {'id': 'c_press', 'label': '继续', 'target': 'g7',
                  'condition': 'courage >= 2', 'assignments': {'score': 0}},
             ]},
            {'node_id': 'g6', 'node_version': 1, 'title': '终幕·息', 'character_id': None,
             'dialogue': '坐下休息。', 'ending': '休息结局'},
            {'node_id': 'g7', 'node_version': 1, 'title': '终幕·末', 'character_id': None,
             'dialogue': '路的尽头。', 'ending': '终局'},
        ],
    }
    return StorySpec.model_validate(raw).model_dump()


def build_snapshot(spec: dict) -> dict:
    analysis = analyze(spec)
    characters = {'alice': '爱丽丝'}
    return {
        'story_id': STORY_ID,
        'revision': 7,
        'status': 'APPROVED',
        'title': spec['title'],
        'spec': spec,
        'spec_digest': contract.digest(spec),
        'source_digest': hashlib.sha256(b'b07-godot-runtime-verifier-source').hexdigest(),
        'review_receipt': hashlib.sha256(b'b07-godot-runtime-verifier-review').hexdigest(),
        'characters': characters,
        'witness': analysis['endings'],
        'media_manifest': [
            {'asset_id': 'bg-harbour', 'version': 1, 'sha256': 'd' * 64, 'kind': 'image',
             'missing': False, 'packaged': False, 'reason': 'REFERENCE_ONLY'},
            {'asset_id': 'bgm-path', 'version': 1, 'sha256': 'e' * 64, 'kind': 'audio',
             'missing': False, 'packaged': False, 'reason': 'REFERENCE_ONLY'},
        ],
        'analysis': analysis,
    }


def expected_for(spec: dict, characters: dict, path: list[str]) -> dict:
    return godot_export.expected_state(spec, characters, path)


# ---------------------------------------------------------------------------
# artifact checks
# ---------------------------------------------------------------------------
def check_artifact(project: Path, bundle, story: dict, cases: dict, spec: dict) -> None:
    project_bytes = (project / 'project.godot').read_bytes().decode('utf-8')
    if 'config_version=5' not in project_bytes:
        record('artifact.project.godot.config_version', 'FAIL', 'config_version=5 missing')
    elif 'run/main_scene="res://main.tscn"' not in project_bytes:
        record('artifact.project.godot.main_scene', 'FAIL', 'main scene missing')
    elif 'viewport_width=960' not in project_bytes or 'viewport_height=600' not in project_bytes:
        record('artifact.project.godot.window', 'FAIL', 'window size missing')
    elif 'config/name="PoemSeed Story ' + STORY_ID + '"' not in project_bytes:
        record('artifact.project.godot.project_name', 'FAIL', 'project name missing')
    else:
        record('artifact.project.godot.config', 'PASS', 'config_version=5, main scene, 960x600, project name')
    if (project / 'main.tscn').is_file() and 'res://main.gd' in (project / 'main.tscn').read_text(encoding='utf-8'):
        record('artifact.main.tscn', 'PASS')
    else:
        record('artifact.main.tscn', 'FAIL', 'main scene or main.gd binding missing')
    template_hashes = godot_export.template_hashes()
    drift = []
    for relative, expected_hash in template_hashes.items():
        shipped = project / relative
        if not shipped.is_file() or sha256_file(shipped) != expected_hash:
            drift.append(relative)
    record('artifact.runtime_template_verbatim', 'PASS' if not drift else 'FAIL',
           'all fixed runtime files match repository template' if not drift else 'drift: ' + ','.join(drift))
    pinned = godot_export.PINNED_TEMPLATE_SHA256
    if pinned and pinned == template_hashes:
        record('artifact.template_hashes_pinned', 'PASS', str(len(template_hashes)) + ' pinned files')
    elif not pinned:
        record('artifact.template_hashes_pinned', 'FAIL', 'PINNED_TEMPLATE_SHA256 is empty')
    else:
        record('artifact.template_hashes_pinned', 'FAIL', 'pinned template hashes drifted from repository template')
    try:
        model = godot_export.GodotRuntimeStory.model_validate(story)
        record('artifact.story_schema', 'PASS', 'typed schema v' + model.format_version)
    except Exception as exc:
        record('artifact.story_schema', 'FAIL', type(exc).__name__ + ':' + str(exc)[:300])
    if story.get('engine_target') != TARGET_ID or story.get('schema') != godot_export.RUNTIME_STORY_SCHEMA:
        record('artifact.story_target_binding', 'FAIL', 'story target/schema mismatch')
    elif story.get('spec_digest') != contract.digest(spec):
        record('artifact.story_target_binding', 'FAIL', 'story spec digest does not bind the reviewed spec')
    else:
        record('artifact.story_target_binding', 'PASS', 'target + spec digest bound')
    expected_cases = godot_export.acceptance_cases(build_snapshot(spec), {'spec': spec, 'characters': {'alice': '爱丽丝'}})
    if json.loads(json.dumps(cases)) != json.loads(json.dumps(expected_cases)):
        record('artifact.acceptance_cases', 'FAIL', 'acceptance/cases.json does not match the Python oracle')
    else:
        record('artifact.acceptance_cases', 'PASS', str(len(cases['cases'])) + ' ending witness cases')
    extra = bundle.manifest['extra']['godot_runtime']
    if extra['template_files'] != template_hashes:
        record('artifact.manifest_template_hashes', 'FAIL', 'manifest template hashes differ from shipped files')
    else:
        record('artifact.manifest_template_hashes', 'PASS')
    read_back = contract.read_zip_safely((project.parent / 'project.zip').read_bytes(), package_prefix(STORY_ID))
    if read_back != bundle.files:
        record('artifact.zip_round_trip', 'FAIL', 'ZIP contents differ from the frozen bundle')
    else:
        record('artifact.zip_round_trip', 'PASS', str(len(read_back)) + ' files, payload digest ' + bundle.payload_files_digest[:16])
    if 'README.md' in bundle.files and 'data/story.schema.json' in bundle.files:
        record('artifact.docs', 'PASS')
    else:
        record('artifact.docs', 'FAIL', 'README.md or data/story.schema.json missing')


def package_prefix(story_id: str) -> str:
    return 'interactive-' + contract._filename_slug(TARGET_ID) + '-' + story_id + '/'


# ---------------------------------------------------------------------------
# static audit of the shipped runtime
# ---------------------------------------------------------------------------
FORBIDDEN_TOKENS = ['Expression', 'JavaScriptBridge', 'OS.execute', 'OS.shell_open',
                    'OS.create_process', 'HTTPRequest', 'HTTPClient', 'WebSocketPeer', 'DirAccess',
                    'ResourceLoader.load', 'RichTextLabel', 'bbcode', 'bbcode_enabled']
FORBIDDEN_PATTERNS = [(r'(?<![A-Za-z0-9_])eval\s*\(', 'eval call'),
                      (r'(?<![A-Za-z0-9_])load\s*\(', 'dynamic load call')]


def strip_gdscript_comments(text: str) -> str:
    cleaned = []
    for line in text.splitlines():
        index = line.find('#')
        cleaned.append(line if index < 0 else line[:index])
    return '\n'.join(cleaned)
FILE_ACCESS_ALLOWLIST = {'runtime/story_loader.gd': 1, 'runtime/save_store.gd': 2}


def check_static_audit(project: Path) -> None:
    problems = []
    for relative in godot_export.FIXED_TEMPLATE_FILES:
        path = project / relative
        if not path.is_file():
            problems.append(relative + ': missing')
            continue
        text = path.read_text(encoding='utf-8')
        code = strip_gdscript_comments(text) if relative.endswith('.gd') else text
        for token in FORBIDDEN_TOKENS:
            if token in code:
                problems.append(relative + ': forbidden token ' + token)
        for pattern, description in FORBIDDEN_PATTERNS:
            if re.search(pattern, code):
                problems.append(relative + ': forbidden ' + description)
        if 'FileAccess.open' in text:
            allowed = FILE_ACCESS_ALLOWLIST.get(relative, 0)
            if text.count('FileAccess.open') > allowed:
                problems.append(relative + ': unexpected FileAccess.open')
    if 'preload("res://runtime/' not in (project / 'main.gd').read_text(encoding='utf-8'):
        problems.append('main.gd: runtime preloads missing')
    record('audit.no_dynamic_execution_or_network', 'PASS' if not problems else 'FAIL', '; '.join(problems[:8]))


# ---------------------------------------------------------------------------
# runtime alignment
# ---------------------------------------------------------------------------
def compare_states(states: list[dict], expected_states: list[dict], label: str) -> int:
    if len(states) != len(expected_states):
        record(label + '.state_count', 'FAIL', 'runtime emitted ' + str(len(states)) + ' states, expected ' + str(len(expected_states)))
        return 0
    mismatches = []
    compared = 0
    for index, (actual, expected) in enumerate(zip(states, expected_states)):
        problems = typed_diff(expected, actual)
        compared += 1
        if problems:
            mismatches.append('step ' + str(index) + ': ' + problems[0])
    record(label, 'PASS' if not mismatches else 'FAIL',
           '' if not mismatches else '; '.join(mismatches[:6]))
    return compared


def check_alignment(engine: str, project: Path, spec: dict, characters: dict, cases: dict) -> dict:
    states_compared = 0
    checked_cases = 0
    initial = run_engine(engine, project, ['--print-user-dir'], 'align.initial')
    ok, detail = healthy_run(initial, 0)
    records = parse_records(initial)
    if not ok:
        record('align.initial.process', 'FAIL', detail + ' stderr=' + initial['stderr'][:200])
    else:
        states_compared += compare_states(records['states'], [expected_for(spec, characters, [])], 'align.initial.states')
    for case in cases['cases']:
        path = list(case['choices'])
        label = 'align.case.' + str(case['case_id'])
        result = run_engine(engine, project, ['--witness-path', ','.join(path)], label)
        ok, detail = healthy_run(result, 0)
        records = parse_records(result)
        if not ok:
            record(label + '.process', 'FAIL', detail)
            continue
        expected_states = [expected_for(spec, characters, path[:index]) for index in range(len(path) + 1)]
        states_compared += compare_states(records['states'], expected_states, label + '.states')
        expected_final = case['expected_final']
        final_problems = typed_diff(expected_final, records['states'][-1]) if records['states'] else ['no state']
        record(label + '.final_matches_cases_json', 'PASS' if not final_problems else 'FAIL',
               '; '.join(final_problems[:3]))
        if records['done'] is None or records['done'].get('path') != path or records['done'].get('status') != 'ENDING':
            record(label + '.done', 'FAIL', 'POEMSEED_DONE record invalid')
        else:
            record(label + '.done', 'PASS', 'status ENDING after ' + str(len(path)) + ' steps')
        checked_cases += 1
    return {'cases': checked_cases, 'states_compared': states_compared}


# ---------------------------------------------------------------------------
# runtime enforcement fixtures (defense in depth)
# ---------------------------------------------------------------------------
def fixture_story(base_story: dict, *, nodes: list[dict], variables: list[dict], max_steps: int,
                  entry: str = 'f1', witness: list[dict] | None = None) -> dict:
    story = deepcopy(base_story)
    story['nodes'] = nodes
    story['variables'] = variables
    story['max_steps'] = max_steps
    story['entry_node_id'] = entry
    story['witness'] = witness or []
    story['media_references'] = []
    return story


def check_enforcement(engine: str, project: Path, bundle, spec: dict) -> int:
    base_story = json.loads(bundle.files['data/story.json'])
    checked = 0
    cycle_spec = StorySpec.model_validate({
        'title': 'B07 runtime cycle fixture', 'graph_id': 'fixture-cycle', 'graph_version': 1,
        'entry_node_id': 'f1', 'max_steps': 3, 'graph_record_ids': [],
        'variables': [{'name': 'flag', 'type': 'bool', 'initial': True, 'minimum': 0, 'maximum': 100}],
        'nodes': [
            {'node_id': 'f1', 'node_version': 1, 'title': '循环', 'dialogue': '再走一次。',
             'choices': [{'id': 'loop', 'label': '重复', 'target': 'f1', 'condition': 'flag', 'assignments': {}}]},
        ],
    }).model_dump()
    cycle_story = fixture_story(base_story, nodes=[{
        'node_id': 'f1', 'title': '循环', 'dialogue': '再走一次。', 'speaker': '', 'ending': '',
        'choices': [{'id': 'loop', 'label': '重复', 'target': 'f1',
                     'condition': {'op': 'var', 'name': 'flag'}, 'assignments': {}}]}],
        variables=[{'name': 'flag', 'type': 'bool', 'initial': True, 'minimum': 0, 'maximum': 100}], max_steps=3)
    cycle_project = project.parent / 'fixture-cycle'
    shutil.copytree(project, cycle_project, dirs_exist_ok=True)
    (cycle_project / 'data' / 'story.json').write_text(json.dumps(cycle_story, ensure_ascii=False, indent=2), encoding='utf-8')
    result = run_engine(engine, cycle_project, ['--witness-path', 'loop,loop,loop'], 'enforce.cycle.step_cap')
    ok, detail = healthy_run(result, 0)
    records = parse_records(result)
    expected = [expected_for(cycle_spec, {}, ['loop'] * index) for index in range(4)]
    if not ok:
        record('enforce.cycle.process', 'FAIL', detail)
    else:
        compared = compare_states(records['states'], expected, 'enforce.cycle.states')
        checked += compared
        status = records['states'][-1]['status'] if records['states'] else ''
        record('enforce.cycle.step_cap_status', 'PASS' if status == 'STEP_CAP_REACHED' else 'FAIL', status)
        beyond = run_engine(engine, cycle_project, ['--witness-path', 'loop,loop,loop,loop'], 'enforce.cycle.beyond_cap')
        beyond_records = parse_records(beyond)
        record('enforce.cycle.refuses_beyond_cap',
               'PASS' if beyond['exit_code'] == 3 and beyond_records['error'] and beyond_records['error']['code'] == 'PATH_REJECTED' else 'FAIL',
               str(beyond['exit_code']) + ' ' + json.dumps(beyond_records['error'])[:200])
    no_exit_spec = StorySpec.model_validate({
        'title': 'B07 runtime no-exit fixture', 'graph_id': 'fixture-no-exit', 'graph_version': 1,
        'entry_node_id': 'f1', 'max_steps': 4, 'graph_record_ids': [],
        'variables': [{'name': 'open', 'type': 'bool', 'initial': False, 'minimum': 0, 'maximum': 100}],
        'nodes': [
            {'node_id': 'f1', 'node_version': 1, 'title': '封闭', 'dialogue': '门锁着。',
             'choices': [{'id': 'open', 'label': '开门', 'target': 'f2', 'condition': 'open', 'assignments': {}}]},
            {'node_id': 'f2', 'node_version': 1, 'title': '门外', 'dialogue': '出去了。', 'ending': '门外结局'},
        ],
    }).model_dump()
    no_exit_story = fixture_story(base_story, nodes=[
        {'node_id': 'f1', 'title': '封闭', 'dialogue': '门锁着。', 'speaker': '', 'ending': '',
         'choices': [{'id': 'open', 'label': '开门', 'target': 'f2',
                      'condition': {'op': 'var', 'name': 'open'}, 'assignments': {}}]},
        {'node_id': 'f2', 'title': '门外', 'dialogue': '出去了。', 'speaker': '', 'ending': '门外结局', 'choices': []},
    ], variables=[{'name': 'open', 'type': 'bool', 'initial': False, 'minimum': 0, 'maximum': 100}], max_steps=4)
    no_exit_project = project.parent / 'fixture-no-exit'
    shutil.copytree(project, no_exit_project, dirs_exist_ok=True)
    (no_exit_project / 'data' / 'story.json').write_text(json.dumps(no_exit_story, ensure_ascii=False, indent=2), encoding='utf-8')
    result = run_engine(engine, no_exit_project, ['--print-user-dir'], 'enforce.no_exit')
    ok, detail = healthy_run(result, 0)
    records = parse_records(result)
    if not ok:
        record('enforce.no_exit.process', 'FAIL', detail)
    else:
        compared = compare_states(records['states'], [expected_for(no_exit_spec, {}, [])], 'enforce.no_exit.states')
        checked += compared
        status = records['states'][-1]['status'] if records['states'] else ''
        record('enforce.no_exit.status', 'PASS' if status == 'NO_EXIT' else 'FAIL', status)
    broken_variants = {
        'unknown_operator': lambda story: story['nodes'][0]['choices'][0].update(condition={'op': 'call', 'name': 'flag'}),
        'undefined_variable': lambda story: story['nodes'][0]['choices'][0].update(condition={'op': 'var', 'name': 'missing'}),
        'assignment_type_mismatch': lambda story: story['nodes'][0]['choices'][0].update(assignments={'flag': 'yes'}),
        'missing_choice_target': lambda story: story['nodes'][0]['choices'][0].update(target='no-such-node'),
    }
    for name, mutate in broken_variants.items():
        broken_story = deepcopy(cycle_story)
        mutate(broken_story)
        broken_project = project.parent / ('fixture-broken-' + name)
        if broken_project.exists():
            shutil.rmtree(broken_project)
        shutil.copytree(project, broken_project)
        (broken_project / 'data' / 'story.json').write_text(json.dumps(broken_story, ensure_ascii=False, indent=2), encoding='utf-8')
        result = run_engine(engine, broken_project, [], 'enforce.broken.' + name)
        records = parse_records(result)
        record('enforce.broken.' + name,
               'PASS' if result['exit_code'] == 3 and records['error'] and records['error']['code'] == 'STORY_LOAD_FAILED' else 'FAIL',
               str(result['exit_code']) + ' ' + json.dumps(records['error'])[:200])
    for name, spec_fixture in (('cycle', cycle_spec), ('no_exit', no_exit_spec)):
        snapshot = build_snapshot(spec_fixture)
        snapshot['witness'] = []
        compatibility = godot_export.compatibility(snapshot)
        record('enforce.authority_refuses_' + name,
               'PASS' if not compatibility['can_export'] else 'FAIL',
               ','.join(issue['code'] for issue in compatibility['issues'][:4]))
    return checked


# ---------------------------------------------------------------------------
# save / restore, rejects and path safety
# ---------------------------------------------------------------------------
def save_state_path(user_dir: Path, name: str) -> Path:
    return user_dir / name


def check_save_restore(engine: str, project: Path, spec: dict, characters: dict, cases: dict) -> dict:
    best = max(cases['cases'], key=lambda case: len(case['choices']))
    path = list(best['choices'])
    if len(path) < 2:
        record('save.path_selection', 'FAIL', 'no witness path long enough for a two-process save test')
        return {}
    split = len(path) // 2
    prefix, continuation = path[:split], path[split:]
    record('save.path_selection', 'PASS', 'path ' + ','.join(path) + ' split after ' + str(split))
    save_name = 'b07-godot-save.json'
    first = run_engine(engine, project, ['--witness-path', ','.join(prefix), '--save', 'user://' + save_name], 'save.process1')
    ok, detail = healthy_run(first, 0)
    records = parse_records(first)
    if not ok:
        record('save.process1', 'FAIL', detail)
        return {}
    user_dir = records['user_dir']
    if user_dir is None:
        record('save.user_dir', 'FAIL', 'POEMSEED_USERDIR not reported')
        return {}
    record('save.user_dir', 'PASS', str(user_dir))
    save_file = save_state_path(user_dir, save_name)
    if not save_file.is_file():
        record('save.file', 'FAIL', 'save file not written under user dir')
        return {}
    save_bytes = save_file.read_bytes()
    save_payload = json.loads(save_bytes.decode('utf-8'))
    saved_record = records['saved'] or {}
    record('save.file_sha256', 'PASS' if saved_record.get('sha256') == sha256_bytes(save_bytes) else 'FAIL',
           str(saved_record.get('sha256')) + ' vs ' + sha256_bytes(save_bytes))
    expected_schema = {
        'schema': godot_export.SAVE_SCHEMA,
        'save_schema_version': 1,
    }
    fields_ok = (save_payload.get('schema') == expected_schema['schema']
                 and save_payload.get('save_schema_version') == expected_schema['save_schema_version']
                 and save_payload.get('current_node_id') == expected_for(spec, characters, prefix)['node']['node_id']
                 and save_payload.get('path') == prefix
                 and save_payload.get('steps') == len(prefix)
                 and save_payload.get('story', {}).get('id') == STORY_ID
                 and save_payload.get('story', {}).get('revision') == 7)
    record('save.schema_and_state', 'PASS' if fields_ok else 'FAIL', 'schema/identity/path/steps')
    restored = run_engine(engine, project, ['--load', 'user://' + save_name], 'save.process2.restore')
    ok, detail = healthy_run(restored, 0)
    restored_records = parse_records(restored)
    compared = 0
    if not ok:
        record('save.process2', 'FAIL', detail)
    else:
        compared += compare_states(restored_records['states'], [expected_for(spec, characters, prefix)], 'save.restored_state')
        record('save.restored_node', 'PASS' if (restored_records['restored'] or {}).get('current_node_id') == expected_for(spec, characters, prefix)['node']['node_id'] else 'FAIL')
    continued = run_engine(engine, project, ['--load', 'user://' + save_name, '--witness-path', ','.join(continuation),
                                             '--result', 'user://b07-godot-result.json'], 'save.process2.continue')
    ok, detail = healthy_run(continued, 0)
    continued_records = parse_records(continued)
    if not ok:
        record('save.process2.continue', 'FAIL', detail)
    else:
        expected_states = [expected_for(spec, characters, prefix)]
        for depth in range(1, len(continuation) + 1):
            expected_states.append(expected_for(spec, characters, prefix + continuation[:depth]))
        compared += compare_states(continued_records['states'], expected_states, 'save.continued_states')
        direct_expected = expected_for(spec, characters, path)
        final = continued_records['states'][-1] if continued_records['states'] else {}
        record('save.continued_final_matches_direct_playback', 'PASS' if not typed_diff(direct_expected, final) else 'FAIL',
               '; '.join(typed_diff(direct_expected, final)[:3]))
        result_file = save_state_path(user_dir, 'b07-godot-result.json')
        if result_file.is_file():
            result_payload = json.loads(result_file.read_text(encoding='utf-8'))
            record('save.result_file', 'PASS' if (result_payload.get('schema') == godot_export.RESULT_SCHEMA
                                                  and not typed_diff(final, result_payload.get('state'))
                                                  and (continued_records['result'] or {}).get('sha256') == sha256_file(result_file)) else 'FAIL')
        else:
            record('save.result_file', 'FAIL', 'result file missing')
    # --- rejection matrix -------------------------------------------------
    base = deepcopy(save_payload)
    tampered_path = deepcopy(base)
    tampered_path['path'] = prefix[:-1] + ['missing_choice']
    tampered_variables = deepcopy(base)
    first_variable = next(iter(tampered_variables['variables']))
    raw_value = tampered_variables['variables'][first_variable]
    tampered_variables['variables'][first_variable] = (not raw_value) if isinstance(raw_value, bool) else (int(raw_value) + 1 if int(raw_value) < 3 else int(raw_value) - 1)
    tampered_revision = deepcopy(base)
    tampered_revision['story']['revision'] = 8
    tampered_spec = deepcopy(base)
    tampered_spec['story']['spec_digest'] = '0' * 64
    tampered_source = deepcopy(base)
    tampered_source['story']['source_digest'] = '0' * 64
    tampered_id = deepcopy(base)
    tampered_id['story']['id'] = 'some-other-story'
    tampered_schema = deepcopy(base)
    tampered_schema['save_schema_version'] = 99
    rejects = {
        'wrong_revision': tampered_revision,
        'wrong_spec_digest': tampered_spec,
        'wrong_source_digest': tampered_source,
        'wrong_story_id': tampered_id,
        'wrong_save_schema_version': tampered_schema,
        'tampered_variables': tampered_variables,
        'tampered_path': tampered_path,
    }
    rejection_checks = []
    for name, payload in rejects.items():
        target = save_state_path(user_dir, 'b07-reject-' + name + '.json')
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        result = run_engine(engine, project, ['--load', 'user://b07-reject-' + name + '.json'], 'reject.' + name)
        records = parse_records(result)
        passed = result['exit_code'] == 2 and records['error'] is not None and records['error']['code'] == 'SAVE_REJECTED' and not records['states']
        rejection_checks.append({'case': name, 'status': 'PASS' if passed else 'FAIL',
                                 'exit_code': result['exit_code'],
                                 'error': records['error']})
        record('reject.' + name, 'PASS' if passed else 'FAIL',
               str(result['exit_code']) + ' ' + json.dumps(records['error'])[:200])
    corrupt = save_state_path(user_dir, 'b07-reject-corrupt.json')
    corrupt.write_text('{not valid json', encoding='utf-8')
    result = run_engine(engine, project, ['--load', 'user://b07-reject-corrupt.json'], 'reject.corrupt_json')
    records = parse_records(result)
    record('reject.corrupt_json', 'PASS' if result['exit_code'] == 2 and records['error'] and records['error']['code'] == 'SAVE_REJECTED' else 'FAIL')
    # --- path safety ------------------------------------------------------
    traversal_result = run_engine(engine, project, ['--result', 'user://../b07-escape.json'], 'path.traversal_result')
    traversal_records = parse_records(traversal_result)
    escaped = user_dir.parent / 'b07-escape.json'
    record('path.traversal_result', 'PASS' if traversal_result['exit_code'] == 3 and traversal_records['error']
           and traversal_records['error']['code'] == 'RESULT_WRITE_FAILED' and not escaped.exists() else 'FAIL',
           str(traversal_result['exit_code']) + ' ' + json.dumps(traversal_records['error'])[:160])
    load_traversal = run_engine(engine, project, ['--load', 'user://../b07-save.json'], 'path.traversal_load')
    load_records = parse_records(load_traversal)
    record('path.traversal_load', 'PASS' if load_traversal['exit_code'] == 2 and load_records['error']
           and load_records['error']['code'] == 'SAVE_REJECTED' else 'FAIL')
    absolute_save = run_engine(engine, project, ['--save', 'C:/Windows/Temp/b07-absolute-save.json'], 'path.absolute_save')
    absolute_records = parse_records(absolute_save)
    record('path.absolute_save', 'PASS' if absolute_save['exit_code'] == 3 and absolute_records['error']
           and absolute_records['error']['code'] == 'SAVE_WRITE_FAILED'
           and not Path('C:/Windows/Temp/b07-absolute-save.json').exists() else 'FAIL')
    bad_suffix = run_engine(engine, project, ['--result', 'user://b07-result.txt'], 'path.bad_suffix')
    bad_suffix_records = parse_records(bad_suffix)
    record('path.bad_suffix', 'PASS' if bad_suffix['exit_code'] == 3 and bad_suffix_records['error']
           and bad_suffix_records['error']['code'] == 'RESULT_WRITE_FAILED' else 'FAIL')
    record('path.no_files_outside_user_dir', 'PASS' if not escaped.exists() else 'FAIL', str(escaped))
    # --- cleanup ----------------------------------------------------------
    cleaned = []
    for pattern in ('b07-*.json',):
        for path in user_dir.glob(pattern):
            try:
                path.unlink()
                cleaned.append(path.name)
            except OSError:
                pass
    record('save.cleanup_user_dir', 'PASS', str(len(cleaned)) + ' temporary user:// files removed')
    return {
        'path': path, 'split': split, 'save_sha256': sha256_bytes(save_bytes), 'save_bytes': len(save_bytes),
        'restored_states_compared': compared, 'rejection_cases': rejection_checks,
        'user_dir': str(user_dir),
    }


# ---------------------------------------------------------------------------
# external artifact verification mode (--artifact): verify what the Studio already
# exported, never re-generate the story, and fail closed on any inconsistency.
# ---------------------------------------------------------------------------
ARTIFACT_REPORT_SCHEMA = 'poemseed-b07-godot-artifact-verification/1'
ARTIFACT_SAVE_NAME = 'artifact-save.json'


def read_artifact_files(content: bytes) -> tuple[dict[str, bytes], str]:
    """Read an externally exported target ZIP with the same path rules as the product."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
    roots = {name.split('/', 1)[0] for name in names if name}
    if len(roots) != 1:
        raise ValueError('ARTIFACT_ROOT_INVALID')
    prefix = roots.pop() + '/'
    files = contract.read_zip_safely(content, prefix)
    return files, prefix


def expression_text(tree: dict) -> str:
    """Serialise a typed condition AST back to the restricted expression grammar."""
    op = str(tree['op'])
    if op == 'literal':
        value = tree['value']
        if type(value) is bool:
            return 'True' if value else 'False'
        return str(int(value))
    if op == 'var':
        return str(tree['name'])
    if op == 'not':
        return '(not (' + expression_text(tree['arg']) + '))'
    if op in ('and', 'or'):
        return '(' + (' ' + op + ' ').join('(' + expression_text(argument) + ')' for argument in tree['args']) + ')'
    operators = {'eq': '==', 'ne': '!=', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}
    if op not in operators:
        raise ValueError('ARTIFACT_CONDITION_OPERATOR_INVALID:' + op)
    return '((' + expression_text(tree['left']) + ') ' + operators[op] + ' (' + expression_text(tree['right']) + '))'


def artifact_spec_from_story(story: dict):
    """Reconstruct a StorySpec-equivalent dict from data/story.json for authoritative playback."""
    from app.experimental.interactive_story import parse_condition
    problems = []
    speakers = {str(node['node_id']): str(node.get('speaker') or '') for node in story['nodes']}
    nodes = []
    for node in story['nodes']:
        choices = []
        for choice in node['choices']:
            text = expression_text(choice['condition'])
            try:
                if parse_condition(text) != choice['condition']:
                    problems.append('condition round trip mismatch at ' + str(node['node_id']) + '/' + str(choice['id']))
            except ValueError as exc:
                problems.append('condition not serialisable at ' + str(node['node_id']) + '/' + str(choice['id'])
                                + ': ' + str(exc)[:160])
            choices.append({'id': choice['id'], 'label': choice['label'], 'target': choice['target'],
                            'condition': text, 'assignments': dict(choice['assignments'])})
        nodes.append({'node_id': node['node_id'], 'node_version': 1, 'title': node['title'],
                      'dialogue': node['dialogue'], 'character_id': None,
                      'background_asset_id': None, 'music_asset_id': None,
                      'ending': node['ending'], 'choices': choices})
    spec = {'title': story['title'], 'graph_id': 'artifact-' + str(story['story_id']),
            'graph_version': int(story['revision']), 'entry_node_id': story['entry_node_id'], 'nodes': nodes,
            'variables': [dict(variable) for variable in story['variables']],
            'graph_record_ids': [], 'max_steps': int(story['max_steps'])}
    try:
        spec = StorySpec.model_validate(spec).model_dump()
    except Exception as exc:
        problems.append('SPEC_RECONSTRUCTION_FAILED:' + type(exc).__name__ + ':' + str(exc)[:200])
        return {}, speakers, problems
    return spec, speakers, problems


def artifact_expected_state(spec: dict, speakers: dict, path) -> dict:
    from app.experimental.interactive_story import play
    result = play(spec, list(path))
    node = result['node']
    return {
        'node': {'node_id': node['node_id'], 'title': node['title'], 'dialogue': node['dialogue'],
                 'speaker': speakers.get(str(node['node_id']), ''), 'ending': node['ending']},
        'choices': [{'id': choice['id'], 'label': choice['label'], 'enabled': bool(choice['enabled'])}
                    for choice in result['choices']],
        'variables': result['variables'], 'steps': result['steps'], 'max_steps': result['max_steps'],
        'status': result['status'], 'path': list(result['path']),
    }


def flatten_state(state: dict) -> dict:
    """The compact per-step projection required by the external E2E report."""
    return {'node_id': str(state['node']['node_id']), 'variables': state['variables'],
            'enabled_choice_ids': [str(choice['id']) for choice in state['choices'] if bool(choice['enabled'])],
            'steps': int(state['steps']), 'status': str(state['status'])}


def artifact_bundle_records(files: dict):
    """Recompute the product bundle integrity from the artifact records, fail closed."""
    problems = []
    for name in ('manifest.json', 'source-receipt.json'):
        if name not in files:
            problems.append('missing ' + name)
    if problems:
        return {}, {}, problems
    try:
        manifest = json.loads(files['manifest.json'])
        receipt = json.loads(files['source-receipt.json'])
    except ValueError as exc:
        return {}, {}, ['RECORD_JSON_INVALID:' + type(exc).__name__]
    story = manifest.get('story') or {}
    raw = {'target_id': manifest.get('target_id'),
           'target_format_version': manifest.get('target_format_version'),
           'adapter_revision': manifest.get('adapter_revision'), 'kind': manifest.get('target_kind'),
           'story_id': story.get('id'), 'revision': story.get('revision'), 'filename_base': 'artifact',
           'files': files, 'payload_files_digest': manifest.get('payload_files_digest'),
           'files_digest': contract.files_digest(files), 'manifest': manifest, 'receipt': receipt,
           'capabilities': manifest.get('capabilities') or {}, 'losses': list(manifest.get('losses') or [])}
    try:
        bundle = contract.ExportBundle.model_validate(raw)
        contract.verify_bundle(bundle)
    except Exception as exc:
        problems.append('BUNDLE_INTEGRITY_INVALID:' + type(exc).__name__ + ':' + str(exc)[:240])
        return manifest, receipt, problems
    if bundle.target_id != TARGET_ID:
        problems.append('target id is ' + str(bundle.target_id))
    if bundle.kind != 'RUNNABLE_PROJECT':
        problems.append('target kind is ' + str(bundle.kind))
    if bundle.target_format_version != godot_export.FORMAT_VERSION:
        problems.append('format version is ' + str(bundle.target_format_version))
    return manifest, receipt, problems


def artifact_story_binding(story: dict, manifest: dict, receipt: dict) -> list:
    problems = []
    story_block = manifest.get('story') or {}
    pairs = [('story_id', story.get('story_id'), story_block.get('id')),
             ('revision', int(story.get('revision', 0)), story_block.get('revision')),
             ('spec_digest', story.get('spec_digest'), story_block.get('spec_digest')),
             ('source_digest', story.get('source_digest'), story_block.get('source_digest')),
             ('review_receipt', story.get('review_receipt'), story_block.get('review_receipt')),
             ('receipt_spec_digest', story.get('spec_digest'), receipt.get('spec_digest')),
             ('receipt_source_digest', story.get('source_digest'), receipt.get('source_digest')),
             ('receipt_story_id', story.get('story_id'), receipt.get('story_id')),
             ('receipt_revision', int(story.get('revision', 0)), receipt.get('story_revision'))]
    for name, story_value, record_value in pairs:
        if story_value != record_value:
            problems.append(name + ' story=' + str(story_value)[:64] + ' records=' + str(record_value)[:64])
    return problems


def artifact_cases_consistency(cases: dict, story: dict, spec: dict, speakers: dict) -> list:
    problems = []
    if not isinstance(cases, dict):
        return ['CASES_JSON_INVALID']
    if cases.get('schema') != godot_export.CASES_SCHEMA:
        problems.append('cases schema is ' + str(cases.get('schema')))
    if cases.get('target_id') != TARGET_ID:
        problems.append('cases target is ' + str(cases.get('target_id')))
    if str(cases.get('story_id')) != str(story['story_id']) or int(cases.get('revision', -1)) != int(story['revision']):
        problems.append('cases do not bind the artifact story/revision')
    if cases.get('spec_digest') != story['spec_digest'] or cases.get('source_digest') != story['source_digest']:
        problems.append('cases do not bind the artifact spec/source digest')
    case_list = cases.get('cases') or []
    if not case_list:
        problems.append('cases are empty: no authoritative witness to replay')
    witness_paths = {tuple(record.get('choices') or []) for record in (story.get('witness') or [])}
    case_paths = set()
    for case in case_list:
        path = list(case.get('choices') or [])
        case_paths.add(tuple(path))
        try:
            expected = artifact_expected_state(spec, speakers, path)
        except (ValueError, TypeError) as exc:
            problems.append('case ' + str(case.get('case_id')) + ' playback failed: ' + str(exc)[:160])
            continue
        if expected['status'] != 'ENDING':
            problems.append('case ' + str(case.get('case_id')) + ' does not reach an ending in authoritative playback')
        for difference in typed_diff(expected, case.get('expected_final'), 'case ' + str(case.get('case_id'))):
            problems.append('cases.json expected_final mismatch: ' + difference[:240])
    if witness_paths and case_paths != witness_paths:
        missing = sorted(witness_paths - case_paths)
        extra = sorted(case_paths - witness_paths)
        problems.append('cases cover different paths than the artifact witness: missing='
                        + str(missing[:4]) + ' extra=' + str(extra[:4]))
    return problems


def artifact_project_checks(project: Path, manifest: dict) -> None:
    project_file = project / 'project.godot'
    project_text = project_file.read_text(encoding='utf-8') if project_file.is_file() else ''
    extra = (manifest.get('extra') or {}).get('godot_runtime') or {}
    failures = []
    if 'config_version=5' not in project_text:
        failures.append('config_version=5 missing')
    if 'run/main_scene="res://main.tscn"' not in project_text:
        failures.append('main scene missing')
    if 'viewport_width=960' not in project_text or 'viewport_height=600' not in project_text:
        failures.append('window size missing')
    if extra.get('project_name') and ('config/name="' + str(extra['project_name']) + '"') not in project_text:
        failures.append('project name does not match the export manifest')
    record('artifact.project_config', 'PASS' if not failures else 'FAIL', '; '.join(failures[:5]))
    drift = [relative for relative, expected in godot_export.PINNED_TEMPLATE_SHA256.items()
             if not (project / relative).is_file() or sha256_file(project / relative) != expected]
    record('artifact.runtime_template_pinned', 'PASS' if not drift else 'FAIL',
           'all delivered runtime files match the audited pinned template' if not drift else 'drift: ' + ','.join(drift[:6]))
    template_mismatch = []
    for relative, expected in (extra.get('template_files') or {}).items():
        shipped = project / relative
        if not shipped.is_file() or sha256_file(shipped) != expected:
            template_mismatch.append(relative)
    record('artifact.manifest_template_hashes', 'PASS' if not template_mismatch else 'FAIL',
           '; '.join(template_mismatch[:6]))
    if not (project / 'data' / 'story.json').is_file() or not (project / 'acceptance' / 'cases.json').is_file():
        record('artifact.data_files', 'FAIL', 'data/story.json or acceptance/cases.json missing after extraction')
    else:
        record('artifact.data_files', 'PASS')


def extract_artifact(files: dict, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    for relative, content in files.items():
        if relative in {'manifest.json', 'source-receipt.json'}:
            continue
        contract.safe_bundle_path(relative)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def artifact_save_restore(engine: str, project: Path, story: dict, spec: dict, speakers: dict, cases: dict) -> dict:
    """Two-process save -> load -> continue and compare with authoritative playback."""
    case_list = list(cases.get('cases') or [])
    scenario = None
    for case in case_list:
        path = list(case.get('choices') or [])
        save_at = case.get('save_at')
        if isinstance(save_at, int) and not isinstance(save_at, bool) and 1 <= save_at < len(path):
            scenario = (path, save_at, 'cases.save_at:' + str(case.get('case_id')))
            break
    if scenario is None and case_list:
        candidates = [case for case in case_list if len(list(case.get('choices') or [])) >= 2]
        if candidates:
            longest = max(candidates, key=lambda case: len(list(case.get('choices') or [])))
            path = list(longest.get('choices') or [])
            scenario = (path, max(1, len(path) // 2), 'derived.two_process')
        else:
            longest = max(case_list, key=lambda case: len(list(case.get('choices') or [])))
            path = list(longest.get('choices') or [])
            if path:
                scenario = (path, 0, 'derived.initial_state_save')
    if scenario is None:
        return {'performed': False, 'passed': False,
                'detail': 'no artifact witness path is available; two-process save/restore not performed'}
    path, split, origin = scenario
    prefix, continuation = path[:split], path[split:]
    result = {'performed': True, 'passed': False, 'origin': origin, 'save_after_steps': len(prefix),
              'continued_steps': len(continuation), 'detail': ''}
    problems = []
    first_args = (['--witness-path', ','.join(prefix)] if prefix else []) + ['--save', 'user://' + ARTIFACT_SAVE_NAME]
    first = run_engine(engine, project, first_args, 'artifact.save.process1')
    ok, detail = healthy_run(first, 0)
    first_records = parse_records(first)
    user_dir = first_records['user_dir']
    result['user_dir'] = str(user_dir)
    if not ok:
        problems.append('process1: ' + detail)
    expected_prefix = [artifact_expected_state(spec, speakers, prefix[:depth]) for depth in range(len(prefix) + 1)]
    if len(first_records['states']) != len(expected_prefix):
        problems.append('process1 emitted ' + str(len(first_records['states'])) + ' states, expected ' + str(len(expected_prefix)))
    else:
        for index, (actual, expected) in enumerate(zip(first_records['states'], expected_prefix)):
            differences = typed_diff(expected, actual)
            if differences:
                problems.append('process1 step ' + str(index) + ': ' + differences[0])
    save_file = (user_dir / ARTIFACT_SAVE_NAME) if user_dir else None
    if save_file is None or not save_file.is_file():
        problems.append('save file was not written under user://')
    else:
        save_bytes = save_file.read_bytes()
        result['save_sha256'] = sha256_bytes(save_bytes)
        result['save_bytes'] = len(save_bytes)
        recorded_sha = (first_records['saved'] or {}).get('sha256')
        if recorded_sha != result['save_sha256']:
            problems.append('reported save sha256 does not match the file')
        try:
            save_payload = json.loads(save_bytes.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            save_payload = {}
            problems.append('save file is not valid UTF-8 JSON')
        if save_payload.get('schema') != godot_export.SAVE_SCHEMA or save_payload.get('save_schema_version') != 1:
            problems.append('save schema invalid')
        save_story = save_payload.get('story') or {}
        if (save_story.get('id') != story['story_id']
                or int(save_story.get('revision', -1)) != int(story['revision'])):
            problems.append('save does not bind the artifact story/revision')
        if save_payload.get('path') != prefix or int(save_payload.get('steps', -1)) != len(prefix):
            problems.append('save does not record the replayed path')
    second = run_engine(engine, project, ['--load', 'user://' + ARTIFACT_SAVE_NAME,
                                          '--witness-path', ','.join(continuation)], 'artifact.save.process2')
    ok, detail = healthy_run(second, 0)
    second_records = parse_records(second)
    if not ok:
        problems.append('process2: ' + detail)
    expected_continued = [artifact_expected_state(spec, speakers, prefix)]
    for depth in range(1, len(continuation) + 1):
        expected_continued.append(artifact_expected_state(spec, speakers, prefix + continuation[:depth]))
    if len(second_records['states']) != len(expected_continued):
        problems.append('process2 emitted ' + str(len(second_records['states'])) + ' states, expected ' + str(len(expected_continued)))
    else:
        for index, (actual, expected) in enumerate(zip(second_records['states'], expected_continued)):
            differences = typed_diff(expected, actual)
            if differences:
                problems.append('process2 step ' + str(index) + ': ' + differences[0])
        direct = artifact_expected_state(spec, speakers, path)
        for difference in typed_diff(direct, second_records['states'][-1]):
            problems.append('restored continuation differs from direct playback: ' + difference[:240])
    result['passed'] = not problems
    result['detail'] = '; '.join(problems[:6]) if problems else (
        'two-process save/restore matched direct playback (' + origin + '; saved after ' + str(len(prefix))
        + ' step(s), continued ' + str(len(continuation)) + ' step(s))')
    return result


def artifact_main(args) -> int:
    """Verify an externally exported target ZIP with the real engine; write a JSON report."""
    started = time.monotonic()
    artifact_path = Path(str(args.artifact))
    if args.report:
        report_path = Path(str(args.report))
    else:
        report_path = Path(args.scratch_root) / ('artifact-verification-' + artifact_path.stem[:60] + '.json')
    report = {'schema': ARTIFACT_REPORT_SCHEMA, 'result': 'FAIL', 'mode': 'EXTERNAL_ARTIFACT',
              'generated_at': datetime.now(timezone.utc).isoformat(), 'target_id': TARGET_ID,
              'artifact': {'path': str(artifact_path), 'filename': artifact_path.name, 'sha256': None,
                           'bundle_files': [], 'story_id': None, 'revision': None,
                           'manifest_sha256': None, 'receipt_sha256': None},
              'engine': {'executable': None, 'version': None, 'exit_code': None, 'minimum_version': '4.0'},
              'cases': [], 'save_restore': {'performed': False, 'passed': False, 'detail': ''},
              'checks': [], 'failures': [], 'elapsed_ms': 0}
    user_dir = None
    print('== B07 Godot runtime verifier (external artifact mode) ==')
    try:
        engine, source = find_engine(args.godot)
        report['engine']['executable'] = engine
        if engine is None:
            record('artifact.engine_found', 'FAIL', source)
            return 1
        record('artifact.engine_found', 'PASS', engine)
        version_proc = subprocess.run([engine, '--version'], capture_output=True, timeout=30)
        report['engine']['version'] = (version_proc.stdout + version_proc.stderr).decode('utf-8', 'replace').strip()
        report['engine']['exit_code'] = version_proc.returncode
        record('artifact.engine_version', 'PASS' if version_proc.returncode == 0 else 'FAIL', report['engine']['version'])
        if not artifact_path.is_file():
            record('artifact.exists', 'FAIL', str(artifact_path))
            return 1
        content = artifact_path.read_bytes()
        report['artifact']['sha256'] = sha256_bytes(content)
        record('artifact.exists', 'PASS', artifact_path.name + ' sha256 ' + report['artifact']['sha256'][:16])
        try:
            files, prefix = read_artifact_files(content)
        except (ValueError, zipfile.BadZipFile, OSError) as exc:
            record('artifact.zip_structure', 'FAIL', type(exc).__name__ + ':' + str(exc)[:200])
            return 1
        report['artifact']['bundle_files'] = sorted(files)
        record('artifact.zip_structure', 'PASS', str(len(files)) + ' files under ' + prefix)
        for name in ('manifest.json', 'source-receipt.json', 'project.godot', 'main.tscn',
                     'data/story.json', 'acceptance/cases.json'):
            record('artifact.file:' + name, 'PASS' if name in files else 'FAIL')
        manifest, receipt, problems = artifact_bundle_records(files)
        record('artifact.bundle_integrity', 'PASS' if not problems else 'FAIL', '; '.join(problems[:5]))
        if problems:
            return 1
        report['artifact']['manifest_sha256'] = sha256_bytes(files['manifest.json'])
        report['artifact']['receipt_sha256'] = sha256_bytes(files['source-receipt.json'])
        try:
            story = json.loads(files['data/story.json'])
            godot_export.GodotRuntimeStory.model_validate(story)
            record('artifact.story_schema', 'PASS', godot_export.RUNTIME_STORY_SCHEMA)
        except Exception as exc:
            record('artifact.story_schema', 'FAIL', type(exc).__name__ + ':' + str(exc)[:240])
            return 1
        report['artifact']['story_id'] = story['story_id']
        report['artifact']['revision'] = story['revision']
        binding_problems = artifact_story_binding(story, manifest, receipt)
        record('artifact.story_binding', 'PASS' if not binding_problems else 'FAIL', '; '.join(binding_problems[:5]))
        spec, speakers, reconstruction_problems = artifact_spec_from_story(story)
        record('artifact.spec_reconstruction', 'PASS' if not reconstruction_problems else 'FAIL',
               '; '.join(reconstruction_problems[:5]))
        if reconstruction_problems:
            return 1
        try:
            cases = json.loads(files['acceptance/cases.json'])
        except ValueError as exc:
            record('artifact.cases_json', 'FAIL', type(exc).__name__)
            return 1
        case_problems = artifact_cases_consistency(cases, story, spec, speakers)
        record('artifact.cases_authority', 'PASS' if not case_problems else 'FAIL', '; '.join(case_problems[:6]))
        if case_problems:
            return 1
        project = Path(args.scratch_root) / ('artifact-' + artifact_path.stem[:50] + '-' + report['artifact']['sha256'][:12])
        try:
            extract_artifact(files, project)
        except (ValueError, OSError) as exc:
            record('artifact.extract', 'FAIL', type(exc).__name__ + ':' + str(exc)[:200])
            return 1
        record('artifact.extract', 'PASS', str(project))
        artifact_project_checks(project, manifest)
        check_static_audit(project)
        initial = run_engine(engine, project, ['--print-user-dir'], 'artifact.initial')
        ok, detail = healthy_run(initial, 0)
        initial_records = parse_records(initial)
        user_dir = initial_records['user_dir']
        problems = []
        if not ok:
            problems.append(detail)
        expected_initial = artifact_expected_state(spec, speakers, [])
        if not initial_records['states']:
            problems.append('no POEMSEED_STATE emitted')
        else:
            problems.extend(typed_diff(expected_initial, initial_records['states'][0])[:3])
        record('artifact.initial_state', 'PASS' if not problems else 'FAIL', '; '.join(problems[:4]))
        for case in cases['cases']:
            path = list(case.get('choices') or [])
            entry = {'case_id': str(case.get('case_id')), 'choices': path, 'states': [],
                     'ending': None, 'step_cap': False, 'result': 'FAIL', 'detail': ''}
            label = 'artifact.case.' + entry['case_id']
            result = run_engine(engine, project, ['--witness-path', ','.join(path)], label)
            ok, detail = healthy_run(result, 0)
            records = parse_records(result)
            problems = []
            if not ok:
                problems.append(detail)
            expected_states = [artifact_expected_state(spec, speakers, path[:depth]) for depth in range(len(path) + 1)]
            if len(records['states']) != len(expected_states):
                problems.append('runtime emitted ' + str(len(records['states'])) + ' states, expected ' + str(len(expected_states)))
            else:
                for index, (actual, expected) in enumerate(zip(records['states'], expected_states)):
                    differences = typed_diff(expected, actual)
                    if differences:
                        problems.append('step ' + str(index) + ': ' + differences[0])
                done = records['done'] or {}
                if done.get('path') != path or done.get('status') != 'ENDING':
                    problems.append('POEMSEED_DONE record mismatch')
                for difference in typed_diff(case.get('expected_final'), records['states'][-1]):
                    problems.append('final state does not match acceptance/cases.json: ' + difference[:240])
            entry['states'] = [flatten_state(state) for state in records['states']]
            if records['states']:
                final_state = records['states'][-1]
                entry['ending'] = str(final_state['node']['ending']) if final_state['status'] == 'ENDING' else None
                entry['step_cap'] = any(str(state['status']) == 'STEP_CAP_REACHED' for state in records['states'])
            entry['result'] = 'PASS' if not problems else 'FAIL'
            entry['detail'] = '; '.join(problems[:5])
            report['cases'].append(entry)
            record(label, entry['result'], entry['detail'])
        report['save_restore'] = artifact_save_restore(engine, project, story, spec, speakers, cases)
        if report['save_restore'].get('user_dir'):
            user_dir = Path(report['save_restore']['user_dir'])
        record('artifact.save_restore', 'PASS' if report['save_restore']['passed'] else 'FAIL',
               report['save_restore']['detail'][:400])
    except Exception as exc:  # noqa: BLE001 - never crash the harness; report the failure
        record('artifact.unexpected_error', 'FAIL', type(exc).__name__ + ':' + str(exc)[:300])
    finally:
        if user_dir is not None and Path(user_dir).is_dir():
            for name in (ARTIFACT_SAVE_NAME, 'artifact-result.json'):
                target = Path(user_dir) / name
                try:
                    if target.exists():
                        target.unlink()
                except OSError:
                    pass
        report['elapsed_ms'] = int((time.monotonic() - started) * 1000)
        report['checks'] = list(CHECKS)
        report['failures'] = list(FAILURES)
        report['result'] = 'PASS' if not FAILURES else 'FAIL'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(json_safe(report), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('artifact report: ' + str(report_path))
        print('result: ' + report['result'] + ', checks: ' + str(len(CHECKS)) + ', failures: ' + str(len(FAILURES)))
        for failure in FAILURES[:10]:
            print('  FAIL ' + failure['check'] + ' :: ' + failure['detail'][:300])
    return 0 if report['result'] == 'PASS' else 1


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def default_main(args) -> int:
    print('== B07 Godot runtime verifier ==')
    engine, source = find_engine(args.godot)
    if engine is None:
        record('engine.found', 'FAIL', source)
        write_evidence(engine=None, engine_info=None, scratch=Path(args.scratch_root), artifacts={}, alignment={}, saves={}, started=datetime.now(timezone.utc))
        return 1
    record('engine.found', 'PASS', engine)
    version_started = time.monotonic()
    version_proc = subprocess.run([engine, '--version'], capture_output=True, timeout=30)
    version_duration = int((time.monotonic() - version_started) * 1000)
    version_stdout = (version_proc.stdout + version_proc.stderr).decode('utf-8', 'replace').strip()
    engine_info = {'executable': engine, 'version_stdout': version_stdout, 'version_exit_code': version_proc.returncode,
                   'source': source, 'minimum_version': '4.0'}
    COMMANDS.append({'label': 'engine.version', 'argv': [engine, '--version'], 'exit_code': version_proc.returncode,
                     'timed_out': False, 'duration_ms': version_duration,
                     'stdout_sha256': sha256_bytes(version_proc.stdout), 'stderr_sha256': sha256_bytes(version_proc.stderr)})
    record('engine.version', 'PASS' if version_proc.returncode == 0 else 'FAIL', version_stdout)

    scratch = Path(args.scratch_root)
    project = scratch / STORY_ID
    if project.exists():
        shutil.rmtree(project)
    project.mkdir(parents=True, exist_ok=True)
    spec = build_story_spec()
    snapshot = build_snapshot(spec)
    analysis = snapshot['analysis']
    record('story.analysis', 'PASS' if analysis['can_review'] else 'FAIL',
           'states_checked=' + str(analysis['states_checked']) + ' endings=' + str(len(analysis['endings'])))
    if not analysis['can_review']:
        write_evidence(engine=engine, engine_info=engine_info, scratch=scratch, artifacts={}, alignment={}, saves={}, started=datetime.now(timezone.utc))
        return 1
    compatibility = godot_export.compatibility(snapshot)
    record('story.compatibility', 'PASS' if compatibility['can_export'] else 'FAIL',
           'issues=' + ','.join(issue['code'] for issue in compatibility['issues'][:4]))
    first_bundle = contract.build_export_bundle(TARGET_ID, snapshot)
    second_bundle = contract.build_export_bundle(TARGET_ID, snapshot)
    record('build.deterministic', 'PASS' if first_bundle.files == second_bundle.files else 'FAIL',
           'digest ' + first_bundle.files_digest[:16])
    package = contract.package_export_zip(first_bundle)
    (project.parent / 'project.zip').write_bytes(package['content'])
    with zipfile.ZipFile(project.parent / 'project.zip') as archive:
        for name in archive.namelist():
            relative = name[len(package['prefix']):]
            if not relative:
                continue
            destination = project / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
    story = json.loads(first_bundle.files['data/story.json'])
    cases = json.loads(first_bundle.files['acceptance/cases.json'])
    record('build.artifact_extracted', 'PASS', str(len(first_bundle.files)) + ' files, zip sha256 ' + package['sha256'][:16])
    check_artifact(project, first_bundle, story, cases, spec)
    check_static_audit(project)
    alignment = check_alignment(engine, project, spec, snapshot['characters'], cases)
    enforcement_states = check_enforcement(engine, project, first_bundle, spec)
    saves = check_save_restore(engine, project, spec, snapshot['characters'], cases) if alignment['states_compared'] else {}
    artifacts = {
        'zip_filename': package['filename'],
        'zip_sha256': package['sha256'],
        'zip_file_count': package['file_count'],
        'bundle_files_digest': first_bundle.files_digest,
        'payload_files_digest': first_bundle.payload_files_digest,
        'story_sha256': sha256_bytes(first_bundle.files['data/story.json']),
        'cases_sha256': sha256_bytes(first_bundle.files['acceptance/cases.json']),
        'project_godot_sha256': sha256_bytes(first_bundle.files['project.godot']),
        'template_sha256': godot_export.template_hashes(),
        'extracted_root': str(project),
        'extracted_zip_sha256_matches': sha256_file(project.parent / 'project.zip') == package['sha256'],
        'manifest_sha256': sha256_bytes(first_bundle.files['manifest.json']),
        'receipt_sha256': sha256_bytes(first_bundle.files['source-receipt.json']),
        'spec_digest': snapshot['spec_digest'],
        'source_digest': snapshot['source_digest'],
        'review_receipt': snapshot['review_receipt'],
    }
    status = 'PASS' if not FAILURES else 'FAIL'
    write_evidence(engine=engine, engine_info=engine_info, scratch=scratch, artifacts=artifacts,
                   alignment=alignment, saves=saves, started=datetime.now(timezone.utc), status=status)
    print('')
    print('== evidence ==')
    print(json.dumps(proposed_evidence(), indent=2))
    print('checks: ' + str(len(CHECKS)) + ', failures: ' + str(len(FAILURES)))
    if FAILURES:
        print(json.dumps(FAILURES[:10], indent=2))
        return 1
    print('RESULT: PASS - real Godot 4 headless execution and two-process save/restore verified.')
    return 0


def proposed_evidence() -> dict:
    record_ok = not FAILURES
    return {
        'SOURCE_IMPLEMENTED': 'PASS',
        'SCHEMA_VALIDATED': 'PASS',
        'FIXTURE_TESTED': 'PASS',
        'GENERATED_ARTIFACT_VALIDATED': 'PASS' if record_ok else 'FAIL',
        'TARGET_RUNTIME_EXECUTED': 'PASS' if record_ok else 'FAIL',
        'SAVE_RESTORE_VERIFIED': 'PASS' if record_ok else 'FAIL',
        'WINDOWS_USABILITY_VERIFIED': 'NOT_RUN',
    }


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def write_evidence(*, engine, engine_info, scratch, artifacts, alignment, saves, started, status=None) -> None:
    status = status or ('PASS' if not FAILURES else 'FAIL')
    head = run_git(['rev-parse', 'HEAD'])
    branch = run_git(['rev-parse', '--abbrev-ref', 'HEAD'])
    script_sha = sha256_file(Path(__file__).resolve())
    evidence = {
        'schema': 'poemseed-b07-godot-runtime-evidence/1',
        'generated_at': started.astimezone(timezone.utc).isoformat(),
        'status': status,
        'title': 'B07/DIF-10/E2E-07 Godot 4 runnable runtime project - real headless acceptance evidence',
        'target': {'target_id': TARGET_ID, 'format_version': godot_export.FORMAT_VERSION,
                   'adapter_revision': godot_export.ADAPTER_REVISION, 'kind': 'RUNNABLE_PROJECT'},
        'product': {'repository_head': head, 'branch': branch,
                    'repository_head_note': 'repository_head is the code commit under test at time of run; '
                                            'the evidence .json/.log files are committed afterwards as a separate docs commit.',
                    'script': 'scripts/verify_godot_interactive_runtime.py', 'script_sha256': script_sha},
        'host': {'platform': platform.platform(), 'machine': platform.machine(), 'python': sys.version.split()[0]},
        'engine': engine_info,
        'artifacts': artifacts,
        'commands': COMMANDS,
        'checks': CHECKS,
        'failures': FAILURES,
        'alignment': alignment,
        'save_restore': saves,
        'evidence_levels': {
            'SOURCE_IMPLEMENTED': 'PASS',
            'SCHEMA_VALIDATED': 'PASS',
            'FIXTURE_TESTED': 'PASS',
            'GENERATED_ARTIFACT_VALIDATED': 'PASS' if not FAILURES else 'FAIL',
            'TARGET_RUNTIME_EXECUTED': 'PASS' if not FAILURES and alignment.get('states_compared', 0) > 0 else 'FAIL',
            'SAVE_RESTORE_VERIFIED': 'PASS' if not FAILURES and saves.get('restored_states_compared', 0) > 0
            and all(item['status'] == 'PASS' for item in saves.get('rejection_cases', []) or []) else 'FAIL',
            'WINDOWS_USABILITY_VERIFIED': 'NOT_RUN',
        },
        'limits': [
            'Headless engine automation does not verify Windows GUI usability, window behavior, input or font glyph rendering; WINDOWS_USABILITY_VERIFIED is NOT_RUN.',
            'The verifier executes the exported project from a scratch extraction directory; it does not install or modify the engine.',
            'Runtime enforcement fixtures (step cap, no-exit, malformed data) are defense in depth; the authority gate refuses to export such stories.',
            'Media references are recorded as IDs only; no media bytes are packaged or played.',
            'This evidence covers one synthetic end-to-end story fixture, not every possible user story; the export path is the real product contract path.',
        ],
        'engine_note': 'Generation is not execution: this file exists only because the packaged project really ran.',
    }
    EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_JSON.write_text(json.dumps(json_safe(evidence), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_log(evidence, engine, scratch)
    print('evidence written: ' + str(EVIDENCE_JSON))
    print('evidence log:     ' + str(EVIDENCE_LOG))


def write_log(evidence: dict, engine, scratch) -> None:
    lines = ['# B07 Godot 4 runtime acceptance evidence log (generated by scripts/verify_godot_interactive_runtime.py)',
             '',
             'status: ' + evidence['status'],
             'generated_at: ' + evidence['generated_at'],
             'target: ' + TARGET_ID + ' ' + godot_export.FORMAT_VERSION,
             'repository_head: ' + str(evidence['product']['repository_head']),
             'engine: ' + str((evidence.get('engine') or {}).get('executable')) + ' -> ' + str((evidence.get('engine') or {}).get('version_stdout')),
             'zip_sha256: ' + str(evidence.get('artifacts', {}).get('zip_sha256')),
             'bundle_files_digest: ' + str(evidence.get('artifacts', {}).get('bundle_files_digest')),
             'scratch: ' + str(scratch),
             '',
             '## evidence levels',
             '']
    for level, status in evidence['evidence_levels'].items():
        lines.append('- ' + level + ': ' + status)
    lines += ['', '## checks', '']
    for check in evidence['checks']:
        lines.append('- ' + check['status'] + ' ' + check['check'] + ((' :: ' + check['detail']) if check['detail'] else ''))
    lines += ['', '## commands', '']
    for command in evidence['commands']:
        lines.append('- ' + command['label'] + ' [exit ' + str(command['exit_code']) + ', ' + str(command['duration_ms']) + ' ms]')
        lines.append('  ' + ' '.join(command['argv']))
        lines.append('  stdout_sha256=' + command['stdout_sha256'] + ' stderr_sha256=' + command['stderr_sha256'])
    lines += ['', '## limits', '']
    lines += ['- ' + limit for limit in evidence['limits']]
    lines += ['', '## failures', '']
    lines += (['- ' + failure['check'] + ' :: ' + failure['detail'] for failure in evidence['failures']] or ['- none'])
    EVIDENCE_LOG.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('evidence log written: ' + str(EVIDENCE_LOG))


def run_git(arguments: list[str]) -> str | None:
    try:
        completed = subprocess.run(['git', *arguments], cwd=REPO_ROOT, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Verify a real Godot 4 runtime project: freshly generated fixture export (default) or an externally exported target ZIP (--artifact).')
    parser.add_argument('--godot', default=None, help='Godot 4 console executable to use')
    parser.add_argument('--scratch-root', default=str(DEFAULT_SCRATCH_ROOT),
                        help='scratch directory for extraction; the artifact report default path lives here')
    parser.add_argument('--artifact', default=None, metavar='ZIP',
                        help='verify an already exported GODOT_4_RUNTIME_PROJECT_V1 ZIP instead of generating one')
    parser.add_argument('--report', default=None, metavar='JSON',
                        help='write the verification report JSON here (artifact mode; defaults under --scratch-root)')
    args = parser.parse_args()
    if args.report and not args.artifact:
        parser.error('--report is only meaningful together with --artifact')
    if args.artifact:
        return artifact_main(args)
    return default_main(args)


if __name__ == '__main__':
    raise SystemExit(main())
