import { describe, expect, it } from 'vitest';
import { previewCheckpointEdit } from './workflowGraphEditing';
import type { AuthoredWorkflow } from './declarativeAgentsClient';
const graph = (): AuthoredWorkflow => ({ agent: { title: '海港', purpose: '作者用途', role_prompt: '保留作者提示词', input_schema: { fields: [{ name: 'source_text', type: 'string', required: true, max_length: 8000 }] }, output_schema: { fields: [{ name: 'draft', type: 'string', required: true, max_length: 8000 }] }, allowed_tools: ['draft_prepare'], model_route: null, capability_requirements: ['LOCAL_RULES'], runtime_requirement: 'TRUSTED_IN_PROCESS_LOCAL', review_required: true, max_steps: 16, timeout_seconds: 30, max_output_bytes: 64000, max_cost_microusd: 0 }, nodes: [{ id: 'prepare', type: 'draft_prepare', name: '准备' }, { id: 'review', type: 'manual_approval', name: '人工审核' }, { id: 'artifact', type: 'review_artifact', name: '材料' }], edges: [{ source: 'prepare', target: 'review' }, { source: 'review', target: 'artifact' }] });
const insert = (g = graph()) => previewCheckpointEdit(g, { kind: 'insert', source: 'prepare', target: 'review' });
const reachability = (g: AuthoredWorkflow, ids: string[]) => ids.flatMap(source => {
  const found = new Set<string>(), queue = [source];
  while (queue.length) { const current = queue.shift(); for (const edge of g.edges.filter(edge => edge.source === current)) if (!found.has(edge.target)) { found.add(edge.target); queue.push(edge.target); } }
  return ids.filter(target => found.has(target)).map(target => [source, target]);
});
function branched(count: number) {
  const g = graph();
  for (let i = 1; i <= count; i++) g.nodes.splice(i, 0, { id: 'branch' + i, type: 'checkpoint', name: '分支' + i });
  g.edges = g.nodes.filter(n => n.type === 'checkpoint').flatMap(n => [{ source: 'prepare', target: n.id }, { source: n.id, target: 'review' }]);
  g.edges.push({ source: 'review', target: 'artifact' }); return g;
}
it('previews insertion without changing any original field, then removal round-trips the full definition', () => {
  const original = graph(), snapshot = JSON.stringify(original), preview = insert(original);
  expect(JSON.stringify(original)).toBe(snapshot);
  expect(preview.definition.agent).toEqual(original.agent); expect(preview.definition.agent).not.toBe(original.agent);
  expect(preview.removed).toEqual([{ source: 'prepare', target: 'review' }]);
  expect(preview.added).toEqual([{ source: 'prepare', target: 'checkpoint1' }, { source: 'checkpoint1', target: 'review' }]);
  expect(previewCheckpointEdit(preview.definition, { kind: 'remove', id: preview.nodeId }).definition).toEqual(original);
});
it('preserves all other branch dependencies and original-node reachability', () => {
  const original = branched(3), ids = original.nodes.map(n => n.id);
  const candidate = previewCheckpointEdit(original, { kind: 'insert', source: 'prepare', target: 'branch2' }).definition;
  expect(reachability(candidate, ids)).toEqual(reachability(original, ids));
  expect(candidate.edges.filter(e => !e.source.startsWith('checkpoint') && !e.target.startsWith('checkpoint'))).toEqual(original.edges.filter(e => !(e.source === 'prepare' && e.target === 'branch2')));
});
it('chooses a unique checkpoint ID without renaming the existing one', () => {
  const first = insert().definition; const next = previewCheckpointEdit(first, { kind: 'insert', source: 'prepare', target: 'checkpoint1' });
  expect(next.nodeId).toBe('checkpoint2'); expect(next.definition.nodes.find(n => n.id === 'checkpoint1')).toEqual(first.nodes.find(n => n.id === 'checkpoint1'));
});
it.each(['review', 'artifact', 'prepare', 'missing'])('never removes %s as a checkpoint', id => expect(() => previewCheckpointEdit(graph(), { kind: 'remove', id })).toThrow(/只可移除/));
it('keeps the unique approval directly adjacent to the artifact', () => expect(() => previewCheckpointEdit(graph(), { kind: 'insert', source: 'review', target: 'artifact' })).toThrow(/不能在人工审核/));
it('refuses a missing selected connection', () => expect(() => previewCheckpointEdit(graph(), { kind: 'insert', source: 'missing', target: 'review' })).toThrow(/不存在/));
it.each(['fan-in', 'fan-out', 'root'])('does not guess a %s checkpoint reconnection', kind => {
  const g = branched(2);
  if (kind === 'fan-in') g.edges.push({ source: 'branch1', target: 'branch2' });
  if (kind === 'fan-out') g.edges.push({ source: 'branch2', target: 'branch1' });
  if (kind === 'root') g.nodes.find(n => n.id === 'prepare')!.type = 'checkpoint';
  expect(() => previewCheckpointEdit(g, { kind: 'remove', id: kind === 'root' ? 'prepare' : 'branch2' })).toThrow(/恰好一条入边/);
});
it('refuses duplicate bridge creation instead of silently deduplicating', () => {
  const g = insert().definition; g.edges.push({ source: 'prepare', target: 'review' });
  expect(() => previewCheckpointEdit(g, { kind: 'remove', id: 'checkpoint1' })).toThrow(/衔接会产生/);
});
it.each(['duplicate-node', 'duplicate-edge', 'self', 'unknown', 'extra-edge-field', 'cycle', 'disconnected', 'another-approval', 'bypass'])('refuses malformed %s without altering the draft', kind => {
  const g = graph();
  if (kind === 'duplicate-node') g.nodes[1].id = 'prepare';
  if (kind === 'duplicate-edge') g.edges.push({ ...g.edges[0] });
  if (kind === 'self') g.edges[0].target = 'prepare';
  if (kind === 'unknown') g.edges[0].source = 'missing';
  if (kind === 'extra-edge-field') Object.assign(g.edges[0], { condition: 'never silently dropped' });
  if (kind === 'cycle') g.edges.push({ source: 'review', target: 'prepare' });
  if (kind === 'disconnected') g.nodes.push({ id: 'orphan', type: 'checkpoint', name: 'orphan' });
  if (kind === 'another-approval') g.nodes[0].type = 'manual_approval';
  if (kind === 'bypass') g.edges.push({ source: 'prepare', target: 'artifact' });
  const snapshot = JSON.stringify(g); expect(() => insert(g)).toThrow(); expect(JSON.stringify(g)).toBe(snapshot);
});
describe('original budgets', () => {
  it('does not raise the author step budget', () => { const g = graph(); g.agent.max_steps = 3; expect(() => insert(g)).toThrow(/预算/); expect(g.agent.max_steps).toBe(3); });
  it('refuses a seventeenth node', () => expect(() => previewCheckpointEdit(branched(13), { kind: 'insert', source: 'prepare', target: 'branch1' })).toThrow(/预算/));
  it('accepts edge 40 but refuses adding edge 41', () => {
    const g = branched(12);
    for (let a = 1; a <= 12; a++) for (let b = a + 1; b <= 12 && g.edges.length < 39; b++) g.edges.push({ source: 'branch' + a, target: 'branch' + b });
    expect(previewCheckpointEdit(g, { kind: 'insert', source: 'prepare', target: 'branch1' }).definition.edges).toHaveLength(40);
    g.edges.push({ source: 'branch11', target: 'branch12' });
    expect(() => previewCheckpointEdit(g, { kind: 'insert', source: 'prepare', target: 'branch1' })).toThrow(/预算/);
  });
});
