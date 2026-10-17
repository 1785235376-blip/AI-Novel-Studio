// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GraphPlanningFork } from './GraphPlanningFork';
import { planningSourceFork, planningSourceReferences } from './graphPlanningFork';
import type { StudioGraphDefinition } from './studioGraphTypes';

afterEach(cleanup);
const pin = { id: 'source', version: 1, digest: 'a'.repeat(64) };
const next = { ...pin, version: 3, digest: 'b'.repeat(64), title: 'Updated source', mode: 'DIRECTOR' as const };
const read = async <T,>(work: () => Promise<T>) => work();
function retainedClick(element: HTMLElement): () => void {
  const key = Object.keys(element).find(name => name.startsWith('__reactProps$'))!;
  return (element as unknown as Record<string, { onClick: () => void }>)[key].onClick;
}
it('rejects a retained prepare callback after consent is explicitly withdrawn', async () => {
  const prepare = vi.fn(() => true);
  render(<GraphPlanningFork client={{ planningDocuments: vi.fn(async () => ({ documents: [next] })) }}
    pin={pin} mode="DIRECTOR" scope={{}} disabled={false} isCurrent={() => true} read={read} prepare={prepare} />);
  fireEvent.click(screen.getByRole('button', { name: '核对更新来源用于独立新图' }));
  const consent = await screen.findByRole('checkbox'); fireEvent.click(consent);
  const click = retainedClick(screen.getByRole('button', { name: '准备使用更新来源的独立草稿' }));
  fireEvent.click(consent);
  act(() => click());
  expect(prepare).not.toHaveBeenCalled();
});

function definition(mode: 'DIRECTOR' | 'STORYBOARD' = 'DIRECTOR'): StudioGraphDefinition {
  return { schema_version: 4, title: 'Multiple independent participants', viewport: { x: 1, y: 2, zoom: 1 }, edges: [],
    nodes: ['a', 'b', 'current', 'other'].map((id, index) => ({ id,
      definition_id: mode === 'DIRECTOR' ? 'director_plan' : 'storyboard_plan', definition_version: 1, enabled: true,
      position: { x: index * 100, y: 0 }, parameters: { document_snapshot: {
        id: id === 'other' ? 'unrelated-source' : pin.id, version: id === 'b' ? 2 : id === 'current' ? 3 : 1,
        digest: id === 'current' ? next.digest : id === 'b' ? 'c'.repeat(64) : pin.digest,
      } } })), presentation: { comment: 'Keep all author data' } };
}
it.each(['DIRECTOR', 'STORYBOARD'] as const)('refreshes explicitly selected older %s references without downgrading current or unrelated pins', mode => {
  const original = definition(mode), before = structuredClone(original);
  expect(planningSourceReferences(original, 'a').map(value => value.nodeId)).toEqual(['a', 'b', 'current']);
  const updated = planningSourceFork(original, 'a', { ...next, mode }, ['a', 'b']);
  expect(updated.nodes.slice(0, 2).map(value => value.parameters.document_snapshot))
    .toEqual([{ id: pin.id, version: 3, digest: next.digest }, { id: pin.id, version: 3, digest: next.digest }]);
  expect(updated.nodes.slice(2)).toEqual(before.nodes.slice(2));
  expect(updated.presentation).toEqual(before.presentation); expect(original).toEqual(before);
  expect(updated.nodes[0].parameters.document_snapshot).not.toBe(updated.nodes[1].parameters.document_snapshot);
});
it.each([[], ['a', 'a'], ['b'], ['a', 'other'], ['a', 'current'], ['a', 'missing']].map(nodeIds => ({ nodeIds })))('rejects an invalid batch scope $nodeIds atomically', ({ nodeIds }) => {
  const original = definition(), before = structuredClone(original);
  expect(() => planningSourceFork(original, 'a', next, nodeIds)).toThrow();
  expect(original).toEqual(before);
});
it('requires fresh consent when switching from one node to all old references', async () => {
  const prepare = vi.fn(() => true), scope = {};
  render(<GraphPlanningFork client={{ planningDocuments: vi.fn(async () => ({ documents: [next] })) }}
    pin={pin} mode="DIRECTOR" scope={scope} disabled={false} isCurrent={() => true} read={read} prepare={prepare}
    references={planningSourceReferences(definition(), 'a')} />);
  fireEvent.click(screen.getByRole('button', { name: '核对更新来源用于独立新图' }));
  const consent = await screen.findByLabelText('确认以这份更新来源准备独立新图草稿，保留原图'); fireEvent.click(consent);
  const staleClick = retainedClick(screen.getByRole('button', { name: '准备使用更新来源的独立草稿' }));
  fireEvent.click(screen.getByLabelText('同时更新这份来源的全部旧引用（2 个节点）'));
  expect(screen.getByLabelText('将更新的来源节点').textContent).toContain('b：v2 → v3');
  act(() => staleClick()); expect(prepare).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: '准备使用更新来源的独立草稿' })).toHaveProperty('disabled', true);
  fireEvent.click(consent); fireEvent.click(screen.getByRole('button', { name: '准备使用更新来源的独立草稿' }));
  expect(prepare).toHaveBeenCalledTimes(1); expect(prepare).toHaveBeenCalledWith(next, scope, ['a', 'b']);
});
