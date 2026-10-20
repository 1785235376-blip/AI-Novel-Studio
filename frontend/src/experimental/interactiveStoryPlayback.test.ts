import { describe, expect, it } from 'vitest';
import { analysisSummary, analysisWarningRows, choiceOverview, describePlayPath, endingRows, findUniqueNode, issueCodeCounts, playStatusNote, variableValueRows } from './interactiveStoryPlayback';
import type { StoryAnalysis, StoryPlay, StorySpec } from './interactiveStoryClient';

const spec: StorySpec = { title: '合成互动故事', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', max_steps: 4,
  variables: [{ name: 'trusted', type: 'bool', initial: false, minimum: 0, maximum: 100 }, { name: 'score', type: 'int', initial: 0, minimum: 0, maximum: 10 }],
  graph_record_ids: [], nodes: [
    { node_id: 'gate', node_version: 1, title: '城门', dialogue: '守卫', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '',
      choices: [{ id: 'home', label: '回家', target: 'end', condition: 'trusted', assignments: {} }, { id: 'wait', label: '等待', target: 'end', condition: '', assignments: {} }] },
    { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
  ] };

const play = (patch: Partial<StoryPlay> = {}): StoryPlay => ({
  node: { node_id: 'gate', node_version: 1, title: '城门', dialogue: '守卫', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '' },
  character_name: 'Alice', choices: [{ id: 'home', label: '回家', enabled: false }, { id: 'wait', label: '等待', enabled: true }],
  variables: { trusted: false, score: 2 }, steps: 0, max_steps: 4, status: 'PLAYING', path: [], ...patch });

describe('describePlayPath', () => {
  it('resolves authoritative labels and titles without evaluating conditions', () => {
    expect(describePlayPath(spec, ['home'])).toEqual([{ choiceId: 'home', label: '回家', nodeId: 'gate', targetNodeId: 'end', targetTitle: '终章', resolved: true }]);
  });
  it('falls back to raw server IDs for unresolvable history and never throws', () => {
    const rows = describePlayPath(spec, ['missing', 'home']);
    expect(rows.map(row => [row.choiceId, row.label, row.resolved])).toEqual([['missing', 'missing', false], ['home', 'home', false]]);
    expect(describePlayPath(undefined, ['x'])).toEqual([{ choiceId: 'x', label: 'x', nodeId: '', targetNodeId: '', targetTitle: undefined, resolved: false }]);
  });
});

describe('choiceOverview', () => {
  it('keeps every server choice visible and explains disabled ones from authored conditions', () => {
    const rows = choiceOverview(spec, play());
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ id: 'home', enabled: false, condition: 'trusted', reason: '服务端判定条件未满足：trusted' });
    expect(rows[1]).toMatchObject({ id: 'wait', enabled: true, condition: '' });
    expect(rows[1].reason).toBeUndefined();
  });
  it('explains a disabled choice without an authored condition without inventing an evaluation', () => {
    const rows = choiceOverview({ ...spec, nodes: [{ ...spec.nodes[0], choices: [{ ...spec.nodes[0].choices[1], condition: '' }] }] }, play());
    expect(rows[0].reason).toBe('服务端判定当前不可选（该选项没有附加条件）。');
  });
  it('does not guess when the play node is not in the displayed spec', () => {
    const rows = choiceOverview(undefined, play());
    expect(rows[0].condition).toBe('');
    expect(rows[0].reason).toBe('服务端判定当前不可选（该选项没有附加条件）。');
  });
});

describe('findUniqueNode', () => {
  it('only resolves a single exact node id', () => {
    expect(findUniqueNode(spec, 'gate')?.title).toBe('城门');
    expect(findUniqueNode(spec, 'missing')).toBeUndefined();
    expect(findUniqueNode(undefined, 'gate')).toBeUndefined();
    expect(findUniqueNode({ ...spec, nodes: [...spec.nodes, { ...spec.nodes[0] }] }, 'gate')).toBeUndefined();
  });
});

