// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor, cleanup } from '@testing-library/react';
import { createStudioGraphClient, checkedStudioGraphDraft } from './studioGraphClient';
import { graphDraftRecoverable, readStudioGraphLocalDraft, checkedLocalGraphDefinition, studioGraphDraftKey } from './studioGraphLocalDraft';
import { boundDefinition, boundOwner, boundSnapshot, boundCatalog, boundChild, boundSaved, boundRequest } from './graphBoundDraftRecovery.testFixtures';
beforeEach(() => localStorage.clear()); afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it.each([3, 4, 5, 6] as const)('shared reproduction: schema%s authoring snapshot must survive refresh', schema => {
  const value = boundSnapshot(schema); value.uncertain = true;
  expect(graphDraftRecoverable(value.definition)).toBe(true); expect(readStudioGraphLocalDraft(JSON.stringify(value), boundOwner).definition).toEqual(JSON.parse(JSON.stringify(checkedStudioGraphDraft(value.definition))));
});
it.each([3, 4, 5] as const)('shared reproduction: schema%s unconfigured route remains local authoring, never a valid Save DTO', schema => {
  const value = boundSnapshot(schema), node = value.definition.nodes.find(n => ['media_generate', 'image_generate', 'video_generate'].includes(n.definition_id))!; node.parameters.provider_id = ''; node.parameters.model_id = '';
  expect(() => checkedStudioGraphDraft(value.definition)).toThrow(); expect(graphDraftRecoverable(value.definition)).toBe(true);
  expect(readStudioGraphLocalDraft(JSON.stringify(value), boundOwner).definition).toEqual(JSON.parse(JSON.stringify(value.definition)));
});

