import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { studioClient, studioTransport } from './studioClient';

vi.mock('../packagedHost', () => ({ isPackagedDesktopHost: () => false }));

const maximum = 8 * 1024 * 1024;
const root = '/api/projects/project%20%2F%20one/studio/assets/asset%20%2F%20one/download';
const context = (): CollaborationContext => ({ sessionToken: 'captured-session', scope: { workspaceId: 'w', projectId: 'project / one', storylineId: 's', branchId: 'captured-branch' } });
const client = () => studioClient('project / one', context());

function streamReply(chunks: Uint8Array[] = [], headers: Record<string, string> = {}) {
  const read = vi.fn<() => Promise<ReadableStreamReadResult<Uint8Array>>>();
  for (const value of chunks) read.mockResolvedValueOnce({ done: false, value });
  read.mockResolvedValue({ done: true, value: undefined });
  const reader = { read, cancel: vi.fn<() => Promise<void>>().mockResolvedValue(undefined), releaseLock: vi.fn() };
  const body = { getReader: vi.fn(() => reader), cancel: vi.fn().mockResolvedValue(undefined) };
  const response = { ok: true, status: 200, type: 'basic', redirected: false, headers: new Headers(headers), body,
    blob: vi.fn(), json: vi.fn() };
  return { response, body, reader };
}

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  useLocalHostSession.setState({ token: '', actorId: '' });
});
afterEach(() => { vi.unstubAllGlobals(); useLocalHostSession.setState({ token: '', actorId: '' }); });

