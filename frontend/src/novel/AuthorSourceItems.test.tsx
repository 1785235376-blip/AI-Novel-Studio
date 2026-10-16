// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AuthorSourceItems } from './AuthorSourceItems';
import { AuthorRequestControls } from './AuthorRequestControls';
import { AuthorRequestPreviewPanel } from './AuthorRequestPreviewPanel';
import { defaultAuthorRequestScope, type AuthorRequestScope, type AuthorSourceManifest } from './authorContextClient';
const item = { key: 'a'.repeat(64), source_digest: 'b'.repeat(64), label: '林青', kind: 'CHARACTER', version: null, version_state: 'CONTENT_DIGEST_ONLY', included: true, pinned: false };
const manifest: AuthorSourceManifest = { items: [item], dependent_context_omitted: false, omission_reason: null, unidentified_sources_require_bundle_removal: false, primary_manuscript_and_author_input_separate: true, granularity: 'IDENTIFIED_RECORDS_WITH_CONSERVATIVE_DEPENDENCIES' };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it('binds exclusion and pinning to actual server source fingerprint without editing request text', () => {
  const change = vi.fn(); render(<AuthorSourceItems manifest={manifest} onChange={change} disabled={false} />);
  fireEvent.click(screen.getByRole('checkbox', { name: '包含人物：林青 · aaaaaaaa' }));
  expect(change).toHaveBeenLastCalledWith({ ...defaultAuthorRequestScope, source_items: [{ key: item.key, source_digest: item.source_digest, include: false }] });
  fireEvent.click(screen.getByRole('button', { name: '固定 林青 当前版本' }));
  expect(change).toHaveBeenLastCalledWith({ ...defaultAuthorRequestScope, source_items: [{ key: item.key, source_digest: item.source_digest, include: true }] });
  expect(screen.getByText(/原记录无数字版本/)).toBeTruthy();
});
it('explains conservative dependent exclusion and keeps unavailable controls noninteractive', () => {
  render(<AuthorSourceItems manifest={{ ...manifest, dependent_context_omitted: true, unidentified_sources_require_bundle_removal: true }} disabled={false} />);
  expect(screen.getByText(/不会通过摘要重新混入/)).toBeTruthy();
  expect((screen.getByRole('checkbox') as HTMLInputElement).disabled).toBe(true);
});
it('lets a stale pin be explicitly cleared even when no preview result is available', () => {
  const change = vi.fn(); render(<AuthorRequestControls value={{ ...defaultAuthorRequestScope, source_items: [{ key: item.key, source_digest: item.source_digest, include: false }] }} onChange={change} source="" operation="continue" />);
  fireEvent.click(screen.getByRole('button', { name: '清除逐项来源限制' }));
  expect(change).toHaveBeenCalledWith(defaultAuthorRequestScope);
});
it('requires a fresh real preflight after item change and never auto-dispatches', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
    const body = JSON.parse(init!.body as string), removed = body.request_scope.source_items?.[0]?.include === false;
    return { ok: true, json: async () => ({ preview_digest: (removed ? 'd' : 'c').repeat(64), chapter_id: 'n:1', chapter_version: 1,
      target: 'local', provider_id: 'fixture', model_id: 'model', source_strategy: 'LAST_2000_SAVED_CHARACTERS', source_characters: 12, prompt_characters: 20,
      privacy_omissions: [], context_sections: [], creation_records: [], request: { prompt: removed ? 'filtered actual request' : 'original actual request', context: {}, parameters: {}, system_instruction: null },
      source_manifest: { ...manifest, items: [{ ...item, included: !removed, pinned: !!body.request_scope.source_items?.length }], dependent_context_omitted: removed } }) } as Response;
  });
  const receipt = vi.fn();
  function Harness() { const [scope, setScope] = useState<AuthorRequestScope>(defaultAuthorRequestScope); return <AuthorRequestPreviewPanel saved disabled={false} onReceipt={receipt} onScopeChange={setScope} context={{ sessionToken: '' }} body={{ novel_id: 'n', chapter_id: 'n:1', chapter_version: 1, operation: 'continue', instruction: '', style: '', profile: 'LOCAL_ONLY', provider_id: 'fixture', model_id: 'model', source: '', selected_text: '', request_scope: scope }} />; }
  render(<Harness />);fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));await screen.findByText('请求已预检');
  fireEvent.click(screen.getByRole('checkbox', { name: '包含人物：林青 · aaaaaaaa' }));
  await waitFor(() => expect(screen.queryByText('请求已预检')).toBeNull());expect(receipt).toHaveBeenLastCalledWith(undefined);expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));await screen.findByText('请求已预检');
  expect(JSON.parse(fetch.mock.calls[1][1]!.body as string).request_scope.source_items).toEqual([{ key: item.key, source_digest: item.source_digest, include: false }]);
  expect(receipt).toHaveBeenLastCalledWith(expect.objectContaining({ previewDigest: 'd'.repeat(64), requestBody: expect.objectContaining({ request_scope: expect.objectContaining({ source_items: expect.any(Array) }) }) }));
});
