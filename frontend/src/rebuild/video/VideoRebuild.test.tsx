// @vitest-environment jsdom
// [HERMIA-FE-20261022 R4] Vera R3 非阻塞建议：图生视频置灰原因 / 服务数量来自真实 /api/video-providers
import {describe, it, expect, vi, afterEach} from 'vitest';
import {render, screen, fireEvent, cleanup} from '@testing-library/react';
import {VideoRebuild} from './VideoRebuild';
const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), {status: 200, headers: {'Content-Type': 'application/json'}}));
const stub = (providers: any[]) => vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('video-providers') ? json({items: providers}) : json([])));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('VideoRebuild 图生视频', () => {
  it('no ready provider: 生成候选… disabled with AI 主控 reason', async () => {
    stub([{provider_id: 'mock-director-video', available: false, registered: true}]);
    render(<VideoRebuild novelId="n1" />);
    fireEvent.click(screen.getAllByRole('button', {name: '图生视频'})[0]);
    await screen.findByText('需要先在 AI 主控里接好视频服务。');
    expect((document.querySelector('#vidGenGo') as HTMLButtonElement).disabled).toBe(true);
    expect(document.body.textContent).not.toContain('mock-director-video');
  });
  it('ready provider counted; still disabled without keyframe', async () => {
    stub([{provider_id: 'mock-director-video', available: true, registered: true}]);
    render(<VideoRebuild novelId="n1" />);
    fireEvent.click(screen.getAllByRole('button', {name: '图生视频'})[0]);
    await screen.findByText(/可用视频服务 1 个/);
    expect((document.querySelector('#vidGenGo') as HTMLButtonElement).disabled).toBe(true);
  });
});
