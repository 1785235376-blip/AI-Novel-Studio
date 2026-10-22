// @vitest-environment jsdom
// [HERMIA-FE-20261022 U3] 双画布 / 专业工具只在专业模式
import {describe, it, expect, vi, afterEach} from 'vitest';
import {render, cleanup} from '@testing-library/react';
import {ImageRebuild} from './ImageRebuild';
const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), {status: 200, headers: {'Content-Type': 'application/json'}}));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('ImageRebuild 双画布门控', () => {
  it('basic: tabs/header have no 双画布; dual view falls back to browse', () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    const onViewChange = vi.fn();
    render(<ImageRebuild novelId="n1" view="dual" onViewChange={onViewChange} shellMode="basic" />);
    expect(onViewChange).toHaveBeenCalledWith('browse');
    expect(document.querySelector('[data-open-dual]')).toBeNull();
    expect(document.querySelector('[data-img-view="dual"]')).toBeNull();
  });
  it('basic canvas view hides 专业工具 fold; pro shows it and 双画布', () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    const r = render(<ImageRebuild novelId="n1" view="canvas" onViewChange={() => {}} shellMode="basic" />);
    expect(document.querySelector('[data-pro-only]')).toBeNull();
    expect(document.body.textContent).not.toContain('双画布');
    r.rerender(<ImageRebuild novelId="n1" view="canvas" onViewChange={() => {}} shellMode="pro" />);
    expect(document.querySelector('[data-pro-only]')).not.toBeNull();
    expect(document.body.textContent).toContain('双画布');
  });
});
