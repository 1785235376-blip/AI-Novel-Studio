// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResearchHistoricalInspector } from './ResearchHistoricalInspector';
import { experimentalClient } from './api';
import type { Source } from './researchLibraryClient';
const source: Source = { id: 'source', version: 2, status: 'ACTIVE', title: 'Source', author: '', source: '', source_version: '', usage_notes: '', access: 'PRIVATE', origin: 'LOCAL_IMPORT', format: 'TXT', filename: 's.txt', accessed_at: '', extraction_status: 'TEXT_EXTRACTED', paragraph_count: 1, warnings: [] };
const revisions = [{ ...source, version: 1 }];
const ref = { source_id: 'source', source_version: 1, paragraph: 1, quote_sha256: 'a'.repeat(64) };
const result = { historical_citation: ref, current_version: 2, text: '<script>bad()</script> [link](https://example.org) 🌊', page: null, historical_only: true, not_understood: false, usable_as_current_evidence: false };
const reply = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(read: () => Promise<Response> = async () => reply(result)) {
  const fetch = vi.fn(read); vi.stubGlobal('fetch', fetch);
  const client = experimentalClient('n', { sessionToken: 'owner' });
  const view = render(<ResearchHistoricalInspector client={client} source={source} revisions={revisions} />);
  return { fetch, client, view };
}
function select() {
  fireEvent.change(screen.getByLabelText('核对历史版本'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('原引用 SHA-256 摘要'), { target: { value: ref.quote_sha256 } });
}
function submit() { fireEvent.click(screen.getByRole('button', { name: '只读核对历史位置' })); }
it('fetches only explicitly selected exact location by GET and renders plain historical text', async () => {
  const { fetch } = setup(); expect(fetch).not.toHaveBeenCalled(); select(); expect(fetch).not.toHaveBeenCalled(); submit();
  const region = await screen.findByRole('region', { name: '历史纯文本' });
  expect(region.textContent).toContain(result.text); expect(region.querySelector('script,a,img')).toBeNull();
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toContain(`/history/1/inspect?expected_current_version=2&paragraph=1&quote_sha256=${ref.quote_sha256}`);
  expect(init.method).toBe('GET'); expect(init.body).toBeUndefined();
});
it.each([401, 403, 404, 409, 500])('clears evidence on a fresh denied or failed inspection (%s)', async status => {
  let calls = 0; setup(async () => ++calls === 1 ? reply(result) : reply({}, status)); select(); submit();
  await screen.findByRole('region', { name: '历史纯文本' }); submit();
  await screen.findByText(/历史位置不可核对/); expect(screen.queryByRole('region', { name: '历史纯文本' })).toBeNull();
});
it.each(['hash', 'version', 'source', 'flags', 'oversized'])('rejects mismatched response %s', async kind => {
  const value = structuredClone(result);
  if (kind === 'hash') value.historical_citation.quote_sha256 = 'b'.repeat(64);
  if (kind === 'version') value.current_version = 3;
  if (kind === 'source') value.historical_citation.source_id = 'foreign';
  if (kind === 'flags') value.usable_as_current_evidence = true;
  if (kind === 'oversized') value.text = 'x'.repeat(8001);
  setup(async () => reply(value)); select(); submit(); await screen.findByText(/历史位置不可核对/);
  expect(screen.queryByRole('region', { name: '历史纯文本' })).toBeNull();
});
it.each(['selection', 'client', 'source', 'cancel'])('fences delayed response across %s ABA', async kind => {
  let resolve!: (value: Response) => void;
  const { view, client } = setup(() => new Promise(done => { resolve = done; })); select(); submit();
  if (kind === 'selection') {
    fireEvent.change(screen.getByLabelText('原引用段落编号（页面引用填 0）'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('原引用段落编号（页面引用填 0）'), { target: { value: '1' } });
  } else if (kind === 'client') {
    view.rerender(<ResearchHistoricalInspector client={experimentalClient('other', { sessionToken: 'other-owner' })} source={source} revisions={revisions} />);
    view.rerender(<ResearchHistoricalInspector client={client} source={source} revisions={revisions} />);
  } else if (kind === 'source') {
    view.rerender(<ResearchHistoricalInspector client={client} source={{ ...source, id: 'other' }} revisions={revisions} />);
    view.rerender(<ResearchHistoricalInspector client={client} source={source} revisions={revisions} />);
  } else fireEvent.click(screen.getByRole('button', { name: '取消历史核对' }));
  resolve(reply(result));
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
  expect(screen.queryByRole('region', { name: '历史纯文本' })).toBeNull();
});
it('represents unread pages without fabricated text or parsing', async () => {
  setup(async () => reply({ ...result, historical_citation: { ...ref, paragraph: 0, page: 4 }, page: 4, text: '', not_understood: true })); select();
  fireEvent.change(screen.getByLabelText('原引用段落编号（页面引用填 0）'), { target: { value: '0' } });
  fireEvent.change(screen.getByLabelText('原引用页码'), { target: { value: '4' } }); submit();
  await screen.findByText('仅保存页面引用；没有提取文字或页面理解证明。');
});

// Mounted owner integration: switching source closes the inspector and fences old work.
import { ResearchLibraryPanel } from './ResearchLibraryPanel';
it('mounts only for the selected active history owner and discards pending selection ABA', async () => {
  let resolve!: (value: Response) => void;
  const current = { ...source, paragraphs: [] };
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.includes('/inspect?')) return new Promise<Response>(done => { resolve = done; });
    if (url.endsWith('/sources')) return reply({ items: [current, { ...current, id: 'other', title: 'Other' }] });
    if (url.endsWith('/sources/source')) return reply(current);
    if (url.endsWith('/sources/other')) return reply({ ...current, id: 'other', title: 'Other' });
    if (url.endsWith('/history')) return reply({ items: revisions, current_version: 2 });
    return reply({ items: [] });
  });
  vi.stubGlobal('fetch', fetch);
  render(<ResearchLibraryPanel client={experimentalClient('n', { sessionToken: 'owner' })} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 Source' }));
  fireEvent.click(await screen.findByRole('button', { name: '核对来源历史版本' }));
  await screen.findByRole('region', { name: '历史原文只读核对' }); select(); submit();
  fireEvent.click(screen.getByRole('button', { name: '打开来源 Other' }));
  await waitFor(() => expect(screen.queryByRole('region', { name: '历史原文只读核对' })).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: '打开来源 Source' }));
  fireEvent.click(await screen.findByRole('button', { name: '核对来源历史版本' }));
  await screen.findByRole('region', { name: '历史原文只读核对' }); resolve(reply(result));
  await waitFor(() => expect(screen.queryByRole('region', { name: '历史纯文本' })).toBeNull());
  expect(screen.getByText('已选择 0 段引用。')).toBeTruthy();
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});


it('clears displayed history when the available revision authority changes', async () => {
  const { view, client } = setup(); select(); submit();
  await screen.findByRole('region', { name: '历史纯文本' });
  view.rerender(<ResearchHistoricalInspector client={client} source={source} revisions={[]} />);
  expect(screen.queryByRole('region', { name: '历史纯文本' })).toBeNull();
});
