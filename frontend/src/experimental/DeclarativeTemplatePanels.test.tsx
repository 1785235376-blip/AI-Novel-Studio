// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { TemplateLibraryPanel } from './TemplateLibraryPanel';
import { DeclarativeAgentsPanel } from './DeclarativeAgentsPanel';
import type { AgentDefinition, AgentRun, AuthoredWorkflow } from './declarativeAgentsClient';
import type { CatalogEntry, TemplateInstance, TemplatePackage } from './templateLibraryClient';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = (name = 'one') => experimentalClient('novel-' + name, { sessionToken: 'token-' + name, scope: { workspaceId: 'workspace-' + name, projectId: 'novel-' + name, storylineId: 'story-' + name, branchId: 'branch-' + name } });
const workflow: AuthoredWorkflow = { agent: { title: '本地草稿整理', purpose: 'Synthetic purpose', role_prompt: '', input_schema: { fields: [{ name: 'source_text', type: 'string', required: true, max_length: 8000 }] }, output_schema: { fields: [{ name: 'draft', type: 'string', required: true, max_length: 8000 }] }, allowed_tools: ['draft_prepare'], model_route: null, review_required: true, max_steps: 8, timeout_seconds: 30, max_output_bytes: 64000, max_cost_microusd: 0 }, nodes: [{ id: 'prepare', type: 'draft_prepare', name: '准备' }, { id: 'review', type: 'manual_approval', name: '审核' }, { id: 'artifact', type: 'review_artifact', name: '材料' }], edges: [{ source: 'prepare', target: 'review' }, { source: 'review', target: 'artifact' }] };
const definition: AgentDefinition = { id: 'definition-one', version: 1, definition: workflow, definition_digest: 'd'.repeat(64) };
const catalog = { tools: ['draft_prepare', 'knowledge_candidates', 'shot_proposals'], node_types: ['draft_prepare', 'knowledge_candidates', 'shot_proposals', 'manual_approval', 'review_artifact', 'checkpoint'], model_routes: [{ id: 'registered-model', model_id: 'model', provider_id: 'host', available: false, reason: 'CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED' }], default_definition: workflow, chapters: [{ id: 'chapter-one', title: '合成章节', version: 3 }], model_dependency: 'CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED' };
const queued: AgentRun = { id: 'run-one', version: 1, status: 'QUEUED', stale: false, definition_id: definition.id, definition_version: 1, input: { source_text: '合成摘录' }, node_states: { prepare: { status: 'PENDING', output: null, error: null }, review: { status: 'PENDING', output: null, error: null }, artifact: { status: 'PENDING', output: null, error: null } }, agent_output: null, trace: [], dispatch_trace: [], applied: false, model_called: false, attempt: 1 };
const waiting: AgentRun = { ...queued, version: 2, status: 'WAITING_APPROVAL', current_node_id: 'review', node_states: { ...queued.node_states, prepare: { status: 'SUCCEEDED', output: { draft: '合成摘录' }, error: null }, review: { status: 'WAITING_APPROVAL', output: null, error: null } }, trace: [{ action: 'WORKFLOW_RUN_ADVANCED', status: 'WAITING_APPROVAL', at: '2026-10-05' }], dispatch_trace: [{ node_id: 'prepare', type: 'draft_prepare', at: '2026-10-05' }] };
function agentTransport(initial?: AgentRun) {
  let row = initial; let saved: AgentDefinition | undefined;
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/preflight')) return reply({ valid: true, definition_digest: definition.definition_digest, topological_order: ['prepare', 'review', 'artifact'], execution_available: !JSON.parse(init!.body as string).agent.model_route, blockers: [] });
    if (url.endsWith('/definitions') && init?.method === 'POST') { saved = { ...definition, definition: JSON.parse(init.body as string).definition }; return reply(saved, 201); }
    if (url.endsWith('/definitions')) return reply({ items: saved ? [saved] : [] });
    if (url.endsWith('/definitions/definition-one/runs')) { row = queued; return reply(row, 201); }
    if (url.endsWith('/runs/run-one/execute')) { row = waiting; return reply(row); }
    if (url.endsWith('/runs/run-one/approve')) { row = { ...waiting, version: 3, status: 'SUCCEEDED', agent_output: { draft: '合成摘录' } }; return reply(row); }
    if (url.endsWith('/runs/run-one/cancel')) { row = { ...queued, version: 2, status: 'CANCELLED' }; return reply(row); }
    if (url.endsWith('/runs/run-one')) return reply(row);
    if (url.endsWith('/runs')) return reply({ items: row ? [row] : [] });
    throw new Error('Unhandled ' + url);
  });
}
const pkg: TemplatePackage = { schema_version: 1, manifest: { id: 'synthetic-character', title: '合成人物档案', version: '1.0.0', type: 'character', description: 'Offline', author: 'Synthetic', license: 'CC0-1.0', dependencies: [], provenance: 'ORIGINAL_SYNTHETIC_OFFLINE' }, content: { sections: [{ key: 'goal', title: '目标', text: '合成人物寻找地图。' }] } };
const entry: CatalogEntry = { id: pkg.manifest.id, package: pkg, digest: 'a'.repeat(64), builtin: true, installed: false, version: 0, favorite: false, favorite_version: 0, missing_dependencies: [] };
const instance: TemplateInstance = { id: 'instance-one', version: 1, package_id: entry.id, package_version: '1.0.0', manifest: pkg.manifest, content: pkg.content, edited: false, linked_target: null };
function libraryTransport() {
  let current = entry; let copied: TemplateInstance | undefined;
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/template-library')) return reply({ items: [current], types: ['character'], remote_sync: 'DISABLED' });
    if (url.endsWith('/favorite')) { current = { ...current, favorite: true, favorite_version: 1 }; return reply(current); }
    if (url.endsWith('/preview')) return reply({ package: JSON.parse(JSON.parse(init!.body as string).package), expected_version: 0, preview_digest: 'b'.repeat(64), diff: { lines: ['+ offline'], truncated: false }, missing_dependencies: [] });
    if (url.endsWith('/install')) { current = { ...current, installed: true, version: 1 }; return reply(current); }
    if (url.endsWith('/uninstall')) { current = { ...current, installed: false, version: 2 }; return reply({ instances_preserved: true }); }
    if (url.endsWith('/instances') && init?.method === 'POST') { copied = instance; return reply(copied, 201); }
    if (url.endsWith('/instances')) return reply({ items: copied ? [copied] : [] });
    if (url.endsWith('/instances/instance-one') && init?.method === 'PUT') { copied = { ...instance, content: JSON.parse(init.body as string).content, version: 2, edited: true }; return reply(copied); }
    if (url.endsWith('/compare')) return reply({ preview_digest: 'c'.repeat(64), expected_version: copied!.version, package_id: entry.id, from_version: '1.0.0', to_version: '2.0.0', edited: true, diff: { lines: ['- old', '+ new'], truncated: false }, linked_target_will_change: false });
    if (url.endsWith('/update')) { copied = { ...copied!, version: 3, package_version: '2.0.0', edited: false }; return reply(copied); }
    if (url.endsWith('/history')) return reply({ items: [{ version: 1, package_version: '1.0.0', content: pkg.content }] });
    if (url.endsWith('/revert')) { copied = { ...copied!, version: 4, package_version: '1.0.0', content: pkg.content }; return reply(copied); }
    throw new Error('Unhandled ' + url);
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('opens both panels read-only in StrictMode with original authority headers and no auto execution', async () => {
  const a = agentTransport(), b = libraryTransport();
  const fetch = vi.fn((url: string, init?: RequestInit) => url.includes('/template-library') ? b(url, init) : a(url, init)); vi.stubGlobal('fetch', fetch);
  const c = client(); render(<StrictMode><TemplateLibraryPanel client={c} /><DeclarativeAgentsPanel client={c} /></StrictMode>);
  await screen.findByLabelText('Agent 名称'); await screen.findByLabelText('选择本地模板');
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  expect(fetch.mock.calls[0][1]?.headers).toMatchObject({ 'X-Session-Token': 'token-one', 'X-Branch-Id': 'branch-one' });
});
it('uses real form contracts, explicit graph check and version-bound creation before separate execute and review', async () => {
  const fetch = agentTransport(); vi.stubGlobal('fetch', fetch); render(<DeclarativeAgentsPanel client={client()} />);
  await screen.findByLabelText('Agent 名称');
  fireEvent.change(screen.getByLabelText('角色提示词'), { target: { value: '不授予工具的角色声明' } });
  const save = screen.getByRole('button', { name: '保存 Agent 定义' }); fireEvent.click(save); fireEvent.click(save);
  await screen.findByText(/已保存定义 definition-one/);
  expect(fetch.mock.calls.filter(([url, init]) => url.endsWith('/definitions') && init?.method === 'POST')).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: '验证 Workflow 图与权限' })); await screen.findByText(/拓扑顺序/);
  fireEvent.change(screen.getByLabelText('测试输入来源'), { target: { value: 'chapter-one' } });
  fireEvent.click(screen.getByLabelText('已核对已保存图版本、输入来源、工具范围和限额'));
  fireEvent.click(screen.getByRole('button', { name: '创建已核对的测试运行' }));
  await screen.findByText(/状态 QUEUED/);
  const create = fetch.mock.calls.find(([url]) => url.endsWith('/definitions/definition-one/runs'))!;
  expect(JSON.parse(create[1]!.body as string)).toMatchObject({ expected_version: 1, input: {}, chapter_ids: ['chapter-one'], reviewed_definition_digest: definition.definition_digest, source_version: 3 });
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/execute'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '执行本地节点到审核点' })); await screen.findByText(/状态 WAITING_APPROVAL/);
  expect((screen.getByRole('button', { name: '批准当前审核节点' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已查看逐节点结果，仅批准草稿材料，不写入正文或 Canon'));
  fireEvent.click(screen.getByRole('button', { name: '批准当前审核节点' })); await screen.findByText(/状态 SUCCEEDED/);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/approve'))).toHaveLength(1);
  expect(screen.getByText('已审核草稿输出')).toBeTruthy();
});
it('invalidates graph preflight on edits, never lists browser invented tools, and preserves input on rejected save', async () => {
  const base = agentTransport(); const fetch = vi.fn((url: string, init?: RequestInit) => url.endsWith('/definitions') && init?.method === 'POST' ? Promise.resolve(reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409)) : base(url, init)); vi.stubGlobal('fetch', fetch);
  render(<DeclarativeAgentsPanel client={client()} />); await screen.findByLabelText('角色提示词');
  fireEvent.click(screen.getByRole('button', { name: '验证 Workflow 图与权限' })); await screen.findByText(/拓扑顺序/);
  fireEvent.change(screen.getByLabelText('角色提示词'), { target: { value: '保留的输入' } });
  expect(screen.queryByText(/拓扑顺序/)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '保存 Agent 定义' })); await screen.findByText(/版本或来源已改变/);
  expect((screen.getByLabelText('角色提示词') as HTMLTextAreaElement).value).toBe('保留的输入');
  expect(screen.queryByLabelText('shell')).toBeNull();
});
it('stale run hides outputs and blocks approval while keeping explicit cancellation', async () => {
  vi.stubGlobal('fetch', agentTransport({ ...waiting, stale: true })); render(<DeclarativeAgentsPanel client={client()} />);
  await waitFor(() => expect((screen.getByLabelText('查看 Workflow 运行') as HTMLSelectElement).options.length).toBe(2));
  fireEvent.change(screen.getByLabelText('查看 Workflow 运行'), { target: { value: 'run-one' } });
  await screen.findByText(/定义或来源已变化/); expect(screen.queryByRole('article', { name: '节点结果 prepare' })).toBeNull();
  expect(screen.queryByRole('button', { name: '批准当前审核节点' })).toBeNull();
  expect((screen.getByRole('button', { name: '取消运行' }) as HTMLButtonElement).disabled).toBe(false);
});
it('previews installs favorites copies edits compares and reverts without running a workflow or overwriting instantiated work', async () => {
  const fetch = libraryTransport(); vi.stubGlobal('fetch', fetch); render(<TemplateLibraryPanel client={client()} />);
  await waitFor(() => expect((screen.getByLabelText('选择本地模板') as HTMLSelectElement).options.length).toBe(2));
  fireEvent.change(screen.getByLabelText('选择本地模板'), { target: { value: entry.id } });
  await screen.findByText(/许可声明：CC0-1.0/);
  fireEvent.click(screen.getByRole('button', { name: '收藏模板' })); await screen.findByRole('button', { name: '取消收藏' });
  fireEvent.click(screen.getByRole('button', { name: '填入安装预览' })); fireEvent.click(screen.getByRole('button', { name: '预检并比较目录' }));
  await screen.findByRole('button', { name: '确认安装这个版本' });
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/install'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '确认安装这个版本' })); await screen.findByRole('button', { name: '卸载本地目录记录' });
  fireEvent.click(screen.getByRole('button', { name: '复制为本项目版本' })); await screen.findByLabelText('项目副本内容 JSON');
  fireEvent.change(screen.getByLabelText('项目副本内容 JSON'), { target: { value: JSON.stringify({ sections: [{ key: 'goal', title: '目标', text: '我的手工修改' }] }) } });
  fireEvent.click(screen.getByRole('button', { name: '保存副本编辑' })); await screen.findByText(/内容 v2/);
  fireEvent.click(screen.getByRole('button', { name: '比较模板更新' })); await screen.findByRole('button', { name: '应用已比较的模板更新' });
  expect((screen.getByRole('button', { name: '应用已比较的模板更新' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('我确认替换手工编辑的库中副本；旧内容保留在历史中'));
  fireEvent.click(screen.getByRole('button', { name: '应用已比较的模板更新' })); await screen.findByText(/内容 v3/);
  fireEvent.click(screen.getByRole('button', { name: '查看副本历史' })); await screen.findByLabelText('要恢复的副本历史版本');
  fireEvent.change(screen.getByLabelText('要恢复的副本历史版本'), { target: { value: '1' } }); fireEvent.click(screen.getByRole('button', { name: '恢复为新的副本版本' })); await screen.findByText(/内容 v4/);
  expect(fetch.mock.calls.some(([url]) => /execute|approve|generate/.test(url))).toBe(false);
});
it('late preview cannot replace changed import JSON or a new client scope', async () => {
  const base = libraryTransport(); let resolve!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/preview') ? new Promise<Response>(r => { resolve = r; }) : base(url, init)));
  const view = render(<TemplateLibraryPanel client={client()} />); await screen.findByLabelText('模板目录 JSON');
  fireEvent.change(screen.getByLabelText('模板目录 JSON'), { target: { value: JSON.stringify(pkg) } });
  fireEvent.click(screen.getByRole('button', { name: '预检并比较目录' }));
  fireEvent.change(screen.getByLabelText('模板目录 JSON'), { target: { value: '{"new":"draft"}' } });
  await act(async () => resolve(reply({ package: pkg, expected_version: 0, preview_digest: 'b'.repeat(64), diff: { lines: [], truncated: false }, missing_dependencies: [] })));
  expect(screen.queryByRole('button', { name: '确认安装这个版本' })).toBeNull();
  expect((screen.getByLabelText('模板目录 JSON') as HTMLTextAreaElement).value).toBe('{"new":"draft"}');
  view.rerender(<TemplateLibraryPanel client={client('two')} />); await screen.findByLabelText('模板目录 JSON');
  expect((screen.getByLabelText('模板目录 JSON') as HTMLTextAreaElement).value).toBe('');
});

it('requires a separate exact model preview confirmation and never auto dispatches or approves a deferred model node', async () => {
  const modelWorkflow: AuthoredWorkflow = { ...workflow, agent: { ...workflow.agent, model_route: 'registered-model' }, nodes: workflow.nodes.map(n => n.id === 'prepare' ? { ...n, type: 'agent_task' } : n) };
  let row: AgentRun = { ...waiting, definition_snapshot: modelWorkflow, current_node_id: 'prepare', model_preview: null };
  const base = agentTransport();
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/runs')) return reply({ items: [row] });
    if (url.endsWith('/model/preview')) { row = { ...row, version: 3, model_preview: { preview_digest: 'e'.repeat(64), source_strategy: 'NO_MANUSCRIPT', execution_available: true, request: { prompt: 'Synthetic exact request', context: {} }, broker: { chosen: { provider_id: 'mock', model_id: 'mock-writer', synthetic: true, cost_state: 'KNOWN_SYNTHETIC_ZERO', price: { reserve_microusd: 0 } }, candidates: [] }, quality_verification: 'NOT_RUN' } }; return reply(row); }
    if (url.endsWith('/model/dispatch')) { row = { ...row, version: 5, status: 'RUNNING', model_execution: { job_id: 'original-job', node_id: 'prepare', reservation_id: 'original-reservation', status: 'QUEUED', receipt_state: 'RECORDED', usage_state: 'UNKNOWN', quality_verification: 'NOT_RUN' } }; return reply(row); }
    if (url.endsWith('/model/refresh')) { row = { ...row, version: 6, model_execution: { ...row.model_execution!, status: 'UNKNOWN', receipt_state: 'UNKNOWN_NO_AUTOMATIC_REPLAY' } }; return reply(row); }
    return base(url, init);
  });
  vi.stubGlobal('fetch', fetch); render(<StrictMode><DeclarativeAgentsPanel client={client()} /></StrictMode>);
  await waitFor(() => expect((screen.getByLabelText('查看 Workflow 运行') as HTMLSelectElement).options.length).toBe(2));
  fireEvent.change(screen.getByLabelText('查看 Workflow 运行'), { target: { value: 'run-one' } });
  expect(screen.queryByRole('button', { name: '批准当前审核节点' })).toBeNull();
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '预览精确模型请求与费用' }));
  await screen.findByText(/正文策略 NO_MANUSCRIPT/);
  expect((screen.getByRole('button', { name: '明确启动这个模型节点' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对精确请求、模型、来源、零成本预留与本地限制'));
  const launch = screen.getByRole('button', { name: '明确启动这个模型节点' }); fireEvent.click(launch); fireEvent.click(launch);
  await screen.findByText(/原任务 original-job/);
  const calls = fetch.mock.calls.filter(([url]) => url.endsWith('/model/dispatch'));
  expect(calls).toHaveLength(1);
  expect(JSON.parse(calls[0][1]!.body as string)).toEqual({ expected_version: 3, reviewed_preview_digest: 'e'.repeat(64) });
  expect((screen.getByRole('button', { name: '暂停运行' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '刷新原模型任务并核对输出' }));
  await screen.findByText(/原执行或结算回执未知/);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/model/dispatch'))).toHaveLength(1);
});

it('late model preview cannot restore data after the captured client scope changes', async () => {
  const modelWorkflow: AuthoredWorkflow = { ...workflow, nodes: workflow.nodes.map(n => n.id === 'prepare' ? { ...n, type: 'agent_task' } : n) };
  const initial = { ...waiting, definition_snapshot: modelWorkflow, current_node_id: 'prepare' };
  const base = agentTransport(initial); let resolve!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/model/preview') ? new Promise<Response>(r => { resolve = r; }) : base(url, init)));
  const view = render(<DeclarativeAgentsPanel client={client()} />);
  await waitFor(() => expect((screen.getByLabelText('查看 Workflow 运行') as HTMLSelectElement).options.length).toBe(2));
  fireEvent.change(screen.getByLabelText('查看 Workflow 运行'), { target: { value: 'run-one' } });
  fireEvent.click(screen.getByRole('button', { name: '预览精确模型请求与费用' }));
  view.rerender(<DeclarativeAgentsPanel client={client('two')} />);
  await screen.findByLabelText('Agent 名称');
  await act(async () => resolve(reply({ ...initial, model_preview: { request: { prompt: 'OLD_SCOPE_SECRET' } } })));
  expect(screen.queryByText(/OLD_SCOPE_SECRET/)).toBeNull();
  expect(screen.queryByRole('button', { name: '明确启动这个模型节点' })).toBeNull();
});
