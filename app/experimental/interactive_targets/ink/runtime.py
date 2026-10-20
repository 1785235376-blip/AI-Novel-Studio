"""Pinned inkjs 2.3.2 runtime facts for the current-artifact Ink target.

The runtime is deliberately NOT bundled: the delivered bundle carries this pin
plus extraction/compile/run instructions, so the product gains no npm dependency
and the lockfile stays untouched. The acceptance verifier
(scripts/verify_ink_current_artifact.mjs) asserts the installed package version
and runtime entry hash against these values before it uses them.
"""
from __future__ import annotations

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


def build_commands():
    """Exact commands a target environment runs; no lifecycle scripts execute."""
    return {
        'install': ['npm install inkjs@2.3.2'],
        'compile_and_verify': 'node scripts/verify_ink_current_artifact.mjs --bundle <extracted-bundle> --vendor <project>/node_modules/inkjs --report acceptance-report.json',
        'independent_play': 'Consume acceptance/witness.json with the pinned runtime: match currentChoices labels to states[i].choices, choose the recorded index, assert ink_state/variables/output_lines per step, then save with state.ToJson() and restore with state.LoadJson() in a fresh process.',
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
        'save_restore': {'save': EVENT_SAVE, 'restore': EVENT_RESTORE, 'process_boundary': 'state JSON is portable across fresh processes'},
        'acceptance': {
            'witness': 'acceptance/witness.json',
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