describe('bounded Asset download captured authority and admission', () => {
  it('uses the original encoded route and captured token and branch, passing the signal and rejecting redirects', async () => {
    const reply = streamReply([new Uint8Array([1, 2]), new Uint8Array([3])], { 'Content-Type': 'image/png', 'Content-Length': '3' });
    fetchMock.mockResolvedValue(reply.response);
    const origin = context(), captured = studioClient('project / one', origin), controller = new AbortController();
    origin.sessionToken = 'later-session'; origin.scope!.branchId = 'later-branch';
    const blob = await captured.downloadBounded('asset / one', 3, controller.signal);
    expect(blob.size).toBe(3); expect(blob.type).toBe('image/png');
    expect([...new Uint8Array(await blob.arrayBuffer())]).toEqual([1, 2, 3]);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(root, {
      method: 'GET', signal: controller.signal, redirect: 'error',
      headers: { 'Content-Type': 'application/json', 'X-Request-ID': expect.any(String), 'X-Session-Token': 'captured-session', 'X-Branch-Id': 'captured-branch' },
    });
    expect(reply.response.blob).not.toHaveBeenCalled(); expect(reply.response.json).not.toHaveBeenCalled();
    expect(reply.reader.read).toHaveBeenCalledTimes(3);
    expect(reply.reader.cancel).not.toHaveBeenCalled(); expect(reply.reader.releaseLock).toHaveBeenCalledOnce();
  });

  it('captures the local host token once for unscoped callers', async () => {
    fetchMock.mockResolvedValue(streamReply().response);
    useLocalHostSession.setState({ token: 'local-at-capture' });
    const captured = studioClient('project', { sessionToken: '' });
    useLocalHostSession.setState({ token: 'local-later' });
    await captured.downloadBounded('asset', 1);
    expect(fetchMock.mock.calls[0][1].headers).toMatchObject({ 'X-Session-Token': 'local-at-capture' });
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('X-Branch-Id');
  });

  it.each([0, -1, 0.5, NaN, Infinity, -Infinity, maximum + 1, Number.MAX_SAFE_INTEGER + 1])('rejects invalid maximum %s before fetching', async value => {
    await expect(client().downloadBounded('asset', value)).rejects.toMatchObject({ problem: { status: 400, code: 'STUDIO_DOWNLOAD_LIMIT_INVALID' } });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([1, maximum])('accepts the inclusive maximum boundary %s', async maxBytes => {
    fetchMock.mockResolvedValue(streamReply([new Uint8Array([7])]).response);
    expect((await client().downloadBounded('asset', maxBytes)).size).toBe(1);
  });

  it('rejects an excessive Content-Length hint before acquiring or reading a reader', async () => {
    const reply = streamReply([new Uint8Array([1])], { 'Content-Length': '999999999999999999999' });
    fetchMock.mockResolvedValue(reply.response);
    await expect(client().downloadBounded('asset', 3)).rejects.toMatchObject({ problem: { code: 'STUDIO_DOWNLOAD_TOO_LARGE' } });
    expect(reply.body.cancel).toHaveBeenCalledOnce(); expect(reply.body.getReader).not.toHaveBeenCalled();
    expect(reply.reader.read).not.toHaveBeenCalled(); expect(reply.response.blob).not.toHaveBeenCalled();
  });
});

describe('bounded Asset download actual streamed byte limits', () => {
  it.each([undefined, '0', '1', '3', 'invalid', '-1'])('counts actual bytes with missing or dishonest Content-Length %s', async length => {
    const reply = streamReply([new Uint8Array([1, 2]), new Uint8Array([3, 4]), new Uint8Array([5])], length === undefined ? {} : { 'Content-Length': length });
    fetchMock.mockResolvedValue(reply.response);
    await expect(client().downloadBounded('asset', 3)).rejects.toMatchObject({ problem: { code: 'STUDIO_DOWNLOAD_TOO_LARGE' } });
    expect(reply.reader.read).toHaveBeenCalledTimes(2); expect(reply.reader.cancel).toHaveBeenCalledOnce();
    expect(reply.reader.releaseLock).toHaveBeenCalledOnce(); expect(reply.response.blob).not.toHaveBeenCalled();
  });

  it('rejects an oversized first chunk without reading the remainder', async () => {
    const reply = streamReply([new Uint8Array(9), new Uint8Array([1])]);
    fetchMock.mockResolvedValue(reply.response);
    await expect(client().downloadBounded('asset', 8)).rejects.toMatchObject({ problem: { code: 'STUDIO_DOWNLOAD_TOO_LARGE' } });
    expect(reply.reader.read).toHaveBeenCalledOnce(); expect(reply.reader.cancel).toHaveBeenCalledOnce();
    expect(reply.reader.releaseLock).toHaveBeenCalledOnce();
  });

  it('accepts an exact actual-byte cap and preserves the response MIME with an ordinary stream', async () => {
    const bytes = new Uint8Array([1, 2, 3, 4]);
    const response = new Response(new ReadableStream<Uint8Array>({ start(controller) { controller.enqueue(bytes.subarray(0, 1)); controller.enqueue(bytes.subarray(1)); controller.close(); } }), { headers: { 'Content-Type': 'image/webp', 'Content-Length': '1' } });
    fetchMock.mockResolvedValue(response);
    const blob = await client().downloadBounded('asset', 4);
    expect(blob.size).toBe(4); expect(blob.type).toBe('image/webp');
    expect([...new Uint8Array(await blob.arrayBuffer())]).toEqual([...bytes]);
    expect(response.body!.locked).toBe(false);
  });

  it('copies admitted chunk views instead of retaining mutable backing buffers', async () => {
    const bytes = new Uint8Array([1, 2, 3]), reply = streamReply();
    reply.reader.read.mockReset().mockResolvedValueOnce({ done: false, value: bytes.subarray(1, 2) }).mockImplementationOnce(async () => {
      bytes[1] = 9;
      return { done: true, value: undefined };
    });
    fetchMock.mockResolvedValue(reply.response);
    const blob = await client().downloadBounded('asset', 1);
    expect([...new Uint8Array(await blob.arrayBuffer())]).toEqual([2]);
  });

  it.each([null, { cancel: vi.fn().mockResolvedValue(undefined) }])('fails closed when a stream reader is unavailable', async body => {
    const reply = streamReply();
    fetchMock.mockResolvedValue({ ...reply.response, body });
    await expect(client().downloadBounded('asset', 3)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
    expect(reply.response.blob).not.toHaveBeenCalled();
  });

  it('sanitizes read errors and releases the reader even if cancellation fails', async () => {
    const reply = streamReply();
    reply.reader.read.mockRejectedValue(new Error('private upstream URL'));
    reply.reader.cancel.mockRejectedValue(new Error('private cancellation URL'));
    fetchMock.mockResolvedValue(reply.response);
    const error = await client().downloadBounded('asset', 3).catch(error => error);
    expect(error.problem.code).toBe('STUDIO_RESPONSE_INVALID'); expect(error.message).not.toContain('private');
    expect(reply.reader.cancel).toHaveBeenCalledOnce(); expect(reply.reader.releaseLock).toHaveBeenCalledOnce();
  });

  it('sanitizes reader acquisition errors without falling back to blob()', async () => {
    const reply = streamReply();
    reply.body.getReader.mockImplementation(() => { throw new Error('private locked response'); });
    fetchMock.mockResolvedValue(reply.response);
    await expect(client().downloadBounded('asset', 3)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
    expect(reply.body.cancel).toHaveBeenCalledOnce(); expect(reply.response.blob).not.toHaveBeenCalled();
  });
});

describe('bounded Asset download cancellation and fail-closed responses', () => {
  it('rejects an already-aborted signal without fetching', async () => {
    const controller = new AbortController(); controller.abort('private cancellation reason');
    await expect(client().downloadBounded('asset', 3, controller.signal)).rejects.toMatchObject({ name: 'AbortError', message: '请求已取消。' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('cancels a response if a fetch implementation ignores an abort', async () => {
    const controller = new AbortController(), reply = streamReply();
    fetchMock.mockImplementation(async () => { controller.abort(); return reply.response; });
    await expect(client().downloadBounded('asset', 3, controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
    expect(reply.body.cancel).toHaveBeenCalledOnce(); expect(reply.body.getReader).not.toHaveBeenCalled();
  });

  it('rejects promptly and releases the lock on abort even when read and cancel never settle', async () => {
    const controller = new AbortController(), reply = streamReply();
    const added = vi.spyOn(controller.signal, 'addEventListener'), removed = vi.spyOn(controller.signal, 'removeEventListener');
    reply.reader.read.mockImplementation(() => new Promise(() => undefined));
    reply.reader.cancel.mockImplementation(() => new Promise(() => undefined));
    fetchMock.mockResolvedValue(reply.response);
    const pending = client().downloadBounded('asset', 3, controller.signal);
    const rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError', message: '请求已取消。' });
    await vi.waitFor(() => expect(reply.reader.read).toHaveBeenCalledOnce());
    controller.abort('private reason');
    await rejected;
    expect(reply.reader.cancel).toHaveBeenCalledOnce(); expect(reply.reader.releaseLock).toHaveBeenCalledOnce();
    expect(added).toHaveBeenCalledWith('abort', expect.any(Function), { once: true });
    expect(removed).toHaveBeenCalledWith('abort', added.mock.calls[0][1]);
  });

  it('does not deliver a blob when the signal aborts as the last read finishes', async () => {
    const controller = new AbortController(), reply = streamReply();
    reply.reader.read.mockImplementation(async () => { controller.abort(); return { done: true, value: undefined }; });
    fetchMock.mockResolvedValue(reply.response);
    await expect(client().downloadBounded('asset', 3, controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
    expect(reply.reader.cancel).toHaveBeenCalledOnce(); expect(reply.reader.releaseLock).toHaveBeenCalledOnce();
  });

  it.each([{ redirected: true }, { type: 'opaque' }, { type: 'opaqueredirect' }, { type: 'error' }])('rejects unsafe response %j before reading bytes', async fields => {
    const reply = streamReply();
    fetchMock.mockResolvedValue({ ...reply.response, ...fields });
    await expect(client().downloadBounded('asset', 3)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
    expect(reply.body.cancel).toHaveBeenCalledOnce(); expect(reply.body.getReader).not.toHaveBeenCalled();
    expect(reply.response.blob).not.toHaveBeenCalled(); expect(reply.response.json).not.toHaveBeenCalled();
  });

  it('cancels failed HTTP bodies without unbounded JSON or blob reads', async () => {
    const reply = streamReply();
    fetchMock.mockResolvedValue({ ...reply.response, ok: false, status: 403 });
    await expect(client().downloadBounded('asset', 3)).rejects.toMatchObject({ problem: { status: 403, code: 'STUDIO_REQUEST_FAILED' } });
    expect(reply.body.cancel).toHaveBeenCalledOnce(); expect(reply.response.json).not.toHaveBeenCalled();
    expect(reply.body.getReader).not.toHaveBeenCalled(); expect(reply.response.blob).not.toHaveBeenCalled();
  });

  it('sanitizes transport failures', async () => {
    fetchMock.mockRejectedValue(new Error('private redirect destination'));
    await expect(client().downloadBounded('asset', 3)).rejects.toMatchObject({ problem: { status: 0, code: 'STUDIO_NETWORK_FAILED' } });
  });
});

describe('generic download and blob behavior stays additive', () => {
  it('retains generic download blob reading without applying the preview cap or redirect policy', async () => {
    const blob = new Blob(['ordinary generic asset']), read = vi.fn().mockResolvedValue(blob);
    fetchMock.mockResolvedValue({ ok: true, status: 200, redirected: true, blob: read });
    expect(await client().download('asset / one')).toBe(blob);
    expect(fetchMock.mock.calls[0][0]).toBe(root); expect(fetchMock.mock.calls[0][1]).not.toHaveProperty('redirect');
    expect(read).toHaveBeenCalledOnce();
  });

  it('retains generic blob method, payload, idempotency, and server error-code handling', async () => {
    const blob = new Blob(['legacy data']), signal = new AbortController().signal;
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, blob: async () => blob });
    const transport = studioTransport(context());
    expect(await transport.blob('/existing/export', 'POST', { old: true }, signal, 'stable-key')).toBe(blob);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST', signal, body: JSON.stringify({ old: true }), headers: { 'Idempotency-Key': 'stable-key' } });
    expect(fetchMock.mock.calls[0][1]).not.toHaveProperty('redirect');
    const json = vi.fn().mockResolvedValue({ code: 'EXISTING_ERROR' });
    fetchMock.mockResolvedValueOnce({ ok: false, status: 409, json });
    await expect(transport.blob('/existing/export')).rejects.toMatchObject({ problem: { status: 409, code: 'EXISTING_ERROR' } });
    expect(json).toHaveBeenCalledOnce();
  });
});
