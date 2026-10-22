// @vitest-environment jsdom
// [HERMIA-FE-20261022 U6] 普通版简化媒体服务配置
import {describe, it, expect, vi, afterEach, beforeEach} from 'vitest';
import {render, screen, fireEvent, cleanup, waitFor} from '@testing-library/react';
import {ControlRebuild} from './ControlRebuild';
import {mediaItemsFrom} from './MediaSimple';
vi.mock('../LocalInteropPanel', () => ({LocalInteropPanel: () => <div>mock-interop</div>}));
const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), {status, headers: {'Content-Type': 'application/json'}}));
const calls: string[] = [];
beforeEach(() => { vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
  calls.push(`${init?.method || 'GET'} ${url}`);
  if (url.includes('asset-providers')) return json({items: [{provider_id: 'comfyui-local', display_name: 'ComfyUI 本地', local: true, configured: true}, {provider_id: 'openai', display_name: 'OpenAI 图片', local: false, requires_credential: true, credential_configured: true, configured: true}]});
  if (url.includes('video-providers')) return json({items: [{id: 'kling', display_name: '可灵', local: false, requires_credential: true, credential_configured: false}]});
  if (url.includes('audio/providers')) return json({items: []});
  if (url.endsWith('/credentials/openai/test')) return json({provider: 'openai', configured: true, reachable: false});
  if (url.includes('/credentials/')) return json({provider: 'x', configured: false});
  if (url.includes('agent-queue')) return json({items: []});
  return json({});
})); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); calls.length = 0; });
describe('[U6] MediaSimple', () => {
  it('normal shows simplified media rows; pro does not', async () => {
    const {rerender} = render(<ControlRebuild shellMode="basic" advanced={<div>ADV</div>} />);
    await screen.findByLabelText('图片服务');
    expect(document.querySelectorAll('[data-media-kind]')).toHaveLength(3);
    expect(screen.getByText('本地服务，不需要密钥')).toBeTruthy();
    expect(screen.getByText('还没填密钥')).toBeTruthy();
    expect(screen.getByText('还没有可用的声音服务')).toBeTruthy();
    const txt = document.body.textContent || '';
    expect(txt).not.toMatch(/专业|comfyui-local|kling|LOCAL_FIRST|端点|endpoint/);
    expect(document.querySelector('.hub-adv')).toBeNull();
    rerender(<ControlRebuild shellMode="pro" advanced={<div>ADV</div>} />);
    expect(document.querySelector('[data-hub-media]')).toBeNull();
  });
  it('验证连接 tests credential; unreachable is never green; no writes', async () => {
    render(<ControlRebuild shellMode="basic" />);
    const sel = await screen.findByLabelText('图片服务');
    fireEvent.change(sel, {target: {value: '1'}});
    expect(screen.getByText('密钥已填')).toBeTruthy();
    const row = document.querySelector('[data-media-kind="image"]')!;
    fireEvent.click(row.querySelector('button')!);
    const st = await waitFor(() => { const e = row.querySelector('[role=status]'); if (!e) throw 0; return e; });
    expect(st.textContent).toMatch(/连不上/);
    expect(st.className).not.toMatch(/ok/);
    expect(calls).toContain('POST /api/credentials/openai/test');
    expect(calls.filter(c => !c.startsWith('GET') && !/\/test$/.test(c))).toEqual([]);
    // video without key: prompt to fill, no test call
    fireEvent.click(document.querySelector('[data-media-kind="video"] button')!);
    await screen.findByText(/先在下方「密钥」里填好/);
    expect(calls.some(c => c.includes('kling/test'))).toBe(false);
  });
  it('helper maps fields', () => {
    expect(mediaItemsFrom('video', [{id: 'v', registered: true, local: true}])[0]).toMatchObject({usable: true, needsKey: false, reachable: null});
  });
});
