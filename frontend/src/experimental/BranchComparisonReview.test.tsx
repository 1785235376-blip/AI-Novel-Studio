// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { BranchComparisonReview } from './BranchComparisonReview';
import { branchBlockExcerpt, type BranchComparison } from './branchComparisonReviewHelpers';
afterEach(cleanup);
const block = (text: string) => ({ type: 'paragraph', content: [{ type: 'text', text }] });
const changed = { kind: 'CONFLICT', start: 0, end: 1, base: [block('旧的🪷')], ORIGINAL: [block('来源修改')], FORK: [block('分支修改')] };
const comparison: BranchComparison = { can_apply: false, preview_digest: 'exact-preview', source: { id: 'fork-chapter', version: 12, branch_id: 'branch-a', document_digest: 'fork-digest' }, target: { id: 'source-chapter', version: 8, branch_id: null, document_digest: 'target-digest' }, conflicts: [{ id: '1' }], segments: [{ kind: 'UNCHANGED', nodes: [block('相同正文')] }, changed], desired_document: null };
it('shows exact original receipts and original-index conflict choices without writing', () => {
  render(<BranchComparisonReview comparison={comparison} choices={{ '1': 'FORK' }} />);
  expect(screen.getByText('章节 fork-chapter · v12 · 分支 branch-a')).toBeTruthy();
  expect(screen.getByText('章节 source-chapter · v8 · 分支 主线')).toBeTruthy();
  expect(screen.getByText('正文摘要：target-digest')).toBeTruthy();
  expect(screen.getByText('比较摘要：exact-preview')).toBeTruthy();
  const row = screen.getByRole('article', { name: '比较段 2' });
  expect(within(row).getByText('当前人工选择：采用当前分支（仅针对本次比较）')).toBeTruthy();
  expect(within(row).getByText('旧的🪷')).toBeTruthy();
  expect(screen.queryByRole('article', { name: '比较段 1' })).toBeNull();
  fireEvent.click(screen.getByLabelText('只看有改动的块'));
  expect(screen.getByText('相同正文')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /合并|保存|应用/ })).toBeNull();
});
it('paginates twenty original blocks without losing indices or empty-root-conflict guidance', () => {
  const view = render(<BranchComparisonReview comparison={{ ...comparison, segments: Array.from({ length: 41 }, () => changed) }} choices={{}} />);
  expect(screen.getAllByRole('article', { name: /比较段/ })).toHaveLength(20);
  fireEvent.click(screen.getByRole('button', { name: '差异下一页' }));
  expect(screen.getByRole('article', { name: '比较段 21' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '差异下一页' }));
  expect(screen.getAllByRole('article', { name: /比较段/ })).toHaveLength(1);
  view.rerender(<BranchComparisonReview comparison={{ ...comparison, segments: [] }} choices={{}} />);
  expect(screen.getByText(/文档根属性冲突仍需/)).toBeTruthy();
  expect((screen.getByRole('button', { name: '差异下一页' }) as HTMLButtonElement).disabled).toBe(true);
});
it('keeps missing receipts unknown and unknown blocks inspectable', () => {
  render(<BranchComparisonReview comparison={{ ...comparison, source: { version: 2 }, segments: [null, { kind: 'FUTURE' }, { kind: '__proto__' }, { kind: 'toString' }] }} choices={{}} />);
  expect(screen.getByText('章节 UNKNOWN · v2 · 分支 UNKNOWN')).toBeTruthy();
  expect(screen.getAllByText('未知差异类型')).toHaveLength(4);
  expect(screen.getByText('比较段 1 完整富文本块')).toBeTruthy();
});
it('bounds text and traversal, preserves short Unicode, and distinguishes empty from unavailable', () => {
  expect(branchBlockExcerpt([block('🪷中文')])).toEqual({ text: '🪷中文', limited: false });
  expect(branchBlockExcerpt([block('第一段'), block('第二段')]).text).toBe('第一段\n第二段');
  expect(branchBlockExcerpt([block('a'.repeat(2398) + '🪷')]).text).not.toMatch(/[\uD800-\uDBFF]$/);
  expect(Array.from(branchBlockExcerpt([block('🪷'.repeat(10000))]).text)).toHaveLength(600);
  expect(branchBlockExcerpt([block('🪷'.repeat(10000))]).limited).toBe(true);
  expect(branchBlockExcerpt(Array.from({ length: 600 }, () => block('a'))).limited).toBe(true);
  expect(branchBlockExcerpt([]).text).toContain('此侧为空');
  expect(branchBlockExcerpt(undefined).text).toContain('未提供');
  expect(branchBlockExcerpt([{ type: 'image', attrs: { src: 'never-load' } }]).text).toContain('没有可显示的纯文本');
});
it('renders source text as inert text rather than markup or active media', () => {
  render(<BranchComparisonReview comparison={{ ...comparison, segments: [{ kind: 'UNCHANGED', nodes: [block('<img src="bad" onerror="throw 1">')] }] }} choices={{}} />);
  fireEvent.click(screen.getByLabelText('只看有改动的块'));
  expect(screen.getByText('<img src="bad" onerror="throw 1">')).toBeTruthy();
  expect(document.querySelector('img')).toBeNull();
});
