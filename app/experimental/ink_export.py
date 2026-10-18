"""Trusted Ink source adapter; no compiler, imports or target execution in product."""
from __future__ import annotations
import hashlib
import json

TARGET = 'INKJS_2_3_2_TYPED_TEXT_SUBSET'
WITNESS_STATE_LIMIT = 1024
WITNESS_BYTE_LIMIT = 1024 * 1024
PIN = {'target': TARGET, 'adapter_revision': 1, 'package': 'inkjs', 'version': '2.3.2',
       'source': 'https://registry.npmjs.org/inkjs/-/inkjs-2.3.2.tgz',
       'integrity': 'sha512-iZjrY0lLeRiC+HtDzCfV9IEAP9ExCmBZUrxKkyLy1qIbbGbR1uTXNZ8LDIg8oVkMXZ9TeKKyEFQpQ/m5nQds8w==',
       'implementation': 'COMMUNITY_JAVASCRIPT_PORT_NOT_NATIVE_CSHARP',
       'artifact_runtime': 'NOT_RUN'}
LOSSES = ['INKJS_COMMUNITY_PORT_NOT_NATIVE_CSHARP_RUNTIME', 'INK_MEDIA_REFERENCES_NOT_PLAYED',
          'INK_TEXT_PARAGRAPH_WHITESPACE_NORMALIZED', 'INK_CHARACTER_NAMES_RENDERED_AS_PLAIN_TEXT',
          'INK_CURRENT_ARTIFACT_TARGET_RUNTIME_NOT_RUN']


def ink_literal(value):
    """Escape each punctuation character inside a trusted Ink string expression.

    Ink's backslash quotes the next character (not JSON escape semantics).
    Physical newlines must be split by the caller, never injected into a string.
    """
    if any(c in value for c in '\n\r\t'):
        raise ValueError('INK_SINGLE_LINE_LITERAL_REQUIRED')
    return '"' + ''.join(c if c.isalnum() or c == ' ' else '\\' + c for c in value) + '"'


def mapping(spec):
    return {'nodes': {n['node_id']: 'ans_node_' + str(i) for i, n in enumerate(spec['nodes'])},
            'variables': {v['name']: 'ans_var_' + str(i) for i, v in enumerate(spec['variables'])},
            'choices': [{'node_id': n['node_id'], 'choice_id': c['id'], 'target': 'ans_choice_' + str(i) + '_' + str(j)}
                        for i, n in enumerate(spec['nodes']) for j, c in enumerate(n['choices'])]}


def expression(tree, names):
    op = tree['op']
    if op == 'literal':
        if type(tree['value']) is bool: return '(1 == 1)' if tree['value'] else '(1 == 0)'
        return str(tree['value'])
    if op == 'var': return names[tree['name']]
    if op == 'not': return '(not ' + expression(tree['arg'], names) + ')'
    if op in {'and', 'or'}: return '(' + (' ' + op + ' ').join(expression(a, names) for a in tree['args']) + ')'
    operator = {'eq': '==', 'ne': '!=', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}[op]
    return '(' + expression(tree['left'], names) + ' ' + operator + ' ' + expression(tree['right'], names) + ')'


