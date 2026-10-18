// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { Blob as NativeBlob } from 'node:buffer';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { comicLayoutsClient, type ComicBook, type ComicPublicationPreflight } from './comicLayoutsClient';

const book: ComicBook = { id: 'book/id', version: 7, stale: false, title: 'Book', chapters: [] };
const report: ComicPublicationPreflight = { book_version: 7, reading_direction: 'RTL', pages: [{ id: 'page2', version: 8, review_digest: 'a'.repeat(64) }, { id: 'page1', version: 5, review_digest: 'b'.repeat(64) }], publication_digest: 'c'.repeat(64), page_count: 2, losses: [] };
const bytes = new TextEncoder().encode('CBZ fixture bytes');
let sha = '';
beforeEach(async () => { vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NativeBlob); sha = Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join(''); });
afterEach(() => vi.unstubAllGlobals());
const headers = () => ({ 'Content-Type': 'application/vnd.comicbook+zip', 'X-Comic-Publication-Digest': report.publication_digest, 'X-Content-SHA256': sha });
const scope = { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'branch' };
const api = () => comicLayoutsClient(experimentalClient('novel', { sessionToken: 'trusted', scope }));

it('preserves the captured novel, session and branch for both preflight and exact export pins', async () => {
  const context = { sessionToken: 'trusted', scope: { ...scope } };
  const client = comicLayoutsClient(experimentalClient('novel/id', context));
  context.sessionToken = 'new-session'; context.scope.branchId = 'other-branch';
  const fetch = vi.fn(async (url: string) => url.endsWith('/publication-preflight') ? new Response(JSON.stringify(report)) : new Response(bytes, { headers: headers() })); vi.stubGlobal('fetch', fetch);
  expect(await client.publicationPreflight(book, 'RTL')).toEqual(report);
  expect((await client.downloadCbz(book, report)).size).toBe(bytes.length);
  expect(fetch).toHaveBeenCalledTimes(2);
  const calls = vi.mocked(globalThis.fetch).mock.calls;
  expect(calls[0][0]).toBe('/api/novels/novel%2Fid/experimental/comic-layouts/books/book%2Fid/publication-preflight');
  expect(calls[1][0]).toBe('/api/novels/novel%2Fid/experimental/comic-layouts/books/book%2Fid/export-cbz');
  for (const [, init] of calls) {
    expect(init?.method).toBe('POST');
    expect(init?.headers).toMatchObject({ 'X-Session-Token': 'trusted', 'X-Branch-Id': 'branch', 'Content-Type': 'application/json', 'X-Request-ID': expect.any(String), 'Idempotency-Key': expect.any(String) });
  }
  expect(JSON.parse(String(calls[0][1]?.body))).toEqual({ expected_version: 7, reading_direction: 'RTL' });
  expect(JSON.parse(String(calls[1][1]?.body))).toEqual({ expected_version: 7, reading_direction: 'RTL', pages: report.pages, publication_digest: report.publication_digest });
});

it.each(['mime', 'publication_digest', 'missing_sha', 'bad_sha', 'corrupt_bytes', 'empty'])('rejects %s before returning download bytes', async kind => {
  const responseHeaders: Record<string, string> = headers(); let payload = bytes;
  if (kind === 'mime') responseHeaders['Content-Type'] = 'text/html';
  if (kind === 'publication_digest') responseHeaders['X-Comic-Publication-Digest'] = 'd'.repeat(64);
  if (kind === 'missing_sha') delete responseHeaders['X-Content-SHA256'];
  if (kind === 'bad_sha') responseHeaders['X-Content-SHA256'] = 'invalid';
  if (kind === 'corrupt_bytes') payload = new TextEncoder().encode('changed bytes');
  if (kind === 'empty') payload = new Uint8Array();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(payload, { headers: responseHeaders })));
  await expect(api().downloadCbz(book, report)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
});

it('does not post an export with an outdated book version', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  await expect(api().downloadCbz({ ...book, version: 8 }, report)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(fetch).not.toHaveBeenCalled();
});

it.each([401, 403, 409, 404])('preserves the established safe %s response behavior in POST blob requests', async status => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>Untrusted server content</html>', { status })));
  const client = experimentalClient('novel', { sessionToken: 'trusted' });
  await expect(client.postBlob('/comic-layouts/books/book/export-cbz', {})).rejects.toMatchObject({ problem: { status } });
  await expect(client.postBlob('/comic-layouts/books/book/export-cbz', {})).rejects.not.toThrow('Untrusted');
});
