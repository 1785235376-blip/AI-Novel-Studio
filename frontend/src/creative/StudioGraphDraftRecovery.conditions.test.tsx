// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { buildConditionalStarter } from './graphConditionContract';
import { graphDraftRecoverable, readStudioGraphLocalDraft, studioGraphDraftKey, type StudioGraphDraftOwner, type StudioGraphLocalDraft } from './studioGraphLocalDraft';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { modelCatalog } from './studioGraphModel.testFixtures';
import actual from './fixtures/conditions.file-api.json';
import type { StudioClient, StudioOverview } from './studioClient';
import type { StudioGraphCatalog, StudioGraphCreateInput, StudioGraphRecord, StudioGraphSaveInput } from './studioGraphTypes';
const owner: StudioGraphDraftOwner = { projectId: 'condition-recovery', incarnation: 'file:original', actorId: 'author', actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' };
const key = studioGraphDraftKey(owner), request = `graph_${'a'.repeat(32)}`;
const snapshot = (): StudioGraphLocalDraft => ({ schema_version: 1, owner, saved_at: '2026-10-20T00:00:00Z', request_id: request, base: null, uncertain: false, definition: buildConditionalStarter('待恢复条件图') });
const overview = () => ({ project: { id: owner.projectId, incarnation: owner.incarnation }, capabilities: { can_mutate: true } }) as StudioOverview;
const saved = (): StudioGraphRecord => ({ ...structuredClone(actual.graph), project_id: owner.projectId, scope: { mode: 'local', novel_id: owner.projectId } }) as unknown as StudioGraphRecord;
function setup() {
  const client = { overview: vi.fn(async () => overview()), graphs: { catalog: vi.fn(async () => modelCatalog(false)), list: vi.fn(async () => ({ items: [] })), conditionsCatalog: vi.fn(async () => structuredClone(actual.catalog) as unknown as StudioGraphCatalog), conditionsList: vi.fn(async () => ({ items: [] })), get: vi.fn(async () => saved()), create: vi.fn(async (body: StudioGraphCreateInput) => ({ ...saved(), id: 'new-condition', version: 1, definition: body.definition })), save: vi.fn(async (_id: string, body: StudioGraphSaveInput) => ({ ...saved(), version: 3, definition: body.definition })), createRun: vi.fn(), preflight: vi.fn(), action: vi.fn(), runs: vi.fn(async () => ({ items: [] })) } };
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'condition-author', client: client as unknown as StudioClient, draftOwner: owner, canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work() };
  return { client, props };
}
beforeEach(() => localStorage.clear()); afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const seed = (value = snapshot()) => { const raw = JSON.stringify(value); localStorage.setItem(key, raw); return raw; };
it('round-trips the existing strict condition definition and original uncertain request envelope', () => {
  const value = snapshot(); value.uncertain = true; value.definition.nodes[1].parameters.predicate = { kind: 'enum', value: 'A', equals: 'B' }; value.definition.nodes[0].parameters.text = '保留作者文本';
  expect(graphDraftRecoverable(value.definition)).toBe(true); expect(readStudioGraphLocalDraft(JSON.stringify(value), owner)).toEqual(value);
});
it('persists a discovered condition draft, reloads, explicitly restores the original owner and saves with the same request without a run', async () => {
  const { client, props } = setup(); const first = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(first.result.current.catalog).toBeTruthy());
  await act(async () => first.result.current.loadConditions()); act(() => first.result.current.createConditions());
  act(() => first.result.current.updateCondition({ kind: 'enum', value: 'A', equals: 'B' }));
  act(() => first.result.current.change({ ...first.result.current.draft, title: '跨刷新条件草稿', nodes: first.result.current.draft.nodes.map(n => n.id === 'input' ? { ...n, parameters: { text: '尚未保存的作者文字' } } : n) }));
  await waitFor(() => expect(localStorage.getItem(key)).not.toBeNull()); const cached = readStudioGraphLocalDraft(localStorage.getItem(key)!, owner); first.unmount();
  const second = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(second.result.current.localRecovery).toBeTruthy()); expect(second.result.current.draft.schema_version).toBe(1);
  const before = client.graphs.conditionsCatalog.mock.calls.length; await act(async () => second.result.current.recoverLocalDraft());
  expect(second.result.current.draft).toEqual(cached.definition); expect(client.graphs.conditionsCatalog).toHaveBeenCalledTimes(before + 1); expect(second.result.current.catalog?.capabilities.local_conditions_schema_version).toBe(7); expect(client.overview).toHaveBeenCalledTimes(2);
  expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.action).not.toHaveBeenCalled();
  await act(async () => second.result.current.save()); expect(client.graphs.create).toHaveBeenCalledWith({ request_id: cached.request_id, expected_version: 0, definition: cached.definition }); expect(localStorage.getItem(key)).toBeNull();
});
it('keeps a rejected gate cache intact and does not restore or send a write', async () => {
  const raw = seed(), { client, props } = setup(); client.graphs.conditionsCatalog.mockRejectedValue(new Error('CONDITIONS_DISABLED'));
  const view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.localRecovery).toBeTruthy()); await act(async () => view.result.current.recoverLocalDraft());
  expect(view.result.current.recoveryError).toContain('CONDITIONS_DISABLED'); expect(view.result.current.draft.schema_version).toBe(1); expect(localStorage.getItem(key)).toBe(raw); expect(client.graphs.create).not.toHaveBeenCalled();
});
it('restores only an exact saved schema7 baseline and retains its CAS for explicit Save', async () => {
  const value = snapshot(), record = saved(); value.base = { id: record.id, version: record.version, definition_digest: record.definition_digest, execution_digest: record.execution_digest }; value.definition = { ...structuredClone(record.definition), title: '已保存图的未保存条件' }; value.definition.nodes[1].parameters.predicate = { kind: 'boolean', value: false }; seed(value);
  const { client, props } = setup(), view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.localRecovery).toBeTruthy()); await act(async () => view.result.current.recoverLocalDraft());
  expect(view.result.current.base?.version).toBe(record.version); expect(view.result.current.draft).toEqual(value.definition); expect(client.graphs.get).toHaveBeenCalledWith(record.id); expect(client.graphs.save).not.toHaveBeenCalled();
  await act(async () => view.result.current.save()); expect(client.graphs.save).toHaveBeenCalledWith(record.id, { expected_version: record.version, definition: value.definition }); expect(client.graphs.createRun).not.toHaveBeenCalled();
});
it.each(['version', 'definition_digest', 'execution_digest', 'can_edit', 'schema'] as const)('retains cached text and predicate if saved %s changed', async field => {
  const value = snapshot(), original = saved(); value.base = { id: original.id, version: original.version, definition_digest: original.definition_digest, execution_digest: original.execution_digest }; const raw = seed(value);
  const changed = saved(); if (field === 'version') changed.version++; else if (field === 'can_edit') changed.can_edit = false; else if (field === 'schema') changed.definition = { ...changed.definition, schema_version: 1 }; else changed[field] = 'b'.repeat(64);
  const { client, props } = setup(); client.graphs.get.mockResolvedValue(changed); const view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.localRecovery).toBeTruthy()); await act(async () => view.result.current.recoverLocalDraft());
  expect(view.result.current.recoveryError).toContain('图服务端版本或摘要已改变'); expect(view.result.current.draft.schema_version).toBe(1); expect(localStorage.getItem(key)).toBe(raw); expect(client.graphs.save).not.toHaveBeenCalled();
});
it.each(['incarnation', 'permission'] as const)('rechecks %s after the gate read before replacing local input', async field => {
  const raw = seed(), { client, props } = setup(); client.overview.mockResolvedValueOnce(overview()).mockResolvedValueOnce(field === 'incarnation' ? { ...overview(), project: { ...overview().project, incarnation: 'file:replacement' } } : { ...overview(), capabilities: { ...overview().capabilities, can_mutate: false } });
  const view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.localRecovery).toBeTruthy()); await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.recoveryError).toMatch(/项目代次已经改变|当前身份没有图编辑权限/); expect(view.result.current.draft.schema_version).toBe(1); expect(localStorage.getItem(key)).toBe(raw); expect(client.graphs.create).not.toHaveBeenCalled();
});
it('keeps original UNKNOWN request and payload across a reload; only explicit original same-request Save retries', async () => {
  const value = snapshot(); value.uncertain = true; value.definition.nodes[1].parameters.predicate = { kind: 'enum', value: 'B', equals: 'A' }; seed(value);
  const { client, props } = setup(), view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.localRecovery).toBeTruthy()); await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.blocked).toBe(true); expect(client.graphs.create).not.toHaveBeenCalled();
  await act(async () => view.result.current.save()); expect(client.graphs.create).not.toHaveBeenCalled(); await act(async () => view.result.current.save(true)); expect(client.graphs.create).toHaveBeenCalledTimes(1); expect(client.graphs.create).toHaveBeenCalledWith({ request_id: request, expected_version: 0, definition: value.definition }); expect(client.graphs.action).not.toHaveBeenCalled();
});
it.each(['busy', 'canMutate', 'externalDirty'] as const)('retires old recovery callbacks and late catalog reads after %s ABA', async field => {
  const raw = seed(), { client, props } = setup(), view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.localRecovery).toBeTruthy());
  const retained = view.result.current.recoverLocalDraft; view.rerender({ ...props, [field]: field !== 'canMutate' }); view.rerender(props); await act(async () => retained()); expect(client.overview).not.toHaveBeenCalled();
  let resolve!: (v: StudioGraphCatalog) => void; client.graphs.conditionsCatalog.mockImplementation(() => new Promise<StudioGraphCatalog>(r => { resolve = r; })); let pending!: Promise<void>;
  act(() => { pending = view.result.current.recoverLocalDraft(); }); await waitFor(() => expect(resolve).toBeTypeOf('function')); view.rerender({ ...props, [field]: field !== 'canMutate' }); view.rerender(props);
  await act(async () => { resolve(actual.catalog as unknown as StudioGraphCatalog); await pending; }); expect(view.result.current.draft.schema_version).toBe(1); expect(view.result.current.recoveryError).toBe(''); expect(localStorage.getItem(key)).toBe(raw); expect(client.graphs.get).not.toHaveBeenCalled();
});
it('consumes one recovery while pending and never overwrites an updated other-tab cache', async () => {
  const raw = seed(), { client, props } = setup(); let resolve!: (v: StudioGraphCatalog) => void; client.graphs.conditionsCatalog.mockImplementation(() => new Promise<StudioGraphCatalog>(r => { resolve = r; }));
  const view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.localRecovery).toBeTruthy()); let first!: Promise<void>, second!: Promise<void>;
  act(() => { const recover = view.result.current.recoverLocalDraft; first = recover(); second = recover(); }); await waitFor(() => expect(resolve).toBeTypeOf('function')); expect(client.graphs.conditionsCatalog).toHaveBeenCalledTimes(1);
  const other = snapshot(); other.definition.title = '另一页面的新缓存'; const otherRaw = seed(other); expect(otherRaw).not.toBe(raw);
  await act(async () => { resolve(actual.catalog as unknown as StudioGraphCatalog); await Promise.all([first, second]); }); expect(view.result.current.recoveryError).toContain('其他页面已更新'); expect(localStorage.getItem(key)).toBe(otherRaw); expect(view.result.current.draft.schema_version).toBe(1); expect(client.graphs.create).not.toHaveBeenCalled();
});
it('keeps strict predicate/topology and owner rules; no run/review/model/cache receipt becomes a recoverable graph', () => {
  for (const change of [(v: StudioGraphLocalDraft) => { Object.assign(v.definition.nodes[1].parameters.predicate!, { value: 'true' }); }, (v: StudioGraphLocalDraft) => { v.definition.edges.pop(); }, (v: StudioGraphLocalDraft) => { v.definition.nodes[2].enabled = false; }, (v: StudioGraphLocalDraft) => { Object.assign(v.definition.nodes[0].parameters, { provider_id: 'model' }); }, (v: StudioGraphLocalDraft) => { Object.assign(v.definition, { reviewed: true, run_id: 'old' }); }]) {
    const value = snapshot(); change(value); expect(() => readStudioGraphLocalDraft(JSON.stringify(value), owner)).toThrow();
  }
  const value = snapshot(); expect(() => readStudioGraphLocalDraft(JSON.stringify(value), { ...owner, incarnation: 'file:new' })).toThrow(); expect(() => readStudioGraphLocalDraft(JSON.stringify(value), { ...owner, actorId: 'other' })).toThrow();
  for (const version of [3, 4, 5, 6] as const) expect(graphDraftRecoverable({ ...value.definition, schema_version: version })).toBe(false);
});
