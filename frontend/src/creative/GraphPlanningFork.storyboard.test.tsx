// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GraphPlanningFork } from './GraphPlanningFork';
import { planningSourceFork, planningSourceReferences, planningStoryboardSourceFork } from './graphPlanningForkHelpers';
import { checkedStudioGraphDraft } from './studioGraphClient';
import { blankGraph } from './graphDraft';
import { buildStoryboardVideoBranches } from './graphStoryboardStarterHelpers';
import { checkedStoryboardReceipt, type StoryboardReceipt } from './studioStoryboardContract';
import type { PlanningDocument } from './studioProductionGraphContract';
import type { StudioGraphCatalog, StudioGraphCreateInput, StudioGraphRecord } from './studioGraphTypes';
import { imageGraphRecord } from './studioImageGraph.testFixtures';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioClient } from './studioClient';
import catalogJson from './fixtures/phase5.capture.video-catalog.json';
import receiptJson from './fixtures/phase5.capture.storyboard-video-approved.json';

afterEach(cleanup);
const read = async <T,>(work: () => Promise<T>) => work();
function fixture(count = 2) {
  const { video_result: _video, ...template } = receiptJson.shots[0];
  const old = checkedStoryboardReceipt({ ...receiptJson, shots: Array.from({ length: count }, (_, index) => ({
    ...template, image_asset: null, shot_id: `source-shot-${index + 1}`, shot_digest: String(index + 1).repeat(64),
    shot: { ...template.shot, id: `source-shot-${index + 1}`, number: index + 1,
      continuity: { characters: 'visitor', outfit: 'blue jacket', environment: '', camera: '' } },
  })) });
  let serial = 0;
  const draft = buildStoryboardVideoBranches({ ...blankGraph(), schema_version: 5 }, catalogJson as unknown as StudioGraphCatalog,
    old, old.shots.map(shot => shot.shot_id), prefix => `${prefix}-${++serial}`);
  for (const node of draft.nodes.filter(node => node.definition_id === 'video_generate'))
    Object.assign(node.parameters, { provider_id: 'fixture-provider', model_id: 'fixture-model', prompt: 'Keep author prompt',
      parameters: { seed: 17 }, license_note: 'Keep authored license', allow_cloud: false });
  draft.presentation = { comment: 'Keep graph annotation' }; draft.viewport = { x: 20, y: 30, zoom: 1.2 };
  if (count === 4) draft.nodes.filter(node => node.definition_id === 'storyboard_shot')[3].enabled = false;
  const receipt = structuredClone(old); receipt.document_snapshot.version++; receipt.document_snapshot.digest = 'b'.repeat(64);
  receipt.shots[0].shot_version++; receipt.shots[0].shot_digest = 'c'.repeat(64); receipt.shots[0].shot.lens = '35mm';
  const document: PlanningDocument = { ...receipt.document_snapshot, title: 'Current approved board', mode: 'STORYBOARD' };
  const nodeId = draft.nodes[0].id;
  return { old, draft, receipt, document, nodeId, parents: [nodeId] };
}
const handler = (element: HTMLElement) => (element as any)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!].onClick;
const button = (name: string) => screen.getByRole('button', { name });
const inspect = () => fireEvent.click(button('核对更新来源用于独立新图'));
const confirm = () => fireEvent.click(screen.getByRole('checkbox', { name: '已核对全部文档及镜头 pin，确认准备独立新图草稿，保留原图' }));
const prepare = () => button('准备使用更新来源的独立草稿');

it.each([1, 4])('forks %i linked Shot pins from the exact approved receipt and preserves all other authored graph bytes', count => {
  const f = fixture(count), before = structuredClone(f.draft), receiptBefore = structuredClone(f.receipt);
  const oldOnly = planningSourceFork(f.draft, f.nodeId, f.document);
  expect(oldOnly.nodes[1].parameters.shot_digest).toBe(before.nodes[1].parameters.shot_digest);
  const result = planningStoryboardSourceFork(f.draft, f.nodeId, f.document, f.receipt, f.parents);
  const expected = structuredClone(before);
  expected.nodes[0].parameters.document_snapshot = { ...f.receipt.document_snapshot };
  for (const node of expected.nodes.filter(node => node.definition_id === 'storyboard_shot')) {
    const source = f.receipt.shots.find(shot => shot.shot_id === node.parameters.shot_id)!;
    node.parameters.shot_version = source.shot_version; node.parameters.shot_digest = source.shot_digest;
  }
  expect(result.definition).toEqual(expected); expect(result.shots).toHaveLength(count);
  expect(checkedStudioGraphDraft(result.definition)).toEqual(expected);
  expect(f.draft).toEqual(before); expect(f.receipt).toEqual(receiptBefore);
  if (count > 1) expect(result.shots[1].after.version).toBe(f.old.shots[1].shot_version); // Title/other-shot changes do not invent new versions.
});

