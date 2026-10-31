// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TranslationMemoryPanel } from './TranslationMemoryPanel';
import { multilingualEditionsClient, type LanguageEdition, type EditionSegment } from './multilingualEditionsClient';
import { experimentalClient } from './api';
const edition = { id: 'edition', version: 4, target_language: 'en', direction: 'ltr', status: 'DRAFT', stale: false, content_withheld: false } as LanguageEdition;
const segment = { id: 'segment', source_text: 'Same source' } as EditionSegment;
const candidate = { source_edition_id: 'origin', source_edition_version: 7, source_segment_id: 'source-segment', source_version: 2, target_text: 'Accepted translation', preview_digest: 'a'.repeat(64), style_matches: false, can_adopt: true, issues: [] };
const response = (value: unknown) => new Response(JSON.stringify(value));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(fetch: any, blocked = false) {
  vi.stubGlobal('fetch', fetch); const api = multilingualEditionsClient(experimentalClient('n1', { sessionToken: 'host' })); const perform = vi.fn(async fn => { await fn(); });
  return { api, perform, props: { api, edition, segment, blocked, perform } };
}
it('reads accepted memory only on demand and copies as draft with exact provenance receipt', async () => {
  const fetch = vi.fn(async (url: string) => response(url.endsWith('/memory') ? { items: [candidate], truncated: false } : edition));
  const { props } = setup(fetch); render(<TranslationMemoryPanel {...props} />); expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '查找完全匹配翻译记忆' })); await screen.findByText('Accepted translation');
  expect(screen.getByText(/两个译本的风格说明不同/)).toBeTruthy(); fireEvent.click(screen.getByRole('button', { name: '采用此记忆为待审草稿' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  const [, init] = fetch.mock.calls[1] as unknown as [string, RequestInit];
  expect(JSON.parse(String(init.body))).toEqual({ expected_version: 4, source_edition_id: 'origin', source_segment_id: 'source-segment', preview_digest: 'a'.repeat(64) });
});
it('blocks locked alias reuse and ignores a late result while unsaved text blocks the panel', async () => {
  let finish: (response: Response) => void = () => {};
  const fetch = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })); const { props } = setup(fetch);
  const view = render(<TranslationMemoryPanel {...props} />); fireEvent.click(screen.getByRole('button', { name: '查找完全匹配翻译记忆' }));
  view.rerender(<TranslationMemoryPanel {...props} blocked />); finish(response({ items: [{ ...candidate, can_adopt: false, issues: [{ code: 'LOCKED_TERM_VARIANT', expected: 'LockedName' }] }], truncated: false }));
  await waitFor(() => expect(screen.queryByText('Accepted translation')).toBeNull()); expect(props.perform).not.toHaveBeenCalled();
});
it('recovers only a selected historical translation as a new draft', async () => {
  const fetch = vi.fn(async (url: string) => response(url.endsWith('/history') ? { items: [{ version: 2, target_text: 'Old text', status: 'ACCEPTED', preview_digest: 'b'.repeat(64) }], truncated: false } : edition));
  const { props } = setup(fetch); render(<TranslationMemoryPanel {...props} />); fireEvent.click(screen.getByRole('button', { name: '读取本段译文历史' }));
  await screen.findByText('Old text'); fireEvent.click(screen.getByRole('button', { name: '恢复 v2 为新草稿' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  const [, init] = fetch.mock.calls[1] as unknown as [string, RequestInit]; expect(JSON.parse(String(init.body))).toEqual({ expected_version: 4, restore_version: 2, preview_digest: 'b'.repeat(64) });
});
it('clears the prior private memory candidate before a recheck that is denied', async () => {
  let denied = false;
  const fetch = vi.fn(async () => new Response(JSON.stringify(denied ? { detail: { code: 'FORBIDDEN' } } : { items: [candidate], truncated: false }), { status: denied ? 403 : 200 }));
  const { props } = setup(fetch); render(<TranslationMemoryPanel {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '查找完全匹配翻译记忆' })); await screen.findByText('Accepted translation');
  denied = true; fireEvent.click(screen.getByRole('button', { name: '查找完全匹配翻译记忆' }));
  await screen.findByText(/FORBIDDEN/); expect(screen.queryByText('Accepted translation')).toBeNull();
});
