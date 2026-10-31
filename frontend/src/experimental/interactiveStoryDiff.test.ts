import { describe, expect, it } from 'vitest';
import { describeStoryDiffRow, diffKindLabel, diffStorySpecs, formatStoryDiffValue, summarizeStoryDiff } from './interactiveStoryDiff';
import type { StorySpec } from './interactiveStoryClient';

function base(): StorySpec {
  return { title: '合成互动故事', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', max_steps: 8, graph_record_ids: ['record-1'],
    variables: [{ name: 'trusted', type: 'bool', initial: false, minimum: 0, maximum: 100 }, { name: 'score', type: 'int', initial: 0, minimum: 0, maximum: 10 }],
    nodes: [
      { node_id: 'gate', node_version: 1, title: '城门', dialogue: '旧对白', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '',
        choices: [{ id: 'home', label: '回家', target: 'end', condition: 'trusted', assignments: { trusted: true } }] },
      { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
    ] };
}

function kinds(spec: StorySpec): string[] { return diffStorySpecs(base(), spec).map(row => row.kind); }

describe('diffStorySpecs', () => {
  it('reports no differences for an identical revision', () => {
    const rows = diffStorySpecs(base(), base());
    expect(rows).toEqual([]);
    expect(summarizeStoryDiff(rows).identical).toBe(true);
  });
  it('diffs story level fields and graph record references', () => {
    const next = { ...base(), title: '新标题', entry_node_id: 'end', max_steps: 12, graph_record_ids: ['record-1', 'record-2'] };
    const rows = diffStorySpecs(base(), next);
    expect(rows.map(row => row.kind)).toEqual(['TITLE', 'ENTRY_NODE', 'MAX_STEPS', 'GRAPH_RECORDS']);
    expect(rows[0]).toMatchObject({ field: '故事标题', before: '合成互动故事', after: '新标题' });
    expect(rows[3]).toMatchObject({ before: '1 项', after: '2 项' });
  });
  it('reports added and removed nodes with their titles', () => {
    const next = base();
    next.nodes = [next.nodes[0], { ...next.nodes[1], node_id: 'epilogue', title: '后日谈', ending: '新的结局', choices: [] }];
    const rows = diffStorySpecs(base(), next);
    expect(rows.filter(row => row.kind === 'NODE_ADDED')).toHaveLength(1);
    expect(rows.filter(row => row.kind === 'NODE_REMOVED')).toHaveLength(1);
    expect(rows.find(row => row.kind === 'NODE_ADDED')).toMatchObject({ nodeId: 'epilogue', nodeTitle: '后日谈' });
    expect(rows.find(row => row.kind === 'NODE_REMOVED')).toMatchObject({ nodeId: 'end' });
    expect(rows.find(row => row.kind === 'NODE_REMOVED' && row.nodeId === 'end')).toBeTruthy();
  });
  it('reports node dialogue, ending, character and version changes', () => {
    const next = base();
    next.nodes[0] = { ...next.nodes[0], title: '城门内侧', dialogue: '新对白', character_id: null, ending: '留守', node_version: 2, choices: [] };
    const rows = diffStorySpecs(base(), next);
    const fields = rows.filter(row => row.kind === 'NODE_FIELD').map(row => row.field);
    expect(fields).toEqual(['标题', '来源节点版本', '对白', '对白角色', '结局']);
    expect(rows.filter(row => row.kind === 'CHOICE_REMOVED')).toHaveLength(1);
    expect(describeStoryDiffRow(rows.find(row => row.field === '对白')!)).toBe('节点「城门内侧」（gate） · 对白：历史「旧对白」→ 当前「新对白」');
  });
  it('reports choice label, condition, target and assignment changes plus added/removed choices', () => {
    const next = base();
    next.nodes[0] = { ...next.nodes[0], choices: [
      { id: 'home', label: '回城', target: 'gate', condition: 'not trusted', assignments: { trusted: false, score: 3 } },
      { id: 'leave', label: '离开', target: 'end', condition: '', assignments: {} },
    ] };
    const rows = diffStorySpecs(base(), next);
    const fields = rows.filter(row => row.kind === 'CHOICE_FIELD').map(row => row.field);
    expect(fields).toEqual(['选项文案', '目标节点', '条件', '选项赋值']);
    expect(rows.find(row => row.kind === 'CHOICE_FIELD' && row.field === '选项文案')).toMatchObject({ before: '回家', after: '回城' });
    expect(rows.find(row => row.kind === 'CHOICE_FIELD' && row.field === '目标节点')).toMatchObject({ before: 'end', after: 'gate' });
    expect(rows.find(row => row.kind === 'CHOICE_FIELD' && row.field === '条件')).toMatchObject({ before: 'trusted', after: 'not trusted' });
    expect(rows.find(row => row.kind === 'CHOICE_FIELD' && row.field === '选项赋值')).toMatchObject({ before: 'trusted=true', after: 'score=3、trusted=false' });
    expect(rows.find(row => row.kind === 'CHOICE_ADDED')).toMatchObject({ choiceId: 'leave', choiceLabel: '离开' });
    expect(rows.filter(row => row.kind === 'CHOICE_ADDED')).toHaveLength(1);
  });
  it('reports variable additions, removals and field changes', () => {
    const next = base();
    next.variables = [{ name: 'trusted', type: 'bool', initial: true, minimum: 0, maximum: 100 }, { name: 'courage', type: 'int', initial: 2, minimum: 0, maximum: 5 }];
    const rows = diffStorySpecs(base(), next);
    expect(rows.find(row => row.kind === 'VARIABLE_FIELD')).toMatchObject({ variable: 'trusted', field: '初始值', before: 'false', after: 'true' });
    expect(rows.find(row => row.kind === 'VARIABLE_ADDED')).toMatchObject({ variable: 'courage' });
    expect(rows.find(row => row.kind === 'VARIABLE_REMOVED')).toMatchObject({ variable: 'score' });
    expect(describeStoryDiffRow(rows.find(row => row.kind === 'VARIABLE_ADDED')!)).toContain('新增变量「courage」');
  });
  it('is deterministic and orders node changes by the current revision', () => {
    const next = base(); next.nodes.reverse();
    const first = diffStorySpecs(base(), next);
    expect(diffStorySpecs(base(), next)).toEqual(first);
    expect(first.every(row => row.key.length > 0)).toBe(true);
  });
  it('tolerates malformed or partial spec objects without throwing', () => {
    expect(diffStorySpecs(undefined as unknown as StorySpec, base())).toEqual([]);
    expect(diffStorySpecs(base(), {} as unknown as StorySpec).length).toBeGreaterThan(0);
    expect(diffStorySpecs(base(), { ...base(), nodes: undefined as unknown as StorySpec['nodes'] }).length).toBeGreaterThan(0);
  });
});

describe('formatters', () => {
  it('formats bounded values with explicit empty markers', () => {
    expect(formatStoryDiffValue(null)).toBe('（无）');
    expect(formatStoryDiffValue('')).toBe('（空）');
    expect(formatStoryDiffValue(true)).toBe('true');
    expect(formatStoryDiffValue(['a', 'b'])).toBe('a、b');
    expect(formatStoryDiffValue({})).toBe('{}');
    expect(formatStoryDiffValue('x'.repeat(400)).endsWith('…')).toBe(true);
  });
  it('labels every diff kind for display', () => {
    expect(diffKindLabel('NODE_FIELD')).toBe('节点变化');
    expect(diffKindLabel('CHOICE_REMOVED')).toBe('移除选择');
    expect(diffKindLabel('VARIABLE_ADDED')).toBe('新增变量');
  });
  it('summarises category counts', () => {
    const next = base(); next.title = '新'; next.variables = [];
    const summary = summarizeStoryDiff(diffStorySpecs(base(), next));
    expect(summary.identical).toBe(false);
    expect(summary.story).toBe(1);
    expect(summary.variables).toBe(2);
  });
});
