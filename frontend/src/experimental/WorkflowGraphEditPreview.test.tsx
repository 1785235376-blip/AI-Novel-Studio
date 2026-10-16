// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { previewCheckpointEdit } from './workflowGraphEditing';
import { WorkflowGraphEditPreview } from './WorkflowGraphEditPreview';
import { DeclarativeAgentsPanel } from './DeclarativeAgentsPanel';
import { experimentalClient } from './api';
import type { AuthoredWorkflow } from './declarativeAgentsClient';
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const graph = (): AuthoredWorkflow => ({ agent: { title: 'Original definition', purpose: 'Preserve purpose', role_prompt: 'Preserve prompt', input_schema: { fields: [{ name: 'source_text', type: 'string', required: true, max_length: 8000 }] }, output_schema: { fields: [{ name: 'draft', type: 'string', required: true, max_length: 8000 }] }, allowed_tools: ['draft_prepare'], model_route: null, review_required: true, max_steps: 8, timeout_seconds: 30, max_output_bytes: 64000, max_cost_microusd: 0 }, nodes: [{ id: 'prepare', type: 'draft_prepare', name: 'Prepare' }, { id: 'review', type: 'manual_approval', name: 'Review' }, { id: 'artifact', type: 'review_artifact', name: 'Artifact' }], edges: [{ source: 'prepare', target: 'review' }, { source: 'review', target: 'artifact' }] });
const props = () => ({ definition: graph(), editorRevision: 0, contextKey: 'definition:1:digest', disabled: false, onApply: vi.fn() });
function preview() { fireEvent.change(screen.getByLabelText('待插入检查点的连接'), { target: { value: '0' } }); fireEvent.click(screen.getByRole('button', { name: '预览检查点结构改动' })); }
const apply = () => screen.getByRole('button', { name: '将结构预览填入当前草稿' });
it('is explicitly local and unvalidated; cancel preserves the entire draft and performs no request', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); const p = props(); render(<WorkflowGraphEditPreview {...p} />); preview();
  expect(screen.getByText(/尚未经过服务端验证/)).toBeTruthy(); expect(p.onApply).not.toHaveBeenCalled(); expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '取消结构预览' })); expect(screen.queryByRole('button', { name: '将结构预览填入当前草稿' })).toBeNull(); expect(p.definition.nodes).toHaveLength(3);
});
it('fills one exact candidate only after explicit apply, without validation/save/run requests', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); const p = props(); render(<WorkflowGraphEditPreview {...p} />); preview(); const button = apply(); fireEvent.click(button); fireEvent.click(button);
  expect(p.onApply).toHaveBeenCalledOnce(); expect(p.onApply.mock.calls[0][0].agent).toEqual(p.definition.agent); expect(p.onApply.mock.calls[0][1]).toBe(0); expect(fetch).not.toHaveBeenCalled();
});
it.each(['edit', 'revision', 'identity', 'disabled'])('retires a preview after %s and never resurrects it after ABA', kind => {
  const p = props(), view = render(<WorkflowGraphEditPreview {...p} />); preview();
  const next = { ...p, ...(kind === 'edit' ? { definition: { ...p.definition, agent: { ...p.definition.agent, title: 'New' } } } : kind === 'revision' ? { editorRevision: 1 } : kind === 'identity' ? { contextKey: 'other' } : { disabled: true }) };
  view.rerender(<WorkflowGraphEditPreview {...next} />); view.rerender(<WorkflowGraphEditPreview {...p} />);
  expect(screen.queryByRole('button', { name: '将结构预览填入当前草稿' })).toBeNull(); expect(p.onApply).not.toHaveBeenCalled();
});
it('shows explicit invalid-adjacency feedback while preserving the draft', () => {
  const p = props(); render(<WorkflowGraphEditPreview {...p} />); fireEvent.change(screen.getByLabelText('待插入检查点的连接'), { target: { value: '1' } }); fireEvent.click(screen.getByRole('button', { name: '预览检查点结构改动' }));
  expect(screen.getByText(/不能在人工审核与末尾/)).toBeTruthy(); expect(p.onApply).not.toHaveBeenCalled();
});
const client = (id = 'one') => experimentalClient(id, { sessionToken: 'token-' + id, scope: { workspaceId: 'w', projectId: id, storylineId: 's', branchId: 'branch-' + id } });
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
function transport() {
  let row = { id: 'definition', version: 1, definition: graph(), definition_digest: 'a'.repeat(64) };
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return response({ tools: ['draft_prepare'], node_types: ['draft_prepare', 'checkpoint', 'manual_approval', 'review_artifact'], model_routes: [], default_definition: graph(), chapters: [] });
    if (url.endsWith('/definitions')) return response({ items: [row] });
    if (url.endsWith('/definitions/definition') && init.method === 'PUT') { row = { ...row, version: row.version + 1, definition: JSON.parse(String(init.body)).definition, definition_digest: 'b'.repeat(64) }; return response(row); }
    if (url.endsWith('/preflight')) return response({ valid: true, definition_digest: row.definition_digest, topological_order: row.definition.nodes.map(n => n.id), execution_available: true, blockers: [] });
    if (url.endsWith('/history?limit=20')) return response({ definition_id: row.id, current_version: row.version, current_definition_digest: row.definition_digest, items: [{ version: 0, title: 'Historic', definition_digest: 'c'.repeat(64), updated_at: '2026-10-16' }], next_before_version: null });
    if (url.endsWith('/history/0')) return response({ definition_id: row.id, current_version: row.version, current_definition_digest: row.definition_digest, version: 0, definition_digest: 'c'.repeat(64), definition: graph() });
    return response({ items: [] });
  });
  return { fetch, current: () => row };
}
async function mountSaved() {
  const server = transport(); vi.stubGlobal('fetch', server.fetch); const p = client(); const view = render(<DeclarativeAgentsPanel client={p} />);
  await screen.findByRole('option', { name: 'Original definition · v1' }); fireEvent.change(screen.getByLabelText('已保存的 Agent 定义'), { target: { value: 'definition' } });
  await screen.findByText(/已保存定义 definition · v1/); return { ...server, view, client: p };
}
it('mounted editor previews, applies, explicitly saves through the existing owner, then reopens the full definition', async () => {
  const server = await mountSaved(); const reads = server.fetch.mock.calls.length; preview(); expect(server.fetch.mock.calls).toHaveLength(reads);
  fireEvent.click(apply()); expect(server.fetch.mock.calls).toHaveLength(reads); expect(screen.getByLabelText('节点 2 类型')).toHaveProperty('value', 'checkpoint');
  expect(screen.getByLabelText('角色提示词')).toHaveProperty('value', 'Preserve prompt');
  fireEvent.click(screen.getByRole('button', { name: '保存 Agent 新版本' })); await screen.findByText(/已保存定义 definition · v2/);
  const writes = server.fetch.mock.calls.filter(([, init]) => init.method !== 'GET'); expect(writes).toHaveLength(1);
  expect(JSON.parse(String(writes[0][1].body))).toEqual({ expected_version: 1, definition: server.current().definition });
  server.view.unmount(); render(<DeclarativeAgentsPanel client={server.client} />); await screen.findByRole('option', { name: 'Original definition · v2' }); fireEvent.change(screen.getByLabelText('已保存的 Agent 定义'), { target: { value: 'definition' } });
  expect(screen.getByLabelText('节点 2 类型')).toHaveProperty('value', 'checkpoint');
  expect(server.fetch.mock.calls.some(([url]) => /preflight|execute|dispatch|\/runs\//.test(url))).toBe(false);
});
it.each(['refresh', 'edit', 'selection', 'identity'])('mounted %s retires the candidate without silently saving', async mode => {
  const server = await mountSaved(); preview();
  if (mode === 'refresh') { fireEvent.click(screen.getByRole('button', { name: '刷新授权目录与记录' })); await waitFor(() => expect(screen.getByLabelText('已保存的 Agent 定义')).toHaveProperty('disabled', false)); }
  if (mode === 'edit') fireEvent.change(screen.getByLabelText('Agent 名称'), { target: { value: 'Unsaved title' } });
  if (mode === 'selection') fireEvent.change(screen.getByLabelText('已保存的 Agent 定义'), { target: { value: '' } });
  if (mode === 'identity') { server.view.rerender(<DeclarativeAgentsPanel client={client('two')} />); await screen.findByLabelText('Agent 名称'); }
  expect(screen.queryByRole('button', { name: '将结构预览填入当前草稿' })).toBeNull(); expect(server.fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
it('applying retires history candidates and original graph review acknowledgement', async () => {
  await mountSaved(); fireEvent.click(screen.getByRole('button', { name: '读取最新定义历史' })); await screen.findByRole('option', { name: /v0 · Historic/ });
  fireEvent.change(screen.getByLabelText('查看 Agent 历史版本'), { target: { value: '0' } }); await screen.findByRole('button', { name: '将历史定义填入表单' });
  const checked = screen.getByLabelText(/已核对已保存图版本/); fireEvent.click(checked); expect(checked).toHaveProperty('checked', true);
  preview(); fireEvent.click(apply()); expect(screen.queryByRole('button', { name: '将历史定义填入表单' })).toBeNull(); expect(checked).toHaveProperty('checked', false);
});
it('keeps the existing dirty-selection confirmation and retires a structural preview when switching is requested', async () => {
  await mountSaved(); fireEvent.change(screen.getByLabelText('Agent 名称'), { target: { value: 'Keep this draft' } }); preview();
  fireEvent.change(screen.getByLabelText('已保存的 Agent 定义'), { target: { value: '' } }); expect(screen.queryByRole('button', { name: '将结构预览填入当前草稿' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '取消切换，保留草稿' })); expect(screen.getByLabelText('Agent 名称')).toHaveProperty('value', 'Keep this draft');
});

it('previews removing a single-in/single-out checkpoint and keeps the terminal approval', () => {
  const p = props(); p.definition = previewCheckpointEdit(p.definition, { kind: 'insert', source: 'prepare', target: 'review' }).definition;
  render(<WorkflowGraphEditPreview {...p} />);
  fireEvent.change(screen.getByLabelText('检查点结构操作'), { target: { value: 'remove' } });
  fireEvent.change(screen.getByLabelText('待移除的自动检查点'), { target: { value: 'checkpoint1' } });
  fireEvent.click(screen.getByRole('button', { name: '预览检查点结构改动' }));
  expect(screen.getByText('新增连接：prepare → review')).toBeTruthy(); expect(p.onApply).not.toHaveBeenCalled();
  fireEvent.click(apply()); expect(p.onApply.mock.calls[0][0]).toEqual(graph());
});
