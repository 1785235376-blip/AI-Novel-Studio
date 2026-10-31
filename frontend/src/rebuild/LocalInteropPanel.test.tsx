// @vitest-environment jsdom
// [HERMIA-FE-20261022 REBUILD-5]
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LocalInteropPanel, isLoopbackEndpoint } from './LocalInteropPanel';
import { useStudio } from '../store';
const wrap = () => render(<QueryClientProvider client={new QueryClient()}><LocalInteropPanel /></QueryClientProvider>);
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
let f: ReturnType<typeof vi.fn>;
beforeEach(() => { useStudio.setState({ novelId: 'n1' }); f = vi.fn(); vi.stubGlobal('fetch', f); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('LocalInteropPanel', () => {
  it('loopback validation', () => { expect(isLoopbackEndpoint('http://127.0.0.1:8188')).toBe(true); expect(isLoopbackEndpoint('http://example.com:80')).toBe(false); expect(isLoopbackEndpoint('https://127.0.0.1:1')).toBe(false); });
  it('status SESSION_REQUIRED frame is shown honestly, not connected', async () => {
    f.mockImplementation(() => json({ protocol_name: 'PoemSeed Local Interop', code: 'SESSION_REQUIRED' }));
    wrap(); expect(await screen.findByText('请先连接已授权的本机 Tutor。')).toBeTruthy();
    expect(screen.getByText('未连接')).toBeTruthy(); expect(document.querySelector('.rb-tag[data-tone="ok"]')).toBeNull();
    expect(f.mock.calls[0][0]).toBe('/api/local-interop/status');
  });
  it('connect POSTs /local-interop/connect; mock mode is not green', async () => {
    f.mockImplementation((url: string) => url.endsWith('/connect') ? json({ request_id: 'r', session_id: 's1', protocol_session_id: 'p', product: { display_name: 'ComfyUI' }, capabilities: [], desktop_status: 'LOCAL_REQUIRED', mode: 'MOCK_ONLY', subscription_active: false, metadata_fields: [] })
      : json({ feature_enabled: true, enabled: true, acceptance_mode: false, product: {}, capabilities: ['a'], disabled_capabilities: [], desktop_status: 'LOCAL_REQUIRED' }));
    wrap(); await screen.findByText('互通可用');
    fireEvent.click(screen.getByRole('button', { name: '连接' }));
    expect(await screen.findByText('模拟连接')).toBeTruthy();
    const post = f.mock.calls.find(c => String(c[0]).endsWith('/connect'))!;
    const body = JSON.parse(post[1].body); expect(body.endpoint).toBe('http://127.0.0.1:8188'); expect(body.project_id).toBe('n1');
  });
  it('non-loopback disables connect', async () => {
    f.mockImplementation(() => json({}, 404)); wrap();
    fireEvent.change(screen.getByLabelText('本机地址'), { target: { value: 'http://evil.com:80' } });
    expect((screen.getByRole('button', { name: '连接' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('地址必须是 http://127.0.0.1:端口')).toBeTruthy();
  });
});
