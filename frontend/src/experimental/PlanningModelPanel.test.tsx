// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { PlanningModelPanel } from './PlanningModelPanel';
import { PlanningPanel } from './PlanningPanel';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
import { experimentalClient, type Row } from './api';
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const node = { id: 'node', graph_id: 'graph', version: 3, title: '原节点', level: 'CHAPTER', status: 'DRAFT', fields: { goal: '已保存目标' }, links: { chapter_ids: ['chapter'] } };
const chapter = { id: 'chapter', version: 2 } as Chapter;
const route = { route_id: 'local', provider_id: 'local-provider', model_id: 'local-model', display_name: '已注册本地模型', synthetic: true, available: true, reasons: [] };
const catalog = { routes: [route], profile: 'LOCAL_ONLY', max_cost_microusd: 0 };
const preview = { preview_digest: 'preview-digest', request: { prompt: 'Exact saved source and author instruction' }, broker: { chosen: route }, budget: { max_cost_microusd: 0 }, sources: { chapter: { version: 2, digest: 'content-digest' } }, source_strategy: 'LINKED_CHAPTERS', execution_available: true, max_output_bytes: 32768, timeout_seconds: 120, quality_verification: 'SYNTHETIC_PROTOCOL_ONLY' };
const candidate = { id: 'candidate', title: '港口方案', fields: { goal: '找到钥匙' }, rationale: '作者应核对动机', analysis_source: 'SYNTHETIC_PROTOCOL_ONLY', evidence: [{ chapter_id: 'chapter', chapter_version: 2, content_sha256: 'content-digest', start: 0, end: 3, quote: '旧钥匙' }] };
const execution = { job_id: 'original-job', status: 'RUNNING', receipt_state: 'PENDING', usage_state: 'PENDING', model_called: true };
const initial = () => ({ id: 'request', node_id: 'node', graph_id: 'graph', version: 1, target_version: 3, title: '原模型请求', instruction: '保留悬念', template_id: 'three-act', candidate_count: 2, stale: false, model_preview: null as typeof preview | null, model_execution: null as typeof execution | null, model_candidates: [] as typeof candidate[], candidates_digest: null as string | null, saved_proposals: {} as Record<string, string> });
type Request = ReturnType<typeof initial>;
function backend(initialRows: Request[] = [], override?: (url: string, options: RequestInit) => Response | undefined | Promise<Response | undefined>) {
  let rows = initialRows;
  return vi.fn(async (url: string, options: RequestInit) => {
    const overridden = await override?.(url, options); if (overridden) return overridden;
    if (url.endsWith('/planning/model/catalog')) return response(catalog);
    if (url.endsWith('/planning/model/requests') && options.method === 'GET') return response({ items: rows });
    if (url.endsWith('/planning/model/requests') && options.method === 'POST') { const value = initial(); rows = [...rows, value]; return response(value, 201); }
    const match = url.match(/\/planning\/model\/requests\/([^/]+)(.*)$/);
    if (match) {
      const index = rows.findIndex(row => row.id === match[1]); if (index < 0) return response({}, 404);
      let value = rows[index]; if (options.method === 'GET') return response(value);
      if (match[2] === '/preview') value = { ...value, version: value.version + 1, model_preview: preview };
      if (match[2] === '/dispatch') value = { ...value, version: value.version + 1, model_execution: execution };
      if (match[2] === '/refresh') value = { ...value, version: value.version + 1, model_execution: { ...value.model_execution!, status: 'COMPLETED', receipt_state: 'RECORDED', usage_state: 'KNOWN' }, model_candidates: [candidate], candidates_digest: 'candidates-digest' };
      if (match[2] === '/cancel') value = { ...value, version: value.version + 1, model_execution: { ...value.model_execution!, status: 'CANCELLED' } };
      if (match[2] === '/candidates/candidate/save') { value = { ...value, version: value.version + 1, saved_proposals: { candidate: 'proposal' } }; rows[index] = value; return response({ run: value, proposal_id: 'proposal', graph_id: 'graph', node_id: 'node', replayed: false }); }
      rows[index] = value; return response(value);
    }
    if (url.endsWith('/planning/graphs')) return response({ items: [{ id: 'graph', title: '原规划图', version: 1 }] });
    if (url.endsWith('/planning/graphs/graph')) return response({ id: 'graph', root_node_id: 'node', status: 'DRAFT', version: 1, nodes: [node] });
    if (url.endsWith('/planning/templates')) return response({ items: [{ id: 'three-act', title: '三幕', version: 1 }] });
    if (url.endsWith('/planning/proposals/proposal')) return response({ id: 'proposal', title: '港口方案', graph_id: 'graph', node_id: 'node', version: 1, target_version: 3, fields: candidate.fields, status: 'REVIEW', stale: false });
    return response({ items: [] });
  });
}
const props = () => ({ client: experimentalClient('novel', { sessionToken: 'test' }), node: node as Row, chapter, sourceReady: true, instruction: '保留悬念', templateId: 'three-act', onOpenProposal: vi.fn() });
async function click(name: string) { await waitFor(() => expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(screen.getByRole('button', { name })); }
async function chooseRequest() { if (screen.queryByRole('button', { name: '打开本地模型规划' })) await click('打开本地模型规划'); await waitFor(() => expect((screen.getByLabelText('查看原规划模型请求') as HTMLSelectElement).disabled).toBe(false)); fireEvent.change(screen.getByLabelText('查看原规划模型请求'), { target: { value: 'request' } }); await screen.findByRole('region', { name: '原规划模型请求 request' }); }
async function prepare() { await click('查看本地规划模型路线'); fireEvent.change(await screen.findByLabelText('本地规划模型'), { target: { value: 'local' } }); await click('准备准确规划模型预览'); await screen.findByLabelText('准确规划模型请求'); }
const writes = (fetch: ReturnType<typeof backend>) => fetch.mock.calls.filter(([, options]) => options.method !== 'GET');
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('persists, previews, dispatches and saves only after separate explicit consent; never replaces the original job', async () => {
  const fetch = backend(), input = props(); vi.stubGlobal('fetch', fetch); render(<StrictMode><PlanningModelPanel {...input} /></StrictMode>);
  await click('打开本地模型规划'); await screen.findByText('还没有模型规划请求'); expect(writes(fetch)).toHaveLength(0);
  await click('保存新的模型规划请求（不发送）'); await screen.findByRole('region', { name: '原规划模型请求 request' });
  expect(JSON.parse(writes(fetch)[0][1].body as string)).toEqual({ node_id: 'node', expected_node_version: 3, instruction: '保留悬念', template_id: 'three-act', candidate_count: 2 });
  await prepare(); expect((screen.getByRole('button', { name: '明确发送此次规划模型请求' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('准确规划模型请求') as HTMLTextAreaElement).value).toContain('Exact saved source');
  fireEvent.click(screen.getByRole('checkbox', { name: '已核对原节点、关联章节、准确请求、模型与零费用预占' }));
  const send = screen.getByRole('button', { name: '明确发送此次规划模型请求' }); fireEvent.click(send); fireEvent.click(send);
  await screen.findByText(/原任务 original-job · RUNNING/); expect(writes(fetch).filter(([url]) => url.endsWith('/dispatch'))).toHaveLength(1);
  expect(JSON.parse(writes(fetch).find(([url]) => url.endsWith('/dispatch'))![1].body as string)).toEqual({ expected_version: 2, reviewed_preview_digest: 'preview-digest' });
  await click('查询原任务并核对规划候选'); await screen.findByRole('article', { name: '规划模型候选 港口方案' });
  expect(screen.getByLabelText('规划候选 candidate 引文 1')).toHaveProperty('value', '旧钥匙'); expect(writes(fetch).some(([url]) => url.includes('/save'))).toBe(false);
  fireEvent.click(screen.getByRole('checkbox', { name: '已核对候选 港口方案 的字段与原文证据' })); await click('将候选 港口方案 保存为原规划待审方案');
  await waitFor(() => expect(input.onOpenProposal).toHaveBeenCalledWith('proposal'));
  expect(JSON.parse(writes(fetch).find(([url]) => url.endsWith('/save'))![1].body as string)).toEqual({ expected_version: 4, reviewed_candidates_digest: 'candidates-digest' });
  await click('打开原规划待审方案'); expect(input.onOpenProposal).toHaveBeenCalledTimes(2);
  expect(writes(fetch).map(([url]) => url.split('/').at(-1))).toEqual(['requests', 'preview', 'dispatch', 'refresh', 'save']);
});

it.each(['missing', 'ambiguous', 'wrong detail'])('fails closed on original Job lookup: %s', async mode => {
  const row = { ...initial(), model_execution: execution };
  const fetch = backend(mode === 'missing' ? [] : mode === 'ambiguous' ? [row, { ...row, id: 'second' }] : [row], url => mode === 'wrong detail' && url.endsWith('/requests/request') ? response({ ...row, id: 'foreign', model_candidates: [candidate] }) : undefined);
  vi.stubGlobal('fetch', fetch); render(<PlanningModelPanel {...props()} requestedJobId="original-job" />);
  if (mode === 'wrong detail') await screen.findByRole('alert'); else await screen.findByText(/原模型任务在当前授权记录中不可用或身份不唯一/);
  expect(screen.queryByRole('article', { name: '规划模型候选 港口方案' })).toBeNull(); expect(screen.queryByRole('button', { name: '查询原任务并核对规划候选' })).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});

it('reopens an exact Job for another node without calls, then cancels only the original Job', async () => {
  const row = { ...initial(), node_id: 'other-node', graph_id: 'other-graph', model_preview: preview, model_execution: { ...execution, receipt_state: 'UNKNOWN_NO_AUTOMATIC_REPLAY', usage_state: 'UNKNOWN' } };
  const fetch = backend([row]); vi.stubGlobal('fetch', fetch); render(<PlanningModelPanel {...props()} requestedJobId="original-job" />);
  await screen.findByText(/原任务 original-job · RUNNING/); expect(screen.getByText(/原规划图 other-graph/)).toBeTruthy(); expect(screen.getByText(/原任务状态未知/)).toBeTruthy(); expect(writes(fetch)).toHaveLength(0);
  expect(screen.queryByRole('button', { name: '明确发送此次规划模型请求' })).toBeNull(); await click('取消原规划模型任务'); await screen.findByText(/原任务 original-job · CANCELLED/);
  expect(writes(fetch)).toHaveLength(1); expect(writes(fetch)[0][0]).toMatch(/\/requests\/request\/cancel$/);
});

it('invalidates preview consent on changed instruction or saved source without sending the old request', async () => {
  const fetch = backend([initial()]), input = props(); vi.stubGlobal('fetch', fetch); const view = render(<PlanningModelPanel {...input} />); await chooseRequest(); await prepare();
  fireEvent.click(screen.getByRole('checkbox', { name: '已核对原节点、关联章节、准确请求、模型与零费用预占' })); view.rerender(<PlanningModelPanel {...input} instruction="新的作者意图" />);
  expect(screen.queryByRole('button', { name: '明确发送此次规划模型请求' })).toBeNull(); await click('重新读取原规划请求'); await screen.findByLabelText('准确规划模型请求');
  expect((screen.getByRole('checkbox', { name: '已核对原节点、关联章节、准确请求、模型与零费用预占' }) as HTMLInputElement).checked).toBe(false);
  view.rerender(<PlanningModelPanel {...input} instruction="新的作者意图" node={{ ...node, version: 4 }} />); expect(screen.queryByLabelText('准确规划模型请求')).toBeNull(); expect(writes(fetch).filter(([url]) => url.endsWith('/dispatch'))).toHaveLength(0);
});

it('hides old evidence on failed reread and recovers only after successful explicit reread', async () => {
  let denied = false; const row = { ...initial(), model_execution: { ...execution, status: 'COMPLETED', receipt_state: 'RECORDED' }, model_candidates: [candidate], candidates_digest: 'digest' };
  const fetch = backend([row], url => denied && url.endsWith('/requests/request') ? response({}, 403) : undefined); vi.stubGlobal('fetch', fetch); render(<PlanningModelPanel {...props()} />);
  await chooseRequest(); await screen.findByRole('article', { name: '规划模型候选 港口方案' }); denied = true; await click('重新读取原规划请求'); await screen.findByRole('alert'); expect(screen.queryByLabelText('规划候选 candidate 引文 1')).toBeNull();
  denied = false; await click('重新读取原规划请求'); await screen.findByLabelText('规划候选 candidate 引文 1'); expect(writes(fetch)).toHaveLength(0);
});

it('ignores delayed original-request responses after changing target Job and client', async () => {
  let release!: (value: Response) => void; const first = { ...initial(), model_execution: { ...execution, job_id: 'first-job' } }, second = { ...initial(), id: 'second', model_execution: { ...execution, job_id: 'second-job' } };
  const fetch = backend([first, second], url => url.endsWith('/requests/request') ? new Promise<Response>(resolve => { release = resolve; }) : undefined); vi.stubGlobal('fetch', fetch); const input = props();
  const view = render(<PlanningModelPanel {...input} requestedJobId="first-job" />); await waitFor(() => expect(release).toBeTypeOf('function'));
  view.rerender(<PlanningModelPanel {...input} requestedJobId="second-job" />); await screen.findByText(/原任务 second-job/); await act(async () => release(response({ ...first, model_candidates: [candidate] })));
  expect(screen.queryByText(/原任务 first-job/)).toBeNull(); expect(screen.queryByLabelText('规划候选 candidate 引文 1')).toBeNull();
  view.rerender(<PlanningModelPanel {...props()} requestedJobId="missing" />); await screen.findByText(/原模型任务在当前授权记录中不可用或身份不唯一/); expect(screen.queryByText(/原任务 second-job/)).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});

it('saves into exact original proposal review without replacing the manual editor draft', async () => {
  const fetch = backend([{ ...initial(), model_execution: { ...execution, status: 'COMPLETED', receipt_state: 'RECORDED' }, model_candidates: [candidate], candidates_digest: 'digest' }]); vi.stubGlobal('fetch', fetch); render(<PlanningPanel client={props().client} chapter={chapter} />);
  await screen.findByRole('heading', { name: '编辑 CHAPTER' }); fireEvent.change(screen.getByLabelText('节点标题'), { target: { value: '保留我的未保存标题' } }); fireEvent.change(screen.getByLabelText('目标', { exact: true }), { target: { value: '保留我的未保存目标' } });
  await chooseRequest(); await screen.findByRole('article', { name: '规划模型候选 港口方案' }); fireEvent.click(screen.getByRole('checkbox', { name: '已核对候选 港口方案 的字段与原文证据' })); await click('将候选 港口方案 保存为原规划待审方案');
  await screen.findByRole('article', { name: '方案 港口方案' }); expect(screen.queryByRole('textbox', { name: '节点标题' })).toBeNull(); await click('返回规划节点与方案列表');
  expect(screen.getByLabelText('节点标题')).toHaveProperty('value', '保留我的未保存标题'); expect(screen.getByLabelText('目标', { exact: true })).toHaveProperty('value', '保留我的未保存目标'); expect(screen.getByLabelText('查看原规划模型请求')).toHaveProperty('value', 'request'); expect(writes(fetch).map(([url]) => url.split('/').at(-1))).toEqual(['save']);
});

it('workbench forwards planning_model_job to its original owner without dispatching', async () => {
  const fetch = backend([{ ...initial(), model_execution: execution }]); vi.stubGlobal('fetch', fetch); render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={{ experimental: true, default_enabled: false, features: { 'experimental.advanced_planning_v2': true } }} requestedTask={{ id: 'original-job', authority: 'planning_model_job' }} />);
  await screen.findByText(/原任务 original-job/); expect(writes(fetch)).toHaveLength(0);
});

it('blocks model request creation without saved linked chapters', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<PlanningModelPanel {...props()} node={{ ...node, links: { chapter_ids: [] } }} />); await click('打开本地模型规划'); await screen.findByText('还没有模型规划请求');
  expect((screen.getByRole('button', { name: '保存新的模型规划请求（不发送）' }) as HTMLButtonElement).disabled).toBe(true); expect(writes(fetch)).toHaveLength(0);
});

 it('keeps oversized instructions intact and blocks only new model requests', async () => {
  const fetch = backend(), instruction = '字'.repeat(4001); vi.stubGlobal('fetch', fetch); render(<PlanningModelPanel {...props()} instruction={instruction} />); await click('打开本地模型规划'); await screen.findByText('还没有模型规划请求');
  expect(screen.getByText(/模型方案指令上限为 4000 个字符/)).toBeTruthy(); expect((screen.getByRole('button', { name: '保存新的模型规划请求（不发送）' }) as HTMLButtonElement).disabled).toBe(true); expect(writes(fetch)).toHaveLength(0);
});
it('hides candidates whose original receipt is unknown even if a stale candidate array is returned', async () => {
  const fetch = backend([{ ...initial(), model_execution: { ...execution, status: 'COMPLETED', receipt_state: 'UNKNOWN_NO_AUTOMATIC_REPLAY' }, model_candidates: [candidate], candidates_digest: 'digest' }]);
  vi.stubGlobal('fetch', fetch); render(<PlanningModelPanel {...props()} requestedJobId="original-job" />); await screen.findByText(/原任务状态未知/); expect(screen.queryByLabelText('规划候选 candidate 引文 1')).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});

