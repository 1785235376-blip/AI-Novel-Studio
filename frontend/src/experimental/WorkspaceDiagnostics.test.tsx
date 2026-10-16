// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { WorkspaceDiagnostics } from './WorkspaceDiagnostics';
import { diagnosticGuidance } from './diagnosticGuidance';
import type { DiagnosticResult, workspaceClient } from './uxClient';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const result: DiagnosticResult = { schema: 'workspace-diagnostics-v1', uploaded: false, preview_digest: 'a'.repeat(64), sections: { error_codes: ['TIMEOUT', 'UNCLASSIFIED'], task_states: [{ authority: 'media', status: 'UNKNOWN', cost_state: 'UNKNOWN' }], coverage: { truncated: true, raw_logs_included: false } } };
function fixture() {
  const preview = vi.fn().mockResolvedValue(result), exportReport = vi.fn().mockResolvedValue(result);
  const api = { preview, export: exportReport } as unknown as ReturnType<typeof workspaceClient>;
  return { api, preview, exportReport };
}
const generate = () => fireEvent.click(screen.getByRole('button', { name: '生成诊断预览' }));
const exportDisabled = () => (screen.getByRole('button', { name: '导出已选诊断项' }) as HTMLButtonElement).disabled;

it('makes bounded coverage and unknown result guidance visible without executing a task', async () => {
  const f = fixture(); render(<WorkspaceDiagnostics api={f.api} />);
  expect(f.preview).not.toHaveBeenCalled(); generate();
  await screen.findByText(/本次诊断达到读取上限/);
  expect(screen.getByText(/等待超时不代表任务未执行/)).toBeTruthy();
  expect(screen.getByText(/未提供可确认的错误分类/)).toBeTruthy();
  expect(f.exportReport).not.toHaveBeenCalled();
});
it('removes the old preview immediately on recheck and keeps export disabled on read failure', async () => {
  const f = fixture(); render(<WorkspaceDiagnostics api={f.api} />); generate();
  await screen.findByRole('region', { name: '诊断预览' });
  let reject!: (error: Error) => void;
  f.preview.mockImplementationOnce(() => new Promise((_, fail) => { reject = fail; }));
  fireEvent.click(screen.getByRole('button', { name: '重新核对诊断预览' }));
  expect(screen.queryByRole('region', { name: '诊断预览' })).toBeNull(); expect(exportDisabled()).toBe(true);
  await act(async () => reject(new Error('offline')));
  await screen.findByText('读取或操作失败，请重试。'); expect(exportDisabled()).toBe(true);
  generate(); await screen.findByRole('region', { name: '诊断预览' });
  await waitFor(() => expect(exportDisabled()).toBe(false));
});
it('uses the original digest and invalidates an export refused for changed source state', async () => {
  const f = fixture();
  f.exportReport.mockRejectedValueOnce(new ApiError({ status: 409, code: 'EXPERIMENTAL_SOURCE_STALE', message: 'changed' }));
  render(<WorkspaceDiagnostics api={f.api} />); generate();
  await waitFor(() => expect(exportDisabled()).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '导出已选诊断项' }));
  await waitFor(() => expect(screen.queryByRole('region', { name: '诊断预览' })).toBeNull());
  expect(f.exportReport).toHaveBeenCalledWith({ include_environment: true, include_task_states: true, include_error_codes: true }, result.preview_digest);
  expect(exportDisabled()).toBe(true);
});
it('does not resurrect an old preview after an A to B to A scope round trip', async () => {
  const first = fixture(); let finish!: (result: DiagnosticResult) => void;
  first.preview.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const view = render(<WorkspaceDiagnostics key="first" api={first.api} />); generate();
  const second = fixture(); view.rerender(<WorkspaceDiagnostics key="second" api={second.api} />);
  view.rerender(<WorkspaceDiagnostics key="first" api={first.api} />);
  await act(async () => finish(result));
  expect(screen.queryByRole('region', { name: '诊断预览' })).toBeNull(); expect(exportDisabled()).toBe(true);
});
it('offers truthful fallback for unregistered codes and prototype names', () => {
  expect(diagnosticGuidance('made-up')).toContain('无法仅凭诊断包判断原因');
  expect(diagnosticGuidance('toString')).toEqual(diagnosticGuidance('UNCLASSIFIED'));
  expect(diagnosticGuidance('PERMISSION_DENIED')).toContain('不要反复提交');
  expect(diagnosticGuidance('VERSION_CONFLICT')).toContain('保留当前草稿');
});

it('downloads only the original digest-bound export result after explicit selection', async () => {
  const f = fixture();
  const createObjectURL = vi.fn().mockReturnValue('blob:diagnostic-fixture');
  const revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  render(<WorkspaceDiagnostics api={f.api} />); generate();
  await waitFor(() => expect(exportDisabled()).toBe(false));
  expect(createObjectURL).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '导出已选诊断项' }));
  await screen.findByText('已请求下载诊断包，未上传');
  expect(click).toHaveBeenCalledTimes(1);
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:diagnostic-fixture');
  const blob = createObjectURL.mock.calls[0][0] as Blob;
  const exported = await new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
  expect(JSON.parse(exported)).toEqual(result);
  expect(exported).not.toContain('等待超时');
});
