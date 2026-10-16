// @vitest-environment node
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Fountain } from 'fountain-js';
import { describe, expect, it } from 'vitest';

const root = fileURLToPath(new URL('../../../', import.meta.url));
describe('Creative projection through independent fountain-js parser', () => {
  it('preserves Unicode dialogue, delivery, context and provenance without extra scenes', () => {
    const row = { mode: 'SCREENPLAY', id: 'synthetic-document', novel_id: 'synthetic-project', title: '港口', status: 'DRAFT', version: 3,
      source_evidence: {}, scenes: [{ id: 's1', sequence: 1, heading: 'EXT. 港口 - NIGHT',
        location: '旧港码头', time: '午夜之后', action: 'INT. THIS IS AUTHORED ACTION - DAY', emotion: '克制',
        dialogue: [{ speaker: '旅人', text: '别忘记这座城。', delivery: '轻声' }] }] };
    const program = 'import json,sys; from app.creative.screenplay_export import render; sys.stdout.buffer.write(render(json.load(sys.stdin),"a"*64,"fountain")["content"])';
    const content = execFileSync(process.env.PYTHON || 'python3', ['-c', program], {
      cwd: root, input: JSON.stringify(row), encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'],
    });
    const parsed = new Fountain().parse(content, true);
    expect(parsed.tokens?.filter(token => token.type === 'scene_heading')).toHaveLength(1);
    expect(parsed.tokens?.filter(token => token.type === 'character').map(token => token.text)).toEqual(['旅人']);
    expect(parsed.tokens?.filter(token => token.type === 'parenthetical').map(token => token.text)).toEqual(['(轻声)']);
    expect(parsed.tokens?.filter(token => token.type === 'dialogue').map(token => token.text)).toEqual(['别忘记这座城。']);
    for (const text of ['旧港码头', '午夜之后', 'INT. THIS IS AUTHORED ACTION - DAY', '克制']) expect(parsed.html.script).toContain(text);
    expect(parsed.html.title_page).toContain('synthetic-document:v3');
    expect(parsed.html.script).not.toContain('Source-Versions');
  });
});
