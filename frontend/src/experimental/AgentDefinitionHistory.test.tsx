// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AgentDefinitionHistory } from './AgentDefinitionHistory';
import { DeclarativeAgentsPanel } from './DeclarativeAgentsPanel';
import { experimentalClient } from './api';
import { declarativeAgentsClient, type AgentDefinition, type AgentHistoryDetail, type AgentHistoryPage, type AuthoredWorkflow } from './declarativeAgentsClient';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = (id = 'one') => experimentalClient(id, { sessionToken: 'token-' + id, scope: { workspaceId: 'w', projectId: id, storylineId: 's', branchId: 'branch-' + id } });
const definition: AuthoredWorkflow = { agent: { title: 'Current definition', purpose: 'Authored purpose', role_prompt: 'Current authored prompt', input_schema: { fields: [{ name: 'source_text', type: 'string', required: true, max_length: 8000 }] }, output_schema: { fields: [{ name: 'draft', type: 'string', required: true, max_length: 8000 }] }, allowed_tools: ['draft_prepare'], model_route: null, review_required: true, max_steps: 8, timeout_seconds: 30, max_output_bytes: 64000, max_cost_microusd: 0 }, nodes: [{ id: 'prepare', type: 'draft_prepare', name: 'Prepare' }, { id: 'review', type: 'manual_approval', name: 'Review' }, { id: 'artifact', type: 'review_artifact', name: 'Artifact' }], edges: [{ source: 'prepare', target: 'review' }, { source: 'review', target: 'artifact' }] };
const saved: AgentDefinition = { id: 'definition', version: 2, definition, definition_digest: 'b'.repeat(64) };
const historical = clone(definition); historical.agent.role_prompt = 'Historical authored prompt';
const page: AgentHistoryPage = { definition_id: saved.id, current_version: 2, current_definition_digest: saved.definition_digest, items: [{ version: 1, title: 'Historical definition', definition_digest: 'a'.repeat(64), updated_at: '2026-10-16T00:00:00+00:00' }], next_before_version: null };
const detail: AgentHistoryDetail = { definition_id: saved.id, current_version: 2, current_definition_digest: saved.definition_digest, version: 1, definition_digest: 'a'.repeat(64), definition: historical };
const props = () => ({ api: declarativeAgentsClient(client()), saved, editorRevision: 0, dirty: false, disabled: false, onFill: vi.fn(), onDiscard: vi.fn() });
function historyTransport(override?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined) {
  return vi.fn(async (url: string, init: RequestInit) => {
    const result = override?.(url, init); if (result) return result;
    if (url.endsWith('/history?limit=20')) return response(page);
    if (url.endsWith('/history/1')) return response(detail);
    throw new Error('Unexpected request ' + url);
  });
}
async function openHistory() {
  fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' }));
  await screen.findByRole('option', { name: /v1 · Historical definition/ });
  fireEvent.change(screen.getByLabelText('查看 Agent 历史版本'), { target: { value: '1' } });
  return screen.findByRole('button', { name: '将历史定义填入表单' });
}

it('loads bounded metadata/detail only on explicit actions and fills authored fields without a mutation', async () => {
  const fetch = historyTransport(); vi.stubGlobal('fetch', fetch); const p = props();
  render(<StrictMode><AgentDefinitionHistory {...p} /></StrictMode>);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(await openHistory());
  expect(p.onFill).toHaveBeenCalledOnce(); expect(p.onFill.mock.calls[0][0]).toEqual(historical);
  expect(p.onFill.mock.calls[0][0]).not.toBe(historical);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  expect(fetch.mock.calls[0][1].headers).toMatchObject({ 'X-Session-Token': 'token-one', 'X-Branch-Id': 'branch-one' });
  expect(screen.getByText(/128000 UTF-8/)).toBeTruthy();
});

