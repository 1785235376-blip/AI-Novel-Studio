// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { Blob as NativeBlob } from 'node:buffer';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { comicLayoutsClient, type ComicBook, type ComicEpubOptions, type ComicEpubPublicationPreflight, type ComicReadingDirection } from './comicLayoutsClient';

const book: ComicBook = { id: 'book/id', version: 7, stale: false, title: 'Book', chapters: [] };
const options: ComicEpubOptions = { format: 'comic-epub-fixed-raster-v1', language: 'und' };
const report = (): ComicEpubPublicationPreflight => ({ ...options, book_version: 7, reading_direction: 'RTL', pages: [{ id: 'p2', version: 6, review_digest: 'a'.repeat(64) }, { id: 'p1', version: 4, review_digest: 'b'.repeat(64) }], publication_digest: 'c'.repeat(64), page_count: 2, losses: [], page_dimensions: [{ width_pixels: 400, height_pixels: 560 }, { width_pixels: 400, height_pixels: 560 }], epub_limits: { max_metadata_bytes: 1048576, max_output_bytes: 67108864, total_page_pixels: 448000, reserved_metadata_bytes: 24576, reserved_output_bytes: 2013184 } });
const bytes = new TextEncoder().encode('EPUB fixed-layout fixture');
let sha = '';
beforeEach(async () => { vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NativeBlob); sha = Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join(''); });
afterEach(() => vi.unstubAllGlobals());
const headers = () => ({ 'Content-Type': 'application/epub+zip', 'X-Comic-Publication-Digest': 'c'.repeat(64), 'X-Content-SHA256': sha });
const api = () => comicLayoutsClient(experimentalClient('novel', { sessionToken: 'trusted' }));

it.each(['LTR', 'RTL'] as const)('pins EPUB format, explicit language, %s direction and ordered pages to the captured authority', async direction => {
  const context = { sessionToken: 'trusted', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'branch' } };
  const client = comicLayoutsClient(experimentalClient('novel/id', context));
  context.sessionToken = 'other'; context.scope.branchId = 'other';
  const receipt = { ...report(), reading_direction: direction };
  const fetch = vi.fn(async (url: string) => url.endsWith('/epub-publication-preflight') ? new Response(JSON.stringify(receipt)) : new Response(bytes, { headers: headers() })); vi.stubGlobal('fetch', fetch);
  expect(await client.epubPublicationPreflight(book, direction, options)).toEqual(receipt);
  expect((await client.downloadEpub(book, receipt)).size).toBe(bytes.length);
  const calls = vi.mocked(globalThis.fetch).mock.calls;
  expect(calls.map(([url]) => url)).toEqual(['/api/novels/novel%2Fid/experimental/comic-layouts/books/book%2Fid/epub-publication-preflight', '/api/novels/novel%2Fid/experimental/comic-layouts/books/book%2Fid/export-epub']);
  for (const [, init] of calls) expect(init?.headers).toMatchObject({ 'X-Session-Token': 'trusted', 'X-Branch-Id': 'branch', 'Content-Type': 'application/json', 'X-Request-ID': expect.any(String), 'Idempotency-Key': expect.any(String) });
  expect(JSON.parse(String(calls[0][1]?.body))).toEqual({ expected_version: 7, reading_direction: direction, ...options });
  expect(JSON.parse(String(calls[1][1]?.body))).toEqual({ expected_version: 7, reading_direction: direction, ...options, pages: receipt.pages, publication_digest: receipt.publication_digest });
  expect(calls[1][1]?.redirect).toBe('error');
});

it.each([undefined, null, true, '', 'UND', 'en', 'zh', 0, ['und']])('does not infer or coerce unsupported language %s', async language => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  expect(() => api().epubPublicationPreflight(book, 'RTL', { ...options, language } as ComicEpubOptions)).toThrow(/出版检查或文件校验/);
  await expect(api().downloadEpub(book, { ...report(), language } as ComicEpubPublicationPreflight)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(fetch).not.toHaveBeenCalled();
});

it.each([undefined, null, '', 'comic-pdf-raster-v1', 'comic-epub-fixed-raster-v2', 'EPUB', true])('rejects unsupported EPUB format %s before either POST', async format => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  expect(() => api().epubPublicationPreflight(book, 'RTL', { ...options, format } as ComicEpubOptions)).toThrow(/出版检查或文件校验/);
  await expect(api().downloadEpub(book, { ...report(), format } as ComicEpubPublicationPreflight)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(fetch).not.toHaveBeenCalled();
});

