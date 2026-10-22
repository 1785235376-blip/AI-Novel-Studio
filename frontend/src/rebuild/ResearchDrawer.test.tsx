// @vitest-environment jsdom
// [HERMIA-FE-20261022 REBUILD-3]
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ResearchBody } from './ResearchDrawer';
const wrap = () => render(<QueryClientProvider client={new QueryClient()}><ResearchBody novelId="n1" /></QueryClientProvider>);
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
let f: ReturnType<typeof vi.fn>; let store: any[];
beforeEach(() => { store = [{ id: 'r1', title: '旧港档案', source_type: 'ARCHIVE', notes: '1931 年码头' }]; f = vi.fn((url: string, init?: RequestInit) => {
  if (url.endsWith('/knowledge-base/review')) return json({ detail: { code: 'KNOWLEDGE_REVIEW_SOURCE_EMPTY', message: '小说尚无可审查的章节正文' }, code: 'KNOWLEDGE_REVIEW_SOURCE_EMPTY', message: '小说尚无可审查的章节正文' }, 422);
  if (init?.method === 'POST') { const b = JSON.parse(String(init.body)); const r = { id: 'r2', ...b }; store.push(r); return json(r, 201); }
  if (init?.method === 'DELETE') { store = store.filter(r => !url.endsWith(r.id)); return json({ ok: true }); }
  return json({ items: store, total: store.length, external_fetch: false });
}); vi.stubGlobal('fetch', f); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('ResearchBody', () => {
  it('lists research from GET /novels/{nid}/research', async () => {
    wrap(); expect(await screen.findByText('旧港档案')).toBeTruthy();
    expect(f.mock.calls[0][0]).toBe('/api/novels/n1/research'); expect(screen.getByText('不联网抓取')).toBeTruthy();
  });
  it('adds via POST and deletes via DELETE', async () => {
    wrap(); await screen.findByText('旧港档案');
    fireEvent.change(screen.getByLabelText('资料标题'), { target: { value: '雾港码头' } });
    fireEvent.click(screen.getByRole('button', { name: '添加资料' }));
    expect(await screen.findByText('雾港码头')).toBeTruthy();
    expect(JSON.parse(f.mock.calls.find(c => c[1]?.method === 'POST')![1].body).title).toBe('雾港码头');
    fireEvent.click(screen.getByRole('button', { name: '删除 旧港档案' }));
    await vi.waitFor(() => expect(screen.queryByText('旧港档案')).toBeNull());
  });
  it('knowledge-base review surfaces the honest backend reason', async () => {
    wrap(); await screen.findByText('旧港档案');
    fireEvent.click(screen.getByRole('button', { name: '从正文生成知识库审阅' }));
    expect(await screen.findByText('知识库：小说尚无可审查的章节正文')).toBeTruthy();
  });
  it('filter shows honest empty', async () => {
    wrap(); await screen.findByText('旧港档案');
    fireEvent.change(screen.getByLabelText('筛选资料'), { target: { value: 'zzz' } });
    expect(screen.getByText('没有匹配的资料。')).toBeTruthy();
  });
});
