"""B07 target adapter: RENPY_8_5_4_PROJECT_V1 complete Ren'Py 8.5.4 project.

Frozen contract surface (see docs/v2/B07_DIF10_E2E07_EXPORT_TARGET_CONTRACT_20261020.md
and app/experimental/interactive_export_contract.py):

    DESCRIPTOR                  - plain dict validated by TargetDescriptor
    compatibility(snapshot)     - can_export + capability/loss/issue report
    build(snapshot, options)    - in-memory project files + manifest_extra

The adapter is a restricted pure conversion of the authorized, approved story
snapshot. It reuses the product story authority (StorySpec, analyze, play and
the Ren'Py escaping helpers) through app/experimental/interactive_targets/renpy;
it opens no files, writes nothing outside the returned dictionary, never installs
or launches an engine, never executes story or target code, embeds no media bytes
and never bundles the Ren'Py engine. Generation is not runtime acceptance: the
evidence levels below record only what this development host actually achieved.
"""
from __future__ import annotations

import copy

from .interactive_export_contract import CAPABILITY_KEYS
from .interactive_story import StorySpec, analyze, text_safe
from .interactive_targets.renpy import project as renpy_project
from .interactive_targets.renpy import witness as renpy_witness

TARGET_ID = renpy_project.TARGET_ID
FORMAT_VERSION = renpy_project.FORMAT_VERSION
ADAPTER_REVISION = renpy_project.ADAPTER_REVISION

# Evidence is independent and never auto-upgraded. TARGET_RUNTIME_EXECUTED and
# SAVE_RESTORE_VERIFIED stay BLOCKED_ENVIRONMENT because Ren'Py is not installed
# on this generation host; generating a project is never reported as running it.
EVIDENCE = {
    'SOURCE_IMPLEMENTED': 'PASS',
    'SCHEMA_VALIDATED': 'PASS',
    'FIXTURE_TESTED': 'NOT_RUN',
    'GENERATED_ARTIFACT_VALIDATED': 'NOT_RUN',
    'TARGET_RUNTIME_EXECUTED': 'BLOCKED_ENVIRONMENT',
    'SAVE_RESTORE_VERIFIED': 'BLOCKED_ENVIRONMENT',
}

LOSSES = [
    'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED',
    'NO_ENGINE_ADDONS_OR_MEDIA_BYTES_BUNDLED',
    'TARGET_FONT_AND_WHITESPACE_RENDERING_NOT_VERIFIED',
    'SAVE_RESTORE_CROSS_REEXPORT_COMPATIBILITY_NOT_GUARANTEED',
    'TARGET_RUNTIME_NOT_EXECUTED_ON_THE_GENERATION_HOST',
    'NO_TARGET_CUSTOM_SCREENS_ANIMATION_OR_PLUGINS',
]

RUNTIME_REQUIREMENTS = [
    'Ren\'Py 8.5.4 or newer installed separately by the reader; the engine, launcher and addons are never bundled.',
    'Read README.txt and open the extracted project folder with the Ren\'Py 8.5.4 launcher.',
    'No media bytes are packaged; approved media asset references stay manifest-only and are not played.',
]

LAUNCH_INSTRUCTIONS = (
    'Extract the downloaded ZIP into a NEW EMPTY directory; it contains one top-level project folder with game/ inside. '
    'Do not extract over or merge into an existing Ren\'Py project and do not copy engine files into it. '
    'Start the installed Ren\'Py 8.5.4 launcher (renpy.exe on Windows, renpy.sh on Linux/macOS), open Preferences, '
    'set "Projects Directory" to the parent directory of the extracted project folder, return to the launcher, '
    'select the project and choose "Launch Project". Command-line alternative: renpy.exe <project folder> or '
    './renpy.sh <project folder>. The project runs with the installed engine; no engine is included in the export.'
)