it('keeps dirty drafts protected and invalidates the candidate after explicit discard', async () => {
  vi.stubGlobal('fetch', historyTransport()); const p = props();
  const view = render(<AgentDefinitionHistory {...p} dirty />);
  expect((await openHistory() as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃未保存的 Agent 定义编辑' })); expect(p.onDiscard).toHaveBeenCalledOnce();
  expect(p.onFill).not.toHaveBeenCalled();
  view.rerender(<AgentDefinitionHistory {...p} editorRevision={1} />);
  expect(screen.queryByRole('button', { name: '将历史定义填入表单' })).toBeNull();
  fireEvent.change(screen.getByLabelText('查看 Agent 历史版本'), { target: { value: '1' } });
  fireEvent.click(await screen.findByRole('button', { name: '将历史定义填入表单' }));
  expect(p.onFill).toHaveBeenCalledOnce();
});

it.each(['list', 'detail'])('hides history and refuses %s current-version drift without rebasing', async location => {
  vi.stubGlobal('fetch', historyTransport(url => location === 'list' && url.includes('?limit=20') ? response({ ...page, current_version: 3 }) : location === 'detail' && url.endsWith('/1') ? response({ ...detail, current_definition_digest: 'c'.repeat(64) }) : undefined));
  const p = props(); render(<AgentDefinitionHistory {...p} />);
  fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' }));
  if (location === 'detail') {
    await screen.findByRole('option', { name: /v1 · Historical definition/ });
    fireEvent.change(screen.getByLabelText('查看 Agent 历史版本'), { target: { value: '1' } });
  }
  await screen.findByText(/已保存定义已变化。请刷新/);
  expect(screen.queryByRole('button', { name: '将历史定义填入表单' })).toBeNull(); expect(p.onFill).not.toHaveBeenCalled();
});

it('discards a delayed historical response after a newer edit', async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal('fetch', historyTransport(url => url.endsWith('/1') ? new Promise<Response>(done => { resolve = done; }) : undefined));
  const p = props(); const view = render(<AgentDefinitionHistory {...p} />);
  fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' })); await screen.findByRole('option', { name: /v1 · Historical definition/ });
  fireEvent.change(screen.getByLabelText('查看 Agent 历史版本'), { target: { value: '1' } });
  view.rerender(<AgentDefinitionHistory {...p} editorRevision={1} dirty />);
  await act(async () => { resolve(response(detail)); });
  expect(screen.queryByText('完整历史声明式定义')).toBeNull(); expect(p.onFill).not.toHaveBeenCalled();
});

it('discards loaded or delayed details when the saved definition identity changes', async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal('fetch', historyTransport(url => url.endsWith('/1') ? new Promise<Response>(done => { resolve = done; }) : undefined));
  const p = props(); const view = render(<AgentDefinitionHistory {...p} />);
  fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' })); await screen.findByRole('option', { name: /v1 · Historical definition/ });
  fireEvent.change(screen.getByLabelText('查看 Agent 历史版本'), { target: { value: '1' } });
  view.rerender(<AgentDefinitionHistory {...p} saved={{ ...saved, id: 'different-definition' }} />);
  await act(async () => { resolve(response(detail)); });
  expect(screen.queryByLabelText('查看 Agent 历史版本')).toBeNull(); expect(p.onFill).not.toHaveBeenCalled();
});

it('clears cached detail after a denied refresh and never falls back to another version', async () => {
  let denied = false;
  vi.stubGlobal('fetch', historyTransport(() => denied ? response({ detail: { code: 'FORBIDDEN' } }, 403) : undefined));
  const p = props(); render(<AgentDefinitionHistory {...p} />); await openHistory();
  denied = true; fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' }));
  await screen.findByText(/当前身份没有此操作权限/);
  expect(screen.queryByText('完整历史声明式定义')).toBeNull(); expect(p.onFill).not.toHaveBeenCalled();
});

it('clears an already loaded detail when the client changes without changing the definition ID', async () => {
  vi.stubGlobal('fetch', historyTransport()); const p = props();
  const view = render(<AgentDefinitionHistory {...p} />); await openHistory();
  view.rerender(<AgentDefinitionHistory {...p} api={declarativeAgentsClient(client('two'))} />);
  expect(screen.queryByText('完整历史声明式定义')).toBeNull();
  expect(screen.queryByRole('button', { name: '将历史定义填入表单' })).toBeNull();
});

it.each(['version', 'definition_digest'])('rejects a mismatched historical %s without showing cached detail', async field => {
  vi.stubGlobal('fetch', historyTransport(url => url.endsWith('/1') ? response({ ...detail, [field]: field === 'version' ? 9 : 'c'.repeat(64) }) : undefined));
  const p = props(); render(<AgentDefinitionHistory {...p} />);
  fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' })); await screen.findByRole('option', { name: /Historical definition/ });
  fireEvent.change(screen.getByLabelText('查看 Agent 历史版本'), { target: { value: '1' } });
  await screen.findByText(/历史详情不可用/);
  expect(screen.queryByText('完整历史声明式定义')).toBeNull(); expect(p.onFill).not.toHaveBeenCalled();
});

it('replaces the metadata page and uses the exclusive older-version cursor', async () => {
  const second = { ...page, items: [], next_before_version: null };
  const fetch = historyTransport(url => url.endsWith('/history?limit=20') ? response({ ...page, next_before_version: 1 }) : url.endsWith('&before_version=1') ? response(second) : undefined);
  vi.stubGlobal('fetch', fetch); render(<AgentDefinitionHistory {...props()} />);
  fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' }));
  fireEvent.click(await screen.findByRole('button', { name: '读取更早定义历史' }));
  await screen.findByText('暂无记录'); expect(screen.queryByRole('option', { name: /Historical definition/ })).toBeNull();
  expect(fetch.mock.calls.at(-1)![0]).toContain('before_version=1');
});

