// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { ExperimentalClient } from './api';
import { WorkflowInspectionPanel } from './WorkflowInspectionPanel';

const metadata = { runtimes: [{ id: 'runtime-fixture', label: 'ComfyUI 1', observed_status: 'RUNNING', version: 'fixture' }], snapshot_state: 'COMPLETED', limits: { nodes: 256 }, official_sources: [] };
const summary = { schema: 'local-ai-workflow-inspection-v1', status: 'REVIEW_REQUIRED', execution_policy: 'DENY_ALL', counts: { nodes: 1, edges: 0, model_components: 0 }, issue_codes: ['IMPORTED_GRAPH_HAS_NO_REVIEWED_ADAPTER'], raw_workflow_included: false };
const result = { ...summary, nodes: [], edges: [], model_components: [], outputs: [], issues: [{ code: 'IMPORTED_GRAPH_HAS_NO_REVIEWED_ADAPTER', severity: 'UNKNOWN' }], adapters: [], declared_alias: { label: null }, export_summary: summary };
function client() { return { get: vi.fn(async (path: string) => path.endsWith('/reports') ? { items: [] } : metadata), post: vi.fn(async () => result), put: vi.fn(), blob: vi.fn() } as unknown as ExperimentalClient; }
function fill() { fireEvent.change(screen.getByLabelText('ComfyUI API 工作流 JSON'), { target: { value: '{"1":{"class_type":"SaveImage","inputs":{}}}' } }); }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('WorkflowInspectionPanel passive API flow', () => {
  it('sends actual imported JSON to scoped API and shows unavailable execution honestly', async () => {
    const api = client(); render(<WorkflowInspectionPanel client={api} />);
    await screen.findByText('快照：COMPLETED'); fill();
    fireEvent.change(screen.getByLabelText('ComfyUI 运行时快照'), { target: { value: 'runtime-fixture' } });
    fireEvent.click(screen.getByRole('button', { name: '检查工作流' }));
    await screen.findByRole('region', { name: '工作流检查结果' });
    expect(api.post).toHaveBeenCalledWith('/local-ai/workflow-inspections/inspect', { workflow_json: '{"1":{"class_type":"SaveImage","inputs":{}}}', runtime_id: 'runtime-fixture', declared_alias: '' });
    expect(screen.getByText(/导入图未绑定经过审核/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /执行工作流/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重新检查并保存脱敏摘要' }));
    await screen.findByText('已保存重新检查后的脱敏摘要，未保存工作流或输入值。');
    expect(api.post).toHaveBeenLastCalledWith('/local-ai/workflow-inspections/reports', expect.objectContaining({ runtime_id: 'runtime-fixture' }));
  });
  it('retains input after permission failure and supports retry', async () => {
    const api = client(); vi.mocked(api.post).mockRejectedValueOnce(new ApiError({ status: 403, code: 'FORBIDDEN', message: '当前身份没有此操作权限。' }));
    render(<WorkflowInspectionPanel client={api} />); await screen.findByText('快照：COMPLETED'); fill();
    fireEvent.click(screen.getByRole('button', { name: '检查工作流' }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect((screen.getByLabelText('ComfyUI API 工作流 JSON') as HTMLTextAreaElement).value).toContain('SaveImage');
    fireEvent.click(screen.getByRole('button', { name: '检查工作流' }));
    await screen.findByRole('region', { name: '工作流检查结果' });
  });
  it('clearing while pending prevents a late response restoring private results', async () => {
    const api = client(); let finish: (value: unknown) => void = () => {};
    vi.mocked(api.post).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    render(<WorkflowInspectionPanel client={api} />); await screen.findByText('快照：COMPLETED'); fill();
    fireEvent.click(screen.getByRole('button', { name: '检查工作流' }));
    expect(await screen.findByText('正在读取或检查…')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '清除输入与结果' })); finish(result);
    await waitFor(() => expect(screen.queryByRole('region', { name: '工作流检查结果' })).toBeNull());
    expect((screen.getByLabelText('ComfyUI API 工作流 JSON') as HTMLTextAreaElement).value).toBe('');
  });
  it('scope changes clear input and fence old responses', async () => {
    const api = client(); let finish: (value: unknown) => void = () => {};
    vi.mocked(api.post).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const view = render(<WorkflowInspectionPanel client={api} />); await screen.findByText('快照：COMPLETED'); fill();
    fireEvent.click(screen.getByRole('button', { name: '检查工作流' }));
    view.rerender(<WorkflowInspectionPanel client={client()} />); finish(result);
    await waitFor(() => expect(screen.queryByRole('region', { name: '工作流检查结果' })).toBeNull());
    expect((screen.getByLabelText('ComfyUI API 工作流 JSON') as HTMLTextAreaElement).value).toBe('');
  });
  it('imports file contents without uploading or running it automatically', async () => {
    const api = client(); render(<WorkflowInspectionPanel client={api} />); await screen.findByText('快照：COMPLETED');
    const file = { size: 42, text: vi.fn().mockResolvedValue('{"1":{"class_type":"Custom","inputs":{}}}') };
    fireEvent.change(screen.getByLabelText('导入 ComfyUI API JSON 文件'), { target: { files: [file] } });
    await waitFor(() => expect((screen.getByLabelText('ComfyUI API 工作流 JSON') as HTMLTextAreaElement).value).toContain('Custom'));
    expect(api.post).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('导入 ComfyUI API JSON 文件'), { target: { files: [{ size: 524289, text: vi.fn() }] } });
    expect(await screen.findByText(/文件超过 512 KiB/)).toBeTruthy();
  });
  it('downloading uses only server allowlisted summary', async () => {
    const api = client(); const create = vi.fn().mockReturnValue('blob:summary'), revoke = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', { value: create, configurable: true }); Object.defineProperty(URL, 'revokeObjectURL', { value: revoke, configurable: true });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<WorkflowInspectionPanel client={api} />); await screen.findByText('快照：COMPLETED'); fill();
    fireEvent.click(screen.getByRole('button', { name: '检查工作流' })); await screen.findByRole('region', { name: '工作流检查结果' });
    fireEvent.click(screen.getByRole('button', { name: '下载脱敏摘要' }));
    expect(create).toHaveBeenCalledTimes(1); expect(create.mock.calls[0][0].type).toBe('application/json');
    await waitFor(() => expect(revoke).toHaveBeenCalledWith('blob:summary'));
  });
});
