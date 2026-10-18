import { afterEach, expect, it, vi } from 'vitest';
import { readBoundedResponseBlob } from './boundedResponseBlob';
import { experimentalClient } from './experimental/api';
import { studioTransport } from './creative/studioClient';

afterEach(() => vi.unstubAllGlobals());
function stream(chunks: Uint8Array[], headers: Record<string, string> = {}) {
  const read = vi.fn<() => Promise<ReadableStreamReadResult<Uint8Array>>>();
  chunks.forEach(value => read.mockResolvedValueOnce({ done: false, value })); read.mockResolvedValue({ done: true, value: undefined });
  const reader = { read, cancel: vi.fn().mockResolvedValue(undefined), releaseLock: vi.fn() };
  const body = { getReader: vi.fn(() => reader), cancel: vi.fn().mockResolvedValue(undefined) };
  const response = { ok: true, status: 200, type: 'basic', redirected: false, headers: new Headers({ 'Content-Type': 'application/zip', ...headers }), body, blob: vi.fn(), json: vi.fn() };
  return { response, body, reader };
}

it.each([undefined, '0', '1', '4', 'invalid', '-1'])('counts streamed bytes despite Content-Length %s and stops at the first excess chunk', async length => {
  const r = stream([new Uint8Array([1, 2]), new Uint8Array([3, 4]), new Uint8Array([5])], length === undefined ? {} : { 'Content-Length': length });
  await expect(readBoundedResponseBlob(r.response as unknown as Response, { maxBytes: 4 })).rejects.toMatchObject({ problem: { code: 'DOWNLOAD_TOO_LARGE' } });
  expect(r.reader.read).toHaveBeenCalledTimes(3); expect(r.reader.cancel).toHaveBeenCalledOnce(); expect(r.reader.releaseLock).toHaveBeenCalledOnce(); expect(r.response.blob).not.toHaveBeenCalled();
});

it('rejects a too-large length before acquiring a reader or allocating the download buffer', async () => {
  const r = stream([], { 'Content-Length': '67108865' });
  await expect(readBoundedResponseBlob(r.response as unknown as Response, { maxBytes: 67108864 })).rejects.toMatchObject({ problem: { code: 'DOWNLOAD_TOO_LARGE' } });
  expect(r.body.cancel).toHaveBeenCalledOnce(); expect(r.body.getReader).not.toHaveBeenCalled(); expect(r.response.blob).not.toHaveBeenCalled();
});

it('accepts the exact byte boundary and snapshots mutable chunk buffers', async () => {
  const bytes = new Uint8Array([1, 2]); const r = stream([]);
  r.reader.read.mockReset().mockResolvedValueOnce({ done: false, value: bytes }).mockImplementationOnce(async () => { bytes.fill(9); return { done: false, value: new Uint8Array([3, 4]) }; }).mockResolvedValue({ done: true, value: undefined });
  const blob = await readBoundedResponseBlob(r.response as unknown as Response, { maxBytes: 4 });
  expect(blob.type).toBe('application/zip'); expect([...new Uint8Array(await blob.arrayBuffer())]).toEqual([1, 2, 3, 4]); expect(r.reader.cancel).not.toHaveBeenCalled(); expect(r.reader.releaseLock).toHaveBeenCalledOnce();
});

it.each(['missing_stream', 'redirect', 'reader_error', 'read_error', 'invalid_chunk'])('fails closed on %s without unbounded fallback', async reason => {
  const r = stream([]);
  if (reason === 'missing_stream') r.response.body = null as unknown as typeof r.body;
  if (reason === 'redirect') r.response.redirected = true;
  if (reason === 'reader_error') r.body.getReader.mockImplementation(() => { throw Error('private details'); });
  if (reason === 'read_error') r.reader.read.mockRejectedValueOnce(Error('private details'));
  if (reason === 'invalid_chunk') r.reader.read.mockResolvedValueOnce({ done: false, value: 'not bytes' as unknown as Uint8Array });
  await expect(readBoundedResponseBlob(r.response as unknown as Response, { maxBytes: 4 })).rejects.toMatchObject({ problem: { code: 'DOWNLOAD_RESPONSE_INVALID' } });
  expect(r.response.blob).not.toHaveBeenCalled(); expect(r.response.json).not.toHaveBeenCalled();
});

it.each(['experimental', 'studio'])('opts %s archive POST into bounded streaming and keeps generic downloads unchanged', async route => {
  const r = stream([new Uint8Array([1, 2])]); const fetch = vi.fn().mockResolvedValue(r.response); vi.stubGlobal('fetch', fetch);
  const context = { sessionToken: 'captured', scope: { workspaceId: 'w', projectId: 'n', storylineId: 's', branchId: 'branch' } };
  const client = route === 'experimental' ? experimentalClient('n', context) : studioTransport(context);
  context.sessionToken = 'later'; context.scope.branchId = 'later';
  const download = (limit?: { maxBytes: number }) => 'postBlob' in client ? client.postBlob('/archive', { pin: 3 }, limit) : client.blobResponse('/archive', 'POST', { pin: 3 }, undefined, undefined, limit);
  const value = await download({ maxBytes: 2 }); expect(value.blob.size).toBe(2); expect(value.headers).toBe(r.response.headers);
  expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'POST', redirect: 'error', headers: { 'X-Session-Token': 'captured', 'X-Branch-Id': 'branch' } }); expect(r.response.blob).not.toHaveBeenCalled();
  const genericBlob = new Blob(['larger generic download']); r.response.blob.mockResolvedValueOnce(genericBlob); await expect(download()).resolves.toMatchObject({ blob: genericBlob });
  expect(fetch.mock.calls[1][1]).not.toHaveProperty('redirect'); expect(r.response.blob).toHaveBeenCalledOnce();
});

it.each(['experimental', 'studio'])('rejects an oversized %s archive response without reading any body bytes', async route => {
  const r = stream([], { 'Content-Length': '67108865' }); vi.stubGlobal('fetch', vi.fn().mockResolvedValue(r.response));
  const context = { sessionToken: 'trusted' };
  const promise = route === 'experimental' ? experimentalClient('n', context).postBlob('/archive', {}, { maxBytes: 67108864 }) : studioTransport(context).blobResponse('/archive', 'POST', {}, undefined, undefined, { maxBytes: 67108864 });
  await expect(promise).rejects.toMatchObject({ problem: { code: 'DOWNLOAD_TOO_LARGE' } }); expect(r.body.getReader).not.toHaveBeenCalled(); expect(r.body.cancel).toHaveBeenCalledOnce(); expect(r.response.blob).not.toHaveBeenCalled();
});

it.each(['experimental', 'studio'])('bounds %s error bodies while preserving permission-denial status', async route => {
  const r = stream([], { 'Content-Length': '999999999' }); r.response.ok = false; r.response.status = 403; vi.stubGlobal('fetch', vi.fn().mockResolvedValue(r.response));
  const context = { sessionToken: 'trusted' };
  const promise = route === 'experimental' ? experimentalClient('n', context).postBlob('/archive', {}, { maxBytes: 67108864 }) : studioTransport(context).blobResponse('/archive', 'POST', {}, undefined, undefined, { maxBytes: 67108864 });
  await expect(promise).rejects.toMatchObject({ problem: { status: 403 } }); expect(r.body.cancel).toHaveBeenCalledOnce(); expect(r.response.json).not.toHaveBeenCalled(); expect(r.response.blob).not.toHaveBeenCalled();
});