function panelTransport(options: { conflict?: boolean; holdDetail?: Promise<Response> } = {}) {
  let current = clone(saved);
  const run = { id: 'old-run', version: 2, status: 'WAITING_APPROVAL', stale: false, definition_id: saved.id, definition_version: 1, input: { source_text: 'Captured input' }, node_states: { review: { status: 'WAITING_APPROVAL', output: null, error: null } }, agent_output: null, trace: [], dispatch_trace: [], applied: false, model_called: false, attempt: 1 };
  return vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return response({ tools: ['draft_prepare'], node_types: ['draft_prepare', 'manual_approval', 'review_artifact'], model_routes: [], default_definition: definition, chapters: [], model_dependency: 'NONE' });
    if (url.endsWith('/definitions')) return response({ items: [current] });
    if (url.endsWith('/history?limit=20')) return response(page);
    if (url.endsWith('/history/1')) return options.holdDetail || response({ ...detail, input: 'MUST_NOT_COPY', version_id: 'MUST_NOT_COPY' });
    if (url.endsWith('/definitions/definition') && init.method === 'PUT') {
      if (options.conflict) return response({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409);
      current = { ...current, version: 3, definition: JSON.parse(String(init.body)).definition, definition_digest: detail.definition_digest };
      return response(current);
    }
    if (url.endsWith('/preflight')) return response({ valid: true, definition_digest: current.definition_digest, topological_order: ['prepare', 'review', 'artifact'], execution_available: true, blockers: [] });
    if (url.endsWith('/runs')) return response({ items: [{ ...run, stale: current.version > 2 }] });
    throw new Error('Unexpected request ' + url);
  });
}
async function selectSaved() {
  await screen.findByRole('option', { name: /Current definition · v2/ });
  fireEvent.change(screen.getByLabelText('已保存的 Agent 定义'), { target: { value: saved.id } });
}

it('integrates draft-fill then explicit current-CAS save, resetting review without reviving the old run', async () => {
  const fetch = panelTransport(); vi.stubGlobal('fetch', fetch); render(<DeclarativeAgentsPanel client={client()} />); await selectSaved();
  fireEvent.click(screen.getByRole('button', { name: '验证 Workflow 图与权限' })); await screen.findByText(/拓扑顺序/);
  fireEvent.click(screen.getByLabelText('已核对已保存图版本、输入来源、工具范围和限额'));
  fireEvent.change(screen.getByLabelText('查看 Workflow 运行'), { target: { value: 'old-run' } });
  fireEvent.click(screen.getByLabelText('已查看逐节点结果，仅批准草稿材料，不写入正文或 Canon'));
  fireEvent.click(await openHistory());
  expect((screen.getByLabelText('角色提示词') as HTMLTextAreaElement).value).toBe('Historical authored prompt');
  expect((screen.getByLabelText('已核对已保存图版本、输入来源、工具范围和限额') as HTMLInputElement).checked).toBe(false);
  expect((screen.getByRole('button', { name: '批准当前审核节点' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.filter(([, init]) => init.method === 'PUT')).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: '保存 Agent 新版本' }));
  await screen.findByText('已保存定义 definition · v3');
  const writes = fetch.mock.calls.filter(([, init]) => init.method === 'PUT'); expect(writes).toHaveLength(1);
  expect(JSON.parse(String(writes[0][1].body))).toEqual({ expected_version: 2, definition: historical });
  expect(screen.queryByText(/状态 WAITING_APPROVAL/)).toBeNull();
  fireEvent.change(screen.getByLabelText('查看 Workflow 运行'), { target: { value: 'old-run' } });
  await screen.findByText(/定义或来源已变化/);
  expect(screen.queryByRole('button', { name: '批准当前审核节点' })).toBeNull();
  expect(fetch.mock.calls.some(([url]) => /\/(execute|approve|dispatch|runs\/old-run)/.test(url))).toBe(false);
});

it('keeps a restored draft after CAS conflict without auto refresh or execution', async () => {
  const fetch = panelTransport({ conflict: true }); vi.stubGlobal('fetch', fetch); render(<DeclarativeAgentsPanel client={client()} />); await selectSaved();
  fireEvent.click(await openHistory()); fireEvent.click(screen.getByRole('button', { name: '保存 Agent 新版本' }));
  await screen.findByText(/版本或来源已改变/);
  expect((screen.getByLabelText('角色提示词') as HTMLTextAreaElement).value).toBe('Historical authored prompt');
  expect(screen.getByText(/已保存定义 definition · v2/)).toBeTruthy();
  expect(fetch.mock.calls.filter(([, init]) => init.method === 'PUT')).toHaveLength(1);
});

