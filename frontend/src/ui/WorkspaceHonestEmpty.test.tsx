// @vitest-environment jsdom
/** [HERMIA-FE-20261022 X-UX-01] */
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {WorkspaceHonestEmpty, honestEmptyCopy} from './WorkspaceHonestEmpty';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement;
afterEach(() => { host?.remove(); });

describe('WorkspaceHonestEmpty X-UX-01', () => {
  it('covers six workspaces + novel with honest no_project copy', () => {
    for (const ws of ['NOVEL', 'IMAGE', 'VIDEO', 'AUDIO', 'EDIT', 'ASSETS'] as const) {
      const c = honestEmptyCopy('no_project', ws);
      expect(c.title).toContain('打开');
      expect(c.detail.length).toBeGreaterThan(8);
      expect(c.detail).not.toMatch(/已接通|全部就绪|成功/);
    }
  });

  it('renders no_chapter / no_track / load_failed / empty_library with CTA and no fake green', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    const retry = vi.fn();
    act(() => root.render(
      <>
        <WorkspaceHonestEmpty kind="no_chapter" workspace="NOVEL" />
        <WorkspaceHonestEmpty kind="no_track" workspace="EDIT" />
        <WorkspaceHonestEmpty kind="load_failed" workspace="AUDIO" onAction={retry} />
        <WorkspaceHonestEmpty kind="empty_library" workspace="ASSETS" />
        <WorkspaceHonestEmpty kind="loading" workspace="IMAGE" />
      </>,
    ));
    expect(host.textContent).toContain('尚未选择章节');
    expect(host.textContent).toContain('还没有可剪片段');
    expect(host.textContent).toContain('加载失败');
    expect(host.textContent).toContain('库里还没有资产');
    expect(host.textContent).toContain('正在加载');
    expect(host.textContent).toMatch(/禁假绿|诚实空态/);
    expect(host.querySelector('[data-capability-tone="success"]')).toBeNull();
    expect(host.querySelectorAll('[data-capability-tone="neutral"]').length).toBeGreaterThanOrEqual(4);
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.textContent?.includes('重试'))?.click();
    });
    expect(retry).toHaveBeenCalled();
    act(() => root.unmount());
  });
});