it.each([undefined, null, '', 'rtl', 'AUTO', true])('rejects unsupported EPUB direction %s before either POST', async direction => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  expect(() => api().epubPublicationPreflight(book, direction as ComicReadingDirection, options)).toThrow(/出版检查或文件校验/);
  await expect(api().downloadEpub(book, { ...report(), reading_direction: direction } as ComicEpubPublicationPreflight)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(fetch).not.toHaveBeenCalled();
});

it.each(['book_version', 'empty_pages', 'duplicate_pages', 'bad_page_version', 'bad_review_digest', 'page_count', 'publication_digest'])('rejects malformed or stale EPUB %s before export', async field => {
  const receipt = report();
  if (field === 'book_version') receipt.book_version++;
  if (field === 'empty_pages') receipt.pages = [];
  if (field === 'duplicate_pages') receipt.pages[1] = receipt.pages[0];
  if (field === 'bad_page_version') receipt.pages[0].version = 0;
  if (field === 'bad_review_digest') receipt.pages[0].review_digest = '';
  if (field === 'page_count') receipt.page_count++;
  if (field === 'publication_digest') receipt.publication_digest = '';
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  await expect(api().downloadEpub(book, receipt)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } }); expect(fetch).not.toHaveBeenCalled();
});

it.each(['mime', 'zip_mime', 'cbz_mime', 'pdf_mime', 'publication_digest', 'missing_digest', 'missing_sha', 'bad_sha', 'corrupt_bytes', 'empty'])('rejects EPUB %s before returning bytes', async field => {
  const responseHeaders: Record<string, string> = headers(); let payload = bytes;
  if (field === 'mime') responseHeaders['Content-Type'] = 'text/html';
  if (field === 'zip_mime') responseHeaders['Content-Type'] = 'application/zip';
  if (field === 'cbz_mime') responseHeaders['Content-Type'] = 'application/vnd.comicbook+zip';
  if (field === 'pdf_mime') responseHeaders['Content-Type'] = 'application/pdf';
  if (field === 'publication_digest') responseHeaders['X-Comic-Publication-Digest'] = 'd'.repeat(64);
  if (field === 'missing_digest') delete responseHeaders['X-Comic-Publication-Digest'];
  if (field === 'missing_sha') delete responseHeaders['X-Content-SHA256'];
  if (field === 'bad_sha') responseHeaders['X-Content-SHA256'] = 'invalid';
  if (field === 'corrupt_bytes') payload = new TextEncoder().encode('corrupt bytes');
  if (field === 'empty') payload = new Uint8Array();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(payload, { headers: responseHeaders })));
  await expect(api().downloadEpub(book, report())).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
});

it('rejects oversized EPUB declared bytes before consuming a stream or hashing', async () => {
  const response = new Response(bytes, { headers: { ...headers(), 'Content-Length': '67108865' } });
  const reader = vi.spyOn(response.body!, 'getReader'); const cancel = vi.spyOn(response.body!, 'cancel'); const digest = vi.spyOn(webcrypto.subtle, 'digest');
  vi.stubGlobal('fetch', vi.fn(async () => response));
  await expect(api().downloadEpub(book, report())).rejects.toMatchObject({ problem: { code: 'DOWNLOAD_TOO_LARGE' } });
  expect(reader).not.toHaveBeenCalled(); expect(cancel).toHaveBeenCalledOnce(); expect(digest).not.toHaveBeenCalled(); digest.mockRestore();
});

it('passes a 64 MiB EPUB cap to alternate adapters and rejects oversized Blob before allocation/hash work', async () => {
  const arrayBuffer = vi.fn(), client = experimentalClient('novel', { sessionToken: 'trusted' });
  const postBlob = vi.fn().mockResolvedValue({ blob: { type: 'application/epub+zip', size: 67108865, arrayBuffer }, headers: new Headers(headers()) });
  await expect(comicLayoutsClient({ ...client, postBlob }).downloadEpub(book, report())).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(postBlob).toHaveBeenCalledWith(expect.stringContaining('/export-epub'), expect.anything(), { maxBytes: 67108864 }); expect(arrayBuffer).not.toHaveBeenCalled();
});
