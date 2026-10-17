// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { imageGraphRecord } from './studioImageGraph.testFixtures';
import rawCatalog from './fixtures/productionGraph.catalog.json';
import type { StudioClient } from './studioClient';
import type { StudioGraphSaveInput, StudioGraphRecord } from './studioGraphTypes';
import { ApiError } from '../api';
import { reviewedDirectorSnapshot } from './directorCanvasHandoff';
import { newDocument, type CreativeDocument } from './types';
const pin = { id: 'reviewed-director', version: 2, digest: 'b'.repeat(64) };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
async function fixture(patch: Partial<StudioGraphEditorProps> = {}) {
  let record = imageGraphRecord();
  record.definition.nodes = [{ id: 'ancestor', definition_id: 'storyboard_plan', definition_version: 1, enabled: true,
    position: { x: 0, y: 0 }, parameters: { document_snapshot: { id: 'source-board', version: 1, digest: 'a'.repeat(64) } } }];
  record.definition.edges = []; record.reference_states = [{ node_id: 'ancestor', state: 'CURRENT' }];
  const save = vi.fn(async (_id: string, input: StudioGraphSaveInput) => { record = { ...record, version: record.version + 1, definition: structuredClone(input.definition) }; return structuredClone(record); });
  const graphs = { catalog: vi.fn().mockResolvedValue(rawCatalog), productionCatalog: vi.fn().mockResolvedValue(rawCatalog),
    list: vi.fn().mockResolvedValue({ items: [] }), get: vi.fn(async () => structuredClone(record)), save, create: vi.fn(), createRun: vi.fn() };
  const initial: StudioGraphEditorProps = { active: true, denied: false, identity: 'actor:scope:incarnation', canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work(),
    client: { graphs } as unknown as StudioClient, ...patch };
  const hook = renderHook(useStudioGraphEditorController, { initialProps: initial });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  await act(() => hook.result.current.open(record.id));
  act(() => hook.result.current.setSelected(['ancestor']));
  return { hook, initial, graphs };
}
it('uses ordinary insertion/history and explicit Graph CAS save; never connects the source storyboard ancestor', async () => {
  const { hook, graphs } = await fixture(); const before = structuredClone(hook.result.current.draft);
  const intent = hook.result.current.reviewedDirectorHandoff;
  act(() => { expect(intent.insert(pin, intent.scope)).toBe(true); expect(intent.insert(pin, intent.scope)).toBe(false); });
  expect(hook.result.current.draft.nodes).toHaveLength(2); expect(hook.result.current.draft.nodes[0]).toEqual(before.nodes[0]);
  expect(hook.result.current.draft.nodes[1].parameters).toEqual({ document_snapshot: pin });
  expect(hook.result.current.draft.edges).toEqual([]); expect(hook.result.current.past).toHaveLength(1);
  expect(hook.result.current.dirty).toBe(true); expect(graphs.save).not.toHaveBeenCalled(); expect(graphs.createRun).not.toHaveBeenCalled();
  act(() => hook.result.current.travel(false)); expect(hook.result.current.draft).toEqual(before);
  act(() => hook.result.current.travel(true));
  await act(() => hook.result.current.save()); expect(graphs.save).toHaveBeenCalledWith('image-graph', expect.objectContaining({ expected_version: 1 }));
  await act(() => hook.result.current.open('image-graph'));
  expect(hook.result.current.draft.nodes[1].parameters).toEqual({ document_snapshot: pin });
});
it.each(['identity', 'client', 'active', 'denied', 'canMutate', 'externalDirty', 'busy'] as const)('rejects retained handoff after %s ABA', async field => {
  const { hook, initial } = await fixture(); const intent = hook.result.current.reviewedDirectorHandoff;
  hook.rerender({ ...initial, [field]: field === 'identity' ? 'other' : field === 'client' ? { ...initial.client } : field === 'active' || field === 'canMutate' ? false : true });
  hook.rerender(initial);
  act(() => expect(intent.insert(pin, intent.scope)).toBe(false));
});
it('rejects selection and edit ABA, malformed pins, live busy and positioned intent', async () => {
  let busy = false; const { hook } = await fixture({ isBusy: () => busy });
  let intent = hook.result.current.reviewedDirectorHandoff;
  act(() => hook.result.current.setSelected([])); act(() => hook.result.current.setSelected(['ancestor']));
  act(() => expect(intent.insert(pin, intent.scope)).toBe(false));
  intent = hook.result.current.reviewedDirectorHandoff;
  act(() => hook.result.current.change({ ...hook.result.current.draft, title: 'edited' })); act(() => hook.result.current.travel(false));
  act(() => expect(intent.insert(pin, intent.scope)).toBe(false));
  intent = hook.result.current.reviewedDirectorHandoff; busy = true;
  act(() => expect(intent.insert(pin, intent.scope)).toBe(false)); busy = false;
  act(() => expect(intent.insert({ ...pin, digest: 'invalid' }, intent.scope)).toBe(false));
  act(() => hook.result.current.requestPositionedInsertion({ x: 20, y: 30 }, hook.result.current.insertionScope, vi.fn()));
  act(() => expect(hook.result.current.reviewedDirectorHandoff.insert(pin, hook.result.current.reviewedDirectorHandoff.scope)).toBe(false));
});
it('does not silently upgrade a new schema-1 graph and preserves the staged pin on failed Graph save', async () => {
  const { hook, graphs } = await fixture();
  act(() => hook.result.current.newGraph());
  expect(hook.result.current.draft.schema_version).toBe(1); let intent = hook.result.current.reviewedDirectorHandoff;
  act(() => expect(intent.insert(pin, intent.scope)).toBe(false)); expect(hook.result.current.draft.schema_version).toBe(1);
  await act(() => hook.result.current.open('image-graph')); intent = hook.result.current.reviewedDirectorHandoff;
  act(() => expect(intent.insert(pin, intent.scope)).toBe(true));
  graphs.save.mockRejectedValue(new ApiError({ status: 409, code: 'CONFLICT', message: 'changed' }));
  await act(() => hook.result.current.save());
  expect(hook.result.current.blocked).toBe(true); expect(hook.result.current.draft.nodes.at(-1)?.parameters).toEqual({ document_snapshot: pin });
  expect(graphs.save).toHaveBeenCalledTimes(1); expect(graphs.create).not.toHaveBeenCalled();
});
it('requires the exact reviewed DRAFT and an immutable digest, returning only scalar pin data', () => {
  const row: CreativeDocument = { ...newDocument('DIRECTOR'), ...pin, title: 'Reviewed', status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} };
  expect(reviewedDirectorSnapshot(pin, row, pin.digest)).toEqual(pin);
  for (const patch of [{ id: 'other' }, { version: 3 }, { mode: 'STORYBOARD' as const }, { status: 'APPROVED' as const }]) {
    expect(() => reviewedDirectorSnapshot(pin, { ...row, ...patch }, pin.digest)).toThrow();
  }
  expect(() => reviewedDirectorSnapshot(pin, row, 'bad')).toThrow();
  expect(() => reviewedDirectorSnapshot(pin, row, 'c'.repeat(64), pin)).toThrow();
});

it('revokes retained intent synchronously before selection and port renders', async () => {
  const { hook } = await fixture();
  for (const change of [() => hook.result.current.setSelected([]), () => hook.result.current.setSourcePort('ancestor'), () => hook.result.current.setTargetPort('other')]) {
    const intent = hook.result.current.reviewedDirectorHandoff;
    act(() => { change(); expect(intent.isVerificationCurrent()).toBe(false); expect(intent.insert(pin, intent.scope)).toBe(false); });
  }
});
it('revokes verification synchronously when Graph navigation begins', async () => {
  const { hook, graphs } = await fixture(); const intent = hook.result.current.reviewedDirectorHandoff;
  graphs.get.mockReturnValue(new Promise<StudioGraphRecord>(() => {}));
  act(() => { void hook.result.current.open('other'); expect(intent.isVerificationCurrent()).toBe(false); expect(intent.insert(pin, intent.scope)).toBe(false); });
});
