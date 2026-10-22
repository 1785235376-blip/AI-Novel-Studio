// @vitest-environment jsdom
// [HERMIA-FE-20261022 REBUILD-4]
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TasksBody } from './TasksMenu';
const wrap = () => render(<QueryClientProvider client={new QueryClient()}><TasksBody novelId="n1" /></QueryClientProvider>);
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
let f: ReturnType<typeof vi.fn>;
beforeEach(() => { f = vi.fn((url: string) => {
  if (url.endsWith('/media-tasks')) return json({ novel_id: 'n1', audiobook: [{ id: 'a1', status: 'running', chapter_id: 'c123456' }], motion: [] });
  if (url.endsWith('/asset-tasks/stats')) return json({ total: 3, by_status: { PENDING: 1, RUNNING: 0, SUCCEEDED: 1, FAILED: 1 }, latest_at: null });
  if (url.endsWith('/workspace/tasks')) return json({ code: 'EXPERIMENTAL_FEATURE_DISABLED', detail: { code: 'EXPERIMENTAL_FEATURE_DISABLED' }, message: 'EXPERIMENTAL_FEATURE_DISABLED' }, 409);
  if (url.includes('/api/exports')) return json({ items: [{ id: 'e1', novel_id: 'n1', format: 'pdf', status: 'failed' }] });
  if (url.endsWith('/asset-trash')) return json({ items: [{ id: 't1', name: '旧封面.png', kind: 'image' }], total: 1 });
  return json({}, 404);
}); vi.stubGlobal('fetch', f); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('TasksBody', () => {
  it('merges media / asset stats / exports and flags the disabled source honestly', async () => {
    wrap();
    expect(await screen.findByText('章节 c12345')).toBeTruthy();
    expect(await screen.findByText('PDF')).toBeTruthy();
    expect(screen.getByText('失败 1')).toBeTruthy(); expect(screen.getByText('排队 1')).toBeTruthy();
    expect(await screen.findByText('工作区任务：后端未开启此功能（实验开关关闭）')).toBeTruthy();
    const urls = f.mock.calls.map(c => c[0]);
    for (const u of ['/api/novels/n1/media-tasks', '/api/novels/n1/asset-tasks/stats', '/api/novels/n1/experimental/workspace/tasks']) expect(urls).toContain(u);
  });
  it('trash tab reads asset-trash', async () => {
    wrap(); fireEvent.click(screen.getByRole('tab', { name: '回收站' }));
    expect(await screen.findByText('旧封面.png')).toBeTruthy();
    expect(f.mock.calls.map(c => c[0])).toContain('/api/novels/n1/asset-trash');
  });
});
