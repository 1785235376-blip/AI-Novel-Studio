// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GraphPlanningFork } from './GraphPlanningFork';
import { planningSourceFork } from './graphPlanningFork';
import type { PlanningDocument } from './studioProductionGraphContract';
import type { StudioGraphDefinition } from './studioGraphTypes';

const pin = { id: 'director-document', version: 1, digest: 'a'.repeat(64) };
const next: PlanningDocument = { ...pin, version: 2, digest: 'b'.repeat(64), title: 'Current direction', mode: 'DIRECTOR' };
const draft = (): StudioGraphDefinition => ({ schema_version: 4, title: 'Author graph',
  viewport: { x: 10, y: 20, zoom: 1.2 }, nodes: [
    { id: 'director', definition_id: 'director_plan', definition_version: 1, enabled: true,
      position: { x: 20, y: 40 }, parameters: { document_snapshot: { ...pin } } },
    { id: 'board', definition_id: 'storyboard_plan', definition_version: 1, enabled: true,
      position: { x: 200, y: 40 }, parameters: { document_snapshot: { id: 'board-document', version: 3, digest: 'c'.repeat(64) } } },
  ], edges: [{ id: 'direction-link', source_node_id: 'director', source_port: 'direction', target_node_id: 'board', target_port: 'direction' }],
  presentation: { comment: 'Keep author notes', notes: [{ id: 'note', text: 'Do not erase', position: { x: 3, y: 5 } }],
    groups: [{ id: 'group', name: 'Author group', node_ids: ['director', 'board'] }] },
});
const read = async <T,>(work: () => Promise<T>) => work();
const button = (name: string) => screen.getByRole('button', { name });
const inspect = () => fireEvent.click(button('核对更新来源用于独立新图'));
const confirm = () => fireEvent.click(screen.getByRole('checkbox'));
const prepare = () => fireEvent.click(button('准备使用更新来源的独立草稿'));
afterEach(cleanup);

describe('new independent draft transformation', () => {
  it('changes only the selected exact pin without modifying source inputs', () => {
    const value = draft(), before = structuredClone(value), document = structuredClone(next);
    const result = planningSourceFork(value, 'director', document);
    const expected = structuredClone(before);
    expected.nodes[0].parameters.document_snapshot = { id: next.id, version: next.version, digest: next.digest };
    expect(result).toEqual(expected); expect(value).toEqual(before); expect(document).toEqual(next);
  });
  it.each([
    { id: 'different-document' }, { mode: 'STORYBOARD' }, { version: 1 }, { version: 0 },
    { version: 1.5 }, { digest: pin.digest }, { digest: 'invalid' },
  ])('rejects an incompatible replacement %j', patch => {
    const value = draft(), before = structuredClone(value);
    expect(() => planningSourceFork(value, 'director', { ...next, ...patch } as PlanningDocument)).toThrow();
    expect(value).toEqual(before);
  });
  it('does not accept a missing node or a board with Director metadata', () => {
    expect(() => planningSourceFork(draft(), 'missing', next)).toThrow();
    expect(() => planningSourceFork(draft(), 'board', next)).toThrow();
  });
});

