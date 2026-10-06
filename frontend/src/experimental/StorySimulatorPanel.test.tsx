// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { experimentalClient } from './api';
import { StorySimulatorPanel } from './StorySimulatorPanel';
import type { SimulatorRun } from './storySimulatorClient';

const chapter = { id: 'chapter-one', title: '雨夜', version: 3 } as Chapter;
const catalog = { chapters: [chapter], characters: [{ id: 'alice', name: '小林' }], planning_nodes: [{ id: 'node-one', title: '原有规划', version: 2, chapter_ids: [chapter.id] }], limits: { max_steps: 32, max_branches: 8, max_expansions: 256 }, model_configured: false };
const context = { chapter_id: chapter.id, character_id: 'alice', world_time: null, calendar: 'story', context_digest: 'a'.repeat(64), knowledge: [{ id: 'fact-one', version: 2, text: '钥匙能开门', category: 'KNOWN_FACT' }], goals: [], graph_links: [{ id: 'relation-one', version: 2, text: '钥匙能开门' }] };
const ready: SimulatorRun = { id: 'run-one', version: 1, status: 'READY', stale: false, chapter_id: chapter.id, source_version: 3, expansions: 0, limits: catalog.limits, model_called: false, limitations: ['不提供未来概率。'], routes: [{ id: 'route-1', title: '强行开门', cursor: 0, status: 'PENDING', steps: [], violations: [], unresolved_questions: [], motivation_hypothesis: '作者的忠诚假设', character_goal: '进城' }], provenance: { method: 'bounded-manual-transitions-v1', execution: 'DETERMINISTIC_MANUAL', source_versions: { [chapter.id]: { version: 3, digest: 'b'.repeat(64) } }, context_digest: context.context_digest, input_digest: 'c'.repeat(64) } };
const completed: SimulatorRun = { ...ready, version: 2, status: 'COMPLETED', expansions: 1, routes: [{ ...ready.routes![0], cursor: 1, status: 'COMPLETED', steps: [{ event_id: 'event-1', title: '试着开门', at: 1, applied: false, violations: [{ code: 'UNMET_PREREQUISITE', message: '事件前提尚未满足。' }], question: '钥匙在哪里？', foreshadowing_links: [] }], violations: [{ code: 'UNMET_PREREQUISITE', message: '事件前提尚未满足。' }], unresolved_questions: ['钥匙在哪里？'] }] };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = () => experimentalClient('novel-one', { sessionToken: 'session-one', scope: { workspaceId: 'workspace-one', projectId: 'novel-one', storylineId: 'story-one', branchId: 'branch-one' } });
function transport(initial?: SimulatorRun) {
  let row = initial;
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/context')) return reply(context);
    if (url.endsWith('/runs/run-one/step')) { row = completed; return reply(row); }
    if (url.endsWith('/runs/run-one/cancel')) { row = { ...ready, version: 2, status: 'CANCELLED' }; return reply(row); }
    if (url.endsWith('/runs/run-one/save')) { row = { ...completed, version: 3, routes: completed.routes!.map(r => ({ ...r, saved_proposal_id: 'proposal-one' })) }; return reply({ proposal_id: 'proposal-one', status: 'REVIEW', run_id: 'run-one' }); }
    if (url.endsWith('/runs/run-one')) return reply(row);
    if (url.endsWith('/runs') && init?.method === 'POST') { row = ready; return reply(row, 201); }
    if (url.endsWith('/runs')) return reply({ items: row ? [row] : [] });
    throw new Error(`Unhandled ${init?.method} ${url}`);
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function fill() {
  await screen.findByLabelText('推演来源：雨夜 · v3');
  fireEvent.change(screen.getByLabelText('推演人物'), { target: { value: 'alice' } });
  fireEvent.change(screen.getByLabelText('待审规划的目标节点'), { target: { value: 'node-one' } });
  fireEvent.click(screen.getByRole('button', { name: '读取并核对人物已知信息' }));
  await screen.findByRole('region', { name: '人物已知信息' });
  fireEvent.change(screen.getByLabelText('路线 1 名称'), { target: { value: '强行开门' } });
  fireEvent.change(screen.getByLabelText('路线 1 事件 1 名称'), { target: { value: '试着开门' } });
  fireEvent.change(screen.getByLabelText('路线 2 名称'), { target: { value: '等待向导' } });
  fireEvent.change(screen.getByLabelText('路线 2 事件 1 名称'), { target: { value: '等一会儿' } });
}
async function chooseRun() {
  await screen.findByLabelText('推演来源：雨夜 · v3');
  fireEvent.change(screen.getByLabelText('查看剧情推演记录'), { target: { value: 'run-one' } });
  await screen.findByRole('article', { name: '比较路线 强行开门' });
}
it('reads only on opening; builds explicit bounded manual inputs with captured authority and normalized fact lines', async () => {
  const fetch = transport(); vi.stubGlobal('fetch', fetch);
  render(<StrictMode><StorySimulatorPanel client={client()} chapter={chapter} /></StrictMode>);
  await screen.findByLabelText('推演来源：雨夜 · v3');
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  await fill();
  fireEvent.change(screen.getByLabelText('路线 1 事件 1 前提事实（每行一条）'), { target: { value: ' key\n\n map ' } });
  fireEvent.change(screen.getByLabelText('人物动机假设（不作为已证实事实）'), { target: { value: '作者假设' } });
  const create = screen.getByRole('button', { name: '保存输入并创建推演' }); fireEvent.click(create); fireEvent.click(create);
  await screen.findByRole('article', { name: '比较路线 强行开门' });
  const writes = fetch.mock.calls.filter(([url, init]) => url.endsWith('/runs') && init?.method === 'POST'); expect(writes).toHaveLength(1);
  const payload = JSON.parse(writes[0][1]!.body as string);
  expect(payload).toMatchObject({ model_budget: 0, model_id: null, world_time: null, expected_versions: { 'chapter-one': 3 }, expected_node_version: 2, context_digest: context.context_digest, motivation_hypothesis: '作者假设' });
  expect(payload.routes[0].events[0].requires).toEqual(['key', 'map']);
  expect(writes[0][1]!.headers).toMatchObject({ 'X-Session-Token': 'session-one', 'X-Branch-Id': 'branch-one' });
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/step'))).toBe(false);
});
it('compares violations and hypotheses, saves only REVIEW once and navigates to the existing planning authority', async () => {
  const fetch = transport(completed), navigate = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<StorySimulatorPanel client={client()} chapter={chapter} onNavigate={navigate} />); await chooseRun();
  expect(screen.getByText('动机假设：作者的忠诚假设')).toBeTruthy();
  expect(screen.getAllByText(/UNMET_PREREQUISITE/).length).toBeGreaterThan(0);
  const save = screen.getByRole('button', { name: '将所选路线另存为待审规划' }) as HTMLButtonElement; expect(save.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('选择路线 强行开门 另存待审规划'));
  fireEvent.click(screen.getByLabelText('已核对所选路线的违规、未决问题和动机假设，仅另存为待审规划'));
  fireEvent.click(save); fireEvent.click(save);
  await screen.findByRole('button', { name: '前往分层规划审核' });
  fireEvent.click(screen.getByRole('button', { name: '前往分层规划审核' }));
  expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'proposal-one', feature: 'advanced_planning_v2' });
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/save'))).toHaveLength(1);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/approve'))).toBe(false);
  expect(screen.getByText(/来源 chapter-one · v3/)).toBeTruthy();
});
it('advances explicitly, cancels explicitly, and stops offering expansion after cancellation', async () => {
  const fetch = transport(ready); vi.stubGlobal('fetch', fetch);
  render(<StorySimulatorPanel client={client()} chapter={chapter} />); await chooseRun();
  fireEvent.click(screen.getByRole('button', { name: '取消本次推演' }));
  await screen.findByText('取消后的记录不能继续或另存规划。上方输入仍可用于明确创建新推演。');
  expect((screen.getByRole('button', { name: '推进一步' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/step'))).toBe(false);
});
it('hides stale routes, receipts and actions instead of showing old knowledge', async () => {
  vi.stubGlobal('fetch', transport({ ...completed, stale: true }));
  render(<StorySimulatorPanel client={client()} chapter={chapter} />);
  await screen.findByLabelText('推演来源：雨夜 · v3'); fireEvent.change(screen.getByLabelText('查看剧情推演记录'), { target: { value: 'run-one' } });
  await screen.findByText(/旧来源的路线与证据已隐藏/);
  expect(screen.queryByRole('article', { name: '比较路线 强行开门' })).toBeNull();
  expect(screen.queryByText('作者的忠诚假设')).toBeNull(); expect(screen.queryByRole('button', { name: '推进一步' })).toBeNull();
});
it('preserves editable drafts on failure and requires recovery before retry', async () => {
  const base = transport(); vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/runs') && init?.method === 'POST' ? Promise.resolve(reply({ detail: { code: 'EXPERIMENTAL_SOURCE_STALE' } }, 409)) : base(url, init)));
  render(<StorySimulatorPanel client={client()} chapter={chapter} />); await fill();
  fireEvent.click(screen.getByRole('button', { name: '保存输入并创建推演' })); await screen.findByText(/EXPERIMENTAL_SOURCE_STALE/);
  expect((screen.getByLabelText('路线 1 名称') as HTMLInputElement).value).toBe('强行开门');
  expect((screen.getByRole('button', { name: '保存输入并创建推演' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '刷新推演与来源（保留输入）' })); await screen.findByLabelText('推演来源：雨夜 · v3');
  expect((screen.getByLabelText('路线 1 名称') as HTMLInputElement).value).toBe('强行开门');
});
it('ignores late context from an old session/branch and drops its saved inputs on scope switch', async () => {
  const base = transport(); let finish!: (r: Response) => void;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/context') ? new Promise<Response>(resolve => { finish = resolve; }) : base(url, init)));
  const view = render(<StorySimulatorPanel client={client()} chapter={chapter} />);
  await screen.findByLabelText('推演来源：雨夜 · v3'); fireEvent.change(screen.getByLabelText('推演人物'), { target: { value: 'alice' } }); fireEvent.click(screen.getByRole('button', { name: '读取并核对人物已知信息' }));
  view.rerender(<StorySimulatorPanel client={experimentalClient('novel-two', { sessionToken: 'new' })} />);
  await act(async () => finish(reply(context)));
  expect(screen.queryByRole('region', { name: '人物已知信息' })).toBeNull();
  expect(screen.queryByText('钥匙能开门')).toBeNull();
});
it('invalidates source-bound context immediately when the active chapter revision advances', async () => {
  vi.stubGlobal('fetch', transport()); const stable = client(); const view = render(<StorySimulatorPanel client={stable} chapter={chapter} />); await fill();
  view.rerender(<StorySimulatorPanel client={stable} chapter={{ ...chapter, version: 4 }} />);
  expect(screen.queryByRole('region', { name: '人物已知信息' })).toBeNull();
  expect((screen.getByRole('button', { name: '保存输入并创建推演' }) as HTMLButtonElement).disabled).toBe(true);
});
it('does not block explicit source rebasing when catalog is newer than an older open editor snapshot', async () => {
  const base = transport(); vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/catalog') ? Promise.resolve(reply({ ...catalog, chapters: [{ ...chapter, version: 4 }] })) : base(url, init)));
  render(<StorySimulatorPanel client={client()} chapter={chapter} />); await screen.findByLabelText('推演来源：雨夜 · v4');
  const rebase = screen.getByRole('button', { name: '已核对，更新来源版本（保留输入）' }) as HTMLButtonElement; expect(rebase.disabled).toBe(false); fireEvent.click(rebase);
  await waitFor(() => expect(screen.queryByRole('button', { name: '已核对，更新来源版本（保留输入）' })).toBeNull());
});
it('recovers persisted manual inputs only by explicit action and requires renewed context review', async () => {
  const input = { chapter_ids: [chapter.id], expected_versions: { [chapter.id]: 3 }, chapter_id: chapter.id, character_id: 'alice', world_time: null, calendar: 'story' as const, node_id: 'node-one', expected_node_version: 2, context_digest: context.context_digest, assumptions: ['held-key'], character_goal: 'Recovered goal', motivation_hypothesis: 'Recovered hypothesis', knowledge_ids: ['fact-one'], resources: { coin: 1 }, hard_constraints: { forbidden_facts: [], resource_caps: { coin: 2 }, required_final_facts: [] }, max_steps: 2, max_branches: 1, model_id: null, model_budget: 0 as const, routes: [{ id: 'route-1', title: 'Recovered route', events: [{ id: 'event-1', title: 'Recovered event', at: 1, requires: [], adds: [], removes: [], requires_knowledge: [], resource_delta: {}, foreshadowing_links: [], question: '' }] }] };
  vi.stubGlobal('fetch', transport({ ...completed, input }));
  render(<StorySimulatorPanel client={client()} chapter={chapter} />); await chooseRun();
  fireEvent.click(screen.getByRole('button', { name: '用此记录恢复输入（覆盖当前表单）' }));
  expect((screen.getByLabelText('路线 1 名称') as HTMLInputElement).value).toBe('Recovered route');
  expect((screen.getByLabelText('人物目标') as HTMLTextAreaElement).value).toBe('Recovered goal');
  expect(screen.queryByRole('region', { name: '人物已知信息' })).toBeNull();
  expect((screen.getByRole('button', { name: '保存输入并创建推演' }) as HTMLButtonElement).disabled).toBe(true);
});

const modelRoute = { route_id: 'route-local', provider_id: 'mock', model_id: 'mock-writer', synthetic: true, available: true, reasons: [] };
const modelPreview = { preview_digest: 'd'.repeat(64), execution_available: true, source_strategy: 'A05_CHARACTER_ONLY_NO_MANUSCRIPT', max_output_bytes: 64000, timeout_seconds: 120, quality_verification: 'NOT_RUN' as const, request: { prompt: 'Synthetic bounded route instructions', context: { character_viewpoint: { character_id: 'alice' } } }, broker: { chosen: { ...modelRoute, price: { source: 'Synthetic test adapter', currency: 'USD', reserve_microusd: 0 } }, candidates: [] } };
const modelCandidate = { id: 'model-a', input: { id: 'model-a', title: '模型替代路线', events: [] }, rules: { ...completed.routes![0], id: 'model-a', title: '模型替代路线' }, evidence_ids: [] as string[], hypothesis: true as const, quality_verification: 'NOT_RUN' as const };
function modelTransport(initial: SimulatorRun = completed) {
  let row = initial;
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/catalog')) return reply({ ...catalog, model_configured: true, model_routes: [modelRoute] });
    if (url.endsWith('/model/preview')) { row = { ...row, version: 3, model_preview: modelPreview }; return reply(row); }
    if (url.endsWith('/model/dispatch')) { row = { ...row, version: 4, model_execution: { job_id: 'job-one', status: 'QUEUED', receipt_state: 'RECORDED', usage_state: 'UNKNOWN', quality_verification: 'NOT_RUN' } }; return reply(row); }
    if (url.endsWith('/model/refresh')) { row = { ...row, version: 5, model_execution: { ...row.model_execution!, status: 'CANDIDATES' }, model_candidates: [modelCandidate], model_candidates_digest: 'e'.repeat(64) }; return reply(row); }
    if (url.endsWith('/model/cancel')) { row = { ...row, version: row.version + 1, model_execution: { ...row.model_execution!, status: 'CANCELLED' }, model_candidates: [] }; return reply(row); }
    if (url.endsWith('/model/select')) { row = { ...ready, id: 'adopted-run', model_called: true, model_adoption: { run_id: 'run-one', candidate_id: 'model-a', evidence_ids: [], quality_verification: 'NOT_RUN' } }; return reply(row, 201); }
    if (url.endsWith('/runs')) return reply({ items: [row] });
    if (url.endsWith('/runs/run-one') || url.endsWith('/runs/adopted-run')) return reply(row);
    throw new Error(`Unhandled ${init?.method} ${url}`);
  });
  return fetch;
}
it('previews exact local character request, dispatches once with consent, then manually selects checked candidate', async () => {
  const fetch = modelTransport(); vi.stubGlobal('fetch', fetch);
  render(<StorySimulatorPanel client={client()} chapter={chapter} />); await chooseRun();
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('推演候选本地模型'), { target: { value: 'route-local' } });
  fireEvent.click(screen.getByRole('button', { name: '预览模型候选请求（不发送）' }));
  await screen.findByRole('region', { name: '模型候选发送预览' });
  expect(screen.getByText(/Synthetic bounded route instructions/)).toBeTruthy();
  const send = screen.getByRole('button', { name: '发送这一次模型候选请求' }) as HTMLButtonElement;
  expect(send.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('我已核对这份发送内容、当前本地路线与零费用上限，允许发送一次模型候选请求'));
  fireEvent.click(send); fireEvent.click(send);
  await screen.findByText(/状态：QUEUED/);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/model/dispatch'))).toHaveLength(1);
  const dispatch = fetch.mock.calls.find(([url]) => url.endsWith('/model/dispatch'))!;
  expect(JSON.parse(dispatch[1]!.body as string)).toEqual({ expected_version: 3, reviewed_preview_digest: modelPreview.preview_digest });
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/model/refresh'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '检查原模型请求结果' }));
  await screen.findByRole('article', { name: '比较路线 模型替代路线' });
  const select = screen.getByRole('button', { name: '将选中模型候选创建为独立推演' }) as HTMLButtonElement;
  expect(select.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('选用模型候选 模型替代路线 创建独立推演'));
  fireEvent.click(screen.getByLabelText('已核对所选模型假设、证据与违规，只创建待手动推进的独立推演'));
  fireEvent.click(select); fireEvent.click(select);
  await screen.findByText(/此记录由人工选用模型候选创建/);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/model/select'))).toHaveLength(1);
  expect(fetch.mock.calls.some(([url]) => /\/(step|save|accept|approve)$/.test(url))).toBe(false);
});
it('model cancellation and unknown admission never offer automatic replay or candidate adoption', async () => {
  const initial: SimulatorRun = { ...completed, model_preview: modelPreview, model_execution: { job_id: 'job-one', status: 'UNKNOWN', receipt_state: 'UNKNOWN_NO_AUTOMATIC_REPLAY', usage_state: 'UNKNOWN', quality_verification: 'NOT_RUN' } };
  const fetch = modelTransport(initial); vi.stubGlobal('fetch', fetch);
  render(<StorySimulatorPanel client={client()} chapter={chapter} />); await chooseRun();
  expect((screen.getByRole('button', { name: '发送这一次模型候选请求' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '检查原模型请求结果' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('button', { name: '将选中模型候选创建为独立推演' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '取消模型候选并丢弃结果' }));
  await screen.findByText(/状态：CANCELLED/);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/model/dispatch'))).toBe(false);
});
it('ignores late model preview from a replaced scope and never preserves its consent', async () => {
  const base = modelTransport(); let finish!: (r: Response) => void;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/model/preview') ? new Promise<Response>(resolve => { finish = resolve; }) : base(url, init)));
  const view = render(<StorySimulatorPanel client={client()} chapter={chapter} />); await chooseRun();
  fireEvent.change(screen.getByLabelText('推演候选本地模型'), { target: { value: 'route-local' } });
  fireEvent.click(screen.getByRole('button', { name: '预览模型候选请求（不发送）' }));
  view.rerender(<StorySimulatorPanel client={experimentalClient('novel-new', { sessionToken: 'session-new' })} />);
  await act(async () => finish(reply({ ...completed, model_preview: modelPreview })));
  expect(screen.queryByRole('region', { name: '模型候选发送预览' })).toBeNull();
  expect(screen.queryByLabelText('我已核对这份发送内容、当前本地路线与零费用上限，允许发送一次模型候选请求')).toBeNull();
});
it('changing selected model route clears consent and fences a previously reviewed request', async () => {
  const base = modelTransport({ ...completed, model_preview: modelPreview });
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/catalog') ? Promise.resolve(reply({ ...catalog, model_configured: true, model_routes: [modelRoute, { ...modelRoute, route_id: 'another-route', model_id: 'other-local' }] })) : base(url, init)));
  render(<StorySimulatorPanel client={client()} chapter={chapter} />); await chooseRun();
  fireEvent.click(screen.getByLabelText('我已核对这份发送内容、当前本地路线与零费用上限，允许发送一次模型候选请求'));
  expect((screen.getByRole('button', { name: '发送这一次模型候选请求' }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText('推演候选本地模型'), { target: { value: 'another-route' } });
  expect((screen.getByRole('button', { name: '发送这一次模型候选请求' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('我已核对这份发送内容、当前本地路线与零费用上限，允许发送一次模型候选请求') as HTMLInputElement).checked).toBe(false);
  expect(screen.getByText('模型选择已变化。请重新预览所选路线后再确认发送。')).toBeTruthy();
  expect(base.mock.calls.some(([url]) => url.endsWith('/model/dispatch'))).toBe(false);
});
