import { expect, it } from 'vitest';
import { applyNodeRemoval, previewNodeRemoval } from './interactiveNodeRemoval';
import type { StorySpec } from './interactiveStoryClient';

function spec(): StorySpec {
  const node = (node_id: string) => ({ node_id, node_version: 3, title: '同名🙂', dialogue: '保留é\n🙂', ending: '', choices: [], character_id: null, background_asset_id: null, music_asset_id: null });
  return { title: '私有改编', graph_id: 'graph', graph_version: 4, entry_node_id: 'entry', nodes: [node('entry'), node('unused')], variables: [{ name: 'n', type: 'int', initial: 3, minimum: 0, maximum: 9 }], graph_record_ids: ['fact'], max_steps: 32 };
}
it('removes exactly one ID without mutating input or surviving references, pins, Unicode or variables', () => {
  const original = spec(), before = structuredClone(original);
  original.nodes[1].choices = [{ id: 'outgoing', target: 'entry', label: '回去', condition: '', assignments: {} }] as any;
  before.nodes[1].choices = structuredClone(original.nodes[1].choices);
  const preview = previewNodeRemoval(original, 'unused'), result = applyNodeRemoval(original, preview)!;
  expect(preview.blockers).toEqual([]); expect(result).toEqual({ ...original, nodes: [original.nodes[0]] });
  expect(result.nodes[0]).toBe(original.nodes[0]); expect(result.variables).toBe(original.variables); expect(result.graph_record_ids).toBe(original.graph_record_ids); expect(original).toEqual(before);
});
it.each(['entry', 'only-node', 'incoming', 'self-loop', 'missing', 'duplicate', 'invalid-entry'])('blocks %s and leaves the original untouched', kind => {
  const original = spec(); let id = 'unused';
  if (kind === 'entry') id = 'entry';
  if (kind === 'only-node') { original.nodes = [original.nodes[0]]; id = 'entry'; }
  if (kind === 'incoming' || kind === 'self-loop') original.nodes[kind === 'incoming' ? 0 : 1].choices = [{ id: 'exact_choice', target: id, label: '选择', condition: 'False', assignments: {} }] as any;
  if (kind === 'missing') id = 'absent';
  if (kind === 'duplicate') original.nodes.push({ ...original.nodes[1] });
  if (kind === 'invalid-entry') original.entry_node_id = 'absent';
  const before = structuredClone(original), preview = previewNodeRemoval(original, id);
  expect(preview.blockers.length).toBeGreaterThan(0); expect(applyNodeRemoval(original, preview)).toBeUndefined(); expect(original).toEqual(before);
  if (kind === 'incoming' || kind === 'self-loop') expect(preview.incoming).toEqual([{ nodeId: kind === 'incoming' ? 'entry' : 'unused', choiceId: 'exact_choice' }]);
});
it('rejects stale and equal-looking replacement drafts and rechecks references at apply time', () => {
  const original = spec(), preview = previewNodeRemoval(original, 'unused');
  expect(applyNodeRemoval(structuredClone(original), preview)).toBeUndefined();
  original.nodes[0].choices = [{ id: 'late', target: 'unused', label: '后加', condition: '', assignments: {} }] as any;
  expect(applyNodeRemoval(original, preview)).toBeUndefined();
});