it('preserves a dirty draft on drift and cancel, then explicitly reloads the current CAS base on confirmation', async () => {
  let current = clone(saved);
  const original = panelTransport();
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/definitions')) return response({ items: [current] });
    if (init.method === 'PUT') { current = { ...current, version: current.version + 1, definition: JSON.parse(String(init.body)).definition }; return response(current); }
    return original(url, init);
  });
  vi.stubGlobal('fetch', fetch); render(<DeclarativeAgentsPanel client={client()} />); await selectSaved();
  fireEvent.change(screen.getByLabelText('角色提示词'), { target: { value: 'Unsaved author draft' } });
  await openHistory();
  current = { ...clone(saved), version: 3, definition_digest: 'c'.repeat(64), definition: { ...clone(definition), agent: { ...definition.agent, role_prompt: 'New server definition' } } };
  fireEvent.click(screen.getByRole('button', { name: '刷新授权目录与记录' }));
  await screen.findByText(/当前已保存定义已变化，历史候选已隐藏/);
  expect(screen.queryByText('完整历史声明式定义')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '重新载入当前已保存定义' }));
  expect((screen.getByLabelText('角色提示词') as HTMLTextAreaElement).value).toBe('Unsaved author draft');
  fireEvent.click(screen.getByRole('button', { name: '取消切换，保留草稿' }));
  expect((screen.getByLabelText('角色提示词') as HTMLTextAreaElement).value).toBe('Unsaved author draft');
  expect(screen.getByText(/已保存定义 definition · v2/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '重新载入当前已保存定义' }));
  fireEvent.click(screen.getByRole('button', { name: '确认放弃编辑并载入所选定义' }));
  expect((screen.getByLabelText('角色提示词') as HTMLTextAreaElement).value).toBe('New server definition');
  expect(screen.getByText('已保存定义 definition · v3')).toBeTruthy();
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('角色提示词'), { target: { value: 'Explicit new draft' } });
  fireEvent.click(screen.getByRole('button', { name: '保存 Agent 新版本' }));
  await screen.findByText('已保存定义 definition · v4');
  const writes = fetch.mock.calls.filter(([, init]) => init.method === 'PUT');
  expect(writes).toHaveLength(1); expect(JSON.parse(String(writes[0][1].body)).expected_version).toBe(3);
  expect(fetch.mock.calls.some(([url]) => /\/(execute|approve|dispatch)/.test(url))).toBe(false);
});

it('retires pending discard confirmation on a newer edit or directory refresh', async () => {
  vi.stubGlobal('fetch', panelTransport()); render(<DeclarativeAgentsPanel client={client()} />); await selectSaved();
  fireEvent.change(screen.getByLabelText('角色提示词'), { target: { value: 'First unsaved draft' } });
  const selectNew = () => fireEvent.change(screen.getByLabelText('已保存的 Agent 定义'), { target: { value: '' } });
  selectNew(); expect(screen.getByRole('button', { name: '确认放弃编辑并载入所选定义' })).toBeTruthy();
  fireEvent.change(screen.getByLabelText('角色提示词'), { target: { value: 'Later unsaved draft' } });
  expect(screen.queryByRole('button', { name: '确认放弃编辑并载入所选定义' })).toBeNull();
  selectNew(); fireEvent.click(screen.getByRole('button', { name: '刷新授权目录与记录' }));
  await waitFor(() => expect((screen.getByLabelText('已保存的 Agent 定义') as HTMLSelectElement).disabled).toBe(false));
  expect(screen.queryByRole('button', { name: '确认放弃编辑并载入所选定义' })).toBeNull();
  expect((screen.getByLabelText('角色提示词') as HTMLTextAreaElement).value).toBe('Later unsaved draft');
});

it('late history from a prior client cannot repopulate the new project', async () => {
  let resolve!: (value: Response) => void;
  const pending = new Promise<Response>(done => { resolve = done; });
  const fetch = panelTransport({ holdDetail: pending }); vi.stubGlobal('fetch', fetch);
  const view = render(<StrictMode><DeclarativeAgentsPanel client={client()} /></StrictMode>); await selectSaved();
  fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' })); await screen.findByRole('option', { name: /Historical definition/ });
  fireEvent.change(screen.getByLabelText('查看 Agent 历史版本'), { target: { value: '1' } });
  view.rerender(<StrictMode><DeclarativeAgentsPanel client={client('two')} /></StrictMode>);
  await act(async () => { resolve(response(detail)); }); await screen.findByLabelText('角色提示词');
  expect(screen.queryByText('完整历史声明式定义')).toBeNull();
  expect((screen.getByLabelText('角色提示词') as HTMLTextAreaElement).value).toBe('Current authored prompt');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