function setup(overrides: Record<string, unknown> = {}) {
  const client = { planningDocuments: vi.fn(async () => ({ documents: [structuredClone(next)] })) };
  const props = { client, pin, mode: 'DIRECTOR' as const, scope: {}, disabled: false, isCurrent: () => true,
    read, prepare: vi.fn(() => true), ...overrides };
  return { props, client, ...render(<GraphPlanningFork {...props} />) };
}
describe('explicit source inspection and consent', () => {
  it('does no initial read/write and requires inspected-version consent', async () => {
    const { props, client } = setup(); expect(client.planningDocuments).not.toHaveBeenCalled();
    inspect(); await screen.findByText('Current direction：v1 → v2');
    expect(button('准备使用更新来源的独立草稿')).toHaveProperty('disabled', true);
    prepare(); expect(props.prepare).not.toHaveBeenCalled(); confirm(); prepare();
    expect(props.prepare).toHaveBeenCalledTimes(1);
    expect(props.prepare).toHaveBeenCalledWith(next, props.scope);
    expect(client.planningDocuments).toHaveBeenCalledTimes(1);
  });
  it.each([[], [next, next], [{ ...next, id: 'other' }], [{ ...next, version: 1 }], [{ ...next, mode: 'STORYBOARD' }]].map(documents => ({ documents })))('rejects missing, ambiguous and stale metadata', async ({ documents }) => {
    const client = { planningDocuments: vi.fn(async () => ({ documents })) };
    const { props } = setup({ client }); inspect();
    await waitFor(() => expect(button('核对更新来源用于独立新图')).toHaveProperty('disabled', false));
    expect(screen.queryByRole('checkbox')).toBeNull(); expect(props.prepare).not.toHaveBeenCalled();
  });
  it('fences late results across an owner change and aborts the old read', async () => {
    let resolve!: (value: { documents: PlanningDocument[] }) => void;
    const client = { planningDocuments: vi.fn((signal?: AbortSignal) => new Promise<{ documents: PlanningDocument[] }>(done => { resolve = done; })) };
    const { props, rerender } = setup({ client }); inspect();
    const signal = client.planningDocuments.mock.calls[0][0];
    rerender(<GraphPlanningFork {...props} scope={{}} />); expect(signal?.aborted).toBe(true);
    await act(async () => resolve({ documents: [next] }));
    expect(screen.queryByRole('checkbox')).toBeNull(); expect(props.prepare).not.toHaveBeenCalled();
  });
  it('retires consent across A to B to A and on revoked live authority', async () => {
    let live = true; const { props, rerender } = setup({ isCurrent: () => live });
    inspect(); await screen.findByRole('checkbox'); confirm();
    live = false; prepare(); expect(props.prepare).not.toHaveBeenCalled(); live = true;
    rerender(<GraphPlanningFork {...props} scope={{}} />); rerender(<GraphPlanningFork {...props} />);
    expect(screen.queryByRole('checkbox')).toBeNull();
  });
  it('does not dispatch while disabled or after unmount', async () => {
    const { client, unmount } = setup({ disabled: true }); inspect(); expect(client.planningDocuments).not.toHaveBeenCalled(); unmount();
  });
  it('does not start a deferred owner read after its source scope retires', async () => {
    let release!: () => Promise<unknown>;
    const delayed = <T,>(work: () => Promise<T>): Promise<T> => new Promise((resolve, reject) => {
      release = async () => { try { resolve(await work()); } catch (error) { reject(error); } };
    });
    const { props, client, rerender } = setup({ read: delayed }); inspect();
    rerender(<GraphPlanningFork {...props} scope={{}} />);
    await act(async () => release());
    expect(client.planningDocuments).not.toHaveBeenCalled(); expect(props.prepare).not.toHaveBeenCalled();
  });
  it('does not let an old response unlock a newer pending read', async () => {
    const releases: ((value: { documents: PlanningDocument[] }) => void)[] = [];
    const client = { planningDocuments: vi.fn(() => new Promise<{ documents: PlanningDocument[] }>(resolve => releases.push(resolve))) };
    const { props, rerender } = setup({ client }); inspect();
    rerender(<GraphPlanningFork {...props} scope={{}} />); inspect();
    expect(client.planningDocuments).toHaveBeenCalledTimes(2);
    await act(async () => releases[0]({ documents: [next] }));
    expect(button('核对更新来源用于独立新图')).toHaveProperty('disabled', true);
    expect(screen.queryByRole('checkbox')).toBeNull();
    await act(async () => releases[1]({ documents: [next] }));
    expect(await screen.findByRole('checkbox')).toBeTruthy();
  });
});
