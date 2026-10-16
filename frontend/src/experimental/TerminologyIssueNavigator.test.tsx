// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TerminologyIssueNavigator } from './TerminologyIssueNavigator';
import type { LanguageEdition } from './multilingualEditionsClient';
afterEach(cleanup);
const edition = (count = 1): LanguageEdition => ({ id: 'edition', version: 3, status: 'DRAFT', target_language: 'ar', direction: 'rtl', stale: false, content_withheld: false, term_revision: 8, segments: Array.from({ length: count }, (_, i) => ({ id: `segment-${i}`, chapter_id: 'chapter', source_version: 2, path: [i], from_pos: i, to_pos: i + 1, source_text: '同名🙂é', target_text: 'مرحبا🙂', note: '', status: 'DRAFT', issues: [{ code: 'TERM_REQUIRED' }] })) });
it('bounds the list to twenty exact segment targets and allows keyboard-native page controls', () => {
  const open = vi.fn(); render(<TerminologyIssueNavigator edition={edition(21)} blocked={false} onOpen={open} />);
  expect(screen.getAllByRole('button', { name: /^定位第/ })).toHaveLength(20);
  expect(screen.queryByRole('button', { name: '定位第 21 段术语问题' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '下一页问题段落' }));
  fireEvent.click(screen.getByRole('button', { name: '定位第 21 段术语问题' }));
  expect(open).toHaveBeenCalledTimes(1); expect(open).toHaveBeenCalledWith('segment-20');
  fireEvent.click(screen.getByRole('button', { name: '上一页问题段落' }));
  expect(screen.getAllByRole('button', { name: /^定位第/ })).toHaveLength(20);
});
it('disables ambiguous original IDs rather than selecting the first duplicate', () => {
  const row = edition(2); row.segments![1].id = row.segments![0].id; const open = vi.fn();
  render(<TerminologyIssueNavigator edition={row} blocked={false} onOpen={open} />);
  for (const button of screen.getAllByRole('button')) { expect((button as HTMLButtonElement).disabled).toBe(true); fireEvent.click(button); }
  expect(open).not.toHaveBeenCalled();
});
it.each(['stale', 'content_withheld'] as const)('omits all issue evidence when %s', flag => {
  const row = edition(); row[flag] = true;
  render(<TerminologyIssueNavigator edition={row} blocked={false} onOpen={vi.fn()} />);
  expect(screen.queryByLabelText('已保存术语问题导航')).toBeNull();
});
it('does not derive errors from prose or invent language quality scores', () => {
  const row = edition(); row.segments![0].issues = [];
  render(<TerminologyIssueNavigator edition={row} blocked={false} onOpen={vi.fn()} />);
  expect(screen.queryByLabelText('已保存术语问题导航')).toBeNull();
});
it.each([
  (row: LanguageEdition) => { row.segments![0].source_version = 0; },
  (row: LanguageEdition) => { row.segments![0].chapter_id = ''; },
  (row: LanguageEdition) => { row.segments![0].issues = null as any; },
  (row: LanguageEdition) => { row.segments![0].path = null as any; },
  (row: LanguageEdition) => { row.version = NaN; },
  (row: LanguageEdition) => { row.segments![0].issues = [null as any]; },
  (row: LanguageEdition) => { row.segments![0].source_text = null as any; },
])('withholds navigation for incomplete original identity/arrays', mutate => {
  const row = edition(); mutate(row);
  render(<TerminologyIssueNavigator edition={row} blocked={false} onOpen={vi.fn()} />);
  expect(screen.queryByRole('button')).toBeNull();
  expect(screen.getByText(/原段落身份或来源版本不完整/)).toBeTruthy();
});
it('clamps the page when saved rows shrink even under the same version', () => {
  const view = render(<TerminologyIssueNavigator edition={edition(21)} blocked={false} onOpen={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: '下一页问题段落' }));
  view.rerender(<TerminologyIssueNavigator edition={edition(1)} blocked={false} onOpen={vi.fn()} />);
  expect(screen.getByRole('button', { name: '定位第 1 段术语问题' })).toBeTruthy();
});
