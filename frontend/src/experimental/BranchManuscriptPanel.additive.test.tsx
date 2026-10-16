// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { BranchManuscriptPanel } from './BranchManuscriptPanel';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const client = (branch = 'branch-a') => experimentalClient('synthetic', { sessionToken: 'trusted-synthetic', scope: { workspaceId: 'w', projectId: 'synthetic', storylineId: 's', branchId: branch } });
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const row = { id: 'synthetic:~b00000000-0000-0000-0000-000000000001', title: '真实分支章节', version: 2, novel_id: 'synthetic', branch_id: 'branch-a' };
const proposal = { id: 'merge-one', status: 'REVIEW', version: 4, preview_digest: 'a'.repeat(64), source: { version: 2 }, target: { version: 3 } };
function backend(options: { readonly?: boolean; rows?: any[]; merges?: any[]; override?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined } = {}) {
  return vi.fn(async (url: string, init: RequestInit) => {
    const value = await options.override?.(url, init); if (value) return value;
    if (url.endsWith('/catalog')) return response({ initialized: !!options.rows?.length, revision: 0, can_write: !options.readonly, can_review: !options.readonly });
    if (url.endsWith('/chapters')) return response(init.method === 'POST' ? row : { items: options.rows || [] }, init.method === 'POST' ? 201 : 200);
    if (url.endsWith('/records')) return response({ forks: [], merges: options.merges || [] });
    if (url.endsWith('/review')) return response({ ...proposal, stale: false, checkpoint: { type: 'doc', content: [] }, desired_document: { type: 'doc', content: [] } });
    throw new Error('unexpected endpoint ' + url);
  });
}

it('mounts exact block review on explicit compare and keeps manual selections inside original comparison', async () => {
  const segment = { kind: 'CONFLICT', start: 0, end: 1, base: [], ORIGINAL: [{ type: 'paragraph', content: [{ type: 'text', text: '来源内容' }] }], FORK: [] };
  const fetch = backend({ rows: [{ ...row, origin: { chapter_id: 'synthetic:1', scope: {} } }], override: (url, init) => {
    if (!url.endsWith('/compare')) return undefined;
    const selected = JSON.parse(init.body as string).choices;
    return response({ can_apply: !!selected['0'], preview_digest: 'comparison-' + (selected['0'] || 'pending'), source: { id: row.id, version: 2, branch_id: 'branch-a', document_digest: 'exact-fork' }, target: { id: 'synthetic:1', version: 5, branch_id: null, document_digest: 'exact-target' }, conflicts: selected['0'] ? [] : [{ id: '0', ...segment }], segments: [segment], desired_document: selected['0'] ? { type: 'doc', content: [] } : null });
  } });
  vi.stubGlobal('fetch', fetch); render(<BranchManuscriptPanel client={client()} />);
  fireEvent.change(await screen.findByLabelText('分支新章节标题'), { target: { value: '保留未保存输入' } });
  fireEvent.click(await screen.findByRole('button', { name: '比较并合并 真实分支章节' }));
  fireEvent.click(screen.getByRole('button', { name: '更新三方比较' }));
  await screen.findByRole('region', { name: '三方差异人工阅读' });
  expect(screen.getByText('章节 synthetic:1 · v5 · 分支 主线')).toBeTruthy();
  expect(screen.getByText('当前人工选择：尚未选择（仅针对本次比较）')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('冲突 0 的人工选择'), { target: { value: 'ORIGINAL' } });
  expect(screen.queryByRole('region', { name: '三方差异人工阅读' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '更新三方比较' }));
  await screen.findByText('当前人工选择：保留当前来源（仅针对本次比较）');
  expect((screen.getByLabelText('分支新章节标题') as HTMLInputElement).value).toBe('保留未保存输入');
  expect(fetch.mock.calls.filter(([, init]) => init.method === 'POST').map(([url]) => url.endsWith('/compare'))).toEqual([true, true]);
});

it('discards a pending comparison after client identity changes', async () => {
  let release!: (value: Response) => void;
  const fetch = backend({ rows: [{ ...row, origin: { chapter_id: 'synthetic:1', scope: {} } }], override: url => url.endsWith('/compare') ? new Promise(resolve => { release = resolve; }) : undefined });
  vi.stubGlobal('fetch', fetch); const view = render(<BranchManuscriptPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '比较并合并 真实分支章节' }));
  fireEvent.click(screen.getByRole('button', { name: '更新三方比较' }));
  await waitFor(() => expect(release).toBeTypeOf('function'));
  view.rerender(<BranchManuscriptPanel client={client('branch-b')} />);
  release(response({ can_apply: true, preview_digest: 'late', source: { version: 2 }, target: { version: 1 }, conflicts: [], segments: [], desired_document: {} }));
  await screen.findByRole('button', { name: '比较并合并 真实分支章节' });
  expect(screen.queryByRole('region', { name: '三方差异人工阅读' })).toBeNull();
  expect(fetch.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1);
});