import { readBoundDraftCatalog, verifyBoundDraftSources } from './studioGraphDraftRecoverySources';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioClient, StudioAsset, StudioOverview } from './studioClient';
import type { StudioGraphDefinition, StudioGraphRecord, StudioGraphCatalog, StudioGraphCreateInput, StudioGraphSaveInput } from './studioGraphTypes';
import type { StudioTimelineRow } from './studioTimelineTypes';
import type { PlanningDocument } from './studioProductionGraphContract';
import type { StoryboardReceipt } from './studioStoryboardContract';
import rawBoard from './fixtures/phase4.file-api-storyboard.json';
const key = studioGraphDraftKey(boundOwner);
function setup(schema: 3 | 4 | 5 | 6) {
  const graph = boundSaved(schema), child = boundChild(), assets = new Map<string, StudioAsset>();
  for (const n of graph.definition.nodes) if (n.definition_id === 'asset_reference') assets.set(n.parameters.asset_id!, { id: n.parameters.asset_id, novel_id: boundOwner.projectId, branch_id: null, version: n.parameters.version, sha256: n.parameters.digest, kind: n.parameters.kind, deleted_at: null } as unknown as StudioAsset);
  const documents: PlanningDocument[] = [], boards = new Map<string, StoryboardReceipt>(), timelines = new Map<string, StudioTimelineRow>();
  const overview = () => ({ project: { id: boundOwner.projectId, incarnation: boundOwner.incarnation }, capabilities: { can_mutate: true } }) as StudioOverview;
  const client = { overview: vi.fn(async () => overview()), asset: vi.fn(async (id: string) => { const a = assets.get(id); if (!a) throw new Error('ASSET_UNAVAILABLE'); return structuredClone(a); }), graphs: {
    catalog: vi.fn(async () => boundCatalog(3)), imageCatalog: vi.fn(async () => boundCatalog(4)), productionCatalog: vi.fn(async () => boundCatalog(4, true)), videoCatalog: vi.fn(async () => boundCatalog(5)), localSubgraphCatalog: vi.fn(async () => boundCatalog(6)),
    list: vi.fn(async () => ({ items: [] })), get: vi.fn(async (id: string) => structuredClone(id === child.id ? child : graph)),
    planningDocuments: vi.fn(async () => ({ documents: structuredClone(documents) })), videoStoryboard: vi.fn(async (id: string) => { const b = boards.get(id); if (!b) throw new Error('BOARD_UNAVAILABLE'); return structuredClone(b); }),
    graphTimelineGet: vi.fn(async (id: string) => { const t = timelines.get(id); if (!t) throw new Error('TIMELINE_UNAVAILABLE'); return structuredClone(t); }),
    create: vi.fn(async (body: StudioGraphCreateInput) => ({ ...graph, id: 'new-bound', version: 1, definition: checkedStudioGraphDraft(body.definition) })), save: vi.fn(async (_id: string, body: StudioGraphSaveInput) => ({ ...graph, version: 3, definition: checkedStudioGraphDraft(body.definition) })), preflight: vi.fn(), createRun: vi.fn(), action: vi.fn() } };
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'bound-author', client: client as unknown as StudioClient, draftOwner: boundOwner, canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work() };
  const verify = (definition = graph.definition, current = () => true, saved?: StudioGraphRecord) => verifyBoundDraftSources(props.client, checkedLocalGraphDefinition(definition), boundCatalog(schema, definition.nodes.some(n => n.definition_id === 'storyboard_plan')), boundOwner, current, saved);
  return { props, client, graph, child, assets, documents, boards, timelines, overview, verify };
}
const seed = (value: ReturnType<typeof boundSnapshot>) => { const raw = JSON.stringify(value); localStorage.setItem(key, raw); return raw; };
async function mounted(p: StudioGraphEditorProps) { const view = renderHook(v => useStudioGraphEditorController(v), { initialProps: p }); await waitFor(() => expect(view.result.current.localRecovery).toBeTruthy()); return view; }
it.each([3, 4, 5, 6] as const)('schema%s full authoring cache reloads through original recovery then explicit same-request Save, without any run', async schema => {
  const value = boundSnapshot(schema), raw = seed(value), { props, client } = setup(schema), view = await mounted(props);
  await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.draft).toEqual(readStudioGraphLocalDraft(raw, boundOwner).definition); expect(view.result.current.catalog?.definitions.some(n => n.id === value.definition.nodes.at(-1)!.definition_id)).toBe(true); expect(client.overview).toHaveBeenCalledTimes(2);
  expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.preflight).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.action).not.toHaveBeenCalled();
  await act(async () => view.result.current.save()); expect(client.graphs.create).toHaveBeenCalledWith({ request_id: boundRequest, expected_version: 0, definition: readStudioGraphLocalDraft(raw, boundOwner).definition }); expect(localStorage.getItem(key)).toBeNull();
});
it.each([3, 4, 5, 6] as const)('schema%s saved UNKNOWN draft preserves CAS/payload and requires original readback instead of blind PUT replay', async schema => {
  const state = setup(schema), value = boundSnapshot(schema); value.uncertain = true; value.definition.title = '未知保存回执的作者输入'; value.base = { id: state.graph.id, version: state.graph.version, definition_digest: state.graph.definition_digest, execution_digest: state.graph.execution_digest }; const raw = seed(value), view = await mounted(state.props);
  await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.blocked).toBe(true); expect(state.client.graphs.save).not.toHaveBeenCalled(); await act(async () => view.result.current.save()); expect(state.client.graphs.save).not.toHaveBeenCalled();
  await act(async () => view.result.current.save(true)); expect(state.client.graphs.save).not.toHaveBeenCalled(); await act(async () => view.result.current.checkServer()); expect(view.result.current.candidate?.version).toBe(2); expect(view.result.current.draft).toEqual(readStudioGraphLocalDraft(raw, boundOwner).definition); expect(view.result.current.blocked).toBe(true); expect(JSON.parse(localStorage.getItem(key)!).request_id).toBe(boundRequest); expect(state.client.graphs.create).not.toHaveBeenCalled(); expect(state.client.graphs.action).not.toHaveBeenCalled();
});
it.each([3, 4, 5, 6] as const)('schema%s gate denial leaves the original cache and current editor intact', async schema => {
  const raw = seed(boundSnapshot(schema)), s = setup(schema); const method = schema === 6 ? s.client.graphs.localSubgraphCatalog : schema === 5 ? s.client.graphs.videoCatalog : schema === 4 ? s.client.graphs.imageCatalog : s.client.graphs.catalog;
  // Preserve the initial legacy catalog read; reject only the explicit recovery read.
  if (schema === 3) method.mockResolvedValueOnce(boundCatalog(3)).mockRejectedValue(new Error('GATE_DISABLED')); else method.mockRejectedValue(new Error('GATE_DISABLED'));
  const view = await mounted(s.props); await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.recoveryError).toContain('GATE_DISABLED'); expect(view.result.current.draft.schema_version).toBe(1); expect(localStorage.getItem(key)).toBe(raw); expect(s.client.graphs.create).not.toHaveBeenCalled();
});
it('keeps empty-route authoring recoverable but the unchanged original Save decoder rejects it before transport', async () => {
  const value = boundSnapshot(5); value.definition.nodes[0].parameters.provider_id = ''; value.definition.nodes[0].parameters.model_id = ''; const raw = seed(value), s = setup(5), view = await mounted(s.props);
  await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.draft.nodes[0].parameters.provider_id).toBe(''); const json = vi.fn(); const original = createStudioGraphClient(boundOwner.projectId, {}, { json });
  expect(() => original.create({ request_id: boundRequest, expected_version: 0, definition: readStudioGraphLocalDraft(raw, boundOwner).definition })).toThrow(); expect(json).not.toHaveBeenCalled(); expect(s.client.graphs.preflight).not.toHaveBeenCalled();
});
it.each(['version', 'definition_digest', 'execution_digest', 'can_edit', 'scope', 'interface'] as const)('schema6 rejects changed child %s without updating a pin or applying stale authoring', async field => {
  const raw = seed(boundSnapshot(6)), s = setup(6); const child = structuredClone(s.child);
  if (field === 'version') child.version++; else if (field === 'can_edit') child.can_edit = false; else if (field === 'scope') child.project_id = 'foreign'; else if (field === 'interface') child.definition.nodes.find(n => n.definition_id === 'text_reference')!.enabled = false; else child[field] = 'd'.repeat(64);
  s.client.graphs.get.mockResolvedValue(child); const view = await mounted(s.props); await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.draft.schema_version).toBe(1); expect(view.result.current.recoveryError).not.toBe(''); expect(localStorage.getItem(key)).toBe(raw); expect(s.client.graphs.create).not.toHaveBeenCalled();
});
it('schema6 preserves fixed saved topology and both parent digests; a fresh child cannot authorize a changed saved pin', async () => {
  const s = setup(6), value = boundSnapshot(6); value.base = { id: s.graph.id, version: s.graph.version, definition_digest: s.graph.definition_digest, execution_digest: s.graph.execution_digest }; value.definition.nodes[1].parameters.execution_digest = 'd'.repeat(64); const raw = seed(value), view = await mounted(s.props);
  await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.recoveryError).toContain('固定来源或子图拓扑'); expect(localStorage.getItem(key)).toBe(raw); expect(view.result.current.draft.schema_version).toBe(1);
});
it.each(['stale', 'deleted', 'foreign', 'late-change'] as const)('asset source %s is never adopted as current', async mode => {
  const s = setup(4), a = structuredClone(s.assets.get('source')!);
  if (mode === 'stale') a.version++; else if (mode === 'deleted') a.deleted_at = '2026-10-20'; else if (mode === 'foreign') a.novel_id = 'other';
  if (mode === 'late-change') s.client.asset.mockResolvedValueOnce(a).mockResolvedValue({ ...a, version: a.version + 1 }); else s.client.asset.mockResolvedValue(a);
  await expect(s.verify()).rejects.toThrow(); expect(s.client.graphs.createRun).not.toHaveBeenCalled();
});
it('halts late source reads and old recovery callbacks across busy/permission/source lifetime changes', async () => {
  const raw = seed(boundSnapshot(6)), s = setup(6), view = await mounted(s.props); const old = view.result.current.recoverLocalDraft; view.rerender({ ...s.props, canMutate: false }); view.rerender(s.props); await act(async () => old()); expect(s.client.overview).not.toHaveBeenCalled();
  let resolve!: (v: StudioGraphRecord) => void; s.client.graphs.get.mockImplementation(() => new Promise<StudioGraphRecord>(r => { resolve = r; })); let pending!: Promise<void>;
  act(() => { pending = view.result.current.recoverLocalDraft(); }); await waitFor(() => expect(resolve).toBeTypeOf('function')); view.rerender({ ...s.props, busy: true }); view.rerender(s.props); await act(async () => { resolve(s.child); await pending; }); expect(view.result.current.draft.schema_version).toBe(1); expect(localStorage.getItem(key)).toBe(raw); expect(s.client.graphs.get).toHaveBeenCalledTimes(1);
});
it.each([3, 4, 5, 6] as const)('schema%s original author edits actually persist, unmount and restore against a fresh saved source', async schema => {
  const s = setup(schema), first = renderHook(p => useStudioGraphEditorController(p), { initialProps: s.props }); await waitFor(() => expect(first.result.current.catalog).toBeTruthy()); await act(async () => first.result.current.open(s.graph.id));
  act(() => first.result.current.change({ ...first.result.current.draft, title: `跨刷新 schema${schema} 作者草稿` })); await waitFor(() => expect(localStorage.getItem(key)).not.toBeNull()); const raw = localStorage.getItem(key)!; first.unmount();
  const second = await mounted(s.props); await act(async () => second.result.current.recoverLocalDraft()); expect(second.result.current.draft).toEqual(readStudioGraphLocalDraft(raw, boundOwner).definition); expect(second.result.current.base?.version).toBe(2); expect(s.client.graphs.save).not.toHaveBeenCalled(); expect(s.client.graphs.createRun).not.toHaveBeenCalled();
});
it.each([3, 4, 5, 6] as const)('schema%s rereads original owner/incarnation after all source checks', async schema => {
  const raw = seed(boundSnapshot(schema)), s = setup(schema); s.client.overview.mockResolvedValueOnce(s.overview()).mockResolvedValueOnce({ ...s.overview(), project: { ...s.overview().project, incarnation: 'file:replacement' } }); const view = await mounted(s.props);
  await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.recoveryError).toContain('项目代次已经改变'); expect(view.result.current.draft.schema_version).toBe(1); expect(localStorage.getItem(key)).toBe(raw); expect(s.client.graphs.create).not.toHaveBeenCalled();
});
it('schema6 final gate reread cannot be replaced by a previously read current child', async () => {
  const raw = seed(boundSnapshot(6)), s = setup(6); s.client.graphs.localSubgraphCatalog.mockResolvedValueOnce(boundCatalog(6)).mockRejectedValue(new Error('FLAG_RETIRED'));
  const view = await mounted(s.props); await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.recoveryError).toContain('FLAG_RETIRED'); expect(view.result.current.draft.schema_version).toBe(1); expect(localStorage.getItem(key)).toBe(raw); expect(s.client.graphs.get).toHaveBeenCalledTimes(2);
});
it('schema6 duplicate pending recovery and other-tab edits never replay or overwrite author input', async () => {
  const raw = seed(boundSnapshot(6)), s = setup(6); let resolve!: (v: StudioGraphRecord) => void; s.client.graphs.get.mockImplementationOnce(() => new Promise<StudioGraphRecord>(r => { resolve = r; })); const view = await mounted(s.props); let pending!: Promise<void>, duplicate!: Promise<void>;
  act(() => { const callback = view.result.current.recoverLocalDraft; pending = callback(); duplicate = callback(); }); await waitFor(() => expect(resolve).toBeTypeOf('function')); expect(s.client.overview).toHaveBeenCalledTimes(1);
  const other = boundSnapshot(6); other.definition.title = '另一页面的子图草稿'; const changed = seed(other); expect(changed).not.toBe(raw);
  await act(async () => { resolve(s.child); await Promise.all([pending, duplicate]); }); expect(s.client.graphs.get).toHaveBeenCalledTimes(2); expect(localStorage.getItem(key)).toBe(changed); expect(view.result.current.recoveryError).toContain('其他页面已更新'); expect(view.result.current.draft.schema_version).toBe(1);
});
function boardSource() {
  const s = setup(5), board = structuredClone(rawBoard) as unknown as StoryboardReceipt, shot = board.shots[0], d = boundDefinition(5);
  d.nodes.push({ id: 'board-source', definition_id: 'storyboard_plan', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { document_snapshot: board.document_snapshot } }, { id: 'shot-source', definition_id: 'storyboard_shot', definition_version: 1, enabled: true, position: { x: 100, y: 0 }, parameters: { shot_id: shot.shot_id, shot_version: shot.shot_version, shot_digest: shot.shot_digest } });
  d.edges.push({ id: 'board-shot', source_node_id: 'board-source', source_port: 'storyboard', target_node_id: 'shot-source', target_port: 'storyboard' }, { id: 'shot-video', source_node_id: 'shot-source', source_port: 'shot', target_node_id: 'video-1', target_port: 'shot' });
  s.documents.push({ ...board.document_snapshot, title: '已保存分镜', mode: 'STORYBOARD' }, ...board.director_sources.map(p => ({ ...p, title: '原导演', mode: 'DIRECTOR' as const }))); s.boards.set(board.document_snapshot.id, board);
  return { ...s, definition: d, board };
}
it('revalidates planning and exact shot pins without reviving cached approval; an unapproved current shot remains authoring', async () => {
  const s = boardSource(); s.board.approved = false; await expect(s.verify(s.definition)).resolves.toBeUndefined(); expect(s.client.graphs.videoStoryboard).toHaveBeenCalledTimes(2); expect(s.client.graphs.action).not.toHaveBeenCalled(); expect(JSON.stringify(s.definition)).not.toContain('approved');
  s.board.shots[0].shot_digest = 'f'.repeat(64); await expect(s.verify(s.definition)).rejects.toThrow();
});
it.each(['document', 'director-parent', 'shot-missing', 'detached-shot'] as const)('planning source %s cannot be silently updated on recovery', async mode => {
  const s = boardSource();
  if (mode === 'document') s.documents[0].version++; else if (mode === 'director-parent') s.board.director_sources.push({ id: 'unreadable-director', version: 1, digest: 'a'.repeat(64) }); else if (mode === 'shot-missing') s.board.shots = []; else s.definition.edges = s.definition.edges.filter(e => e.id !== 'board-shot');
  await expect(s.verify(s.definition)).rejects.toThrow(); expect(s.client.graphs.action).not.toHaveBeenCalled();
});
it('schema4 production metadata uses the original production catalog and permits a not-yet-selected shot only as local input', async () => {
  const s = setup(4), d = boundDefinition(4); d.nodes.push({ id: 'pending-shot', definition_id: 'storyboard_prompt', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { shot_id: '' } });
  expect(() => checkedStudioGraphDraft(d)).toThrow(); const cached = checkedLocalGraphDefinition(d); expect(cached.nodes.at(-1)!.parameters.shot_id).toBe(''); await readBoundDraftCatalog(s.props.client, cached, () => true); expect(s.client.graphs.productionCatalog).toHaveBeenCalledTimes(1); await expect(s.verify(cached)).resolves.toBeUndefined();
});
function timelineSource() {
  const s = setup(3), d = boundDefinition(3), old = { id: 'old-video', kind: 'ASSET' as const, asset_kind: 'video' as const, version: 1, digest: 'e'.repeat(64) }, added = { id: 'new-video', kind: 'ASSET' as const, asset_kind: 'video' as const, version: 2, digest: 'f'.repeat(64) };
  const row: StudioTimelineRow = { id: 'timeline', version: 2, timeline_digest: 'd'.repeat(64), title: '已有时间线', created_at: '2026-10-20', updated_at: '2026-10-20', timeline: { duration_ms: 1000, width: 64, height: 64, fps: 24, tracks: [{ id: 'track', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'clip', source_snapshot: old, start_ms: 0, in_ms: 0, out_ms: 500 }] }], captions: [] } };
  d.nodes.push({ id: 'export', definition_id: 'timeline_export', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { timeline_snapshot: { id: row.id, version: row.version, digest: row.timeline_digest }, source_bindings: [], edit_operations: [{ op: 'clip.insert', track_id: 'track', clip: { id: 'added', source_snapshot: added, start_ms: 500, in_ms: 0, out_ms: 500 } }], export_profile: { preset: 'REVIEW_MP4' } } });
  s.timelines.set(row.id, row); for (const p of [old, added]) s.assets.set(p.id, { id: p.id, novel_id: boundOwner.projectId, branch_id: null, version: p.version, sha256: p.digest, kind: p.asset_kind, deleted_at: null } as unknown as StudioAsset);
  return { ...s, definition: d, row };
}
it('checks Graph timeline snapshot and every declared old/edit asset pin without replaying timeline operations', async () => {
  const s = timelineSource(); await expect(s.verify(s.definition)).resolves.toBeUndefined(); expect(s.client.graphs.graphTimelineGet).toHaveBeenCalledTimes(2); expect(s.client.asset.mock.calls.map(c => c[0])).toEqual(['old-video', 'new-video', 'old-video', 'new-video']); expect(s.client.graphs.action).not.toHaveBeenCalled();
  s.assets.get('new-video')!.version++; await expect(s.verify(s.definition)).rejects.toThrow();
});
it('keeps conservative timeline source boundary: stale snapshot or even an unapplied removed reference is not adopted', async () => {
  const s = timelineSource(); s.row.version++; await expect(s.verify(s.definition)).rejects.toThrow(); s.row.version--; s.assets.delete('old-video'); s.definition.nodes.at(-1)!.parameters.edit_operations!.push({ op: 'clip.remove', clip_id: 'clip', ripple: false }); await expect(s.verify(s.definition)).rejects.toThrow();
});
it('a fresh asset cannot authorize a changed immutable saved Graph binding', async () => {
  const value = boundSnapshot(4), s = setup(4); value.base = { id: s.graph.id, version: 2, definition_digest: s.graph.definition_digest, execution_digest: s.graph.execution_digest }; value.definition.nodes[0].parameters.version = 3; s.assets.get('source')!.version = 3; const raw = seed(value), view = await mounted(s.props);
  await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.recoveryError).toContain('固定来源或子图拓扑'); expect(localStorage.getItem(key)).toBe(raw); expect(view.result.current.draft.schema_version).toBe(1);
});

it.each([3, 4, 5, 6] as const)('schema%s unsaved UNKNOWN create keeps its original request and source pins for one explicit original same-key retry', async schema => {
  const value = boundSnapshot(schema), s = setup(schema); value.uncertain = true; const raw = seed(value), view = await mounted(s.props); await act(async () => view.result.current.recoverLocalDraft()); expect(view.result.current.blocked).toBe(true); expect(s.client.graphs.create).not.toHaveBeenCalled();
  await act(async () => view.result.current.save()); expect(s.client.graphs.create).not.toHaveBeenCalled(); await act(async () => view.result.current.save(true)); expect(s.client.graphs.create).toHaveBeenCalledTimes(1); expect(s.client.graphs.create).toHaveBeenCalledWith({ request_id: boundRequest, expected_version: 0, definition: readStudioGraphLocalDraft(raw, boundOwner).definition }); expect(s.client.graphs.createRun).not.toHaveBeenCalled();
});
