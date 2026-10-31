// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { Blob as NativeBlob } from 'node:buffer';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { comicLayoutsClient, type ComicBook, type ComicPageArchiveOptions, type ComicPageArchivePreflight } from './comicLayoutsClient';

const book: ComicBook = { id: 'book/id', version: 7, stale: false, title: 'Book', chapters: [] };
const lossy = (image_format: 'JPEG' | 'WEBP', quality: 60 | 80 | 95 | 100): ComicPageArchiveOptions => ({ image_format, loss_mode: 'LOSSY', quality });
const modes: ComicPageArchiveOptions[] = [60, 80, 95, 100].flatMap(quality => [lossy('JPEG', quality as 60), lossy('WEBP', quality as 60)]);
modes.push({ image_format: 'WEBP', loss_mode: 'LOSSLESS', quality: null });
const report = (options: ComicPageArchiveOptions): ComicPageArchivePreflight => ({ ...options, format: 'comic-page-archive-v1', book_version: 7, reading_direction: 'RTL', pages: [{ id: 'p2', version: 6, review_digest: 'a'.repeat(64) }, { id: 'p1', version: 4, review_digest: 'b'.repeat(64) }], publication_digest: 'c'.repeat(64), page_count: 2, losses: [], page_archive_limits: { max_total_page_pixels: 1048576, max_pages: 8, max_side_pixels: 2048, max_codec_work_bytes: 536870912, max_output_bytes: 67108864, total_page_pixels: 448000, reserved_codec_work_bytes: 131465216, reserved_output_bytes: 7909376 } });
const bytes = new TextEncoder().encode('ordered page ZIP fixture');
let sha = '';
beforeEach(async () => { vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NativeBlob); sha = Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join(''); });
afterEach(() => vi.unstubAllGlobals());
const headers = () => ({ 'Content-Type': 'application/zip', 'X-Comic-Publication-Digest': 'c'.repeat(64), 'X-Content-SHA256': sha });
const api = () => comicLayoutsClient(experimentalClient('novel', { sessionToken: 'trusted' }));

it.each(modes)('pins $image_format $loss_mode $quality, page order and captured collaboration scope in both requests', async options => {
  const context = { sessionToken: 'trusted', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'branch' } };
  const client = comicLayoutsClient(experimentalClient('novel/id', context));
  context.sessionToken = 'new-session'; context.scope.branchId = 'new-branch';
  const receipt = report(options);
  const fetch = vi.fn(async (url: string) => url.endsWith('/page-archive-preflight') ? new Response(JSON.stringify(receipt)) : new Response(bytes, { headers: headers() })); vi.stubGlobal('fetch', fetch);
  expect(await client.pageArchivePreflight(book, 'RTL', options)).toEqual(receipt);
  expect((await client.downloadPageArchive(book, receipt)).size).toBe(bytes.length);
  const calls = vi.mocked(globalThis.fetch).mock.calls;
  expect(calls.map(([url]) => url)).toEqual(['/api/novels/novel%2Fid/experimental/comic-layouts/books/book%2Fid/page-archive-preflight', '/api/novels/novel%2Fid/experimental/comic-layouts/books/book%2Fid/export-page-archive']);
  for (const [, init] of calls) expect(init?.headers).toMatchObject({ 'X-Session-Token': 'trusted', 'X-Branch-Id': 'branch', 'Content-Type': 'application/json', 'X-Request-ID': expect.any(String), 'Idempotency-Key': expect.any(String) });
  expect(JSON.parse(String(calls[0][1]?.body))).toEqual({ expected_version: 7, reading_direction: 'RTL', ...options });
  expect(JSON.parse(String(calls[1][1]?.body))).toEqual({ expected_version: 7, reading_direction: 'RTL', ...options, pages: receipt.pages, publication_digest: receipt.publication_digest });
});

it.each(['mime', 'cbz_mime', 'pdf_mime', 'publication_digest', 'missing_digest', 'missing_sha', 'bad_sha', 'corrupt_bytes', 'empty'])('rejects archive %s before returning bytes', async kind => {
  const responseHeaders: Record<string, string> = headers(); let payload = bytes;
  if (kind === 'mime') responseHeaders['Content-Type'] = 'text/html';
  if (kind === 'cbz_mime') responseHeaders['Content-Type'] = 'application/vnd.comicbook+zip';
  if (kind === 'pdf_mime') responseHeaders['Content-Type'] = 'application/pdf';
  if (kind === 'publication_digest') responseHeaders['X-Comic-Publication-Digest'] = 'd'.repeat(64);
  if (kind === 'missing_digest') delete responseHeaders['X-Comic-Publication-Digest'];
  if (kind === 'missing_sha') delete responseHeaders['X-Content-SHA256'];
  if (kind === 'bad_sha') responseHeaders['X-Content-SHA256'] = 'invalid';
  if (kind === 'corrupt_bytes') payload = new TextEncoder().encode('changed bytes');
  if (kind === 'empty') payload = new Uint8Array();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(payload, { headers: responseHeaders })));
  await expect(api().downloadPageArchive(book, report(lossy('JPEG', 100)))).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
});

const invalidOptions = [
  ...[undefined, null, true, '80', 0, 59, 61, 81, 96, 101, 80.5, NaN, Infinity].map(quality => ({ image_format: 'JPEG', loss_mode: 'LOSSY', quality })),
  { image_format: 'JPEG', loss_mode: 'LOSSLESS', quality: null },
  { image_format: 'WEBP', loss_mode: 'LOSSLESS', quality: 100 },
  { image_format: 'WEBP', loss_mode: 'LOSSLESS', quality: undefined },
  { image_format: 'PNG', loss_mode: 'LOSSY', quality: 80 },
  { image_format: 'WEBP', loss_mode: 'AUTO', quality: 80 },
];
it.each(invalidOptions)('rejects invalid archive options $image_format/$loss_mode/$quality locally', async options => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  expect(() => api().pageArchivePreflight(book, 'RTL', options as ComicPageArchiveOptions)).toThrow(/出版检查或文件校验/);
  await expect(api().downloadPageArchive(book, { ...report(lossy('JPEG', 80)), ...options } as ComicPageArchivePreflight)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(fetch).not.toHaveBeenCalled();
});

it('rejects changed book versions and receipt formats before archive POST', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  await expect(api().downloadPageArchive({ ...book, version: 8 }, report(lossy('JPEG', 80)))).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  await expect(api().downloadPageArchive(book, { ...report(lossy('JPEG', 80)), format: 'comic-pdf-raster-v1' } as unknown as ComicPageArchivePreflight)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(fetch).not.toHaveBeenCalled();
});

it('rejects an oversized Blob from an alternate adapter before arrayBuffer or digest work', async () => {
  const arrayBuffer = vi.fn(); const client = experimentalClient('novel', { sessionToken: 'trusted' });
  const postBlob = vi.fn().mockResolvedValue({ blob: { type: 'application/zip', size: 67108865, arrayBuffer }, headers: new Headers(headers()) });
  await expect(comicLayoutsClient({ ...client, postBlob }).downloadPageArchive(book, report(lossy('JPEG', 80)))).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(postBlob).toHaveBeenCalledWith(expect.stringContaining('/export-page-archive'), expect.anything(), { maxBytes: 67108864 }); expect(arrayBuffer).not.toHaveBeenCalled();
});