describe('endingRows', () => {
  it('maps witness choices, session exploration and node warnings', () => {
    const analysis: StoryAnalysis = { issues: [], warnings: [{ code: 'CYCLE_STEP_CAP_REQUIRED', node_id: 'gate' }], endings: [{ node_id: 'end', ending: '回家', choices: ['home'] }],
      states_checked: 2, analysis_complete: true, state_limit_reached: false, step_limit_reached: false, max_steps: 4, can_review: true };
    expect(endingRows(analysis, { end: true }, spec)).toEqual([{ key: 'end:0', nodeId: 'end', ending: '回家', choices: ['home'], steps: 1, explored: true, warningCodes: [], nodeTitle: '终章' }]);
    expect(endingRows(analysis, {}, spec)[0].explored).toBe(false);
    expect(endingRows(undefined, {}, spec)).toEqual([]);
  });
});

describe('analysis summaries', () => {
  const analysis: StoryAnalysis = { issues: [{ code: 'NO_EXIT', node_id: 'end' }, { code: 'NO_EXIT', node_id: 'gate' }, { code: 'UNDEFINED_VARIABLE', node_id: 'gate' }],
    warnings: [{ code: 'CYCLE_STEP_CAP_REQUIRED', node_id: 'gate' }, { code: 'UNREACHABLE_NODE', node_id: 'hidden' }],
    endings: [{ node_id: 'end', ending: '回家', choices: ['home'] }], states_checked: 3, analysis_complete: false, state_limit_reached: true, step_limit_reached: false, max_steps: 4, can_review: false };
  it('summarises bounded analysis without upgrading it to a proof', () => {
    expect(analysisSummary(analysis)).toEqual({ present: true, endings: 1, issues: 3, warnings: 2, statesChecked: 3, analysisComplete: false, canReview: false,
      stateLimitReached: true, stepLimitReached: false, cycleStepCapRequired: 1, unreachableNode: 1, maxSteps: 4 });
    expect(analysisSummary(undefined).present).toBe(false);
  });
  it('labels known warnings and keeps unknown warning codes visible', () => {
    const rows = analysisWarningRows(spec, { ...analysis, warnings: [...analysis.warnings, { code: 'OTHER_WARNING', node_id: 'gate' }] });
    expect(rows.map(row => row.label)).toEqual(['循环需要步数上限', '不可达节点', '路径提醒']);
    expect(rows[0]).toMatchObject({ nodeId: 'gate', nodeTitle: '城门' });
    expect(rows[1].nodeTitle).toBeUndefined();
  });
  it('aggregates issue codes deterministically', () => {
    expect(issueCodeCounts(analysis)).toEqual([{ code: 'NO_EXIT', label: '节点没有结局或选择', count: 2 }, { code: 'UNDEFINED_VARIABLE', label: '条件或赋值引用了未定义变量', count: 1 }]);
    expect(issueCodeCounts(undefined)).toEqual([]);
  });
});

describe('variableValueRows and playStatusNote', () => {
  it('shows exact server variable values with declared types', () => {
    const rows = variableValueRows(spec, play());
    expect(rows).toEqual([{ name: 'trusted', value: false, display: 'false', type: 'bool', initial: false }, { name: 'score', value: 2, display: '2', type: 'int', initial: 0 }]);
  });
  it('explains every server play status without claiming runtime execution', () => {
    expect(playStatusNote(play()).tone).toBe('info');
    expect(playStatusNote(play({ status: 'ENDING' })).tone).toBe('success');
    expect(playStatusNote(play({ status: 'STEP_CAP_REACHED' })).tone).toBe('warning');
    expect(playStatusNote(play({ status: 'NO_EXIT' })).tone).toBe('warning');
    expect(playStatusNote(play({ status: 'ENDING' })).text).toContain('不写回故事');
  });
});
