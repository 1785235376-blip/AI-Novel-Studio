// @vitest-environment jsdom
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {RevisionPanel, type RevisionDetail, type RevisionSummary} from './RevisionPanel';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;

const revisions: RevisionSummary[] = [
  {version: 4, createdAt: '2026-08-10T02:00:00Z', actorLabel: '林岚', reason: '调整结尾'},
  {version: 3, createdAt: '2026-08-10T01:00:00Z', actorLabel: '周明', source: 'USER'},
];
const selected: RevisionDetail = {
  ...revisions[1],
  comparison: {
    historicalLabel: '历史版本 3', historicalText: '旧结尾',
    currentLabel: '当前正文（版本 4）', currentText: '新结尾',
  },
};

let host: HTMLDivElement | undefined;
let root: Root | undefined;

function render(overrides: Partial<React.ComponentProps<typeof RevisionPanel>> = {}) {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<RevisionPanel revisions={revisions} currentVersion={4} selectedRevision={selected} onSelectRevision={vi.fn()} onRestore={vi.fn().mockResolvedValue(undefined)} {...overrides}/>));
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = undefined;
  host = undefined;
});

describe('RevisionPanel', () => {
  it('renders an accessible timeline and human-readable comparison', () => {
    const onSelectRevision = vi.fn();
    render({onSelectRevision});
    expect(host!.querySelector('nav')?.getAttribute('aria-label')).toBe('版本记录时间线');
    expect(host!.textContent).toContain('旧结尾');
    expect(host!.textContent).toContain('新结尾');
    expect(host!.textContent).not.toContain('Revision v3');
    expect(host!.textContent).not.toContain('{"type"');
    const revision4 = [...host!.querySelectorAll('button')].find(button => button.textContent?.includes('版本 4'))!;
    act(() => revision4.click());
    expect(onSelectRevision).toHaveBeenCalledWith(4);
  });

  it('requires explicit confirmation and submits both revision versions', async () => {
    const onRestore = vi.fn().mockResolvedValue(undefined);
    render({onRestore});
    const preview = [...host!.querySelectorAll('button')].find(button => button.textContent === '预览并恢复此版本')!;
    act(() => preview.click());
    expect(host!.textContent).toContain('现有历史版本不会被删除');
    const confirm = [...host!.querySelectorAll('button')].find(button => button.textContent === '恢复此版本')!;
    await act(async () => confirm.click());
    expect(onRestore).toHaveBeenCalledWith({revisionVersion: 3, expectedCurrentVersion: 4});
    expect(host!.textContent).toContain('恢复完成');
  });

  it('preserves the preview and persistent conflict after restore fails', async () => {
    const onRestore = vi.fn().mockRejectedValue({kind: 'conflict', message: '预期 v4，但当前已是 v5。', currentVersion: 5});
    render({onRestore});
    act(() => ([...host!.querySelectorAll('button')].find(button => button.textContent === '预览并恢复此版本')!).click());
    await act(async () => ([...host!.querySelectorAll('button')].find(button => button.textContent === '恢复此版本')!).click());
    expect(host!.querySelector('[role="alert"]')?.textContent).toContain('版本冲突，未恢复');
    expect(host!.textContent).toContain('旧结尾');
    expect(host!.textContent).toContain('恢复此版本');
  });

  it('covers loading, empty, error, and unauthorized states', () => {
    render({loading: true});
    expect(host!.querySelector('[role="status"]')?.textContent).toContain('正在加载');
    act(() => root!.render(<RevisionPanel revisions={[]} currentVersion={4} onSelectRevision={vi.fn()} onRestore={vi.fn()}/>));
    expect(host!.textContent).toContain('暂无历史版本');
    act(() => root!.render(<RevisionPanel revisions={[]} currentVersion={4} error="网络错误" onSelectRevision={vi.fn()} onRestore={vi.fn()}/>));
    expect(host!.querySelector('[role="alert"]')?.textContent).toContain('网络错误');
    act(() => root!.render(<RevisionPanel revisions={[]} currentVersion={4} unauthorized onSelectRevision={vi.fn()} onRestore={vi.fn()}/>));
    expect(host!.querySelector('[role="alert"]')?.textContent).toContain('无权查看');
  });
});