it('refuses unapproved/mismatched/removed shots and more than four references without partial updates', () => {
  const f = fixture(), before = structuredClone(f.draft);
  for (const change of [
    (receipt: StoryboardReceipt) => { receipt.approved = false; },
    (receipt: StoryboardReceipt) => { receipt.document_snapshot.version++; },
    (receipt: StoryboardReceipt) => { receipt.document_snapshot.digest = 'e'.repeat(64); },
    (receipt: StoryboardReceipt) => { receipt.shots.shift(); },
  ]) {
    const receipt = structuredClone(f.receipt); change(receipt);
    expect(() => planningStoryboardSourceFork(f.draft, f.nodeId, f.document, receipt, f.parents)).toThrow();
  }
  const big = fixture(4); big.draft.nodes.push({ ...structuredClone(big.draft.nodes[1]), id: 'extra-shot' });
  big.draft.edges.push({ id: 'extra-link', source_node_id: big.nodeId, source_port: 'storyboard', target_node_id: 'extra-shot', target_port: 'storyboard' });
  expect(() => planningStoryboardSourceFork(big.draft, big.nodeId, big.document, big.receipt, big.parents)).toThrow(/1–4/);
  expect(f.draft).toEqual(before);
});

it('requires all old references for this document, matching by stable shot ID even after a reorder', () => {
  const f = fixture(); const parent = { ...structuredClone(f.draft.nodes[0]), id: 'second-board' };
  f.draft.nodes.push(parent); const secondShot = f.draft.nodes.filter(node => node.definition_id === 'storyboard_shot')[1];
  f.draft.edges.find(edge => edge.target_node_id === secondShot.id && edge.target_port === 'storyboard')!.source_node_id = parent.id;
  expect(() => planningStoryboardSourceFork(f.draft, f.nodeId, f.document, f.receipt, f.parents)).toThrow(/全部旧引用/);
  f.receipt.shots.reverse(); f.receipt.shots[0].shot.number = 1; f.receipt.shots[1].shot.number = 2;
  const result = planningStoryboardSourceFork(f.draft, f.nodeId, f.document, f.receipt, [f.nodeId, parent.id]);
  expect(result.documents).toHaveLength(2); expect(result.shots[0].after.digest).toBe('c'.repeat(64));
  expect(result.definition.edges).toEqual(f.draft.edges);
});

function props() {
  const f = fixture();
  return { ...f, scope: {}, pin: f.old.document_snapshot, mode: 'STORYBOARD' as const, definition: f.draft,
    references: planningSourceReferences(f.draft, f.nodeId), disabled: false, isCurrent: () => true, read,
    client: { planningDocuments: vi.fn(async () => ({ documents: [f.document] })), videoStoryboard: vi.fn(async () => f.receipt) }, prepare: vi.fn(() => true) };
}
async function loaded(p = props()) { const view = render(<GraphPlanningFork {...p} />); inspect(); await screen.findByLabelText('更新分镜与镜头 pin 预览'); return { p, view }; }

it('previews both pin levels, needs new human consent, and consumes original-owner preparation once without writes', async () => {
  const { p } = await loaded(); expect(p.prepare).not.toHaveBeenCalled();
  expect(screen.getByLabelText('更新分镜与镜头 pin 预览').textContent).toContain('c'.repeat(64));
  confirm(); const retained = handler(prepare());
  act(() => { confirm(); retained(); }); expect(p.prepare).not.toHaveBeenCalled();
  confirm(); const fresh = handler(prepare()); act(() => { fresh(); fresh(); });
  expect(p.prepare).toHaveBeenCalledTimes(1); expect(p.prepare).toHaveBeenCalledWith(p.document, p.scope, p.parents, p.receipt);
  expect(p.client.planningDocuments).toHaveBeenCalledTimes(1); expect(p.client.videoStoryboard).toHaveBeenCalledTimes(1);
});

