// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StyleComparisonReview } from './StyleComparisonReview';
import { measuredRatio, readStyleComparison } from './styleComparison';
import type { StyleAnalysis } from './styleReviewClient';
const metrics = { sentence_length_mean: { numerator: 18, denominator: 3 }, dialogue_share_nonspace: { numerator: 2, denominator: 18 }, sample_sufficiency: 'SHORT_SAMPLE' };
const target = { chapter_id: 'target-章', expected_version: 7, language: 'zh', comparable: true, metrics, paragraphs: [{ paragraph: 1, start: 4, end: 7, quote: '雨😀。', metrics }], paragraphs_truncated: false, interpretation: 'RAW_COUNT_DIFFERENCES_NOT_QUALITY_OR_NORMALIZED_DRIFT' };
const row = { id: 'report', version: 1, style_id: 'profile', style_version: 2, language: 'zh', stale: false, metrics, comparison: target } as unknown as StyleAnalysis;
afterEach(cleanup);
it('shows paired measured ratios, exact Unicode text and original target version without writing', () => {
  const navigate = vi.fn(); render(<StyleComparisonReview row={row} onNavigate={navigate} />);
  expect(screen.getByText(/参考样本：18 \/ 3 = 6.000；目标全文：18 \/ 3 = 6.000/)).toBeTruthy();
  expect(screen.getByText(/短样本：/)).toBeTruthy();
  expect((screen.getByLabelText('比较目标 report 段落 1 原文') as HTMLTextAreaElement).value).toBe('雨😀。');
  expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '打开比较目标原章节 v7' }));
  expect(navigate).toHaveBeenCalledWith({ kind: 'chapter', id: 'target-章', version: 7 });
});
it('withholds stale and malformed evidence and never substitutes current chapter versions', () => {
  const view = render(<StyleComparisonReview row={{ ...row, stale: true }} />);
  expect(screen.queryByText(/样本与目标/)).toBeNull();
  view.rerender(<StyleComparisonReview row={{ ...row, comparison: { ...target, expected_version: 0 } }} />);
  expect(screen.getByText(/比较证据格式不完整/)).toBeTruthy();
  expect(screen.queryByRole('button')).toBeNull();
});
it('does not compare unlike language methods or contradictory comparison flags', () => {
  for (const patch of [{ language: 'en' }, { comparable: false }, { interpretation: 'LANGUAGE_METHODS_NOT_COMPARABLE' }]) {
    const view = render(<StyleComparisonReview row={{ ...row, comparison: { ...target, ...patch } }} />);
    expect(screen.getByText(/不作跨方法比例比较/)).toBeTruthy();
    expect(screen.queryByText(/参考样本：/)).toBeNull();
    expect(screen.getByLabelText('比较目标 report 段落 1 原文')).toBeTruthy(); view.unmount();
  }
});
it('paginates target evidence and discloses truncated reports without changing measurements', () => {
  const paragraphs = Array.from({ length: 21 }, (_, i) => ({ paragraph: i + 1, start: i * 4, end: i * 4 + 3, quote: '雨😀。', metrics }));
  render(<StyleComparisonReview row={{ ...row, comparison: { ...target, paragraphs, paragraphs_truncated: true } }} />);
  expect(screen.getAllByRole('textbox', { hidden: true })).toHaveLength(20);
  fireEvent.click(screen.getByRole('button', { name: '下一页目标段落', hidden: true }));
  expect(screen.getAllByRole('textbox', { hidden: true })).toHaveLength(1);
  expect(screen.getByLabelText('比较目标 report 段落 21 原文')).toBeTruthy();
  expect(screen.getByText(/报告仅保存前 200/)).toBeTruthy();
});
it('distinguishes missing and empty denominators without NaN or infinity', () => {
  render(<StyleComparisonReview row={{ ...row, metrics: { sentence_length_mean: { numerator: 0, denominator: 0 } } }} />);
  expect(screen.getByText(/参考样本：没有可测量单位/)).toBeTruthy();
  expect(screen.getAllByText(/测量不可用/).length).toBeGreaterThan(0);
  expect(document.body.textContent).not.toMatch(/NaN|Infinity/);
});
it('validates unknown stored comparison identity, ordering, Unicode and bounds', () => {
  expect(readStyleComparison(target)).toEqual(target);
  for (const value of [null, [], {}, { ...target, language: ['zh'] }, { ...target, interpretation: [target.interpretation] }, { ...target, chapter_id: ' ' }, { ...target, expected_version: 1.5 }, { ...target, paragraphs: [{ ...target.paragraphs[0], end: 8 }] }, { ...target, paragraphs: [target.paragraphs[0], target.paragraphs[0]] }, { ...target, paragraphs: [{ ...target.paragraphs[0], metrics: null }] }]) expect(readStyleComparison(value)).toBeUndefined();
  for (const value of [null, { numerator: NaN, denominator: 1 }, { numerator: -1, denominator: 1 }, { numerator: 1, denominator: 0 }, { numerator: 1, denominator: Infinity }]) expect(measuredRatio(value)).toBeUndefined();
});
