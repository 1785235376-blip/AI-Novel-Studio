// @vitest-environment jsdom
// [HERMIA-FE-20261022 REBUILD-1]
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ExportBody } from './ExportMenu';
const wrap = (ui: React.ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => { fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); (URL as any).createObjectURL = vi.fn(() => 'blob:x'); (URL as any).revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('ExportBody', () => {
  it('novel export calls GET /novels/{nid}/export with format and reports download', async () => {
    fetchMock.mockImplementation(() => json({ format: 'markdown', filename: 'n1.md', content: '# a' }));
    wrap(<ExportBody novelId="n1" />);
    fireEvent.change(screen.getByLabelText('小说导出格式'), { target: { value: 'markdown' } });
    fireEvent.click(screen.getByRole('button', { name: '导出并下载' }));
    await screen.findByText('已下载 n1.md');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/novels/n1/export?format=markdown');
  });
  it('novel export failure is honest, not green', async () => {
    fetchMock.mockImplementation(() => Promise.reject(new TypeError('down')));
    wrap(<ExportBody novelId="n1" />);
    fireEvent.click(screen.getByRole('button', { name: '导出并下载' }));
    expect((await screen.findByText(/导出失败：后端不可用/)).getAttribute('data-tone')).toBe('err');
  });
  it('render tab lists /exports and creates with POST', async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => init?.method === 'POST' ? json({ id: 'j2', novel_id: 'n1', format: 'pdf', status: 'queued' }, 201) : json({ items: [{ id: 'j1', novel_id: 'n1', format: 'docx', status: 'completed' }] }));
    wrap(<ExportBody novelId="n1" initialTab="render" />);
    expect(await screen.findByRole('link', { name: '下载' })).toBeTruthy();
    expect(fetchMock.mock.calls[0][0]).toContain('/api/exports?novel_id=n1');
    fireEvent.change(screen.getByLabelText('成片导出格式'), { target: { value: 'pdf' } });
    fireEvent.click(screen.getByRole('button', { name: '新建导出任务' }));
    await screen.findByText(/已加入导出队列/);
    const post = fetchMock.mock.calls.find(c => c[1]?.method === 'POST')!;
    expect(post[0]).toBe('/api/exports?novel_id=n1'); expect(JSON.parse(post[1].body)).toEqual({ format: 'pdf' });
  });
  it('no novel → honest empty', () => { wrap(<ExportBody novelId="" />); expect(screen.getByText('先打开一部作品再导出。')).toBeTruthy(); });
});
