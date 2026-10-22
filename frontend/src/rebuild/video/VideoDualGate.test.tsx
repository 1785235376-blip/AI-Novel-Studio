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
