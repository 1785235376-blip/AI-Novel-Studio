// @vitest-environment jsdom
// [HERMIA-FE-20261025 DUI P1-9] 首次指引条：可关闭且持久；「不再显示」对所有模块生效
import {describe, it, expect, beforeEach} from 'vitest';
import {render, fireEvent, cleanup} from '@testing-library/react';
import {NovelOrient, ORIENT_ALL_KEY} from './NovelOrient';
describe('NovelOrient dismiss', () => {
  beforeEach(() => { cleanup(); localStorage.clear(); });
  it('收起 persists for that module only', () => {
    const a = render(<NovelOrient what="w" can="c" effect="e" storageKey="k-a" />);
    fireEvent.click(a.getByRole('button', {name: '收起指引'}));
    expect(a.container.querySelector('.nv-orient')).toBeNull();
    cleanup();
    expect(render(<NovelOrient what="w" can="c" effect="e" storageKey="k-a" />).container.querySelector('.nv-orient')).toBeNull();
    cleanup();
    expect(render(<NovelOrient what="w" can="c" effect="e" storageKey="k-b" />).container.querySelector('.nv-orient')).not.toBeNull();
  });
  it('不再显示 hides the guide in every module after remount', () => {
    const a = render(<NovelOrient what="w" can="c" effect="e" storageKey="k-a" />);
    fireEvent.click(a.getByRole('button', {name: '不再显示'}));
    expect(localStorage.getItem(ORIENT_ALL_KEY)).toBe('1');
    cleanup();
    expect(render(<NovelOrient what="w" can="c" effect="e" storageKey="k-b" />).container.querySelector('.nv-orient')).toBeNull();
  });
});