it('keeps saved proposal links when approved source changes make the original request stale', async () => {
  const fetch = backend([{ ...initial(), stale: true, saved_proposals: { candidate: 'proposal' }, model_execution: { ...execution, status: 'COMPLETED', receipt_state: 'RECORDED' } }]), input = props();
  vi.stubGlobal('fetch', fetch); render(<PlanningModelPanel {...input} requestedJobId="original-job" />); await screen.findByText(/来源已变化，旧预览与候选已隐藏/);
  expect(screen.queryByLabelText('规划候选 candidate 引文 1')).toBeNull(); await click('打开原规划待审方案'); expect(input.onOpenProposal).toHaveBeenCalledWith('proposal'); expect(writes(fetch)).toHaveLength(0);
});
it('leaves optional model endpoints unread until explicitly opened', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<PlanningPanel client={props().client} chapter={chapter} />); await screen.findByRole('heading', { name: '编辑 CHAPTER' });
  expect(fetch.mock.calls.some(([url]) => url.includes('/planning/model/'))).toBe(false); expect(screen.getByRole('button', { name: '生成 Mock 双方案' })).toBeTruthy(); expect(screen.getByRole('button', { name: '保存节点' })).toBeTruthy();
  await click('打开本地模型规划'); await screen.findByText('还没有模型规划请求'); expect(fetch.mock.calls.some(([url]) => url.endsWith('/planning/model/requests'))).toBe(true); expect(writes(fetch)).toHaveLength(0);
});

