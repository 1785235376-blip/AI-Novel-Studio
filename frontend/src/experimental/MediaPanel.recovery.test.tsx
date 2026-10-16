// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
import type { ExperimentalFlags } from './api';
const flags = (key: string): ExperimentalFlags => ({ experimental: true, default_enabled: false, features: { [`experimental.${key}`]: true } });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function fixture(stale: boolean | undefined, domain?: string, interruptFirstApproval = false) {
  let interrupted = false;
  let row = { id: 'proposal-r3', version: interruptFirstApproval ? 1 : 4, status: interruptFirstApproval ? 'PENDING_REVIEW' : 'APPROVING', kind: 'COVER', candidate_index: 0, stale, domain, preview: 'Interrupted synthetic media', verification: 'MOCK_ONLY', promotion_asset_id: interruptFirstApproval ? undefined : 'existing-asset-r3', promotion_asset_digest: interruptFirstApproval ? undefined : 'checkpoint-sha256', promotion_state: interruptFirstApproval ? undefined : 'ASSET_CREATED', source_digest: 'source-sha256', allowed_actions: ['approve', 'reject'], batch_safe: true, batch_actions: ['approve', 'reject'] };
  const fetch = vi.fn(async (url: string, request: RequestInit) => {
    if (request.method === 'POST' && interruptFirstApproval && !interrupted) { interrupted = true; row = { ...row, version: 4, status: 'APPROVING', promotion_asset_id: 'existing-asset-r3', promotion_asset_digest: 'checkpoint-sha256', promotion_state: 'ASSET_CREATED' }; return new Response(JSON.stringify({ detail: { code: 'PROMOTION_INTERRUPTED' } }), { status: 500 }); }
    if (request.method === 'POST') { row = { ...row, version: 5, status: 'APPROVED' }; return new Response(JSON.stringify(row), { status: 200 }); }
    if (url.endsWith('/preview')) return new Response(new Uint8Array([1, 2, 3]), { status: 200, headers: { 'Content-Type': 'image/png' } });
    return new Response(JSON.stringify({ items: url.endsWith('/proposals') || url.endsWith('/review-inbox') ? [row] : [] }), { status: 200 });
  });
  vi.stubGlobal('fetch', fetch);
  vi.stubGlobal('URL', class extends URL { static createObjectURL() { return 'blob:synthetic-preview'; } static revokeObjectURL() {} });
  return fetch;
}
describe('media promotion checkpoint recovery', () => {
  it('makes interrupted cover approval recoverable with Inbox disabled, only after explicit action', async () => {
    const fetch = fixture(false);
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('cover_storyboard_generation')} />);
    const recovery = await screen.findByRole('region', { name: '资产批准恢复' });
    expect(recovery.textContent).toContain('existing-asset-r3'); expect(recovery.textContent).toContain('checkpoint-sha256'); expect(recovery.textContent).toContain('RESUME_APPROVAL');
    expect(screen.queryByRole('button', { name: '统一审核' })).toBeNull();
    expect(screen.queryByRole('button', { name: '驳回媒体候选' })).toBeNull();
    expect(fetch.mock.calls.filter(([, request]) => request.method === 'POST')).toHaveLength(0);
    const resume = within(recovery).getByRole('button', { name: '恢复此次资产批准' });
    await waitFor(() => expect((resume as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(resume);
    await waitFor(() => expect(screen.queryByRole('region', { name: '资产批准恢复' })).toBeNull());
    const writes = fetch.mock.calls.filter(([, request]) => request.method === 'POST'); expect(writes).toHaveLength(1);
    expect(writes[0][0]).toBe('/api/novels/novel/experimental/media/proposals/proposal-r3/approve');
    expect(JSON.parse(writes[0][1].body as string)).toEqual({ expected_version: 4 });
  });
  it('reloads the durable checkpoint after an interrupted first approval without automatically resuming', async () => {
    const fetch = fixture(false, undefined, true);
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('cover_storyboard_generation')} />);
    const approve = await screen.findByRole('button', { name: '批准媒体为资产' });
    await waitFor(() => expect((approve as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(approve);
    const recovery = await screen.findByRole('region', { name: '资产批准恢复' });
    expect(recovery.textContent).toContain('existing-asset-r3'); expect(screen.queryByRole('button', { name: '驳回媒体候选' })).toBeNull();
    expect(screen.getByRole('alert').textContent).toContain('PROMOTION_INTERRUPTED');
    expect(fetch.mock.calls.filter(([, request]) => request.method === 'POST')).toHaveLength(1);
  });
  it('preserves checkpoint details but removes resume if the current-source refresh fails', async () => {
    const fetch = fixture(false);
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('cover_storyboard_generation')} />);
    await screen.findByRole('button', { name: '恢复此次资产批准' });
    const refresh = screen.getByRole('button', { name: '刷新实验记录' });
    await waitFor(() => expect((refresh as HTMLButtonElement).disabled).toBe(false));
    fetch.mockImplementation(async () => new Response(JSON.stringify({ detail: { code: 'READ_UNAVAILABLE' } }), { status: 503 }));
    fireEvent.click(refresh); await screen.findByRole('alert');
    const recovery = screen.getByRole('region', { name: '资产批准恢复' });
    expect(recovery.textContent).toContain('existing-asset-r3'); expect(recovery.textContent).toContain('checkpoint-sha256'); expect(recovery.textContent).toContain('SOURCE_FRESHNESS_UNVERIFIED');
    expect(screen.queryByRole('button', { name: '恢复此次资产批准' })).toBeNull(); expect(screen.queryByRole('button', { name: '驳回媒体候选' })).toBeNull();
    expect(fetch.mock.calls.filter(([, request]) => request.method === 'POST')).toHaveLength(0);
  });
  it.each([true, undefined])('retains asset references and offers no resume/reject when source currentness is %s', async stale => {
    const fetch = fixture(stale);
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('cover_storyboard_generation')} />);
    const recovery = await screen.findByRole('region', { name: '资产批准恢复' });
    expect(recovery.textContent).toContain(stale ? 'SOURCE_CHANGED_RECONCILIATION_REQUIRED' : 'SOURCE_FRESHNESS_UNVERIFIED');
    expect(recovery.textContent).toContain('existing-asset-r3'); expect(recovery.textContent).toContain('checkpoint-sha256');
    expect(screen.queryByRole('button', { name: '恢复此次资产批准' })).toBeNull(); expect(screen.queryByRole('button', { name: '驳回媒体候选' })).toBeNull();
    expect(fetch.mock.calls.filter(([, request]) => request.method === 'POST')).toHaveLength(0);
  });
  it.each(['media', 'audiobook'])('keeps %s Inbox checkpoints visible without reject/batch paths', async domain => {
    const fetch = fixture(true, domain);
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('unified_review_inbox')} />);
    const recovery = await screen.findByRole('region', { name: '资产批准恢复' }); expect(recovery.textContent).toContain('existing-asset-r3');
    expect(screen.queryByRole('button', { name: '恢复此次资产批准' })).toBeNull(); expect(screen.queryByRole('button', { name: '驳回此审核项' })).toBeNull(); expect(screen.queryByRole('checkbox', { name: '加入安全批量审核' })).toBeNull();
    expect(fetch.mock.calls.filter(([, request]) => request.method === 'POST')).toHaveLength(0);
  });
});
