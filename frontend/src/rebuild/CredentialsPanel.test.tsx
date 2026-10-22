// @vitest-environment jsdom
// [HERMIA-FE-20261022 REBUILD-2]
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CredentialsPanel } from './CredentialsPanel';
const wrap = () => render(<QueryClientProvider client={new QueryClient()}><CredentialsPanel /></QueryClientProvider>);
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
let f: ReturnType<typeof vi.fn>;
beforeEach(() => { f = vi.fn(); vi.stubGlobal('fetch', f); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const ok = (url: string, init?: RequestInit) => {
  if (url === '/api/model-center/health') return json({ status: 'READY', models: 14, ready_models: 7, runtimes: 2, mutation_authorization: { can_mutate: false } });
  if (url.endsWith('/test')) return json({ provider: 'openai', configured: false, reachable: false });
  if (init?.method === 'PUT') return json({ provider: 'openai', configured: true });
  return json({ provider: url.split('/').pop(), configured: url.endsWith('deepseek'), degraded: true, degraded_reason: 'KEYRING_NOT_INSTALLED' });
};
describe('CredentialsPanel', () => {
  it('shows model-center capability and per-provider honest status', async () => {
    f.mockImplementation(ok); wrap();
    await screen.findByText('模型中心 就绪');
    expect(screen.getByText('可用模型 7/14')).toBeTruthy();
    expect(screen.getByText('修改模型需登录会话')).toBeTruthy();
    expect(await screen.findByText(/系统密钥库不可用/)).toBeTruthy();
    const ds = document.querySelector('[data-provider="deepseek"]') as HTMLElement;
    expect(await within(ds).findByText('已配置·未持久')).toBeTruthy();
  });
  it('save PUTs credential and never echoes it; test reports unconfigured', async () => {
    f.mockImplementation(ok); wrap();
    const input = await screen.findByLabelText('OpenAI 密钥');
    fireEvent.change(input, { target: { value: 'sk-secret' } });
    const row = document.querySelector('[data-provider="openai"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: '保存' }));
    await within(row).findByText('已保存');
    const put = f.mock.calls.find(c => c[1]?.method === 'PUT')!;
    expect(put[0]).toBe('/api/credentials/openai'); expect(JSON.parse(put[1].body)).toEqual({ provider: 'openai', credential: 'sk-secret' });
    expect((input as HTMLInputElement).value).toBe('');
    fireEvent.click(within(row).getByRole('button', { name: '测试' }));
    await within(row).findByText('未配置，无法测试');
  });
  it('backend down → error tags, no green', async () => {
    f.mockImplementation(() => Promise.reject(new TypeError('down'))); wrap();
    expect(await screen.findByText(/模型中心：后端不可用/)).toBeTruthy();
    expect(document.querySelector('.rb-tag[data-tone="ok"]')).toBeNull();
  });
});