it.each(['disabled', 'scope', 'definition'])('retires coupled old consent across %s ABA, including a later fresh confirmation', async key => {
  const { p, view } = await loaded(); confirm(); const retained = handler(prepare());
  view.rerender(<GraphPlanningFork {...p} {...(key === 'disabled' ? { disabled: true } : key === 'scope' ? { scope: {} } : { definition: structuredClone(p.definition) })} />);
  view.rerender(<GraphPlanningFork {...p} />); act(retained); expect(p.prepare).not.toHaveBeenCalled();
  inspect(); await screen.findByLabelText('更新分镜与镜头 pin 预览'); confirm(); act(retained); expect(p.prepare).not.toHaveBeenCalled();
  fireEvent.click(prepare()); expect(p.prepare).toHaveBeenCalledTimes(1);
});

it('permits busy toggles during its own read but refuses a prior client late receipt', async () => {
  const p = props(); let resolve!: (value: StoryboardReceipt) => void;
  p.client.videoStoryboard = vi.fn(() => new Promise<StoryboardReceipt>(done => { resolve = done; }));
  const view = render(<GraphPlanningFork {...p} />); inspect(); await waitFor(() => expect(p.client.videoStoryboard).toHaveBeenCalledTimes(1));
  view.rerender(<GraphPlanningFork {...p} disabled />); view.rerender(<GraphPlanningFork {...p} />);
  await act(async () => resolve(p.receipt)); await screen.findByLabelText('更新分镜与镜头 pin 预览'); confirm();
  fireEvent.click(prepare()); expect(p.prepare).toHaveBeenCalledTimes(1); view.unmount();
  const old = props(); let late!: (value: StoryboardReceipt) => void;
  old.client.videoStoryboard = vi.fn(() => new Promise<StoryboardReceipt>(done => { late = done; }));
  const nextView = render(<GraphPlanningFork {...old} />); inspect(); await waitFor(() => expect(old.client.videoStoryboard).toHaveBeenCalledTimes(1));
  const next = props(); nextView.rerender(<GraphPlanningFork {...next} />); inspect(); await screen.findByLabelText('更新分镜与镜头 pin 预览');
  await act(async () => late(old.receipt)); confirm(); fireEvent.click(prepare());
  expect(old.prepare).not.toHaveBeenCalled(); expect(next.prepare).toHaveBeenCalledTimes(1);
});

it('uses original independent staging and explicit create Save; an unbundled v5 callback cannot leave old shot pins', async () => {
  localStorage.clear(); const f = fixture(), original: StudioGraphRecord = { ...imageGraphRecord(), definition: f.draft,
    reference_states: [{ node_id: f.nodeId, state: 'STALE' }], can_edit: true };
  const create = vi.fn(async (body: StudioGraphCreateInput) => ({ ...structuredClone(original), id: 'new-fork', definition: checkedStudioGraphDraft(body.definition), reference_states: [{ node_id: f.nodeId, state: 'CURRENT' as const }] }));
  const save = vi.fn(), createRun = vi.fn();
  const client = { graphs: { catalog: vi.fn(async () => catalogJson), videoCatalog: vi.fn(async () => catalogJson),
    list: vi.fn(async () => ({ items: [structuredClone(original)] })), get: vi.fn(async () => structuredClone(original)), create, save, createRun } } as unknown as StudioClient;
  const base: StudioGraphEditorProps = { active: true, denied: false, identity: 'pin-fork-owner', client,
    canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read, mutate: read };
  const view = renderHook(extra => useStudioGraphEditorController({ ...base, ...extra }), { initialProps: {} as Partial<StudioGraphEditorProps> });
  await waitFor(() => expect(view.result.current.loading).toBe(false));
  await act(async () => view.result.current.open(original.id)); act(() => view.result.current.setSelected([f.nodeId]));
  act(() => expect(view.result.current.preparePlanningGraphFork(f.document, view.result.current.planningForkScope, f.parents)).toBe(false));
  expect(view.result.current.base?.id).toBe(original.id);
  act(() => expect(view.result.current.preparePlanningGraphFork(f.document, view.result.current.planningForkScope, f.parents, f.receipt)).toBe(true));
  expect(view.result.current.base).toBeUndefined(); expect(create).not.toHaveBeenCalled(); expect(save).not.toHaveBeenCalled();
  expect(view.result.current.draft.nodes[1].parameters.shot_digest).toBe('c'.repeat(64));
  await act(async () => view.result.current.save()); expect(create).toHaveBeenCalledTimes(1); expect(save).not.toHaveBeenCalled(); expect(createRun).not.toHaveBeenCalled();
  expect(create.mock.calls[0][0].definition).toEqual(planningStoryboardSourceFork(f.draft, f.nodeId, f.document, f.receipt, f.parents).definition);
  expect(original.definition).toEqual(f.draft);
});
