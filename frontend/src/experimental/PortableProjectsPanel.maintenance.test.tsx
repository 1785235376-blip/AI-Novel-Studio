// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PortableProjectsPanel } from './PortableProjectsPanel';
import { experimentalClient } from './api';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = () => experimentalClient('n1', { sessionToken: 'host' });
const catalog = { chapters: [{ id: 'c1', title: '合成海港', version: 4 }], missing: [{ id: 'missing-a', expected_sha256: 'a'.repeat(64), chapter_ids: ['c1'] }], restore_available: true, limitations: [] };
const storage = { categories: [{ kind: 'HISTORY', bytes: 43, measurement: 'AUTHORIZED_ACTIVE_CHAPTER_HISTORY_CONTENT_BYTES', cleanable: false }, { kind: 'TEMPORARY_FAILED_FILES', bytes: 100, measurement: 'OWNED_PRESERVED_INPUT_AND_STAGED_ASSET_BYTES', unmeasured_records: 1, cleanable: false }], eligible: [], preview_digest: 'd'.repeat(64) };
const row = { id: 'relink', version: 1, kind: 'RELINK', status: 'PREFLIGHT', snapshot_digest: 'c'.repeat(64), digest_matches: false,
  relink_review: { missing_id: 'missing-a', expected_sha256: 'a'.repeat(64), candidate_sha256: 'b'.repeat(64), affected_chapters: [{ id: 'c1', title: '合成海港', version: 3, current_version: 3 }], conflicts: [{ code: 'DIGEST_MISMATCH', blocking: false }], can_confirm: true } };
function mock(items: () => unknown[] = () => [row], mutation?: () => Response) {
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation?.() || reply({ ...row, status: 'RELINKED' });
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/storage')) return reply(storage);
    return reply({ items: items() });
  });
  vi.stubGlobal('fetch', fetch); return fetch;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it('shows original and candidate hashes plus exact affected versions before explicit replacement consent', async () => {
  const fetch = mock(); render(<StrictMode><PortableProjectsPanel client={client()} /></StrictMode>);
  const original = await screen.findByLabelText('原媒体 SHA-256') as HTMLInputElement;
  const candidate = screen.getByLabelText('候选文件 SHA-256') as HTMLInputElement;
  expect(original.value).toBe('a'.repeat(64)); expect(candidate.value).toBe('b'.repeat(64)); expect(original.readOnly).toBe(true);
  original.focus(); expect(document.activeElement).toBe(original);
  expect(screen.getByText('合成海港 · 预检 v3 · 当前 v3')).toBeTruthy();
  expect(screen.getByText(/候选文件与原媒体摘要不同/)).toBeTruthy();
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  const confirm = screen.getByRole('button', { name: '确认重连当前引用' }) as HTMLButtonElement;
  fireEvent.click(screen.getByLabelText('已核对本记录与缺失项，确认重连所列章节引用')); expect(confirm.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('明确使用内容不同或摘要未知的替代文件')); fireEvent.click(confirm);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/relink'))).toBe(true));
  const [, init] = fetch.mock.calls.find(([url]) => url.endsWith('/relink'))!;
  expect(JSON.parse(String(init.body))).toEqual({ expected_version: 1, snapshot_digest: row.snapshot_digest, confirmed: true, accept_different_digest: true });
});
it('persistent source conflicts show both versions and cannot be approved with replacement consent', async () => {
  const fetch = mock(() => [{ ...row, relink_review: { ...row.relink_review, affected_chapters: [{ ...row.relink_review.affected_chapters[0], current_version: 4 }], conflicts: [{ code: 'SOURCE_CHANGED', blocking: true }], can_confirm: false } }]);
  render(<PortableProjectsPanel client={client()} />); await screen.findByText('合成海港 · 预检 v3 · 当前 v4');
  expect(screen.getByText(/章节版本或来源权限已变化/)).toBeTruthy();
  fireEvent.click(screen.getByLabelText('已核对本记录与缺失项，确认重连所列章节引用'));
  fireEvent.click(screen.getByLabelText('明确使用内容不同或摘要未知的替代文件'));
  expect((screen.getByRole('button', { name: '确认重连当前引用' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
it('failed confirmation refreshes the conflict report, clears consent and retains the chosen file', async () => {
  let failed = false;
  const fetch = mock(() => [{ ...row, relink_review: { ...row.relink_review, can_confirm: !failed, conflicts: failed ? [{ code: 'ORIGINAL_REFERENCE_CHANGED', blocking: true }] : row.relink_review.conflicts } }], () => { failed = true; return reply({ detail: { code: 'EXPERIMENTAL_SOURCE_STALE', message: 'PORTABLE_ORIGINAL_REFERENCE_CHANGED' } }, 409); });
  render(<PortableProjectsPanel client={client()} />); await screen.findByLabelText('原媒体 SHA-256');
  fireEvent.change(screen.getByLabelText('选择重连媒体文件'), { target: { files: [new File(['x'], 'retained.wav')] } });
  fireEvent.click(screen.getByLabelText('已核对本记录与缺失项，确认重连所列章节引用'));
  fireEvent.click(screen.getByLabelText('明确使用内容不同或摘要未知的替代文件'));
  fireEvent.click(screen.getByRole('button', { name: '确认重连当前引用' }));
  await screen.findByText(/原媒体状态或摘要已变化/);
  expect(screen.getByText('已选择重连文件：retained.wav')).toBeTruthy();
  expect((screen.getByLabelText('已核对本记录与缺失项，确认重连所列章节引用') as HTMLInputElement).checked).toBe(false);
  expect((screen.getByRole('button', { name: '确认重连当前引用' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/relink'))).toHaveLength(1);
});
it('labels retained storage measurements and incomplete bytes without enabling cleanup', async () => {
  mock(() => []); render(<PortableProjectsPanel client={client()} />);
  await screen.findByText('历史版本：43 字节（不清理）');
  expect(screen.getByText(/另有 1 项无法校验，保留且未计入/)).toBeTruthy();
  expect(screen.getByText(/不代表整个磁盘占用/)).toBeTruthy();
  const details = screen.getByText('查看本次可清理缓存清单'); expect(details.tagName).toBe('SUMMARY');
  fireEvent.click(screen.getByLabelText('已核对当前预览，只清理列出的可重建缓存'));
  expect((screen.getByRole('button', { name: '确认清理预览中的缓存' }) as HTMLButtonElement).disabled).toBe(true);
});
it('keeps the missing-media manifest inspectable before creating any restored project', async () => {
  const fetch = mock(() => [{ id: 'import', version: 1, kind: 'IMPORT', status: 'PREFLIGHT', snapshot_digest: 'c'.repeat(64), title: 'Synthetic import', chapter_count: 1, media: [{ ref: 'a0001', state: 'MISSING', sha256: 'a'.repeat(64) }] }]);
  render(<PortableProjectsPanel client={client()} />);
  const summary = await screen.findByText('查看缺失媒体清单');
  expect(summary.tagName).toBe('SUMMARY'); expect(summary.parentElement?.textContent).toContain('a0001');
  expect(summary.parentElement?.textContent).toContain('a'.repeat(64));
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
