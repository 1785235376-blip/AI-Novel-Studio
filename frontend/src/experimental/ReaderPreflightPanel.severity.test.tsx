// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { ReaderPreflightPanel } from './ReaderPreflightPanel';

const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const settings = { version: 0, rules: { punctuation: true, repeated_words: true, literals: [] }, license_declaration: '', font_declaration: '' };
const reading = { chapters: [{ id: 'c', title: '港口', version: 2, revision: 'a'.repeat(64), paragraphs: [{ index: 0, offset: 0, text: '甲' }] }], annotations: [], source_digest: 'source', branch_sources_available: true };
const proof = { items: [], truncated: false };
const finding = (code: string, severity: string, message: string, feature: string, chapter_id?: string) => ({ code, severity, message, feature, ...(chapter_id ? { chapter_id } : {}) });
const report = (findings: Record<string, any>[], over: Record<string, any> = {}) => ({ findings, coverage: [{ area: 'chapters', state: 'CHECKED' }, { area: 'generation_candidates', state: 'UNKNOWN' }], source_digest: 'source', has_integrity_blockers: true, checked_format: 'docx', ...over });
const mixed = report([
  finding('b1', 'BLOCKER', '阻塞一', 'exports'),
  finding('b2', 'BLOCKER', '阻塞二', 'exports', 'c'),
  finding('b3', 'BLOCKER', '阻塞三', 'scenes'),
  finding('w1', 'WARNING', '警告一', 'assets'),
  finding('w2', 'WARNING', '警告二', 'review'),
  finding('i1', 'INFO', '提示一', 'chapters'),
  finding('i2', 'INFO', '提示二', 'covers'),
  finding('i3', 'INFO', '提示三', 'export'),
  finding('i4', 'INFO', '提示四', 'stats')
]);
const client = () => experimentalClient('novel', { sessionToken: 'synthetic', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'branch' } });
function backend(reports: Record<string, any>[]) {
  let checkIndex = 0;
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/reader-preflight/settings')) return response(settings);
    if (url.endsWith('/reader-preflight/read')) return response(reading);
    if (url.endsWith('/reader-preflight/proof')) return response(proof);
    if (url.endsWith('/reader-preflight/check')) return response(reports[Math.min(checkIndex++, reports.length - 1)]);
    return response({ items: [] });
  });
  return fetch;
}
const severitySelect = () => screen.getByLabelText('问题等级筛选') as HTMLSelectElement;
const entryButtons = () => screen.getAllByRole('button', { name: /^打开问题入口/ });
async function runPreflight(reports: Record<string, any>[], onNavigate = vi.fn()) {
  const fetch = backend(reports);
  vi.stubGlobal('fetch', fetch);
  render(<ReaderPreflightPanel client={client()} onNavigate={onNavigate} />);
  await screen.findByText('甲');
  fireEvent.click(screen.getByRole('button', { name: '运行发布预检' }));
  await screen.findByLabelText('问题等级筛选');
  return { fetch, onNavigate };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('shows all three severity counts from the complete preflight result with the default all-view', async () => {
  await runPreflight([mixed]);
  expect(severitySelect().value).toBe('ALL');
  expect(screen.getByText('BLOCKER：3')).toBeTruthy();
  expect(screen.getByText('WARNING：2')).toBeTruthy();
  expect(screen.getByText('INFO：4')).toBeTruthy();
  expect(entryButtons()).toHaveLength(9);
});

it('keeps the complete-result counts when a severity filter hides other findings', async () => {
  await runPreflight([mixed]);
  fireEvent.change(severitySelect(), { target: { value: 'WARNING' } });
  expect(screen.getByText('BLOCKER：3')).toBeTruthy();
  expect(screen.getByText('WARNING：2')).toBeTruthy();
  expect(screen.getByText('INFO：4')).toBeTruthy();
  expect(entryButtons()).toHaveLength(2);
  expect(screen.getByText(/警告一/)).toBeTruthy();
  expect(screen.getByText(/警告二/)).toBeTruthy();
  expect(screen.queryByText(/阻塞一/)).toBeNull();
  expect(screen.queryByText(/提示一/)).toBeNull();
});

it('filters precisely by BLOCKER, WARNING and INFO and restores all on 全部', async () => {
  await runPreflight([mixed]);
  fireEvent.change(severitySelect(), { target: { value: 'BLOCKER' } });
  expect(entryButtons()).toHaveLength(3);
  expect(screen.queryByText(/警告一/)).toBeNull();
  fireEvent.change(severitySelect(), { target: { value: 'INFO' } });
  expect(entryButtons()).toHaveLength(4);
  expect(screen.getByText(/提示四/)).toBeTruthy();
  fireEvent.change(severitySelect(), { target: { value: 'ALL' } });
  expect(entryButtons()).toHaveLength(9);
});

it('shows an explicit zero-match prompt without misreporting the whole check as passed', async () => {
  const noWarnings = report([finding('b1', 'BLOCKER', '阻塞一', 'exports'), finding('i1', 'INFO', '提示一', 'covers')]);
  await runPreflight([noWarnings]);
  fireEvent.change(severitySelect(), { target: { value: 'WARNING' } });
  expect(screen.queryAllByRole('button', { name: /^打开问题入口/ })).toHaveLength(0);
  expect(screen.getByText(/当前筛选（警告）没有对应等级的问题/)).toBeTruthy();
  expect(screen.getByText('WARNING：0')).toBeTruthy();
  expect(screen.getByText(/存在文件完整性阻塞/)).toBeTruthy();
});

it('handles an empty findings list distinctly from a filtered zero match', async () => {
  await runPreflight([report([])]);
  expect(screen.getByText('BLOCKER：0')).toBeTruthy();
  expect(screen.getByText('WARNING：0')).toBeTruthy();
  expect(screen.getByText('INFO：0')).toBeTruthy();
  expect(screen.getByText(/本次预检结果没有记录问题/)).toBeTruthy();
  fireEvent.change(severitySelect(), { target: { value: 'BLOCKER' } });
  expect(screen.getByText(/本次预检结果没有记录问题/)).toBeTruthy();
  expect(screen.queryAllByRole('button', { name: /^打开问题入口/ })).toHaveLength(0);
});

it('keeps unknown severities visible in the all view, never counted or relabelled', async () => {
  const withUnknown = report([finding('u1', 'FATAL', '未知等级一', 'exports'), finding('i1', 'INFO', '提示一', 'covers')]);
  await runPreflight([withUnknown]);
  expect(screen.getByText('未知等级一')).toBeTruthy();
  expect(screen.getByText('BLOCKER：0')).toBeTruthy();
  expect(screen.getByText('WARNING：0')).toBeTruthy();
  expect(screen.getByText('INFO：1')).toBeTruthy();
  fireEvent.change(severitySelect(), { target: { value: 'INFO' } });
  expect(screen.queryByText('未知等级一')).toBeNull();
  expect(screen.getByText(/提示一/)).toBeTruthy();
});

it('keeps original finding numbering and navigation targets after filtering', async () => {
  const { onNavigate } = await runPreflight([mixed]);
  fireEvent.change(severitySelect(), { target: { value: 'WARNING' } });
  expect(screen.getByRole('button', { name: '打开问题入口 4' })).toBeTruthy();
  expect(screen.getByRole('button', { name: '打开问题入口 5' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '打开问题入口 4' }));
  expect(onNavigate).toHaveBeenCalledWith({ kind: 'feature', id: 'assets', feature: 'assets' });
  fireEvent.change(severitySelect(), { target: { value: 'BLOCKER' } });
  fireEvent.click(screen.getByRole('button', { name: '打开问题入口 2' }));
  expect(onNavigate).toHaveBeenCalledWith({ kind: 'chapter', id: 'c', anchor: { offset: 0, scroll: 0 } });
  expect(screen.queryByRole('button', { name: '打开问题入口 1' })?.textContent).toContain('1');
  fireEvent.change(severitySelect(), { target: { value: 'ALL' } });
  expect(screen.getByRole('button', { name: '打开问题入口 1' })).toBeTruthy();
});

it('keeps the full integrity conclusion, coverage and stale warning visible across filter changes', async () => {
  await runPreflight([mixed]);
  expect(screen.getByText(/存在文件完整性阻塞/)).toBeTruthy();
  expect(screen.getByText('generation_candidates：UNKNOWN')).toBeTruthy();
  fireEvent.change(severitySelect(), { target: { value: 'INFO' } });
  expect(screen.getByText(/存在文件完整性阻塞/)).toBeTruthy();
  expect(screen.getByText('generation_candidates：UNKNOWN')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('目标导出格式'), { target: { value: 'epub' } });
  await screen.findByText(/输入状态或已读取来源已变化，请重新预检/);
  fireEvent.change(severitySelect(), { target: { value: 'BLOCKER' } });
  expect(screen.getByText(/输入状态或已读取来源已变化，请重新预检/)).toBeTruthy();
  expect(screen.getByText(/存在文件完整性阻塞/)).toBeTruthy();
});

it('never runs a new preflight request or mutates the report when filtering', async () => {
  const first = structuredClone(mixed);
  const { fetch } = await runPreflight([mixed]);
  const checkCalls = () => fetch.mock.calls.filter(([url]) => String(url).endsWith('/check')).length;
  expect(checkCalls()).toBe(1);
  fireEvent.change(severitySelect(), { target: { value: 'BLOCKER' } });
  fireEvent.change(severitySelect(), { target: { value: 'INFO' } });
  fireEvent.change(severitySelect(), { target: { value: 'ALL' } });
  expect(checkCalls()).toBe(1);
  expect(mixed).toEqual(first);
});

it('recomputes the counts when a genuinely new preflight result arrives', async () => {
  const second = report([finding('b1', 'BLOCKER', '新的阻塞', 'exports')]);
  await runPreflight([mixed, second]);
  expect(screen.getByText('BLOCKER：3')).toBeTruthy();
  fireEvent.change(severitySelect(), { target: { value: 'INFO' } });
  fireEvent.click(screen.getByRole('button', { name: '运行发布预检' }));
  await waitFor(() => expect(screen.getByText('BLOCKER：1')).toBeTruthy());
  expect(screen.getByText('WARNING：0')).toBeTruthy();
  expect(screen.getByText('INFO：0')).toBeTruthy();
  expect(screen.queryAllByRole('button', { name: /^打开问题入口/ })).toHaveLength(0);
  expect(screen.getByText(/存在文件完整性阻塞/)).toBeTruthy();
});

it('leaves the original export-center navigation available regardless of the filter', async () => {
  const { onNavigate } = await runPreflight([mixed]);
  fireEvent.change(severitySelect(), { target: { value: 'INFO' } });
  fireEvent.click(screen.getByRole('button', { name: '打开原导出中心' }));
  expect(onNavigate).toHaveBeenCalledWith({ kind: 'feature', id: 'exports', feature: 'exports' });
  expect(screen.getByText(/存在文件完整性阻塞/)).toBeTruthy();
});
