// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, type ExportJob } from '../api';
import { ExportPanel } from './ExportPanel';

const jobs: ExportJob[] = ['a', 'b'].map(id => ({ id: `export-${id}`, novel_id: 'novel-feedback',
  format: 'txt', status: 'succeeded', created_at: '', updated_at: '', result: { format: 'txt', filename: `${id}.txt` } }));
const clients: QueryClient[] = [];
const handoffText = /已请求浏览器下载 a.txt/;
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}><ExportPanel novelId="novel-feedback" /></QueryClientProvider>);
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
function select(id: 'a' | 'b') { fireEvent.click(screen.getByRole('button', { name: new RegExp(`TXT 小说 · 已完成 · export-${id}`) })); }
beforeEach(() => {
  vi.spyOn(api, 'exportHistory').mockResolvedValue({ items: jobs, next_offset: null });
  vi.spyOn(api, 'exportJob').mockImplementation(async id => jobs.find(job => job.id === id)!);
  const OriginalURL = URL;
  class DownloadURL extends OriginalURL {
    static createObjectURL = vi.fn(() => 'blob:feedback');
    static revokeObjectURL = vi.fn();
  }
  vi.stubGlobal('URL', DownloadURL);
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('Export download feedback', () => {
  it('reports browser handoff only after requesting it and explains where to confirm the saved file', async () => {
    const pending = deferred<Blob>();
    vi.spyOn(api, 'exportDownload').mockReturnValue(pending.promise);
    mount();
    fireEvent.click(await screen.findByRole('button', { name: '下载 a.txt' }));
    expect(screen.queryByText(handoffText)).toBeNull();
    await act(async () => pending.resolve(new Blob(['original artifact'])));
    const receipt = await screen.findByText(handoffText);
    expect(receipt.textContent).toContain('浏览器下载列表');
    expect(receipt.textContent).toContain('是否已保存');
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/已保存到|下载成功/)).toBeNull();
  });

  it('keeps a failed download attached to its own task when another history item is selected', async () => {
    vi.spyOn(api, 'exportDownload').mockRejectedValue(new ApiError({ status: 500, code: 'DOWNLOAD_A_FAILED', message: '下载暂不可用' }));
    mount();
    fireEvent.click(await screen.findByRole('button', { name: '下载 a.txt' }));
    await screen.findByText('DOWNLOAD_A_FAILED');
    select('b');
    await screen.findByRole('button', { name: '下载 b.txt' });
    expect(screen.queryByText('DOWNLOAD_A_FAILED')).toBeNull();
    select('a');
    await screen.findByRole('button', { name: '下载 a.txt' });
    expect(screen.getByText('DOWNLOAD_A_FAILED')).toBeTruthy();
    expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
  });

  it('explains the existing single-download wait when selecting a different task during a request', async () => {
    const pending = deferred<Blob>();
    const download = vi.spyOn(api, 'exportDownload').mockReturnValue(pending.promise);
    mount();
    fireEvent.click(await screen.findByRole('button', { name: '下载 a.txt' }));
    await screen.findByRole('button', { name: '准备下载…' });
    select('b');
    const waiting = await screen.findByRole('button', { name: '等待上一项下载…' });
    expect((waiting as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/正在准备另一项任务的文件 a.txt/)).toBeTruthy();
    fireEvent.click(waiting);
    expect(download).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(new Blob(['original artifact'])));
    await screen.findByRole('button', { name: '下载 b.txt' });
    expect(screen.queryByText(handoffText)).toBeNull();
    select('a');
    await screen.findByText(handoffText);
  });

  it('clears a prior handoff receipt when a fresh attempt fails without claiming a second download', async () => {
    vi.spyOn(api, 'exportDownload').mockResolvedValueOnce(new Blob(['artifact'])).mockRejectedValueOnce(new ApiError({ status: 500, code: 'SECOND_DOWNLOAD_FAILED', message: '下载失败，请重试。' }));
    mount();
    fireEvent.click(await screen.findByRole('button', { name: '下载 a.txt' }));
    await screen.findByText(handoffText);
    fireEvent.click(screen.getByRole('button', { name: '下载 a.txt' }));
    await screen.findByText('下载失败，请重试。');
    expect(screen.queryByText(handoffText)).toBeNull();
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
  });

  it('keeps URL-creation failures recoverable without requesting a browser download', async () => {
    vi.spyOn(api, 'exportDownload').mockResolvedValue(new Blob(['artifact']));
    vi.mocked(URL.createObjectURL).mockImplementationOnce(() => { throw new Error('synthetic URL failure'); });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: '下载 a.txt' }));
    await screen.findByText(/浏览器未能开始下载，请重试/);
    expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    expect(screen.queryByText(handoffText)).toBeNull();
    expect((screen.getByRole('button', { name: '下载 a.txt' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('recovers visibly if the browser file handoff fails and releases its temporary URL', async () => {
    vi.spyOn(api, 'exportDownload').mockResolvedValue(new Blob(['artifact']));
    vi.mocked(HTMLAnchorElement.prototype.click).mockImplementationOnce(() => { throw new Error('synthetic browser handoff failure'); });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: '下载 a.txt' }));
    await screen.findByText(/浏览器未能开始下载，请重试/);
    expect(screen.queryByText(handoffText)).toBeNull();
    expect(document.querySelector('a[download]')).toBeNull();
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:feedback'));
    expect((screen.getByRole('button', { name: '下载 a.txt' }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '下载 a.txt' }));
    await screen.findByText(handoffText);
  });
});