INTEGRATION_NOTES = [
    'The generated output is a complete minimal Ren\'Py project skeleton: game/script.rpy, game/options.rpy and game/screens.rpy. No Ren\'Py engine template file is copied.',
    'Every user string is emitted through the story authority renpy_text escape as one literal; no python blocks, imports, eval/exec or file access are generated.',
    'acceptance/witness.json stores one bounded play() witness per discovered ending with per-step expected state for target-environment acceptance.',
    'manifest.json and source-receipt.json are added by the contract; this adapter never emits those names.',
    'Runtime evidence levels are independent: generation, artifact validation and target-runtime execution are never conflated.',
]


def _capabilities(media_count=0):
    """Exact frozen capability vocabulary for the runnable Ren'Py project target."""
    if media_count:
        media_note = (str(media_count) + ' approved asset reference(s) are recorded in the manifest and README only; '
                      'no media bytes are packaged or played by the generated project.')
    else:
        media_note = 'The approved story references no media assets; in all cases no media bytes are packaged or played.'
    return {
        'conditions': {'supported': True, 'lossy': False,
                       'note': 'Approved bounded bool/int and/or/not comparisons become Ren\'Py if conditions and conditional menu items.'},
        'bool_variables': {'supported': True, 'lossy': False, 'note': 'Bounded boolean variables become default bool variables assigned by inline Ren\'Py assignments.'},
        'int_variables': {'supported': True, 'lossy': False, 'note': 'Bounded integer variables become default integer variables with the approved bounds preserved.'},
        'assignment': {'supported': True, 'lossy': False, 'note': 'Choice assignments are emitted as one typed inline assignment per approved target variable.'},
        'dialogue': {'supported': True, 'lossy': True, 'note': 'Dialogue and speaker names use the authority escape; target font, line wrapping and whitespace rendering are not verified.'},
        'choices': {'supported': True, 'lossy': False, 'note': 'Every menu item is gated by its approved typed condition; a disabled choice cannot be selected.'},
        'endings': {'supported': True, 'lossy': False, 'note': 'Ending nodes display the approved ending text and return to the Ren\'Py main menu.'},
        'loops': {'supported': True, 'lossy': True, 'note': 'Cycles are projected as labels and jumps and execute until the approved step cap; bounded analysis is not an unbounded proof.'},
        'step_cap': {'supported': True, 'lossy': False, 'note': 'The generated script checks ans_steps against the approved max_steps before every menu and returns instead of exceeding it.'},
        'save': {'supported': True, 'lossy': True, 'note': 'Ren\'Py native save stores variables and the current label; save compatibility across re-exported story revisions is not guaranteed.'},
        'restore': {'supported': True, 'lossy': True, 'note': 'Ren\'Py native load restores variables and the current label; SAVE_RESTORE_VERIFIED is BLOCKED_ENVIRONMENT on this host.'},
        'unicode': {'supported': True, 'lossy': True, 'note': 'UTF-8 text with Chinese, quotes, newlines and interpolation/markup punctuation is escaped; target font and bidi rendering are not verified.'},
        'media': {'supported': False, 'lossy': True, 'note': media_note},
    }


DESCRIPTOR = {
    'target_id': TARGET_ID,
    'display_name': 'Ren\'Py 8.5.4 complete runnable project',
    'kind': 'RUNNABLE_PROJECT',
    'format_version': FORMAT_VERSION,
    'adapter_revision': ADAPTER_REVISION,
    'engine': {
        'name': 'Ren\'Py',
        'minimum_version': renpy_project.RENPY_MINIMUM_VERSION,
        'executables': ['renpy.exe', 'renpy', 'renpy.sh', 'renpy.py'],
        'version_args': ['--version'],
        'env_override': 'POEMSEED_RENPY_BIN',
        'search_hints': [
            'D:/RenPy/renpy-8.5.4-sdk/renpy.exe',
            'D:/GameDev/RenPy/renpy-8.5.4-sdk/renpy.exe',
            'C:/RenPy/renpy-8.5.4-sdk/renpy.exe',
        ],
        'gui': True,
        'note': 'The installed Ren\'Py 8.5.4 SDK launcher is required to run the project and is never bundled. '
                'Version probing uses the launcher command line; if the installed launcher does not answer --version the probe reports PROBE_FAILED, never a guessed version.',
    },
    'capabilities': _capabilities(0),
    'losses': list(LOSSES),
    'runtime_requirements': list(RUNTIME_REQUIREMENTS),
    'launch_instructions': LAUNCH_INSTRUCTIONS,
    'integration_notes': list(INTEGRATION_NOTES),
    'evidence': dict(EVIDENCE),
}


