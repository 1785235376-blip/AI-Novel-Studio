"""Frozen target descriptor for INK_2_3_2_CURRENT_ARTIFACT_V1.

The contract validates this plain dict through TargetDescriptor; evidence is
declared per independent level and is only promoted after the matching check was
really executed. Generation success never promotes a runtime level.
"""
from __future__ import annotations

from .runtime import INTEGRITY, PINNED_VERSION, REGISTRY

TARGET_ID = 'INK_2_3_2_CURRENT_ARTIFACT_V1'
FORMAT_VERSION = 'ink-current-artifact-1'
ADAPTER_REVISION = 1
DISPLAY_NAME = 'Ink 2.3.2 current-artifact delivery (pinned inkjs)'

CAPABILITIES = {
    'conditions': (True, False, 'Bounded bool/int comparisons, and/or/not; rendered as Ink conditions and asserted per step.'),
    'bool_variables': (True, False, 'Boolean variables map to Ink boolean VARs and runtime values are type-checked.'),
    'int_variables': (True, False, 'Int variables are bounded to +/-10000 and stay exact in Ink integers and JS numbers.'),
    'assignment': (True, False, 'Constant choice assignments only; bounds are validated before rendering.'),
    'dialogue': (True, True, 'Each non-empty dialogue line is preserved; blank lines and paragraph spacing normalize in Ink text output.'),
    'choices': (True, False, 'Every enabled choice label is asserted against the runtime choice list, in order.'),
    'endings': (True, False, 'Every discovered ending witness plays to its ending state in the pinned runtime.'),
    'loops': (True, True, 'Cycles replay until the generated explicit step cap; the cap case is part of acceptance.'),
    'step_cap': (True, False, 'The generated ans_steps branch ends the story at the exact max_steps cap.'),
    'save': (True, False, 'story.state.ToJson() is captured at every acceptance step.'),
    'restore': (True, False, 'A fresh process restores the saved state with LoadJson and resumes to the ending.'),
    'unicode': (True, True, 'UTF-8 dialogue/choice text including emoji and escapes is asserted exactly; target font rendering is not verified.'),
    'media': (False, True, 'Approved asset references remain manifest-only; no media bytes are bundled or played.'),
}

LOSSES = [
    'INKJS_COMMUNITY_PORT_NOT_NATIVE_CSHARP_RUNTIME',
    'INK_MEDIA_REFERENCES_NOT_PLAYED',
    'INK_TEXT_PARAGRAPH_WHITESPACE_NORMALIZED',
    'INK_CHARACTER_NAMES_RENDERED_AS_PLAIN_TEXT',
    'INK_RUNTIME_NOT_VENDORED_INSTALL_REQUIRED',
    'INK_TARGET_FONT_RENDERING_NOT_VERIFIED',
]

INTEGRATION_NOTES = [
    'Consumes the same frozen typed subset as INKJS_2_3_2_TYPED_TEXT_SUBSET; the legacy target and its bundle bytes are unchanged.',
    'acceptance/witness.json drives target-environment acceptance; generating the bundle is not running it.',
    'Only the pinned community JavaScript port (inkjs 2.3.2) is verified; native C# Ink is NOT_RUN.',
]

EVIDENCE = {
    'SOURCE_IMPLEMENTED': 'PASS',
    'SCHEMA_VALIDATED': 'PASS',
    'FIXTURE_TESTED': 'PASS',
    'GENERATED_ARTIFACT_VALIDATED': 'PASS',
    # Promoted only after the real current-artifact acceptance run recorded in
    # docs/v2/B07_INK_CURRENT_ARTIFACT_EVIDENCE_20261020.json (pinned inkjs 2.3.2
    # compiled the exported source, played every witness state to its ending and
    # restored a saved state in a fresh process).
    'TARGET_RUNTIME_EXECUTED': 'PASS',
    'SAVE_RESTORE_VERIFIED': 'PASS',
    'WINDOWS_USABILITY_VERIFIED': 'NOT_RUN',
}

DESCRIPTOR = {
    'target_id': TARGET_ID,
    'display_name': DISPLAY_NAME,
    'kind': 'RUNNABLE_PROJECT',
    'format_version': FORMAT_VERSION,
    'adapter_revision': ADAPTER_REVISION,
    'engine': {
        'name': 'Node.js (inkjs runtime host)',
        'minimum_version': '18.0',
        'executables': ['node', 'node.exe'],
        'version_args': ['--version'],
        'env_override': 'POEMSEED_NODE',
        'search_hints': [],
        'gui': False,
        'note': 'The pinned inkjs 2.3.2 npm package is installed into the extracted project to compile and play it; no runtime bytes ship in the bundle.',
    },
    'capabilities': CAPABILITIES,
    'losses': LOSSES,
    'runtime_requirements': [
        'Node.js >= 18.0 to compile and play the pinned JavaScript runtime.',
        'inkjs ' + PINNED_VERSION + ' installed from ' + REGISTRY + ' with integrity ' + INTEGRITY + ' (see ink/runtime-pin.json).',
        'No runtime code, npm lifecycle script, engine or media bytes are bundled; the product has no runtime dependency on inkjs.',
    ],
    'launch_instructions': (
        'Extract the ZIP into a NEW empty directory. In that directory run "npm install inkjs@2.3.2" (registry URL and sha512 '
        'integrity are pinned in ink/runtime-pin.json), compile ink/story.ink with the pinned compiler with Ink file access denied, '
        'then play the compiled story artifact with the pinned runtime. acceptance/witness.json lists every discovered ending and one '
        'bounded step-cap case with exact per-step text, enabled choices, variables and status; verify state save/restore across processes '
        'with story.state.ToJson()/LoadJson(). Native C# Ink is not claimed and no runtime is bundled.'
    ),
    'integration_notes': INTEGRATION_NOTES,
    'evidence': EVIDENCE,
}
