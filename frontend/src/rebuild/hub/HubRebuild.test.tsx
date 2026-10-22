// @vitest-environment jsdom
// [HERMIA-FE-20261022 R7] 主控/插件单页：真实接口、模拟服务不给绿、验证连接不派发、无内部编号
import {describe, it, expect, vi, afterEach, beforeEach} from 'vitest';
import {render, screen, fireEvent, cleanup, waitFor} from '@testing-library/react';
import {ControlRebuild, hubRowsFrom} from './ControlRebuild';
import {PluginsRebuild, pluginState} from './PluginsRebuild';
vi.mock('../LocalInteropPanel', () => ({LocalInteropPanel: () => <div>mock-interop</div>}));
vi.mock('../../novel/PluginManagerPanel', () => ({PluginManagerPanel: () => <div>mock-plugin-manager</div>}));
const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), {status, headers: {'Content-Type': 'application/json'}}));
const calls: string[] = []; let plugins: any[] = [];
beforeEach(() => { vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
  calls.push(`${init?.method || 'GET'} ${url}`);
  if (url === '/api/providers') return json({mock: {available: true, configured: true, kind: 'local'}, deepseek: {available: true, configured: true, kind: 'cloud', execution_mode: 'mock_standin'}, openai: {available: false, configured: false, kind: 'cloud'}});
  if (url.includes('model-center/models')) return json({items: [{id: 'qwen36-27b-q4km', display_name: 'Qwen 27B', status: 'READY', verified: false}]});
  if (url.includes('agent-queue')) return json({code: 'SESSION_REQUIRED'}, 401);
  if (url.includes('/api/plugins')) return json({items: plugins, execution_supported: false});
  if (url.includes('/credentials/')) return json({provider: 'x', configured: false});
  return json({items: []});
})); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); calls.length = 0; plugins = []; });
describe('ControlRebuild', () => {
  it('single page with sections; simulated services never green; yellow strip when nothing verified', async () => {
    render(<ControlRebuild />);
    await screen.findByText('Qwen 27B');
    for (const h of ['模型与提供方', '预算与任务', '密钥']) expect(screen.getAllByText(h).length).toBeGreaterThan(0);
    expect(document.querySelectorAll('[role=tab]')).toHaveLength(0);
    expect(screen.getAllByText('模拟').length).toBe(2);
    expect(screen.getByText('这些服务还没验证，生成按钮会保持灰色。')).toBeTruthy();
    expect(document.querySelectorAll('.ws-head .nv-btn--primary')[0].textContent).toBe('验证连接');
    await waitFor(() => expect(document.body.textContent).toMatch(/排队任务暂时看不到|需要登录会话/));
    expect(document.body.textContent).not.toMatch(/qwen36|mock_standin|LOCAL_REQUIRED|试派发|ModelBroker/);
  });
  it('验证连接 only reads/tests, never dispatches', async () => {
    render(<ControlRebuild />);
    await screen.findByText('Qwen 27B');
    fireEvent.click(document.querySelector('#aiVerify')!);
    await screen.findByText(/没有填密钥的云端服务/);
    expect(calls.filter(c => !c.startsWith('GET') && !/\/credentials\/[^/]+\/test$/.test(c))).toEqual([]);
  });
  it('rows helper', () => {
    expect(hubRowsFrom({text: {ollama: {configured: true, available: false, kind: 'local'}}})[0]).toMatchObject({name: 'Ollama（本地）', verified: false, where: '本地'});
  });
});
describe('PluginsRebuild', () => {
  it('empty: local software + honest empty; 安装插件… is primary and opens governance drawer', async () => {
    render(<PluginsRebuild />);
    await screen.findByText(/还没装插件/);
    expect(screen.getByText('本地软件')).toBeTruthy();
    expect(screen.getByText(/还不能真正运行/)).toBeTruthy();
    fireEvent.click(document.querySelector('#plugInstall')!);
    expect(screen.getByText('mock-plugin-manager')).toBeTruthy();
  });
  it('unreviewed plugin cannot be enabled; enable hits real endpoint', async () => {
    plugins = [{id: 'p-1', name: '排版辅助', validated: true}, {id: 'p-2', name: '镜头包', validated: false}];
    render(<PluginsRebuild />);
    await screen.findByText('排版辅助');
    const btns = screen.getAllByRole('button', {name: '启用'}) as HTMLButtonElement[];
    expect(btns[1].disabled).toBe(true);
    fireEvent.click(btns[0]);
    await waitFor(() => expect(calls).toContain('POST /api/plugins/p-1/enable'));
    expect(pluginState({enabled: true}).label).toBe('已启用');
  });
});
