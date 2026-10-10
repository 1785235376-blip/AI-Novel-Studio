// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { BranchManuscriptPanel } from './BranchManuscriptPanel';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
import { InboxPanel } from './InboxPanel';

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

it('keeps uninitialized branch empty and opens exact branch chapter in the original editor', async () => {
  const fetch = backend({ rows: [row] }); vi.stubGlobal('fetch', fetch); const navigate = vi.fn();
  render(<StrictMode><BranchManuscriptPanel client={client()} onNavigate={navigate} /></StrictMode>);
  fireEvent.click(await screen.findByRole('button', { name: '在原编辑器打开 真实分支章节' }));
  expect(navigate).toHaveBeenCalledWith({ kind: 'chapter', id: row.id, novel_id: 'synthetic', branch_id: 'branch-a', version: 2, anchor: { offset: 0, scroll: 0 } });
  expect(fetch.mock.calls.every(([, init]) => (init.headers as any)['X-Branch-Id'] === 'branch-a')).toBe(true);
  expect(fetch.mock.calls.every(([url]) => url.includes('/branch-manuscript/'))).toBe(true);
});

it('renders disabled read-only and unavailable states without writes', async () => {
  const fetch = backend({ readonly: true }); vi.stubGlobal('fetch', fetch);
  render(<BranchManuscriptPanel client={client()} />);
  await screen.findByText('此分支尚未初始化。创建章节或明确分叉后，分支正文才可用。');
  expect((screen.getByRole('button', { name: '创建独立分支章节' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '读取已授权来源章节' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('requires reopening exact proposal content before versioned human merge and preserves conflict', async () => {
  const fetch = backend({ merges: [proposal], override: (url, init) => url.endsWith('/apply') ? response({ detail: { code: 'BRANCH_MERGE_REVIEW_CHANGED' } }, 409) : undefined });
  vi.stubGlobal('fetch', fetch); render(<BranchManuscriptPanel client={client()} />);
  const confirmation = await screen.findByLabelText('确认采用已审核正文并改写指定来源');
  expect((confirmation as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '读取此提案正文与当前来源' }));
  await waitFor(() => expect((confirmation as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(confirmation); fireEvent.click(screen.getByRole('button', { name: '确认人工合并' }));
  await screen.findByText(/BRANCH_MERGE_REVIEW_CHANGED/);
  const writes = fetch.mock.calls.filter(([, init]) => init.method === 'POST');
  expect(writes).toHaveLength(1); expect(JSON.parse(writes[0][1].body as string)).toEqual({ expected_version: 4, preview_digest: 'a'.repeat(64), confirmed: true });
  expect((screen.getByRole('button', { name: '确认人工合并' }) as HTMLButtonElement).disabled).toBe(true);
});

it('prevents double create and discards a late result after branch navigation', async () => {
  let release!: (value: Response) => void;
  const fetch = backend({ override: (url, init) => url.endsWith('/chapters') && init.method === 'POST' ? new Promise(resolve => { release = resolve; }) : undefined });
  vi.stubGlobal('fetch', fetch); const view = render(<BranchManuscriptPanel client={client()} />);
  await screen.findByText('此分支尚未初始化。创建章节或明确分叉后，分支正文才可用。');
  fireEvent.change(screen.getByLabelText('分支新章节标题'), { target: { value: '合成新章' } });
  const create = screen.getByRole('button', { name: '创建独立分支章节' }); fireEvent.click(create); fireEvent.click(create);
  await waitFor(() => expect(release).toBeTypeOf('function'));
  expect(fetch.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1);
  view.rerender(<BranchManuscriptPanel client={client('branch-b')} />); release(response(row, 201));
  await screen.findByText('此分支尚未初始化。创建章节或明确分叉后，分支正文才可用。');
  expect((screen.getByLabelText('分支新章节标题') as HTMLInputElement).value).toBe('');
  expect(screen.queryByText('已创建分支章节，可在原编辑器继续写作。')).toBeNull();
});

it('exposes the branch surface only under its own default-off flag', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch);
  const view = render(<ExperimentalWorkbench novelId="synthetic" context={{ sessionToken: '' }} flags={{ experimental: true, default_enabled: false, features: {} }} />);
  expect(screen.queryByRole('region', { name: '协作分支正文' })).toBeNull(); expect(fetch).not.toHaveBeenCalled();
  view.rerender(<ExperimentalWorkbench novelId="synthetic" context={{ sessionToken: 'trusted-synthetic', scope: { workspaceId: 'w', projectId: 'synthetic', storylineId: 's', branchId: 'branch-a' } }} flags={{ experimental: true, default_enabled: false, features: { 'experimental.branch_manuscript_v1': true } }} />);
  await screen.findByRole('region', { name: '协作分支正文' });
});

it('keeps branch inbox entries read-only and exposes their original panel contract', async () => {
  const fetch = vi.fn(async () => response({ items: [{ ...proposal, domain: 'branch_manuscript',
    preview: 'Branch human merge', allowed_actions: [], batch_safe: false, batch_actions: [],
    review_mode: 'ORIGINAL_DOMAIN_REQUIRED', target: { panel: 'BranchManuscriptPanel',
      feature: 'branch_manuscript_v1', kind: 'merges', id: proposal.id, version: proposal.version,
      novel_id: 'synthetic', branch_id: 'branch-a',
      api: { cancel: '/novels/synthetic/experimental/branch-manuscript/merge/merge-one/cancel',
        cancel_body: { expected_version: 4 }, cancel_permissions: ['domain.read', 'domain.review'] } } }] }));
  vi.stubGlobal('fetch', fetch);
  render(<InboxPanel client={client()} requestedDomain="branch_manuscript" requestedItemId={proposal.id} />);
  await screen.findByText('此领域当前状态仅供查看。');
  expect(screen.queryByRole('button', { name: /此审核项|取消/ })).toBeNull();
  expect(screen.queryByLabelText('加入安全批量审核')).toBeNull();
  expect((screen.getByRole('button', { name: '批量批准已选审核项' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/BranchManuscriptPanel/).textContent).toContain('/branch-manuscript/merge/merge-one/cancel');
  expect(fetch.mock.calls.every((call: any[]) => call[1].method === 'GET')).toBe(true);
});