def _bounded_text(value, limit):
    if not isinstance(value, str):
        return None
    return value[:limit]


def _meta(snapshot):
    title = snapshot.get('title')
    if not isinstance(title, str) or not title:
        raise ValueError('RENPY_SNAPSHOT_TITLE_INVALID')
    text_safe(title)
    revision = snapshot.get('revision')
    if type(revision) is not int or revision < 1:
        raise ValueError('RENPY_SNAPSHOT_REVISION_INVALID')
    return {
        'story_id': _bounded_text(snapshot.get('story_id'), 80) or 'story',
        'revision': revision,
        'title': title,
        'spec_digest': _bounded_text(snapshot.get('spec_digest'), 64) or '',
        'source_digest': _bounded_text(snapshot.get('source_digest'), 64) or '',
        'review_receipt': _bounded_text(snapshot.get('review_receipt'), 64) or '',
    }


def _media_references(snapshot):
    references = []
    media = snapshot.get('media_manifest') or []
    if not isinstance(media, list):
        raise ValueError('RENPY_SNAPSHOT_MEDIA_INVALID')
    for item in media:
        if not isinstance(item, dict):
            continue
        references.append({
            'asset_id': str(item.get('asset_id')),
            'kind': str(item.get('kind')),
            'version': item.get('version'),
            'missing': bool(item.get('missing')),
            'packaged': False,
        })
    return references


def _speaker_issues(spec, characters):
    issues = []
    for node in spec['nodes']:
        character_id = node.get('character_id')
        if not character_id:
            continue
        name = characters.get(character_id) if isinstance(characters, dict) else None
        if not isinstance(name, str) or not name:
            issues.append({'code': 'RENPY_SPEAKER_UNAVAILABLE', 'node_id': node['node_id'],
                           'character_id': str(character_id)[:160],
                           'detail': 'approved character display name is unavailable for this node'})
    return issues


def compatibility(snapshot):
    """Report whether the approved snapshot converts to a runnable Ren'Py project."""
    spec = StorySpec.model_validate(snapshot['spec']).model_dump()
    analysis = analyze(spec)
    issues = []
    for issue in (analysis.get('issues') or [])[:200]:
        code = issue.get('code') if isinstance(issue, dict) else None
        issues.append({
            'code': str(code or 'STORY_ANALYSIS_ISSUE')[:120],
            'node_id': _bounded_text(issue.get('node_id') if isinstance(issue, dict) else None, 160),
            'choice_id': _bounded_text(issue.get('choice_id') if isinstance(issue, dict) else None, 160),
            'detail': '',
        })
    if analysis.get('step_limit_reached'):
        issues.append({'code': 'STORY_ANALYSIS_STEP_LIMIT',
                       'detail': 'bounded analysis reached the approved step cap before every ending path was proven'})
    if analysis.get('state_limit_reached'):
        issues.append({'code': 'STORY_ANALYSIS_STATE_LIMIT',
                       'detail': 'bounded analysis reached its state budget; analysis is incomplete'})
    if not analysis.get('analysis_complete', False) and not issues:
        issues.append({'code': 'STORY_ANALYSIS_INCOMPLETE',
                       'detail': 'bounded analysis did not complete'})
    characters = snapshot.get('characters') or {}
    issues.extend(_speaker_issues(spec, characters))
    media = snapshot.get('media_manifest') or []
    media_count = len(media) if isinstance(media, list) else 0
    can_export = bool(analysis.get('can_review')) and not issues
    return {
        'can_export': can_export,
        'capabilities': _capabilities(media_count),
        'losses': list(LOSSES),
        'issues': issues[:256],
        'notes': [
            'GENERATION_IS_NOT_RUNTIME_ACCEPTANCE',
            'ENGINE_IS_NEVER_BUNDLED',
            'ONE_WITNESS_PER_DISCOVERED_ENDING_NOT_ALL_PATHS',
            'MEDIA_REFERENCES_ARE_MANIFEST_ONLY',
        ],
    }


