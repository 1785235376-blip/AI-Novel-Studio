"""B07/DIF-10 interactive export target contract.

Frozen shared interface between the Studio service and the shipped per-engine
adapters (Ren'Py project, Godot runtime project, Ink current-artifact delivery).

An adapter is a restricted pure conversion step. It receives an authorized,
approved story snapshot that already carries its spec digest, source digest,
review receipt, witness and media manifest, and returns an in-memory file
dictionary plus a compatibility/loss report. It never opens arbitrary files,
never writes outside the returned dictionary, never launches or installs an
engine, and never executes story code.

This module owns the only accepted bundle shape: relative-path validation,
per-file SHA-256, deterministic manifest, source receipt, deterministic ZIP
container, capability vocabulary and evidence levels. Adapters cannot bypass
it and the service never trusts an adapter's raw output.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_SCHEMA = 'poemseed-interactive-export-contract/1'
CONTRACT_VERSION = 1
MANIFEST_SCHEMA = 'poemseed-interactive-export-manifest/1'
RECEIPT_SCHEMA = 'poemseed-interactive-export-source-receipt/2'
TARGETS_SCHEMA = 'poemseed-interactive-export-targets/1'

CAPABILITY_KEYS = (
    'conditions', 'bool_variables', 'int_variables', 'assignment', 'dialogue',
    'choices', 'endings', 'loops', 'step_cap', 'save', 'restore', 'unicode', 'media',
)
EVIDENCE_LEVELS = (
    'SOURCE_IMPLEMENTED', 'SCHEMA_VALIDATED', 'FIXTURE_TESTED',
    'GENERATED_ARTIFACT_VALIDATED', 'TARGET_RUNTIME_EXECUTED',
    'SAVE_RESTORE_VERIFIED', 'WINDOWS_USABILITY_VERIFIED',
)
EVIDENCE_STATUSES = ('PASS', 'FAIL', 'PARTIAL', 'BLOCKED_ENVIRONMENT', 'BLOCKED_AUTHORITY', 'NOT_RUN')
TARGET_KINDS = ('RUNNABLE_PROJECT', 'DATA_ONLY_ADAPTER', 'LEGACY_FRAGMENT')

# Bundle limits: a workbook, a typed story and small runtime scripts, nothing more.
MAX_FILES = 256
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_PATH_LENGTH = 180
WINDOWS_RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}
_SAFE_SEGMENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
_DIGEST = re.compile(r'^[a-f0-9]{64}$')

# Adapters are discovered lazily so this contract module stays importable while
# target lines are developed in parallel. A missing module means the target line
# has not landed yet: it is reported as unavailable, never as passing.
TARGET_MODULES: dict[str, str] = {
    'RENPY_8_5_4_PROJECT_V1': '.interactive_renpy_export',
    'GODOT_4_RUNTIME_PROJECT_V1': '.interactive_godot_export',
    'INK_2_3_2_CURRENT_ARTIFACT_V1': '.ink_export',
}
_MODULE_CACHE: dict[str, object] = {}

# Evidence is recorded per independent check. Real runtime execution can only be
# claimed here after the integration owner actually ran the generated artifact
# in the target runtime; generation success never promotes a lower level.
# Updated by the integration owner at the end of a verified slice.
EVIDENCE_OVERRIDES: dict[str, dict[str, str]] = {}


class Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CapabilitySupport(Frozen):
    supported: bool
    lossy: bool = False
    note: str = ''


class EngineRequirement(Frozen):
    name: str = Field(min_length=1, max_length=80)
    minimum_version: str = Field(min_length=1, max_length=40)
    executables: list[str] = Field(default_factory=list, max_length=12)
    version_args: list[str] = Field(default_factory=lambda: ['--version'], max_length=4)
    env_override: str | None = Field(default=None, max_length=80)
    search_hints: list[str] = Field(default_factory=list, max_length=8)
    gui: bool = False
    note: str = ''


class TargetDescriptor(Frozen):
    target_id: str = Field(pattern=r'^[A-Z][A-Z0-9_]{2,80}$')
    display_name: str = Field(min_length=1, max_length=160)
    kind: Literal['RUNNABLE_PROJECT', 'DATA_ONLY_ADAPTER', 'LEGACY_FRAGMENT']
    format_version: str = Field(min_length=1, max_length=40)
    adapter_revision: int = Field(ge=1, le=1000)
    engine: EngineRequirement | None = None
    capabilities: dict[str, CapabilitySupport]
    losses: list[str] = Field(default_factory=list, max_length=64)
    runtime_requirements: list[str] = Field(default_factory=list, max_length=32)
    launch_instructions: str = Field(min_length=1, max_length=4000)
    integration_notes: list[str] = Field(default_factory=list, max_length=32)
    evidence: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode='after')
    def complete_capabilities(self):
        missing = [key for key in CAPABILITY_KEYS if key not in self.capabilities]
        if missing: raise ValueError('capability vocabulary incomplete: ' + ','.join(missing))
        for level, status in self.evidence.items():
            if level not in EVIDENCE_LEVELS or status not in EVIDENCE_STATUSES:
                raise ValueError('unknown evidence record: ' + level + '=' + status)
        return self


class StorySnapshot(Frozen):
    """The only story authority an adapter may consume."""
    story_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    revision: int = Field(ge=1)
    status: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=160)
    spec: dict
    spec_digest: str = Field(pattern=_DIGEST.pattern)
    source_digest: str = Field(pattern=_DIGEST.pattern)
    review_receipt: str = Field(pattern=_DIGEST.pattern)
    characters: dict[str, str] = Field(default_factory=dict, max_length=100)
    witness: list[dict] = Field(default_factory=list, max_length=100)
    media_manifest: list[dict] = Field(default_factory=list, max_length=256)
    analysis: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def spec_shape(self):
        spec = self.spec
        if not isinstance(spec, dict): raise ValueError('snapshot spec must be an object')
        nodes, variables = spec.get('nodes'), spec.get('variables', [])
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= 100: raise ValueError('snapshot nodes out of range')
        if not isinstance(variables, list) or len(variables) > 16: raise ValueError('snapshot variables out of range')
        if not isinstance(spec.get('entry_node_id'), str) or not isinstance(spec.get('max_steps'), int):
            raise ValueError('snapshot entry/max_steps invalid')
        if spec['max_steps'] < 1 or spec['max_steps'] > 128: raise ValueError('snapshot max_steps out of range')
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get('node_id'), str): raise ValueError('snapshot node invalid')
            if not isinstance(node.get('choices', []), list) or len(node.get('choices', [])) > 8: raise ValueError('snapshot choices out of range')
        for value in self.characters.values():
            if not isinstance(value, str) or len(value) > 2000: raise ValueError('character display name invalid')
        return self


class CompatibilityIssue(Frozen):
    code: str = Field(min_length=1, max_length=120)
    node_id: str | None = Field(default=None, max_length=160)
    choice_id: str | None = Field(default=None, max_length=160)
    character_id: str | None = Field(default=None, max_length=160)
    detail: str = Field(default='', max_length=400)


class TargetCompatibility(Frozen):
    target_id: str = Field(pattern=r'^[A-Z][A-Z0-9_]{2,80}$')
    can_export: bool
    capabilities: dict[str, CapabilitySupport]
    losses: list[str] = Field(default_factory=list, max_length=64)
    issues: list[CompatibilityIssue] = Field(default_factory=list, max_length=256)
    notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode='after')
    def complete_capabilities(self):
        missing = [key for key in CAPABILITY_KEYS if key not in self.capabilities]
        if missing: raise ValueError('capability vocabulary incomplete: ' + ','.join(missing))
        return self


class ExportOptions(Frozen):
    include_witness: bool = True
    story_filename: str = 'story'
    target_options: dict = Field(default_factory=dict)


class FileEntry(Frozen):
    path: str
    bytes: int = Field(ge=0, le=MAX_FILE_BYTES)
    sha256: str = Field(pattern=_DIGEST.pattern)


class ExportBundle(Frozen):
    target_id: str
    target_format_version: str
    adapter_revision: int
    kind: str
    story_id: str
    revision: int
    filename_base: str
    files: dict[str, bytes]
    payload_files_digest: str
    files_digest: str
    manifest: dict
    receipt: dict
    capabilities: dict[str, CapabilitySupport]
    losses: list[str]


# ---------------------------------------------------------------------------
# deterministic helpers
# ---------------------------------------------------------------------------
def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def encode_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')


def files_digest(files: dict[str, bytes]) -> str:
    lines = ''.join(path + '\0' + sha256_bytes(files[path]) + '\n' for path in sorted(files))
    return hashlib.sha256(lines.encode('utf-8')).hexdigest()


def _caps(mapping: dict) -> dict[str, dict]:
    """Build the exact capability vocabulary; omitted features are unsupported."""
    result = {}
    for key in CAPABILITY_KEYS:
        value = mapping.get(key)
        if value is None: result[key] = {'supported': False, 'lossy': False, 'note': ''}
        elif isinstance(value, bool): result[key] = {'supported': value, 'lossy': False, 'note': ''}
        elif isinstance(value, dict):
            result[key] = {'supported': bool(value.get('supported')), 'lossy': bool(value.get('lossy')), 'note': str(value.get('note', ''))[:400]}
        elif isinstance(value, (tuple, list)) and 2 <= len(value) <= 3:
            result[key] = {'supported': bool(value[0]), 'lossy': bool(value[1]), 'note': str(value[2])[:400] if len(value) > 2 else ''}
        else: raise ValueError('invalid capability declaration: ' + key)
    return result


def safe_bundle_path(path: str) -> str:
    """Accept only plain relative POSIX paths inside the delivered project."""
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LENGTH: raise ValueError('BUNDLE_PATH_INVALID')
    if '\\' in path or path.startswith('/') or path != path.strip() or ':' in path: raise ValueError('BUNDLE_PATH_INVALID')
    segments = path.split('/')
    if len(segments) > 12: raise ValueError('BUNDLE_PATH_TOO_DEEP')
    for segment in segments:
        if segment in {'', '.', '..'} or segment.endswith('.') or segment.endswith(' '): raise ValueError('BUNDLE_PATH_INVALID')
        if not _SAFE_SEGMENT.match(segment): raise ValueError('BUNDLE_PATH_INVALID')
        stem = segment.split('.')[0].lower()
        if stem in WINDOWS_RESERVED: raise ValueError('BUNDLE_PATH_RESERVED')
    return path


def normalize_files(raw: dict[str, bytes]) -> dict[str, bytes]:
    if not isinstance(raw, dict): raise ValueError('BUNDLE_FILES_INVALID')
    if not 1 <= len(raw) <= MAX_FILES: raise ValueError('BUNDLE_FILE_COUNT_INVALID')
    files, folded, total = {}, set(), 0
    for path, content in raw.items():
        path = safe_bundle_path(path)
        if isinstance(content, str): raise ValueError('BUNDLE_FILE_CONTENT_MUST_BE_BYTES:' + path)
        if not isinstance(content, (bytes, bytearray)): raise ValueError('BUNDLE_FILE_CONTENT_MUST_BE_BYTES:' + path)
        if len(content) > MAX_FILE_BYTES: raise ValueError('BUNDLE_FILE_TOO_LARGE:' + path)
        if path.lower() in folded: raise ValueError('BUNDLE_PATH_COLLISION:' + path)
        folded.add(path.lower()); total += len(content)
        files[path] = bytes(content)
    if total > MAX_TOTAL_BYTES: raise ValueError('BUNDLE_TOTAL_SIZE_INVALID')
    return files


# ---------------------------------------------------------------------------
# target registry
# ---------------------------------------------------------------------------
LEGACY_TARGETS: dict[str, dict] = {
    'RENPY_8_5_4_TEXT_MENU_SUBSET': {
        'target_id': 'RENPY_8_5_4_TEXT_MENU_SUBSET', 'display_name': "Ren'Py 8.5.4 text/menu fragment (legacy)",
        'kind': 'LEGACY_FRAGMENT', 'format_version': 'legacy-text-menu-1', 'adapter_revision': 1,
        'engine': {'name': "Ren'Py", 'minimum_version': '8.5.4', 'executables': ['renpy', 'renpy.sh', 'renpy.exe'],
                   'version_args': ['--version'], 'env_override': 'POEMSEED_RENPY_BIN', 'gui': True,
                   'note': 'Legacy fragment only; it is not a complete Ren\'Py project.'},
        'capabilities': _caps({'conditions': True, 'bool_variables': True, 'int_variables': True, 'assignment': True,
            'dialogue': True, 'choices': True, 'endings': True, 'loops': (True, True, 'Cycles execute until the explicit step cap.'), 'step_cap': True,
            'save': False, 'restore': False, 'unicode': True, 'media': (False, True, 'Approved asset references are manifest-only; bytes are never embedded or played.')}),
        'losses': ['MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED', 'FRAGMENT_ONLY_NOT_A_PROJECT', 'NO_TARGET_CUSTOM_SCREENS_ANIMATION_OR_PLUGINS', 'TARGET_WHITESPACE_AND_FONT_RENDERING_NOT_VERIFIED'],
        'runtime_requirements': ["Ren'Py 8.5.4 for manual inspection of the generated fragment."],
        'launch_instructions': "Legacy fragment: copy game/story.rpy into a NEW Ren'Py project. Not a runnable deliverable.",
        'integration_notes': ['Old target ID and old fragment output are preserved for compatibility.'],
        'evidence': {'SOURCE_IMPLEMENTED': 'PASS', 'SCHEMA_VALIDATED': 'PASS', 'FIXTURE_TESTED': 'PASS', 'GENERATED_ARTIFACT_VALIDATED': 'PASS'},
    },
    'GODOT_4_DATA_ADAPTER': {
        'target_id': 'GODOT_4_DATA_ADAPTER', 'display_name': 'Godot 4 typed data adapter (legacy)',
        'kind': 'DATA_ONLY_ADAPTER', 'format_version': 'godot-data-1', 'adapter_revision': 1,
        'engine': {'name': 'Godot', 'minimum_version': '4.0', 'executables': ['godot', 'godot.exe', 'Godot_v4.7-stable_win64_console.exe'],
                   'version_args': ['--version'], 'env_override': 'POEMSEED_GODOT_BIN', 'gui': False,
                   'note': 'Data only: the old target is not a plottable project and includes no runtime.'},
        'capabilities': _caps({'conditions': True, 'bool_variables': True, 'int_variables': True, 'assignment': True, 'dialogue': True,
            'choices': True, 'endings': True, 'loops': (True, True, 'Runtime step cap is data; no runtime ships with this adapter.'),
            'step_cap': (True, True, 'Declared as data; consuming integration must enforce it.'), 'save': False, 'restore': False,
            'unicode': True, 'media': (False, True, 'Asset IDs only; no media bytes are packaged.')}),
        'losses': ['DATA_ONLY_TARGET_IMPORTER_REQUIRED', 'NO_SAVE_OR_RESTORE', 'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED'],
        'runtime_requirements': ['Godot 4 integration project that imports the typed JSON and never evaluates expressions dynamically.'],
        'launch_instructions': 'Legacy data adapter: import godot/story.json into a trusted Godot 4 project. Not a runnable deliverable.',
        'integration_notes': ['Old target ID and old godot/story.json output are preserved for compatibility.'],
        'evidence': {'SOURCE_IMPLEMENTED': 'PASS', 'SCHEMA_VALIDATED': 'PASS', 'FIXTURE_TESTED': 'PASS', 'GENERATED_ARTIFACT_VALIDATED': 'PASS'},
    },
    'INKJS_2_3_2_TYPED_TEXT_SUBSET': {
        'target_id': 'INKJS_2_3_2_TYPED_TEXT_SUBSET', 'display_name': 'inkjs 2.3.2 typed text subset (legacy)',
        'kind': 'LEGACY_FRAGMENT', 'format_version': 'ink-typed-subset-1', 'adapter_revision': 1, 'engine': None,
        'capabilities': _caps({'conditions': True, 'bool_variables': True, 'int_variables': True, 'assignment': True,
            'dialogue': (True, True, 'Paragraph whitespace is normalized by the target.'), 'choices': True, 'endings': True,
            'loops': True, 'step_cap': True, 'save': False, 'restore': False,
            'unicode': (True, True, 'Ink string escaping is verified but target font rendering is not.'), 'media': (False, True, 'Media references are not exported.')}),
        'losses': ['INKJS_COMMUNITY_PORT_NOT_NATIVE_CSHARP_RUNTIME', 'INK_MEDIA_REFERENCES_NOT_PLAYED', 'INK_TEXT_PARAGRAPH_WHITESPACE_NORMALIZED',
                   'INK_CHARACTER_NAMES_RENDERED_AS_PLAIN_TEXT', 'INK_CURRENT_ARTIFACT_TARGET_RUNTIME_NOT_RUN'],
        'runtime_requirements': ['pinned inkjs 2.3.2 community JavaScript port; native C# Ink is not claimed.'],
        'launch_instructions': 'Legacy Ink fragment: compile ink/story.ink with the pinned inkjs 2.3.2 compiler in a new project.',
        'integration_notes': ['Old target ID and old ink/story.ink output are preserved for compatibility.'],
        'evidence': {'SOURCE_IMPLEMENTED': 'PASS', 'FIXTURE_TESTED': 'PASS'},
    },
}
LEGACY_ORDER = tuple(LEGACY_TARGETS)


def clear_target_cache() -> None:
    _MODULE_CACHE.clear()


def _module(target_id: str):
    """Resolve an adapter only when it exposes the frozen three-part surface."""
    if target_id in _MODULE_CACHE: return _MODULE_CACHE[target_id]
    name = TARGET_MODULES.get(target_id)
    module = None
    if name is not None:
        try: module = importlib.import_module(name, __package__)
        except ImportError: module = None
        else:
            if not (isinstance(getattr(module, 'DESCRIPTOR', None), dict)
                    and callable(getattr(module, 'compatibility', None))
                    and callable(getattr(module, 'build', None))):
                module = None
    _MODULE_CACHE[target_id] = module
    return module


def available_target_ids() -> list[str]:
    ids = list(LEGACY_ORDER)
    ids += [target_id for target_id in TARGET_MODULES if _module(target_id) is not None]
    return ids


def describe_target(target_id: str) -> TargetDescriptor:
    if target_id in LEGACY_TARGETS:
        return TargetDescriptor.model_validate(LEGACY_TARGETS[target_id])
    module = _module(target_id)
    if module is None: raise ValueError('EXPORT_TARGET_UNAVAILABLE:' + str(target_id))
    raw = getattr(module, 'DESCRIPTOR', None)
    if not isinstance(raw, dict): raise ValueError('EXPORT_TARGET_DESCRIPTOR_INVALID:' + str(target_id))
    data = dict(raw)
    data['capabilities'] = _caps(data.get('capabilities') or {})
    descriptor = TargetDescriptor.model_validate(data)
    if descriptor.target_id != target_id: raise ValueError('EXPORT_TARGET_ID_MISMATCH:' + target_id)
    return descriptor


def all_target_descriptors() -> list[dict]:
    return [describe_target(target_id).model_dump(mode='json') for target_id in available_target_ids()]


def evidence_for(target_id: str) -> dict[str, str]:
    base = {level: 'NOT_RUN' for level in EVIDENCE_LEVELS}
    declared: dict[str, str] = {}
    if target_id in LEGACY_TARGETS:
        declared = dict(LEGACY_TARGETS[target_id].get('evidence') or {})
    else:
        module = _module(target_id)
        raw = getattr(module, 'DESCRIPTOR', None) if module is not None else None
        if isinstance(raw, dict) and isinstance(raw.get('evidence'), dict): declared = dict(raw['evidence'])
    declared.update(EVIDENCE_OVERRIDES.get(target_id) or {})
    for level, status in declared.items():
        if level not in EVIDENCE_LEVELS or status not in EVIDENCE_STATUSES: raise ValueError('EXPORT_EVIDENCE_INVALID:' + str(level))
        base[level] = status
    return base


def evidence_for_level(target_id: str, level: str) -> str:
    return evidence_for(target_id).get(level, 'NOT_RUN')


# ---------------------------------------------------------------------------
# compatibility
# ---------------------------------------------------------------------------
def _compat_from_legacy(target_id: str, snapshot: dict) -> TargetCompatibility:
    legacy = LEGACY_TARGETS[target_id]
    analysis = snapshot.get('analysis') or {}
    issues = []
    can_export = bool(analysis.get('can_review', True))
    if not can_export: issues.append({'code': 'STORY_ANALYSIS_INCOMPLETE', 'detail': 'bounded path analysis must complete before export'})
    if not analysis.get('issues') and not analysis.get('analysis_complete', True):
        can_export = False; issues.append({'code': 'STORY_ANALYSIS_INCOMPLETE'})
    return TargetCompatibility(target_id=target_id, can_export=can_export, capabilities=_caps(legacy['capabilities']),
        losses=list(legacy['losses']), issues=issues, notes=['LEGACY_TARGET_OUTPUT_SHAPE_PRESERVED'])


def compatibility_report(target_id: str, snapshot: dict) -> dict:
    if target_id in LEGACY_TARGETS:
        return _compat_from_legacy(target_id, snapshot).model_dump(mode='json')
    module = _module(target_id)
    if module is None: raise ValueError('EXPORT_TARGET_UNAVAILABLE:' + str(target_id))
    validated = StorySnapshot.model_validate(snapshot)
    raw = module.compatibility(validated.model_dump(mode='json'))
    if not isinstance(raw, dict): raise ValueError('EXPORT_TARGET_COMPATIBILITY_INVALID:' + target_id)
    data = dict(raw); data['target_id'] = target_id
    data['capabilities'] = _caps(data.get('capabilities') or {})
    data.setdefault('losses', list(getattr(module, 'DESCRIPTOR', {}).get('losses') or []))
    # media support must reflect the actual manifest: unsupported media is never
    # silently dropped from the report.
    media = data['capabilities']['media']
    if snapshot.get('media_manifest') and not media['supported']:
        data['losses'] = list(dict.fromkeys([*data['losses'], 'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED']))
    return TargetCompatibility.model_validate(data).model_dump(mode='json')


# ---------------------------------------------------------------------------
# engine probing (product-owned, bounded, no installs, no arbitrary scanning)
# ---------------------------------------------------------------------------
_PROBE_CACHE: dict[str, tuple[float, dict]] = {}
_PROBE_TTL_SECONDS = 30.0


def clear_probe_cache() -> None:
    _PROBE_CACHE.clear()


def _candidate_paths(engine: dict) -> list[str]:
    candidates: list[str] = []
    override = engine.get('env_override')
    if override:
        value = os.environ.get(override)
        if value: candidates.append(value)
    for name in engine.get('executables') or []:
        found = shutil.which(name)
        if found: candidates.append(found)
    for hint in engine.get('search_hints') or []:
        if os.path.isfile(hint): candidates.append(hint)
    ordered = []
    for path in candidates:
        if path not in ordered: ordered.append(path)
    return ordered


def _run_version(path: str, args: list[str], timeout: float = 5.0) -> str | None:
    try:
        completed = subprocess.run([path, *args], capture_output=True, text=True, timeout=timeout, shell=False,
            creationflags=0x08000000 if os.name == 'nt' else 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    output = ((completed.stdout or '') + '\n' + (completed.stderr or '')).strip()
    return output[:400] or None


def _parse_version(text: str | None) -> tuple[int, int, int] | None:
    if not text: return None
    match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', text)
    if not match: return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def _version_at_least(found: tuple[int, int, int], minimum: tuple[int, int, int]) -> bool:
    return found >= minimum


def probe_engine(engine: dict | None, *, refresh: bool = False) -> dict:
    """Report whether the declared target engine is present on this host."""
    if not engine:
        return {'status': 'NOT_REQUIRED', 'detected': False, 'executable': None, 'version': None, 'version_ok': False,
                'detail': 'No external engine is required to generate this target.', 'declared': None}
    engine = EngineRequirement.model_validate(engine).model_dump(mode='json')
    key = json.dumps(engine, sort_keys=True)
    now = time.monotonic()
    cached = _PROBE_CACHE.get(key)
    if cached and not refresh and now - cached[0] < _PROBE_TTL_SECONDS: return dict(cached[1])
    declared = {'name': engine['name'], 'minimum_version': engine['minimum_version'], 'gui': engine['gui']}
    paths = _candidate_paths(engine)
    if not paths:
        result = {'status': 'NOT_INSTALLED', 'detected': False, 'executable': None, 'version': None, 'version_ok': False,
                  'detail': engine['note'] or (engine['name'] + ' was not found on PATH or in the declared install hints.'), 'declared': declared}
    else:
        path = paths[0]; output = _run_version(path, engine['version_args'])
        found = _parse_version(output); minimum = _parse_version(engine['minimum_version']) or (0, 0, 0)
        if output is None:
            result = {'status': 'PROBE_FAILED', 'detected': True, 'executable': path, 'version': None, 'version_ok': False,
                      'detail': 'The executable was found but the bounded version probe did not complete.', 'declared': declared}
        elif found is None:
            result = {'status': 'UNSUPPORTED_VERSION', 'detected': True, 'executable': path, 'version': output[:120], 'version_ok': False,
                      'detail': 'The probed version could not be parsed against the required minimum.', 'declared': declared}
        else:
            result = {'status': 'READY' if _version_at_least(found, minimum) else 'UNSUPPORTED_VERSION', 'detected': True,
                      'executable': path, 'version': '%d.%d.%d' % found, 'version_ok': _version_at_least(found, minimum),
                      'detail': (engine['name'] + ' ' + '%d.%d.%d' % found + ' detected.'), 'declared': declared}
    _PROBE_CACHE[key] = (now, dict(result))
    return result


# ---------------------------------------------------------------------------
# bundle construction and packaging
# ---------------------------------------------------------------------------
def _filename_slug(target_id: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', target_id.lower()).strip('-')[:48] or 'target'


def render_manifest(descriptor: TargetDescriptor, snapshot: StorySnapshot, compatibility: TargetCompatibility,
                    payload: dict[str, bytes], options: ExportOptions, extra: dict | None = None) -> dict:
    return {
        'schema': MANIFEST_SCHEMA,
        'contract_schema': CONTRACT_SCHEMA,
        'contract_version': CONTRACT_VERSION,
        'target_id': descriptor.target_id,
        'target_format_version': descriptor.format_version,
        'target_kind': descriptor.kind,
        'adapter_revision': descriptor.adapter_revision,
        'story': {
            'id': snapshot.story_id, 'revision': snapshot.revision, 'title': snapshot.title,
            'spec_digest': snapshot.spec_digest, 'source_digest': snapshot.source_digest,
            'review_receipt': snapshot.review_receipt,
            'entry_node_id': snapshot.spec.get('entry_node_id'),
            'nodes': len(snapshot.spec.get('nodes') or []),
            'variables': len(snapshot.spec.get('variables') or []),
            'max_steps': snapshot.spec.get('max_steps'),
            'witness_digest': digest(snapshot.witness),
            'media_manifest_digest': digest(snapshot.media_manifest),
        },
        'files': [{'path': path, 'bytes': len(payload[path]), 'sha256': sha256_bytes(payload[path])} for path in sorted(payload)],
        'payload_files_digest': files_digest(payload),
        'capabilities': {key: value.model_dump(mode='json') for key, value in compatibility.capabilities.items()},
        'losses': list(compatibility.losses),
        'runtime': {
            'engine': descriptor.engine.model_dump(mode='json') if descriptor.engine else None,
            'requirements': list(descriptor.runtime_requirements),
            'launch_instructions': descriptor.launch_instructions,
            'evidence': evidence_for(descriptor.target_id),
        },
        'generation': {
            'deterministic': True, 'wall_clock_included': False, 'options': options.model_dump(mode='json'),
            'producer': 'poemseed-studio/b07-export-contract-v1',
        },
        'extra': extra or {},
    }


def render_receipt(descriptor: TargetDescriptor, snapshot: StorySnapshot,
                   payload_digest: str, manifest_bytes: bytes, compatibility: TargetCompatibility) -> dict:
    return {
        'schema': RECEIPT_SCHEMA,
        'contract_schema': CONTRACT_SCHEMA,
        'contract_version': CONTRACT_VERSION,
        'story_id': snapshot.story_id,
        'story_revision': snapshot.revision,
        'spec_digest': snapshot.spec_digest,
        'source_digest': snapshot.source_digest,
        'review_receipt': snapshot.review_receipt,
        'target_id': descriptor.target_id,
        'target_format_version': descriptor.format_version,
        'adapter_revision': descriptor.adapter_revision,
        'payload_files_digest': payload_digest,
        'manifest_sha256': sha256_bytes(manifest_bytes),
        'losses': list(compatibility.losses),
        'capabilities_supported': sorted(key for key, value in compatibility.capabilities.items() if value.supported),
        'capabilities_unsupported': sorted(key for key, value in compatibility.capabilities.items() if not value.supported),
        'export_policy': 'APPROVED_REVISION_ONLY_PURE_CONVERSION_NO_EXTERNAL_WRITE',
        'reproduce': 'Regenerate from the same story revision, spec digest and target adapter revision; this receipt is deterministic.',
    }


def build_export_bundle(target_id: str, snapshot: dict, options: dict | None = None) -> ExportBundle:
    snapshot_model = StorySnapshot.model_validate(snapshot)
    options_model = ExportOptions.model_validate(options or {})
    descriptor = describe_target(target_id)
    compatibility = TargetCompatibility.model_validate(compatibility_report(target_id, snapshot_model.model_dump(mode='json')))
    if not compatibility.can_export: raise ValueError('EXPORT_TARGET_INCOMPATIBLE:' + target_id)
    module = _module(target_id)
    if module is None: raise ValueError('EXPORT_TARGET_UNAVAILABLE:' + target_id)
    raw = module.build(snapshot_model.model_dump(mode='json'), options_model.model_dump(mode='json'))
    if not isinstance(raw, dict) or not isinstance(raw.get('files'), dict):
        raise ValueError('EXPORT_TARGET_BUILD_INVALID:' + target_id)
    payload = normalize_files(raw['files'])
    for injected in ('manifest.json', 'source-receipt.json'):
        if injected in payload: raise ValueError('BUNDLE_INJECTED_NAME_RESERVED:' + injected)
    manifest = render_manifest(descriptor, snapshot_model, compatibility, payload, options_model, raw.get('manifest_extra') if isinstance(raw.get('manifest_extra'), dict) else None)
    manifest_bytes = encode_json(manifest)
    receipt = render_receipt(descriptor, snapshot_model, files_digest(payload), manifest_bytes, compatibility)
    receipt_bytes = encode_json(receipt)
    files = dict(payload); files['manifest.json'] = manifest_bytes; files['source-receipt.json'] = receipt_bytes
    bundle = ExportBundle(target_id=target_id, target_format_version=descriptor.format_version,
        adapter_revision=descriptor.adapter_revision, kind=descriptor.kind, story_id=snapshot_model.story_id,
        revision=snapshot_model.revision, filename_base=_filename_slug(target_id) + '-' + snapshot_model.story_id + '-v' + str(snapshot_model.revision),
        files=files, payload_files_digest=files_digest(payload), files_digest=files_digest(files), manifest=manifest,
        receipt=receipt, capabilities=compatibility.capabilities, losses=list(compatibility.losses))
    verify_bundle(bundle)
    return bundle


def verify_bundle(bundle: ExportBundle) -> None:
    """Fail closed unless every file and both injected records recompute exactly."""
    files = normalize_files(bundle.files)
    if 'manifest.json' not in files or 'source-receipt.json' not in files: raise ValueError('BUNDLE_RECORDS_MISSING')
    manifest = json.loads(files['manifest.json']); receipt = json.loads(files['source-receipt.json'])
    if manifest.get('schema') != MANIFEST_SCHEMA or receipt.get('schema') != RECEIPT_SCHEMA: raise ValueError('BUNDLE_RECORD_SCHEMA_INVALID')
    payload = {path: content for path, content in files.items() if path not in {'manifest.json', 'source-receipt.json'}}
    if manifest.get('payload_files_digest') != files_digest(payload): raise ValueError('BUNDLE_PAYLOAD_DIGEST_INVALID')
    entries = manifest.get('files') or []
    if [entry.get('path') for entry in entries] != sorted(payload): raise ValueError('BUNDLE_MANIFEST_FILES_INVALID')
    for entry in entries:
        content = payload[entry['path']]
        if entry.get('bytes') != len(content) or entry.get('sha256') != sha256_bytes(content): raise ValueError('BUNDLE_FILE_HASH_INVALID:' + entry['path'])
    if receipt.get('manifest_sha256') != sha256_bytes(files['manifest.json']): raise ValueError('BUNDLE_RECEIPT_MANIFEST_HASH_INVALID')
    if receipt.get('payload_files_digest') != manifest.get('payload_files_digest'): raise ValueError('BUNDLE_RECEIPT_PAYLOAD_INVALID')
    if receipt.get('target_id') != bundle.target_id or manifest.get('target_id') != bundle.target_id: raise ValueError('BUNDLE_TARGET_MISMATCH')
    story = manifest.get('story') or {}
    if receipt.get('story_id') != bundle.story_id or receipt.get('story_revision') != bundle.revision: raise ValueError('BUNDLE_RECEIPT_STORY_INVALID')
    if story.get('id') != bundle.story_id or story.get('revision') != bundle.revision: raise ValueError('BUNDLE_MANIFEST_STORY_INVALID')
    if receipt.get('spec_digest') != story.get('spec_digest') or receipt.get('source_digest') != story.get('source_digest'):
        raise ValueError('BUNDLE_RECEIPT_DIGEST_INVALID')
    if bundle.payload_files_digest != manifest.get('payload_files_digest') or bundle.files_digest != files_digest(files):
        raise ValueError('BUNDLE_FILES_DIGEST_INVALID')


def package_export_zip(bundle: ExportBundle) -> dict:
    """Deterministic ZIP container: fixed timestamps, sorted entries, one root folder."""
    verify_bundle(bundle)
    prefix = 'interactive-' + _filename_slug(bundle.target_id) + '-' + bundle.story_id + '/'
    buffer = __import__('io').BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle.files):
            info = zipfile.ZipInfo(prefix + path, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, bundle.files[path])
    content = buffer.getvalue()
    return {'content': content, 'sha256': sha256_bytes(content), 'filename': bundle.filename_base + '.zip',
            'prefix': prefix, 'file_count': len(bundle.files), 'files_digest': bundle.files_digest}


def read_zip_safely(content: bytes, expected_prefix: str) -> dict[str, bytes]:
    """Read back a delivered ZIP with the same path rules used to create it."""
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(__import__('io').BytesIO(content)) as archive:
        if len(archive.namelist()) > MAX_FILES + 8: raise ValueError('BUNDLE_ZIP_TOO_MANY_ENTRIES')
        total = 0
        for info in archive.infolist():
            if info.is_dir(): continue
            name = info.filename
            if not name.startswith(expected_prefix): raise ValueError('BUNDLE_ZIP_PREFIX_INVALID')
            relative = name[len(expected_prefix):]
            safe_bundle_path(relative)
            data = archive.read(info); total += len(data)
            if total > MAX_TOTAL_BYTES: raise ValueError('BUNDLE_ZIP_TOO_LARGE')
            if relative in files: raise ValueError('BUNDLE_ZIP_DUPLICATE_ENTRY')
            files[relative] = data
    return files


def contract_document() -> dict:
    return {
        'schema': CONTRACT_SCHEMA,
        'version': CONTRACT_VERSION,
        'capabilities': list(CAPABILITY_KEYS),
        'evidence_levels': list(EVIDENCE_LEVELS),
        'evidence_statuses': list(EVIDENCE_STATUSES),
        'target_kinds': list(TARGET_KINDS),
        'records': {'manifest': MANIFEST_SCHEMA, 'receipt': RECEIPT_SCHEMA, 'targets': TARGETS_SCHEMA},
        'limits': {'files': MAX_FILES, 'file_bytes': MAX_FILE_BYTES, 'total_bytes': MAX_TOTAL_BYTES, 'path_length': MAX_PATH_LENGTH},
        'adapter_contract': {
            'module_exports': ['DESCRIPTOR', 'compatibility(snapshot)', 'build(snapshot, options)'],
            'snapshot_is_only_story_authority': True,
            'pure_conversion': True,
            'may_read_arbitrary_files': False, 'may_write_external_paths': False,
            'may_install_or_launch_engine': False, 'may_execute_story_or_user_code': False,
            'may_fetch_remote_urls': False, 'may_bypass_review_or_authority': False,
            'unsupported_features_must_be_reported': True,
        },
    }