class InkExportAdapter:
    target = TARGET

    def validate(self, spec):
        from .interactive_story import StorySpec, analyze
        spec = StorySpec.model_validate(spec).model_dump()
        result = analyze(spec)
        # Existing strict bool/int +/-10000 bounds are exactly representable in
        # both Ink integers and JS numbers. Do not broaden to floats/arithmetic.
        for n in spec['nodes']:
            for field in ('dialogue', 'ending'):
                if '\r' in n[field] or '\t' in n[field]:
                    result['issues'].append({'code': 'INK_UNSUPPORTED_TEXT_CONTROL', 'node_id': n['node_id']})
            for c in n['choices']:
                if any(ch in c['label'] for ch in '\n\r\t') or c['label'] != c['label'].strip():
                    result['issues'].append({'code': 'INK_UNSUPPORTED_CHOICE_WHITESPACE', 'node_id': n['node_id'], 'choice_id': c['id']})
        result['can_review'] = result['can_review'] and not result['issues']
        return result

    def files(self, spec, characters):
        from .interactive_story import StorySpec, compile_story, play, digest
        spec = StorySpec.model_validate(spec).model_dump()
        analysis = self.validate(spec)
        if not analysis['can_review']: raise ValueError('INK_STORY_UNSUPPORTED')
        nodes, compiled, _ = compile_story(spec)
        source_map = mapping(spec); labels = source_map['nodes']; names = source_map['variables']
        lines = ['// Trusted generated subset for inkjs 2.3.2. Current artifact runtime NOT_RUN.',
                 'VAR ans_steps = 0', 'VAR ans_node = -1', 'VAR ans_status = 0']
        lines += ['VAR ' + names[v['name']] + ' = ' + str(v['initial']).lower() for v in spec['variables']]
        lines += ['-> ' + labels[spec['entry_node_id']]]
        for i, (nid, node) in enumerate(nodes.items()):
            lines += ['', '=== ' + labels[nid] + ' ===', '~ ans_node = ' + str(i)]
            speaker = characters.get(node['character_id']) if node['character_id'] else None
            if speaker:
                lines += ['{ ' + ink_literal(speaker) + ' }']
            for line in node['dialogue'].split('\n'):
                if line: lines += ['{ ' + ink_literal(line) + ' }']
            if node['ending']:
                lines += ['~ ans_status = 1']
                for line in node['ending'].split('\n'):
                    if line: lines += ['{ ' + ink_literal(line) + ' }']
                lines += ['-> END']; continue
            conditions = [expression(compiled[(nid, c['id'])], names) for c in node['choices']]
            lines += ['{ ans_steps >= ' + str(spec['max_steps']) + ':', '    ~ ans_status = 2', '    -> END', '}',
                      '{ not (' + ' or '.join(conditions) + '):', '    ~ ans_status = 3', '    -> END', '}']
            for j, (choice, condition) in enumerate(zip(node['choices'], conditions)):
                # Sticky choices preserve repeat visits; [] suppresses choice echo.
                lines += ['+ {' + condition + '} [{ ' + ink_literal(choice['label']) + ' }] -> ans_choice_' + str(i) + '_' + str(j)]
            for j, choice in enumerate(node['choices']):
                lines += ['', '=== ans_choice_' + str(i) + '_' + str(j) + ' ===', '~ ans_steps = ans_steps + 1']
                lines += ['~ ' + names[name] + ' = ' + str(value).lower() for name, value in choice['assignments'].items()]
                lines += ['-> ' + labels[choice['target']]]
        script = ('\n'.join(lines) + '\n').encode('utf-8')
        def state(path):
            result = play(spec, path)
            return {'node_id': result['node']['node_id'], 'variables': result['variables'],
                    'enabled_choice_ids': [c['id'] for c in result['choices'] if c['enabled']],
                    'steps': result['steps'], 'status': result['status']}
        witnesses = []; witness_states = 0; witness_bytes = 2; truncated = False
        for end in analysis['endings']:
            count = len(end['choices']) + 1
            if witness_states + count > WITNESS_STATE_LIMIT:
                truncated = True; break
            witness = {'choices': end['choices'], 'states': [state(end['choices'][:i]) for i in range(count)]}
            size = len(json.dumps(witness, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')) + 2
            if witness_bytes + size > WITNESS_BYTE_LIMIT:
                truncated = True; break
            witnesses.append(witness); witness_states += count; witness_bytes += size
        manifest = {'schema': 'poemseed-ink-exchange/1', **PIN, 'spec_digest': digest(spec),
                    'script_sha256': hashlib.sha256(script).hexdigest(), 'source_map': source_map,
                    'losses': LOSSES, 'coverage': 'ONE_WITNESS_PER_DISCOVERED_ENDING_NOT_ALL_PATHS',
                    'witnesses': witnesses, 'witnesses_truncated': truncated,
                    'witness_state_limit': WITNESS_STATE_LIMIT, 'witness_byte_limit': WITNESS_BYTE_LIMIT,
                    'witness_states': witness_states, 'status_codes': {'0': 'PLAYING', '1': 'ENDING', '2': 'STEP_CAP_REACHED', '3': 'NO_EXIT'}}
        encode = lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return {'ink/story.ink': script, 'ink/validation.json': encode(manifest),
                'ink/README.txt': b'inkjs 2.3.2 community JS port target, not native C# acceptance.\nCompile in a new project with the pinned trusted compiler; no runtime is bundled.\nDisplay output as plain text, never HTML. Deny INCLUDE/file access and external functions.\nCurrent artifact runtime NOT_RUN. validation.json gives original-owner replay expectations.\nMedia is reference-only. Whitespace/paragraph presentation may normalize.\n'}
