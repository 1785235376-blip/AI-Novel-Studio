// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { DirectorModelControls } from './DirectorModelControls';
import { GraphDirectorProposalReview } from './GraphDirectorProposalReview';
import { AIDirectorPanel } from './AIDirectorPanel';
import { creativeClient, STORYBOARD_SOURCE_CONTRACT, type DirectorProposal } from './client';
import { newDocument, newScene, newShot, type CreativeDocument } from './types';

const source: CreativeDocument = { ...newDocument('STORYBOARD', 'chapter'), id: 'board', title: 'Authored board', version: 7, status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {}, scenes: [{ ...newScene(1, 'chapter'), id: 'scene', action: 'Authored scene' }], shots: [{ ...newShot(9, 'scene'), id: 'last', frame_prompt: 'Authored last' }, { ...newShot(3, 'scene'), id: 'first', frame_prompt: 'Authored first' }] };
function proposal(): DirectorProposal {
  const shots = [...source.shots].sort((a, b) => a.number - b.number);
  return { id: 'proposal', version: 1, status: 'NEEDS_REVIEW', source_document_id: 'board', source_version: 7, source_digest: 'a'.repeat(64), title: 'Board direction', output_digest: 'digest', director_notes: shots.map(shot => ({ id: `note-${shot.id}`, scene_id: shot.scene_id, number: shot.number, note: '', shot_size: shot.shot_size, camera_angle: shot.camera_angle, camera_motion: shot.camera_motion, duration_seconds: shot.duration_seconds, emotion: '', pacing: '', performance: '', blocking: '' })), provenance: { source_mode: 'STORYBOARD', model_called: false, source_shots: shots.map(shot => ({ source_shot_id: shot.id, note_id: `note-${shot.id}`, scene_id: shot.scene_id, source_number: shot.number, source_shot: shot, copied_fields: ['camera_angle'], suggested_fields: ['pacing'], retained_source_only_fields: ['sound'] })) } };
}
function preview(): DirectorProposal {
  const row = proposal(), source_mapping = row.provenance.source_shots!.map(({ source_shot_id, note_id, scene_id, source_number }) => ({ source_shot_id, note_id, scene_id, source_number }));
  const instruction = STORYBOARD_SOURCE_CONTRACT + '\n' + JSON.stringify({ contract: STORYBOARD_SOURCE_CONTRACT, source_document_id: source.id, source_version: source.version, source_digest: row.source_digest, storyboard: { title: source.title, scenes: source.scenes, shots: [...source.shots].sort((a, b) => a.number - b.number) }, source_mapping });
  return { ...row, version: 2, model_preview: { preview_digest: 'b'.repeat(64), execution_available: true, model_called: false, allow_cloud_fallback: false, automatic_retry: false, timeout_seconds: 30, max_output_bytes: 128000, source_strategy: 'EXACT_CREATIVE_STORYBOARD_SHOTS_AND_SCENES_NO_IMPLICIT_CONTEXT', source_contract: STORYBOARD_SOURCE_CONTRACT, source_mode: 'STORYBOARD', source_document_id: source.id, source_version: source.version, input_digest: row.source_digest, source_mapping, token_fit_guaranteed: false, author: { instruction }, request: { prompt: instruction }, broker: { chosen: { provider_id: 'local', model_id: 'model', price: { reserve_microusd: 0 } } } } };
}
const support = { storyboard_source_contract: STORYBOARD_SOURCE_CONTRACT, storyboard_preview_suffix: 'storyboard-preview', storyboard_dispatch_suffix: 'storyboard-dispatch', token_fit_guaranteed: false };
const route = { route_id: 'route', provider_id: 'local', model_id: 'model', synthetic: false, available: true, reasons: [] };
function api() {
  return { modelCapabilities: vi.fn().mockResolvedValue(support), modelRoutes: vi.fn().mockResolvedValue({ items: [route] }), previewStoryboardModel: vi.fn().mockResolvedValue(preview()), dispatchStoryboardModel: vi.fn().mockResolvedValue({ ...preview(), version: 3, status: 'GENERATING', director_notes: [], model_execution: { source_contract: STORYBOARD_SOURCE_CONTRACT, preview_digest: 'b'.repeat(64), job_id: 'job', status: 'QUEUED', model_called: false, receipt_state: 'PENDING', usage_state: 'PENDING' } }), previewModel: vi.fn(), dispatchModel: vi.fn(), refreshModel: vi.fn(), cancelProposal: vi.fn() };
}
const ready = () => screen.findByRole('button', { name: '预览分镜模型输入' });
const consent = () => screen.getByLabelText('已核对完整分镜输入和固定映射，允许本地调用一次');
const dispatch = () => screen.getByRole('button', { name: '确认调用分镜本地模型' });
function mount(client = api(), initial = proposal()) {
  function Harness() { const [row, setRow] = useState(initial); return <DirectorModelControls client={client} proposal={row} source={source} disabled={false} run={async action => { try { await action(); } catch { /* Mock the parent uncertain-result owner. */ } }} onUpdate={setRow} />; }
  return { client, view: render(<Harness />) };
}
function retained<T>(element: HTMLElement, name: string): T {
  const key = Object.keys(element).find(key => key.startsWith('__reactProps$'))!;
  return (element as unknown as Record<string, Record<string, T>>)[key][name];
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('requires advertised support, exact complete input and one-call consent without automatic calls', async () => {
  const { client } = mount(); await ready();
  expect(client.previewStoryboardModel).not.toHaveBeenCalled(); expect(client.dispatchStoryboardModel).not.toHaveBeenCalled();
  fireEvent.click(await ready()); await screen.findByText('预览尚未调用模型');
  expect(screen.getByText(/不保证适合模型 token 窗口/)).toBeTruthy();
  const displayed = JSON.parse(screen.getByText(/STORYBOARD_SHOT_CONTEXT_V1/, { selector: 'pre' }).textContent!);
  expect(displayed.request).toEqual(preview().model_preview!.request);
  expect(displayed.source_mapping).toEqual(preview().model_preview!.source_mapping);
  const authored = JSON.parse(displayed.request.prompt.slice(STORYBOARD_SOURCE_CONTRACT.length + 1));
  expect(authored.storyboard).toEqual({ title: source.title, scenes: source.scenes, shots: [...source.shots].sort((a, b) => a.number - b.number) });
  expect((dispatch() as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(consent()); const click = retained<() => void>(dispatch(), 'onClick');
  expect((dispatch() as HTMLButtonElement).disabled).toBe(false);
  act(() => { click(); click(); });
  expect(client.dispatchStoryboardModel).toHaveBeenCalledTimes(1);
  await screen.findByText('任务：job');
  expect(client.dispatchStoryboardModel).toHaveBeenCalledTimes(1); expect(client.previewModel).not.toHaveBeenCalled(); expect(client.dispatchModel).not.toHaveBeenCalled();
});

it('admits a normal DOM dispatch click after direct-owner preview and consent', async () => {
  const { client } = mount(); fireEvent.click(await ready()); await screen.findByText('预览尚未调用模型');
  fireEvent.click(consent()); expect((dispatch() as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(dispatch()); expect(client.dispatchStoryboardModel).toHaveBeenCalledTimes(1);
  await screen.findByText('任务：job');
});

it.each(['missing', 'unknown', 'unsupported endpoint'] as const)('fails closed for %s capability without route reads', async failure => {
  const client = api();
  if (failure === 'unsupported endpoint') client.modelCapabilities.mockRejectedValue(new Error('404'));
  else client.modelCapabilities.mockResolvedValue(failure === 'missing' ? {} : { ...support, storyboard_source_contract: 'UNKNOWN' });
  mount(client); await screen.findByText(/当前仅支持 RULE_ASSISTED/);
  expect(client.modelRoutes).not.toHaveBeenCalled(); expect(client.previewStoryboardModel).not.toHaveBeenCalled();
});

it.each(['contract', 'source id', 'version', 'digest', 'proposal version', 'preview digest', 'mapping', 'authored shot', 'truncated request'] as const)('rejects %s mismatch in preview without enabling dispatch', async mismatch => {
  const client = api(), row = preview(), model = row.model_preview!;
  if (mismatch === 'proposal version') row.version = 0;
  if (mismatch === 'preview digest') model.preview_digest = 'malformed';
  if (mismatch === 'contract') model.source_contract = 'UNKNOWN';
  if (mismatch === 'source id') model.source_document_id = 'other';
  if (mismatch === 'version') model.source_version = 8;
  if (mismatch === 'digest') model.input_digest = 'b'.repeat(64);
  if (mismatch === 'mapping') model.source_mapping!.reverse();
  if (mismatch === 'authored shot') row.provenance.source_shots![0].source_shot = { ...row.provenance.source_shots![0].source_shot, frame_prompt: 'Changed' };
  if (mismatch === 'truncated request') model.request.prompt = 'Partial request';
  client.previewStoryboardModel.mockResolvedValue(row); mount(client); fireEvent.click(await ready());
  await screen.findByText(/模型回执来源或契约不一致/); expect(client.dispatchStoryboardModel).not.toHaveBeenCalled(); expect(screen.queryByRole('button', { name: '确认调用分镜本地模型' })).toBeNull();
});

it('does not invent chapter anchors for source-independent boards', async () => {
  const client = api(); render(<DirectorModelControls client={client} proposal={proposal()} source={{ ...source, source_independent: true, source_chapter_ids: [] }} disabled={false} run={async action => action()} onUpdate={() => {}} />);
  await screen.findByText(/分镜缺少章节锚点/); expect(screen.queryByRole('button', { name: '预览分镜模型输入' })).toBeNull();
});

it.each(['unmount', 'source ABA', 'source version', 'permission', 'client ABA'] as const)('retires retained model actions after %s', async retirement => {
  const client = api(), props = { client, proposal: preview(), source, disabled: false, run: async (action: () => Promise<void>) => action(), onUpdate: vi.fn() };
  const view = render(<DirectorModelControls {...props} />); await ready(); fireEvent.click(consent());
  const click = retained<() => void>(dispatch(), 'onClick');
  if (retirement === 'unmount') view.unmount();
  else if (retirement === 'permission') view.rerender(<DirectorModelControls {...props} disabled />);
  else if (retirement === 'source version') view.rerender(<DirectorModelControls {...props} source={{ ...source, version: 8 }} />);
  else if (retirement === 'source ABA') { view.rerender(<DirectorModelControls {...props} source={{ ...source, id: 'other' }} />); view.rerender(<DirectorModelControls {...props} />); }
  else { view.rerender(<DirectorModelControls {...props} client={api()} />); view.rerender(<DirectorModelControls {...props} />); }
  act(() => click()); expect(client.dispatchStoryboardModel).not.toHaveBeenCalled();
});

it('retires consent synchronously when revoked before a paint', async () => {
  mount(api(), preview()); await ready(); fireEvent.click(consent());
  const click = retained<() => void>(dispatch(), 'onClick'), revoke = retained<(event: { target: { checked: boolean } }) => void>(consent(), 'onChange');
  act(() => { revoke({ target: { checked: false } }); click(); });
  expect((dispatch() as HTMLButtonElement).disabled).toBe(true);
});

it.each(['unmount', 'source ABA', 'client ABA'] as const)('ignores late preview completion after %s', async retirement => {
  const client = api(); let resolve!: (row: DirectorProposal) => void;
  client.previewStoryboardModel.mockReturnValue(new Promise<DirectorProposal>(yes => { resolve = yes; }));
  const props = { client, proposal: proposal(), source, disabled: false, run: async (action: () => Promise<void>) => action(), onUpdate: vi.fn() };
  const view = render(<DirectorModelControls {...props} />); fireEvent.click(await ready());
  if (retirement === 'unmount') view.unmount();
  else if (retirement === 'source ABA') { view.rerender(<DirectorModelControls {...props} source={{ ...source, id: 'other' }} />); view.rerender(<DirectorModelControls {...props} />); }
  else { view.rerender(<DirectorModelControls {...props} client={api()} />); view.rerender(<DirectorModelControls {...props} />); }
  await act(async () => resolve(preview())); expect(props.onUpdate).not.toHaveBeenCalled();
});

it('uses additive source contracts on both HTTP payloads and leaves screenplay bodies unchanged', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => preview() }); vi.stubGlobal('fetch', fetchMock);
  const client = creativeClient('novel', { sessionToken: 'session' });
  await client.previewStoryboardModel(proposal(), 'route'); await client.dispatchStoryboardModel(preview());
  await client.previewModel(proposal(), 'route'); await client.dispatchModel(preview());
  const calls = fetchMock.mock.calls;
  expect(calls.map(([url]) => String(url).split('/').pop())).toEqual(['storyboard-preview', 'storyboard-dispatch', 'preview', 'dispatch']);
  expect(calls.map(([, init]) => JSON.parse(init.body))).toEqual([
    { expected_version: 1, route_id: 'route', source_contract: STORYBOARD_SOURCE_CONTRACT },
    { expected_version: 2, reviewed_preview_digest: 'b'.repeat(64), source_contract: STORYBOARD_SOURCE_CONTRACT },
    { expected_version: 1, route_id: 'route' }, { expected_version: 2, reviewed_preview_digest: 'b'.repeat(64) },
  ]);
});

it('labels rule seed field records independently after model refresh', async () => {
  const row = proposal(); row.provenance.model_called = true;
  const client = { ...api(), proposals: vi.fn().mockResolvedValue({ items: [row] }), proposal: vi.fn(), propose: vi.fn(), review: vi.fn(), get: vi.fn() };
  render(<AIDirectorPanel client={client} documents={[source]} canMutate onDocument={() => {}} onDenied={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: /Board direction/ }));
  expect(screen.getByText(/不代表模型候选的字段来源/)).toBeTruthy(); expect(screen.getAllByText(/最初规则种子复制字段/)).toHaveLength(2);
});

it('does not let a late capability response enable a retired client', async () => {
  const client = api(); let resolve!: (value: typeof support) => void;
  client.modelCapabilities.mockReturnValue(new Promise<typeof support>(yes => { resolve = yes; }));
  const props = { client, proposal: proposal(), source, disabled: false, run: async (action: () => Promise<void>) => action(), onUpdate: vi.fn() };
  const view = render(<DirectorModelControls {...props} />), replacement = api(); replacement.modelCapabilities.mockResolvedValue({});
  view.rerender(<DirectorModelControls {...props} client={replacement} />);
  await screen.findByText(/当前仅支持 RULE_ASSISTED/); await act(async () => resolve(support));
  expect(client.modelRoutes).not.toHaveBeenCalled(); expect(screen.queryByRole('button', { name: '预览分镜模型输入' })).toBeNull();
});

it('does not relabel a storyboard as screenplay when provenance is missing', () => {
  const client = api(), row = proposal(); delete row.provenance.source_mode;
  render(<DirectorModelControls client={client} proposal={row} source={source} disabled={false} run={async action => action()} onUpdate={() => {}} />);
  expect(screen.getByText(/来源类型记录不一致或缺失/)).toBeTruthy(); expect(client.modelRoutes).not.toHaveBeenCalled();
});

it('parent source authority retirement rejects a late model response without replacing the review', async () => {
  const row = proposal(), model = api(); let resolve!: (value: DirectorProposal) => void;
  model.previewStoryboardModel.mockReturnValue(new Promise<DirectorProposal>(yes => { resolve = yes; }));
  const client = { ...model, proposals: vi.fn().mockResolvedValue({ items: [row] }), proposal: vi.fn(), propose: vi.fn(), review: vi.fn(), get: vi.fn() };
  const props = { client, documents: [source], canMutate: true, onDocument: vi.fn(), onDenied: vi.fn() };
  const view = render(<AIDirectorPanel {...props} />); fireEvent.click(await screen.findByRole('button', { name: /Board direction/ })); fireEvent.click(await ready());
  view.rerender(<AIDirectorPanel {...props} canMutate={false} />);
  await act(async () => resolve({ ...preview(), title: 'Stale changed title' }));
  expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Board direction');
  expect(props.onDocument).not.toHaveBeenCalled(); expect(client.dispatchStoryboardModel).not.toHaveBeenCalled();
});

function graphClient() {
  return { ...api(), list: vi.fn().mockResolvedValue({ items: [source] }), proposals: vi.fn().mockResolvedValue({ items: [proposal()] }), proposal: vi.fn(), propose: vi.fn(), review: vi.fn(), get: vi.fn() };
}
function graphMount(client = graphClient()) {
  const mutate = vi.fn();
  function Harness() {
    const [busy, setBusy] = useState(false);
    return <GraphDirectorProposalReview client={client} active canMutate busy={busy} isCurrent={() => true} read={work => work()} mutate={async work => { mutate(); setBusy(true); try { return await work(); } finally { setBusy(false); } }} onPendingChange={() => {}} onDocument={() => {}} onDenied={() => {}} />;
  }
  return { ...render(<Harness />), mutate, client };
}
async function openGraph() {
  fireEvent.click(screen.getByRole('button', { name: '从已保存分镜打开导演建议审核' }));
  fireEvent.click(await screen.findByRole('button', { name: /Board direction/ })); await ready();
}
it('actual graph owner forwards explicit model calls through mutation leases despite own busy renders', async () => {
  const { client, mutate } = graphMount(); await openGraph();
  fireEvent.click(await ready()); await screen.findByText('预览尚未调用模型');
  fireEvent.click(consent()); fireEvent.click(dispatch()); await screen.findByText('任务：job');
  expect(client.modelCapabilities).toHaveBeenCalled(); expect(client.previewStoryboardModel).toHaveBeenCalledTimes(1); expect(client.dispatchStoryboardModel).toHaveBeenCalledTimes(1); expect(mutate).toHaveBeenCalledTimes(2);
  const candidates = { ...preview(), version: 4, provenance: { ...proposal().provenance, model_called: true }, model_execution: { source_contract: STORYBOARD_SOURCE_CONTRACT, preview_digest: 'b'.repeat(64), job_id: 'job', status: 'CANDIDATES', model_called: true, receipt_state: 'RECORDED', usage_state: 'RECORDED' } };
  client.refreshModel.mockResolvedValue(candidates);
  fireEvent.click(screen.getByRole('button', { name: '核对模型结果' })); await screen.findByText(/不代表模型候选的字段来源/);
  expect(client.refreshModel).toHaveBeenCalledTimes(1); expect(mutate).toHaveBeenCalledTimes(3); expect(client.review).not.toHaveBeenCalled();
});

it.each(['CANCELLED', 'MODEL_UNAVAILABLE'] as const)('adopts source-bound empty-note %s receipts through the graph owner', async status => {
  const { client } = graphMount(); await openGraph(); fireEvent.click(await ready()); await screen.findByText('预览尚未调用模型'); fireEvent.click(consent()); fireEvent.click(dispatch()); await screen.findByText('任务：job');
  const receipt = { ...preview(), version: 4, status, director_notes: [], model_execution: { source_contract: STORYBOARD_SOURCE_CONTRACT, preview_digest: 'b'.repeat(64), job_id: 'job', status: status === 'CANCELLED' ? 'CANCELLED' : 'DISCARDED', model_called: false, receipt_state: 'RECORDED', usage_state: 'RECORDED' } };
  if (status === 'CANCELLED') { client.cancelProposal.mockResolvedValue(receipt); fireEvent.click(screen.getByRole('button', { name: '取消模型任务' })); }
  else { client.refreshModel.mockResolvedValue(receipt); fireEvent.click(screen.getByRole('button', { name: '核对模型结果' })); }
  await waitFor(() => expect(screen.getByRole('button', { name: new RegExp(`Board direction.*${status}`) })).toBeTruthy());
  expect(screen.queryByRole('button', { name: '重新读取建议状态' })).toBeNull(); expect(screen.queryByText(/模型回执来源或契约不一致/)).toBeNull();
});

it('keeps malformed successful POST receipts under the original uncertain-result owner', async () => {
  const { client } = graphMount(); await openGraph();
  client.previewStoryboardModel.mockResolvedValue({ ...preview(), source_version: 999 });
  fireEvent.click(await ready()); await screen.findByRole('button', { name: '重新读取建议状态' });
  expect(screen.getByText(/操作结果需核对。当前审核内容已保留/)).toBeTruthy(); expect(client.dispatchStoryboardModel).not.toHaveBeenCalled();
  expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Board direction');
});

it.each(['missing request', 'missing broker', 'malformed digest', 'missing instruction', 'object timeout', 'object provider', 'object model', 'nonzero price'] as const)('renders a safe warning for queued %s preview without admission', async corruption => {
  const row = preview(), model = row.model_preview!;
  if (corruption === 'missing request') Object.assign(model, { request: null });
  if (corruption === 'missing broker') Object.assign(model, { broker: null });
  if (corruption === 'malformed digest') model.preview_digest = 'not-sha256';
  if (corruption === 'missing instruction') delete model.author;
  if (corruption === 'object timeout') Object.assign(model, { timeout_seconds: {} });
  if (corruption === 'object provider') Object.assign(model.broker.chosen!, { provider_id: {} });
  if (corruption === 'object model') Object.assign(model.broker.chosen!, { model_id: {} });
  if (corruption === 'nonzero price') model.broker.chosen!.price!.reserve_microusd = 1;
  const { client } = mount(api(), row); await ready();
  expect(screen.getByText(/预览来源或契约不一致/)).toBeTruthy(); expect((consent() as HTMLInputElement).disabled).toBe(true); expect((dispatch() as HTMLButtonElement).disabled).toBe(true);
  expect(client.dispatchStoryboardModel).not.toHaveBeenCalled();
});

it('rejects a queued proposal with an unsafe version before preview', async () => {
  const row = proposal(); row.version = Number.MAX_SAFE_INTEGER + 1;
  const { client } = mount(api(), row); await screen.findByText(/来源标识、版本或逐镜头映射不一致/);
  expect(client.previewStoryboardModel).not.toHaveBeenCalled();
});

it('does not consent to a preview omitting the approved visual target', async () => {
  const row = preview(); row.visual_target = { style: 'Authored style', atmosphere: '', reference_works: [], color: '', rhythm: '' };
  mount(api(), row); await ready(); expect((consent() as HTMLInputElement).disabled).toBe(true);
});

it('matches the backend 20000 Unicode-code-point instruction limit', async () => {
  const row = preview(), model = row.model_preview!, prefix = STORYBOARD_SOURCE_CONTRACT + '\n';
  const data = JSON.parse(model.author!.instruction!.slice(prefix.length)); data.task = '';
  const remaining = 20000 - Array.from(prefix + JSON.stringify(data)).length; data.task = '🎬'.repeat(remaining);
  model.author!.instruction = prefix + JSON.stringify(data); model.request.prompt = model.author!.instruction;
  expect(Array.from(model.author!.instruction).length).toBe(20000); expect(model.author!.instruction.length).toBeGreaterThan(20000);
  mount(api(), row); await ready(); expect((consent() as HTMLInputElement).disabled).toBe(false);
});

it.each([null, {}, { items: null }, { items: [{ ...route, provider_id: {} }] }, { items: [{ ...route, reasons: null }] }])('fails closed for malformed route catalogs', async catalog => {
  const client = api(); client.modelRoutes.mockResolvedValue(catalog); mount(client);
  await screen.findByText(/当前仅支持 RULE_ASSISTED/); expect(screen.queryByRole('button', { name: '预览分镜模型输入' })).toBeNull();
  expect(client.previewStoryboardModel).not.toHaveBeenCalled(); expect(client.dispatchStoryboardModel).not.toHaveBeenCalled();
});
