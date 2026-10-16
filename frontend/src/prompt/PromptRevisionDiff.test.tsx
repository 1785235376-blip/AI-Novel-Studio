// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { RevisionDiff } from './PromptWorkspace';

const side = (revision: number, value: string) => ({ revision,
  body: { state: 'COMPLETE', value, verified: true, readComplete: true } });
const props = (before: string, after: string) => ({ from: side(1, before), to: side(2, after), professional: false });
afterEach(cleanup);

describe('Prompt revision comparison usability', () => {
  it('counts a trailing blank-line addition instead of calling the text identical', () => {
    render(<RevisionDiff {...props('第一行', '第一行\n')} />);
    expect(screen.getByText(/1 行不同（共 2 行）/)).toBeTruthy();
    const rows = within(screen.getByRole('table')).getAllByRole('row');
    expect(within(rows[2]).getByText('无此行')).toBeTruthy();
    expect(within(rows[2]).getByText('空行')).toBeTruthy();
  });

  it('counts removal of multiple blank lines and keeps whitespace differences', () => {
    render(<RevisionDiff {...props('第一行\n\n', '第一行 ')} />);
    expect(screen.getByText(/3 行不同（共 3 行）/)).toBeTruthy();
    expect(screen.getAllByText('无此行')).toHaveLength(2);
    expect(screen.getAllByText('空行')).toHaveLength(2);
  });

  it('paginates long comparisons without truncating their totals or last lines', () => {
    const text = Array.from({ length: 205 }, (_, index) => `正文 ${index + 1}`).join('\n');
    render(<RevisionDiff {...props(text, `${text} 修改`)} />);
    expect(screen.getByText(/1 行不同（共 205 行）/)).toBeTruthy();
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(101);
    expect(screen.queryByText('正文 205 修改')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '下一页差异' }));
    fireEvent.click(screen.getByRole('button', { name: '下一页差异' }));
    expect(screen.getByText('正文 205 修改')).toBeTruthy();
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(6);
    expect((screen.getByRole('button', { name: '下一页差异' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '上一页差异' }));
    expect(screen.queryByText('正文 205 修改')).toBeNull();
  });

  it('filters to changed lines while preserving original line numbers and resets paging', () => {
    const text = Array.from({ length: 205 }, (_, index) => `正文 ${index + 1}`).join('\n');
    render(<RevisionDiff {...props(text, `${text} 修改`)} />);
    fireEvent.click(screen.getByRole('button', { name: '下一页差异' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '仅显示差异行' }));
    const rows = within(screen.getByRole('table')).getAllByRole('row');
    expect(rows).toHaveLength(2);
    expect(within(rows[1]).getByText('205')).toBeTruthy();
    expect(screen.getByText('正文 205 修改')).toBeTruthy();
    expect(screen.getByText(/第 1 \/ 1 页/)).toBeTruthy();
    fireEvent.click(screen.getByRole('checkbox', { name: '仅显示差异行' }));
    expect(screen.queryByText('正文 205 修改')).toBeNull();
    expect(screen.getByText(/第 1 \/ 3 页/)).toBeTruthy();
  });

  it('states that there are no changed lines without inventing an empty result table', () => {
    render(<RevisionDiff {...props('相同', '相同')} />);
    fireEvent.click(screen.getByRole('checkbox', { name: '仅显示差异行' }));
    expect(screen.getByText('两个修订没有正文行差异。')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('resets the page when another comparison body is displayed', () => {
    const text = Array.from({ length: 205 }, (_, index) => `正文 ${index + 1}`).join('\n');
    const view = render(<RevisionDiff {...props(text, text)} />);
    fireEvent.click(screen.getByRole('button', { name: '下一页差异' }));
    view.rerender(<RevisionDiff {...props(text, `${text} 修改`)} />);
    expect(screen.getByText(/第 1 \/ 3 页/)).toBeTruthy();
    expect(screen.queryByText('正文 205 修改')).toBeNull();
  });

  it('resets the page when only the revision numbers change', () => {
    const text = Array.from({ length: 205 }, (_, index) => `正文 ${index + 1}`).join('\n');
    const view = render(<RevisionDiff {...props(text, text)} />);
    fireEvent.click(screen.getByRole('button', { name: '下一页差异' }));
    view.rerender(<RevisionDiff from={side(3, text)} to={side(4, text)} professional={false} />);
    expect(screen.getByText(/第 1 \/ 3 页/)).toBeTruthy();
    expect(screen.getByText(/修订 3 → 修订 4/)).toBeTruthy();
  });

  it('keeps the DOM bounded for newline-heavy bodies at the existing 64 KiB limit', () => {
    render(<RevisionDiff {...props('\n'.repeat(65535), '\n'.repeat(65536))} />);
    expect(screen.getByText(/1 行不同（共 65537 行）/)).toBeTruthy();
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(101);
    fireEvent.click(screen.getByRole('checkbox', { name: '仅显示差异行' }));
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(2);
    expect(screen.getByText('65537')).toBeTruthy();
  });

  it('retains the existing incomplete-body warning and exposes no comparison controls', () => {
    const value = props('完整正文', '不完整正文');
    value.to.body.state = 'TRUNCATED';
    render(<RevisionDiff {...value} />);
    expect(screen.getByText(/无法比较完整正文/)).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('checkbox', { name: '仅显示差异行' })).toBeNull();
    expect(screen.queryByText('不完整正文')).toBeNull();
  });
});
