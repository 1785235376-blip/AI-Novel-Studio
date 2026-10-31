// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { PromptWorkspace } from './PromptWorkspace';
import { clearAllStashedDrafts, editDraft, newDraft, stashDraft, takeDraft } from './promptDraft';

const fixture = (name: string): Record<string, any> => JSON.parse(readFileSync(
  resolve(process.cwd(), 'src/prompt/__fixtures__', name), 'utf8'));
const detail = (family: string, revision = 2) => {
  const value = fixture('detail.json');
  return { ...value, family_id: family, head_asset_id: `${family}-${revision}`, revision,
    body: { ...value.body, value: `${family} server text` },
    versions: Array.from({ length: revision }, (_, index) => ({ ...value.versions[0], revision: index + 1,
      asset_id: `${family}-${index + 1}`, previous_asset_id: index ? `${family}-${index}` : null })) };
};
const library = () => {
  const value = fixture('library.json');
  return { ...value, entries: ['A', 'B'].map(family => ({ ...value.entries[0], family_id: family,
    head_asset_id: `${family}-2`, revision: 2 })), prompt_count: 2, projected_families: 2, revision_count: 4 };
};
const body = () => screen.getByLabelText('正文', { exact: true }) as HTMLTextAreaElement;
const select = (index: number) => fireEvent.click(document.querySelectorAll('.prompt-list-item')[index]);
const status = () => document.querySelector('.prompt-status')?.textContent ?? '';
function harness(outcome: 'saved' | 'conflict' | 'rejected' | 'unknown' = 'saved') {
  let release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  let returned = false;
  let aRevision = 2;
  const transport: StudioGraphTransport = {
    async json<T>(url: string, method = 'GET', request?: unknown): Promise<T> {
      // Exact method/path first: a revision POST must never be mistaken for a family GET.
      if (method === 'POST' && url === '/api/projects/p/studio/prompts/A/revisions') {
        posts.push({ url, body: request as Record<string, unknown> });
        await gate;
        returned = true;
        if (outcome === 'conflict') throw new ApiError({ status: 409, code: 'HTTP_409', message: 'stale',
          details: { code: 'PROMPT_REVISION_STALE', family_id: 'A', current_revision: 3 } });
        if (outcome === 'rejected') throw new ApiError({ status: 422, code: 'HTTP_422', message: 'invalid' });
        if (outcome === 'unknown') throw new TypeError('response lost');
        return { family_id: 'A', asset_id: 'A-3', revision: 3, asset_version: 1,
          text_digest: 'd'.repeat(64), payload_digest: 'e'.repeat(64),
          previous_asset_id: 'A-2', idempotent_replay: false } as T;
      }
      if (method === 'GET' && url.endsWith('/studio/prompts')) return library() as T;
      if (method === 'GET' && /\/studio\/prompts\/[AB]$/.test(url)) return detail(url.slice(-1), url.endsWith('/A') ? aRevision : 2) as T;
      throw new Error(`Unexpected ${method} ${url}`);
    },
  };
  return { transport, posts, release, returned: () => returned, advanceA: () => { aRevision = 3; } };
}
const props = (transport: StudioGraphTransport, actor = 'actor', projectId = 'p', branchId: string | null = null) => ({
  projectId, branchId, actor, transport, mode: 'PROFESSIONAL' as const, writable: true, denied: false,
});
async function saveAThenOpenB(h: ReturnType<typeof harness>) {
  await waitFor(() => expect(document.querySelectorAll('.prompt-list-item')).toHaveLength(2));
  select(0);
  await waitFor(() => expect(body().value).toBe('A server text'));
  fireEvent.change(body(), { target: { value: 'A frozen local text' } });
  fireEvent.click(screen.getByRole('button', { name: '保存新版本' }));
  await waitFor(() => expect(h.posts).toHaveLength(1));
  expect(h.posts[0].body).toMatchObject({ text: 'A frozen local text', expected_previous_asset_id: 'A-2', expected_revision: 2 });
  select(1);
  await waitFor(() => expect(body().value).toBe('B server text'));
}
async function finish(h: ReturnType<typeof harness>) {
  await act(async () => { h.release(); await Promise.resolve(); });
  await waitFor(() => expect(h.returned()).toBe(true));
}
beforeEach(() => { clearAllStashedDrafts(); localStorage.clear(); });
afterEach(cleanup);

