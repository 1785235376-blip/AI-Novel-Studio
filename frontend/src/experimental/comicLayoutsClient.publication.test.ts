// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { Blob as NativeBlob } from 'node:buffer';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { comicLayoutsClient, type ComicBook, type ComicPdfPublicationPreflight, type ComicPublicationPreflight } from './comicLayoutsClient';

const book: ComicBook = { id: 'book/id', version: 7, stale: false, title: 'Book', chapters: [] };
const report: ComicPublicationPreflight = { book_version: 7, reading_direction: 'RTL', pages: [{ id: 'page2', version: 8, review_digest: 'a'.repeat(64) }, { id: 'page1', version: 5, review_digest: 'b'.repeat(64) }], publication_digest: 'c'.repeat(64), page_count: 2, losses: [] };
const pdfReport: ComicPdfPublicationPreflight = { ...report, format: 'comic-pdf-raster-v1', dpi: 144, page_dimensions: [{ width_pixels: 800, height_pixels: 1120, width_points: 400, height_points: 560 }, { width_pixels: 1000, height_pixels: 1200, width_points: 500, height_points: 600 }] };
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

it('pins PDF format-specific requests to the captured session, branch, explicit DPI and saved page order', async () => {
  const context = { sessionToken: 'pdf-session', scope: { ...scope } };
  const client = comicLayoutsClient(experimentalClient('novel/id', context));
  context.sessionToken = 'changed'; context.scope.branchId = 'changed';
  const fetch = vi.fn(async (url: string) => url.endsWith('/pdf-publication-preflight') ? new Response(JSON.stringify(pdfReport)) : new Response(bytes, { headers: { ...headers(), 'Content-Type': 'application/pdf' } }));
  vi.stubGlobal('fetch', fetch);
  expect(await client.pdfPublicationPreflight(book, 'RTL', 144)).toEqual(pdfReport);
  expect((await client.downloadPdf(book, pdfReport)).size).toBe(bytes.length);
  const calls = vi.mocked(globalThis.fetch).mock.calls;
  expect(calls.map(([url]) => url)).toEqual(['/api/novels/novel%2Fid/experimental/comic-layouts/books/book%2Fid/pdf-publication-preflight', '/api/novels/novel%2Fid/experimental/comic-layouts/books/book%2Fid/export-pdf']);
  for (const [, init] of calls) expect(init?.headers).toMatchObject({ 'X-Session-Token': 'pdf-session', 'X-Branch-Id': 'branch', 'Content-Type': 'application/json', 'X-Request-ID': expect.any(String), 'Idempotency-Key': expect.any(String) });
  expect(JSON.parse(String(calls[0][1]?.body))).toEqual({ expected_version: 7, reading_direction: 'RTL', dpi: 144 });
  expect(JSON.parse(String(calls[1][1]?.body))).toEqual({ expected_version: 7, reading_direction: 'RTL', dpi: 144, pages: pdfReport.pages, publication_digest: pdfReport.publication_digest });
});

it.each(['mime', 'cbz_mime', 'publication_digest', 'missing_digest', 'missing_sha', 'bad_sha', 'corrupt_bytes', 'empty'])('rejects PDF %s before returning any download bytes', async kind => {
  const responseHeaders: Record<string, string> = { ...headers(), 'Content-Type': 'application/pdf' }; let payload = bytes;
  if (kind === 'mime') responseHeaders['Content-Type'] = 'text/html';
  if (kind === 'cbz_mime') responseHeaders['Content-Type'] = 'application/vnd.comicbook+zip';
  if (kind === 'publication_digest') responseHeaders['X-Comic-Publication-Digest'] = 'd'.repeat(64);
  if (kind === 'missing_digest') delete responseHeaders['X-Comic-Publication-Digest'];
  if (kind === 'missing_sha') delete responseHeaders['X-Content-SHA256'];
  if (kind === 'bad_sha') responseHeaders['X-Content-SHA256'] = 'invalid';
  if (kind === 'corrupt_bytes') payload = new TextEncoder().encode('changed bytes');
  if (kind === 'empty') payload = new Uint8Array();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(payload, { headers: responseHeaders })));
  await expect(api().downloadPdf(book, pdfReport)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
});

it.each([undefined, null, true, '144', 35, 601, 144.5, NaN, Infinity])('rejects invalid PDF DPI %s locally without a request', async dpi => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  expect(() => api().pdfPublicationPreflight(book, 'RTL', dpi as number)).toThrow(/出版检查或文件校验/);
  await expect(api().downloadPdf(book, { ...pdfReport, dpi: dpi as number })).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(fetch).not.toHaveBeenCalled();
});

it.each([36, 600])('accepts the explicit PDF DPI boundary %s', async dpi => {
  const fetch = vi.fn(async () => new Response(JSON.stringify({ ...pdfReport, dpi }))); vi.stubGlobal('fetch', fetch);
  await api().pdfPublicationPreflight(book, 'LTR', dpi);
  expect(JSON.parse(String(vi.mocked(globalThis.fetch).mock.calls[0][1]?.body))).toEqual({ expected_version: 7, reading_direction: 'LTR', dpi });
});

it('does not post a PDF export with an outdated book version or a different format', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  await expect(api().downloadPdf({ ...book, version: 8 }, pdfReport)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  await expect(api().downloadPdf(book, { ...pdfReport, format: 'cbz' } as unknown as ComicPdfPublicationPreflight)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(fetch).not.toHaveBeenCalled();
});

it.each(['CBZ', 'PDF'])('bounds %s response consumption while preserving exact request contracts', async format => {
  const arrayBuffer = vi.fn(), postBlob = vi.fn().mockResolvedValue({ blob: { type: format === 'PDF' ? 'application/pdf' : 'application/vnd.comicbook+zip', size: 67108865, arrayBuffer }, headers: new Headers(headers()) });
  const client = comicLayoutsClient({ ...experimentalClient('novel', { sessionToken: 'trusted' }), postBlob });
  await expect(format === 'PDF' ? client.downloadPdf(book, pdfReport) : client.downloadCbz(book, report)).rejects.toMatchObject({ problem: { code: 'COMIC_PUBLICATION_INVALID_RESPONSE' } });
  expect(postBlob).toHaveBeenCalledWith(expect.stringContaining(format === 'PDF' ? '/export-pdf' : '/export-cbz'), expect.anything(), { maxBytes: 67108864 }); expect(arrayBuffer).not.toHaveBeenCalled();
});