it('never automatically replays an unconfirmed dispatch and can recover its persisted original Job', async () => {
  let dispatched = false; const row = { ...initial(), model_preview: preview };
  const fetch = backend([row], (url, options) => {
    if (url.endsWith('/dispatch')) { dispatched = true; return response({}, 503); }
    if (dispatched && options.method === 'GET' && url.endsWith('/requests')) return response({ items: [{ ...row, version: 2, model_execution: execution }] });
    if (dispatched && options.method === 'GET' && url.endsWith('/requests/request')) return response({ ...row, version: 2, model_execution: execution });
    return undefined;
  });
  vi.stubGlobal('fetch', fetch); render(<PlanningModelPanel {...props()} />); await chooseRequest(); await screen.findByLabelText('准确规划模型请求');
  fireEvent.click(screen.getByRole('checkbox', { name: '已核对原节点、关联章节、准确请求、模型与零费用预占' })); await click('明确发送此次规划模型请求'); await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: '明确发送此次规划模型请求' })).toBeNull(); await click('重新读取原规划请求'); await screen.findByText(/原任务 original-job/);
  expect(writes(fetch).map(([url]) => url.split('/').at(-1))).toEqual(['dispatch']);
});
it('discards a delayed preview response after its instruction changes, requiring original-request recovery', async () => {
  let release!: (value: Response) => void; const row = initial();
  const fetch = backend([row], url => url.endsWith('/preview') ? new Promise<Response>(resolve => { release = resolve; }) : undefined);
  vi.stubGlobal('fetch', fetch); const input = props(); const view = render(<PlanningModelPanel {...input} />); await chooseRequest(); await click('查看本地规划模型路线');
  fireEvent.change(await screen.findByLabelText('本地规划模型'), { target: { value: 'local' } }); await click('准备准确规划模型预览'); await waitFor(() => expect(release).toBeTypeOf('function'));
  view.rerender(<PlanningModelPanel {...input} instruction="changed intent" />); await act(async () => release(response({ ...row, version: 2, model_preview: preview })));
  expect(screen.queryByLabelText('准确规划模型请求')).toBeNull(); expect(screen.queryByRole('button', { name: '明确发送此次规划模型请求' })).toBeNull(); expect(writes(fetch).map(([url]) => url.split('/').at(-1))).toEqual(['preview']);
});
