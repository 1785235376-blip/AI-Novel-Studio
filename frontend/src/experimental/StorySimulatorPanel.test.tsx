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
