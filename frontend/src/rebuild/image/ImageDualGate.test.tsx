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
  // [HERMIA-FE-20261022 U3b]
  it('basic browse hides 「专业 · 创作画布」 fold; pro shows it', () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    const r = render(<ImageRebuild novelId="n1" view="browse" onViewChange={() => {}} shellMode="basic" />);
    expect(document.querySelector('details.img-pro')).toBeNull();
    expect(document.body.textContent).not.toContain('专业 · 创作画布');
    r.rerender(<ImageRebuild novelId="n1" view="browse" onViewChange={() => {}} shellMode="pro" />);
    expect(document.querySelector('details.img-pro')).not.toBeNull();
  });
  it('canvas header has no 「专业」 badge in either mode', () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    for (const m of ['basic', 'pro'] as const) {
      render(<ImageRebuild novelId="n1" view="canvas" onViewChange={() => {}} shellMode={m} />);
      const head = document.querySelector('.mw-head[aria-label="图片子入口"]')!;
      expect(head.querySelector('.nv-badge')).toBeNull();
      cleanup();
    }
  });
});
describe('[U4] 图片 普通/专业', () => {
  it('basic gen: no 多图约束 / 画面分析 / 批量; pro canvas has 多图约束; no 批量生成 entry in either mode (no capability)', () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    const r = render(<ImageRebuild novelId="n1" view="gen" onViewChange={() => {}} shellMode="basic" />);
    expect(document.body.textContent).not.toMatch(/多图约束|画面分析|批量/);
    r.rerender(<ImageRebuild novelId="n1" view="canvas" onViewChange={() => {}} shellMode="pro" />);
    expect(document.body.textContent).toContain('多图约束');
    expect(document.body.textContent).not.toContain('批量生成');
  });
});