def build(snapshot, options):
    """Convert the approved snapshot into the complete in-memory Ren'Py project."""
    spec = StorySpec.model_validate(snapshot['spec']).model_dump()
    analysis = analyze(spec)
    if not analysis.get('can_review'):
        raise ValueError('RENPY_STORY_NOT_APPROVABLE')
    options = options if isinstance(options, dict) else {}
    story_filename = options.get('story_filename') or 'story'
    if not isinstance(story_filename, str) or not renpy_project.STORY_FILENAME.match(story_filename):
        raise ValueError('RENPY_STORY_FILENAME_INVALID')
    # Ren'Py's canonical start file is game/script.rpy, while ExportOptions.story_filename
    # defaults to the target-neutral base name 'story'. Map that generic default to the
    # Ren'Py convention and honor any explicitly requested other base name.
    script_name = 'script' if story_filename == 'story' else story_filename
    target_options = options.get('target_options') or {}
    if not isinstance(target_options, dict):
        raise ValueError('RENPY_TARGET_OPTIONS_INVALID')
    if target_options:
        raise ValueError('RENPY_TARGET_OPTIONS_UNSUPPORTED:' + ','.join(sorted(str(key) for key in target_options)[:8]))
    include_witness = bool(options.get('include_witness', True))
    characters = snapshot.get('characters') or {}
    if not isinstance(characters, dict):
        raise ValueError('RENPY_SNAPSHOT_CHARACTERS_INVALID')
    speaker_issues = _speaker_issues(spec, characters)
    if speaker_issues:
        raise ValueError('RENPY_SPEAKER_UNAVAILABLE:' + speaker_issues[0]['node_id'])
    meta = _meta(snapshot)
    projection = renpy_project.projection(spec)
    script_path = 'game/' + script_name + '.rpy'
    media_references = _media_references(snapshot)
    files = {
        script_path: renpy_project.render_script(projection, characters, meta, include_witness=include_witness).encode('utf-8'),
        renpy_project.OPTIONS_PATH: renpy_project.render_options(projection, meta).encode('utf-8'),
        renpy_project.SCREENS_PATH: bytes(renpy_project.SCREENS_RPY),
        renpy_project.README_PATH: renpy_project.render_readme(
            projection, meta, script_path=script_path, include_witness=include_witness,
            media_references=media_references, runtime_evidence=EVIDENCE).encode('utf-8'),
    }
    witness_summary = {'witness_count': 0, 'state_count': 0, 'truncated': False}
    if include_witness:
        acceptance = renpy_witness.build_acceptance_witness(
            projection, analysis, meta, media_references, EVIDENCE, script_path)
        files[renpy_project.WITNESS_PATH] = renpy_project.encode_json(acceptance)
        witness_summary = {
            'witness_count': acceptance['witness_count'],
            'state_count': acceptance['state_count'],
            'truncated': acceptance['truncated'],
        }
    manifest_extra = {'renpy_project': {
        'schema': renpy_project.PROJECT_SCHEMA,
        'target_format_version': FORMAT_VERSION,
        'adapter_revision': ADAPTER_REVISION,
        'engine_bundled': False,
        'engine_minimum_version': renpy_project.RENPY_MINIMUM_VERSION,
        'script_path': script_path,
        'options_path': renpy_project.OPTIONS_PATH,
        'screens_path': renpy_project.SCREENS_PATH,
        'witness_path': renpy_project.WITNESS_PATH if include_witness else None,
        'witness_count': witness_summary['witness_count'],
        'witness_state_count': witness_summary['state_count'],
        'witness_truncated': witness_summary['truncated'],
        'media_bytes_packaged': False,
        'runtime_evidence': dict(EVIDENCE),
    }}
    return {'files': files, 'manifest_extra': manifest_extra}
