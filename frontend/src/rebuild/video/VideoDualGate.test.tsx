// @vitest-environment jsdom
// [HERMIA-FE-20261022 U3] 双画布只在专业模式
import {describe, it, expect, vi, afterEach} from 'vitest';
import {render, screen, fireEvent, cleanup} from '@testing-library/react';
import {VideoRebuild} from './VideoRebuild';
const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), {status: 200, headers: {'Content-Type': 'application/json'}}));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('VideoRebuild 双画布门控', () => {
  it('basic: no 双画布 anywhere', () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    render(<VideoRebuild novelId="n1" shellMode="basic" />);
    expect(screen.queryAllByText('双画布')).toHaveLength(0);
    expect(document.querySelector('[data-open-dual]')).toBeNull();
  });
  it('pro shows it; switching to basic falls back to 视频工作室', () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    const r = render(<VideoRebuild novelId="n1" shellMode="pro" />);
    fireEvent.click(document.querySelector('[data-open-dual]')!);
    expect(document.body.textContent).toContain('视频 › 双画布');
    r.rerender(<VideoRebuild novelId="n1" shellMode="basic" />);
    expect(document.body.textContent).not.toContain('双画布');
    expect(document.body.textContent).toContain('视频工作室');
  });
});
describe('[U4] 视频 普通/专业', () => {
  const plays = [{id: 'sp1', shots: [{id: 'x1', shot_size: '近景', description: '码头', dialogue: '来了'}]}];
  it('basic hides 图生视频 and advanced 分镜表 columns; pro shows them; pro→basic falls back from 图生视频', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('screenplays') ? json(plays) : json({items: []})));
    const r = render(<VideoRebuild novelId="n1" shellMode="basic" />);
    expect(document.querySelector('[data-pro-only="i2v"]')).toBeNull();
    expect(screen.queryAllByText('图生视频')).toHaveLength(0);
    fireEvent.click(screen.getAllByRole('button', {name: '分镜表'})[0]);
    expect((await screen.findByRole('table')).getAttribute('data-cols')).toBe('basic');
    expect(document.querySelector('.vid-table')?.textContent).not.toContain('近景');
    r.rerender(<VideoRebuild novelId="n1" shellMode="pro" />);
    expect(document.querySelector('.vid-table')?.getAttribute('data-cols')).toBe('advanced');
    expect(document.querySelector('.vid-table')?.textContent).toContain('近景');
    fireEvent.click(document.querySelector('[data-pro-only="i2v"]')!);
    expect(document.body.textContent).toContain('视频 › 图生视频');
    r.rerender(<VideoRebuild novelId="n1" shellMode="basic" />);
    expect(document.body.textContent).toContain('视频工作室');
    expect(document.body.textContent).not.toContain('图生视频');
  });
});
