// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PromptVersionHistory } from './PromptVersionHistory';
import type { PromptVersionRow } from './promptTypes';

const row = (revision: number, extra: Partial<PromptVersionRow> = {}): PromptVersionRow => ({
  assetId: `asset-${revision}`, revision, assetVersion: 1, changeNote: `修改 ${revision}`,
  changeReason: `调整 ${revision}`, previousAssetId: null, redacted: false, available: true, ...extra,
});
const setup = (versions: PromptVersionRow[]) => ({ versions, headAssetId: 'asset-2',
  professional: false, fromId: 'asset-1', toId: 'asset-2', onSelectFrom: vi.fn(), onSelectTo: vi.fn() });
afterEach(cleanup);

describe('Prompt version history records', () => {
  it('preserves input ordering while displaying newest-first records and their availability labels', () => {
    const rows = [row(1, { redacted: true }), row(2, { available: false })];
    render(<PromptVersionHistory {...setup(rows)} />);
    expect(document.querySelectorAll('.prompt-version-list li')[0].textContent).toContain('修订 2');
    expect(rows.map(item => item.revision)).toEqual([1, 2]);
    expect(screen.getByText('已脱敏')).toBeTruthy();
    expect(screen.getByText('已删除 / 不可读')).toBeTruthy();
    expect(screen.getByText('当前')).toBeTruthy();
  });

  it('searches notes and reasons without inventing absent authored values', () => {
    render(<PromptVersionHistory {...setup([row(1, { changeReason: null }), row(2, { changeReason: 'Color FIX' })])} />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '  color fix  ' } });
    expect(document.querySelectorAll('.prompt-version-list li')).toHaveLength(1);
    expect(screen.getByText('修改原因：Color FIX')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '清除版本搜索' }));
    expect(screen.queryByText('修改原因：调整 1')).toBeNull();
  });

  it('only calls the chosen selection callback and marks current comparison selections', () => {
    const props = setup([row(1), row(2)]);
    render(<PromptVersionHistory {...props} />);
    expect(screen.getByRole('button', { name: '将修订 1 选作旧版' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: '将修订 2 选作旧版' }));
    expect(props.onSelectFrom).toHaveBeenCalledTimes(1);
    expect(props.onSelectFrom).toHaveBeenCalledWith('asset-2');
    expect(props.onSelectTo).not.toHaveBeenCalled();
  });

  it('returns keyboard focus to the searchbox after clearing its query', () => {
    render(<PromptVersionHistory {...setup([row(1), row(2)])} />);
    const searchbox = screen.getByRole('searchbox');
    fireEvent.change(searchbox, { target: { value: 'unmatched' } });
    const clear = screen.getByRole('button', { name: '清除版本搜索' });
    clear.focus();
    fireEvent.click(clear);
    expect(document.activeElement).toBe(searchbox);
    expect((searchbox as HTMLInputElement).value).toBe('');
    expect(document.querySelectorAll('.prompt-version-list li')).toHaveLength(2);
  });

  it('keeps selected old and new sides visible after focus moves away', () => {
    const props = setup([row(1), row(2)]);
    const view = render(<PromptVersionHistory {...props} />);
    expect(screen.getByRole('button', { name: '将修订 1 选作旧版' }).textContent).toBe('已选旧版');
    expect(screen.getByRole('button', { name: '将修订 2 选作新版' }).textContent).toBe('已选新版');
    view.rerender(<PromptVersionHistory {...props} fromId="asset-2" toId="asset-1" />);
    screen.getByRole('searchbox').focus();
    expect(screen.getByRole('button', { name: '将修订 2 选作旧版' }).textContent).toBe('已选旧版');
    expect(screen.getByRole('button', { name: '将修订 1 选作新版' }).textContent).toBe('已选新版');
    expect(screen.getByRole('button', { name: '将修订 1 选作旧版' }).textContent).toBe('选作旧版');
  });

  it('clears its search when the workspace mounts a different family key', () => {
    const props = setup([row(1), row(2)]);
    const view = render(<PromptVersionHistory key="family-a" {...props} />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'unmatched' } });
    expect(screen.getByText('已加载记录中没有匹配的版本')).toBeTruthy();
    view.rerender(<PromptVersionHistory key="family-b" {...props} />);
    expect((screen.getByRole('searchbox') as HTMLInputElement).value).toBe('');
    expect(document.querySelectorAll('.prompt-version-list li')).toHaveLength(2);
  });

  it('distinguishes an unloaded history from a search with no matches', () => {
    render(<PromptVersionHistory {...setup([])} />);
    expect(screen.getByText('没有已加载的版本记录')).toBeTruthy();
    expect(screen.queryByText('已加载记录中没有匹配的版本')).toBeNull();
    expect(screen.queryByRole('button', { name: /选作/ })).toBeNull();
  });
});