describe('mounted save receipts survive family navigation', () => {
  it.each(['saved', 'conflict', 'rejected', 'unknown'] as const)('reopens A with its actual %s outcome and never changes B', async outcome => {
    const h = harness(outcome);
    render(<PromptWorkspace {...props(h.transport)} />);
    try {
      await saveAThenOpenB(h);
      await finish(h);
      expect(body().value).toBe('B server text');
      expect(status()).not.toContain('已保存');
      const expected = { saved: 'SAVED', conflict: 'CONFLICT', rejected: 'REJECTED', unknown: 'UNKNOWN' }[outcome];
      await waitFor(() => expect(takeDraft('p', null, 'actor', 'A')?.state).toBe(expected));
      select(0);
      await waitFor(() => expect(body().value).toBe('A frozen local text'));
      expect(takeDraft('p', null, 'actor', 'A')?.state).toBe(expected);
      if (outcome === 'saved') {
        expect(status()).toContain('已保存');
        expect(takeDraft('p', null, 'actor', 'A')).toMatchObject({ baseAssetId: 'A-3', baseRevision: 3, requestId: null });
        expect(screen.queryByRole('button', { name: '用同一请求重试' })).toBeNull();
      }
      if (outcome === 'conflict') {
        h.advanceA();
        fireEvent.click(screen.getByRole('button', { name: '重新基准到服务器最新修订' }));
        await waitFor(() => expect(takeDraft('p', null, 'actor', 'A')).toMatchObject({
          state: 'DIRTY', conflictCode: null, baseAssetId: 'A-3', baseRevision: 3,
          content: { text: 'A frozen local text' }, requestId: null,
        }));
        expect(screen.queryByRole('button', { name: '重新基准到服务器最新修订' })).toBeNull();
        expect(body().value).toBe('A frozen local text');
      }
      if (outcome === 'unknown') {
        expect(screen.getByRole('button', { name: '用同一请求重试' })).toBeTruthy();
        expect(takeDraft('p', null, 'actor', 'A')?.requestId).toBe(h.posts[0].body.request_id);
      }
      expect(h.posts).toHaveLength(1);
    } finally { h.release(); }
  });

  it.each(['saved', 'conflict'] as const)('does not overwrite a replaced A slot on late %s', async outcome => {
    const h = harness(outcome);
    render(<PromptWorkspace {...props(h.transport)} />);
    try {
      await saveAThenOpenB(h);
      stashDraft('p', null, 'actor', editDraft({ ...newDraft('A'), familyId: 'A', baseAssetId: 'A-2', baseRevision: 2 }, { text: 'replacement A' }));
      await finish(h);
      select(0);
      await waitFor(() => expect(body().value).toBe('replacement A'));
      expect(takeDraft('p', null, 'actor', 'A')?.state).toBe('DIRTY');
      expect(h.posts).toHaveLength(1);
    } finally { h.release(); }
  });

  it.each(['actor', 'project', 'branch', 'client'] as const)('fences an authority %s ABA round trip', async kind => {
    const h = harness();
    const view = render(<PromptWorkspace {...props(h.transport)} />);
    try {
      await saveAThenOpenB(h);
      const changed = props(h.transport, kind === 'actor' ? 'other' : 'actor', kind === 'project' ? 'other' : 'p', kind === 'branch' ? 'other' : null);
      view.rerender(<PromptWorkspace {...changed} scope={kind === 'client' ? { projectId: 'p' } : undefined} />);
      view.rerender(<PromptWorkspace {...props(h.transport)} />);
      const before = takeDraft('p', null, 'actor', 'A');
      await finish(h);
      expect(takeDraft('p', null, 'actor', 'A')).toEqual(before);
      expect(takeDraft('p', null, 'actor', 'A')?.state).toBe('SUBMITTING');
      expect(h.posts).toHaveLength(1);
    } finally { h.release(); }
  });

  it('keeps unmounted pending work unresolved even when the response later arrives', async () => {
    const h = harness();
    const view = render(<PromptWorkspace {...props(h.transport)} />);
    try {
      await saveAThenOpenB(h);
      view.unmount();
      await finish(h);
      expect(takeDraft('p', null, 'actor', 'A')?.state).toBe('SUBMITTING');
      expect(h.posts).toHaveLength(1);
    } finally { h.release(); }
  });
});
