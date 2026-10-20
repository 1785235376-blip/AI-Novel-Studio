"""Pinned inkjs 2.3.2 runtime facts for the current-artifact Ink target.

The runtime is deliberately NOT bundled: the delivered bundle carries this pin
plus extraction/compile/run instructions, so the product gains no npm dependency
and the lockfile stays untouched. The acceptance verifier
(scripts/verify_ink_current_artifact.mjs) asserts the installed package version
and runtime entry hash against these values before it uses them.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PACKAGE = 'inkjs'
PINNED_VERSION = '2.3.2'
REGISTRY = 'https://registry.npmjs.org/inkjs/-/inkjs-2.3.2.tgz'
INTEGRITY = 'sha512-iZjrY0lLeRiC+HtDzCfV9IEAP9ExCmBZUrxKkyLy1qIbbGbR1uTXNZ8LDIg8oVkMXZ9TeKKyEFQpQ/m5nQds8w=='
RUNTIME_ENTRY = 'dist/ink-full.js'
# Verified against the registry tarball for 2.3.2; the verifier fails closed on
# any other runtime entry so a substituted package cannot silently pass.
RUNTIME_ENTRY_SHA256 = '4a76187c713c889b5e71d9380b37b5b42eaba9d24af099bb9f968d02311cfeef'
NODE_MINIMUM = '18.0'
IMPLEMENTATION = 'COMMUNITY_JAVASCRIPT_PORT_NOT_NATIVE_CSHARP'
RUNTIME_BASIS = 'INKJS_2_3_2_JAVASCRIPT_PORT'
STATUS_CODES = {'PLAYING': 0, 'ENDING': 1, 'STEP_CAP_REACHED': 2, 'NO_EXIT': 3}
STATUS_NAMES = {code: name for name, code in STATUS_CODES.items()}
EVENT_SAVE = 'story.state.ToJson()'
EVENT_RESTORE = 'new Story(compiledJson); story.state.LoadJson(savedState)'

# Delivered, dependency-free player helper: the save envelope is bound to the
# exact story revision, compiled-artifact digest, target format and runtime.
PLAYER_DIRECTORY = Path(__file__).with_name('player')
SAVE_ENVELOPE_PATH = 'ink/player/save_envelope.mjs'
SAVE_ENVELOPE_SCHEMA_PATH = 'ink/player/save-envelope.schema.json'
SAVE_ENVELOPE_SCHEMA = 'poemseed-ink-save-envelope/1'
SAVE_ENVELOPE_FORMAT_VERSION = 'ink-save-envelope-1'
SAVE_ENVELOPE_BINDING_FIELDS = ('story_id', 'revision', 'compiled_artifact_sha256', 'target_format_version', 'runtime')
SAVE_ENVELOPE_RESTORE_CONTEXT_FIELDS = ('storyId', 'revision', 'compiledArtifactSha256', 'targetFormatVersion', 'runtime')
SAVE_ENVELOPE_CONTEXT_ERRORS = ('SAVE_ENVELOPE_CONTEXT_REQUIRED', 'SAVE_ENVELOPE_CONTEXT_INVALID')
SAVE_ENVELOPE_LEGACY_POLICY = 'UNBOUND_LEGACY_SAVE_REJECTED_EXPLICIT_MIGRATION_REQUIRED'
SAVE_ENVELOPE_MAX_BYTES = 2 * 1024 * 1024


def player_asset_bytes(name):
    """Read one repo-maintained player asset (never an arbitrary disk path)."""
    if name not in {'save_envelope.mjs', 'save-envelope.schema.json'}:
        raise ValueError('INK_PLAYER_ASSET_UNKNOWN')
    return (PLAYER_DIRECTORY / name).read_bytes()


def save_envelope_module_sha256():
    return hashlib.sha256(player_asset_bytes('save_envelope.mjs')).hexdigest()


def save_envelope_schema_sha256():
    return hashlib.sha256(player_asset_bytes('save-envelope.schema.json')).hexdigest()


def save_envelope_document():
    return {
        'schema': SAVE_ENVELOPE_SCHEMA,
        'format_version': SAVE_ENVELOPE_FORMAT_VERSION,
        'player_module': {'path': SAVE_ENVELOPE_PATH, 'sha256': save_envelope_module_sha256()},
        'json_schema': {'path': SAVE_ENVELOPE_SCHEMA_PATH, 'sha256': save_envelope_schema_sha256()},
        'binding_fields': list(SAVE_ENVELOPE_BINDING_FIELDS),
        'integrity': 'sha256(canonical-json(schema,binding,save))',
        'max_bytes': SAVE_ENVELOPE_MAX_BYTES,
        'legacy_policy': SAVE_ENVELOPE_LEGACY_POLICY,
        'restore_context': {
            'required': True,
            'fields': list(SAVE_ENVELOPE_RESTORE_CONTEXT_FIELDS),
            'errors': list(SAVE_ENVELOPE_CONTEXT_ERRORS),
            'policy': 'CALLER_MUST_DERIVE_FROM_CURRENT_LOADED_ARTIFACT_AND_RUNTIME_NEVER_FROM_SAVE',
        },
        'restore_rules': [
            'Restore requires the complete current-artifact context: storyId, revision, compiledArtifactSha256, targetFormatVersion and runtime name/version/format, derived from the currently loaded artifact and runtime.',
            'A missing, empty, partial or malformed restore context is rejected with SAVE_ENVELOPE_CONTEXT_REQUIRED or SAVE_ENVELOPE_CONTEXT_INVALID before story.state.LoadJson() is called; the save is never allowed to fill in its own expected identity.',
            'Reject before restore when the envelope schema, integrity digest, story id, revision, compiled-artifact digest, target format or runtime identity does not match the supplied current-artifact context.',
            'Reject unbound legacy state with LEGACY_SAVE_ENVELOPE_REQUIRED; explicit migration (migrateLegacySaveEnvelope) labels the result as migrated, never as verified execution.',
            'Reject a state that does not restore to the recorded typed variable snapshot.',
        ],
    }


def build_commands():
    """Exact commands a target environment runs; no lifecycle scripts execute."""
    return {
        'install': ['npm install inkjs@2.3.2'],
        'compile_and_verify': 'node scripts/verify_ink_current_artifact.mjs --bundle <exported-zip-or-extracted-bundle> --vendor <project>/node_modules/inkjs --report acceptance-report.json',
        'independent_play': 'Consume acceptance/witness.json with the pinned runtime: match currentChoices labels to states[i].choices, choose the recorded index, assert ink_state/variables/output_lines per step.',
        'save': 'import { createSaveEnvelope } from "./ink/player/save_envelope.mjs"; write the returned bytes as a new file (the envelope binds story_id, revision, compiled_artifact_sha256, target_format_version and runtime).',
        'restore': 'import { loadSaveEnvelope } from "./ink/player/save_envelope.mjs"; call loadSaveEnvelope({ bytes, story, expected }) in a fresh process where expected is derived from the CURRENT loaded artifact/runtime and contains storyId, revision, compiledArtifactSha256, targetFormatVersion and runtime {name,version,format}. Missing/incomplete context throws SAVE_ENVELOPE_CONTEXT_REQUIRED or SAVE_ENVELOPE_CONTEXT_INVALID before state restore; mismatched story/revision/artifact/format/runtime or a tampered envelope is rejected with a readable code; unbound legacy saves are rejected with LEGACY_SAVE_ENVELOPE_REQUIRED.',
    }


def runtime_pin_document():
    """The machine-readable pin shipped as ink/runtime-pin.json."""
    return {
        'schema': 'poemseed-ink-runtime-pin/1',
        'package': PACKAGE,
        'version': PINNED_VERSION,
        'registry': REGISTRY,
        'integrity': INTEGRITY,
        'implementation': IMPLEMENTATION,
        'runtime_basis': RUNTIME_BASIS,
        'native_csharp_runtime': 'NOT_CLAIMED_NOT_RUN',
        'runtime_bundled': False,
        'product_runtime_dependency': False,
        'node': {'minimum_version': NODE_MINIMUM},
        'runtime_entry': {'path': RUNTIME_ENTRY, 'sha256': RUNTIME_ENTRY_SHA256},
        'commands': build_commands(),
        'module_entries': {
            'cjs': 'require("inkjs/full") exposes {Compiler, Story}; require("inkjs") exposes runtime Story only',
            'esm': 'import {Compiler, Story} from "inkjs/full"',
            'dist_file': 'node_modules/inkjs/dist/ink-full.js (CJS) / dist/ink-full.mjs (ESM)',
        },
        'compile': {
            'compiler_entry': 'new (require("inkjs/full").Compiler)(source, {errorHandler, fileHandler}).Compile()',
            'errors': 'read compiler.errors and fail closed; never compile silently',
            'artifact': 'story.ToJson()',
            'artifact': 'story.ToJson()',
            'source_file': 'ink/story.ink',
            'file_access': 'DENY_ALL; ResolveInkFilename and LoadInkFileContents throw, so INCLUDE/external files cannot load',
        },
        'run': {
            'runtime_entry': 'new (require("inkjs/full").Story)(compiledArtifactJson)',
            'advance': 'while (story.canContinue) { story.Continue(); }',
            'choices': 'story.currentChoices maps to {text, index}',
            'choose': 'story.ChooseChoiceIndex(index)',
            'variables': 'story.variablesState.$(name)',
        },
        'save_restore': {
            'player_helper': SAVE_ENVELOPE_PATH,
            'player_helper_sha256': save_envelope_module_sha256(),
            'envelope': save_envelope_document(),
            'raw_state_primitive': {'save': EVENT_SAVE, 'restore': EVENT_RESTORE},
            'process_boundary': 'state JSON is portable across fresh processes only inside a bound save envelope',
        },
        'acceptance': {
            'witness': 'acceptance/witness.json',
            'save_envelope_schema': SAVE_ENVELOPE_SCHEMA_PATH,
            'verifier': 'scripts/verify_ink_current_artifact.mjs',
            'selection': 'For each witness state assert runtime currentChoices labels equal states[i].choices labels in order, then choose the choice whose id matches choices[i].',
        },
        'security': [
            'Only the frozen typed Ink subset is generated; no INCLUDE, external function, user code, remote import or dynamic path can be emitted.',
            'Cycles are bounded by the generated ans_steps step-cap branch; the runtime never runs unbounded story logic.',
            'The verifier denies Ink file access and counts attempted file calls; a non-zero count fails acceptance.',
        ],
        'notes': [
            'The community JavaScript port is verified; the native C# Ink runtime is NOT_RUN and not claimed.',
            'Presentation uses plain text; whitespace and font rendering are target-side concerns recorded as losses.',
        ],
    }


def evidence_record():
    """Evidence declared by the frozen descriptor for this adapter revision."""
    from .descriptor import EVIDENCE
    return dict(EVIDENCE)
