import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import capture from './__fixtures__/comicHandoffHttp.json';
import { checkedHandoffRequest, handoffCanonical, handoffHash, studioComicHandoffClient } from './studioComicHandoffClient';
import { clearComicHandoffAttempt, readComicHandoffAttempt, saveComicHandoffAttempt } from './comicHandoffAttempt';

const copy = <T,>(v: T): T => structuredClone(v);
const context = { sessionToken: 'test-only-host-token' };
const api = () => studioComicHandoffClient(capture.original_timeline.novel_id, context);
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
const fetcher = vi.fn();
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('fetch', fetcher); fetcher.mockReset(); });
afterEach(() => vi.unstubAllGlobals());

it('decodes the actual 608f629b File HTTP JSON and PNGs through original bounded transport', async () => {
  fetcher.mockResolvedValueOnce(reply(capture.preview_response)).mockResolvedValueOnce(reply(capture.created));
  const client = api(), result = await client.preview(capture.request);
  expect(result.report).toEqual(capture.preview_response.preview);
  expect(await handoffHash(new Uint8Array(await result.images[1].arrayBuffer()))).toBe(result.report.pages[1].png_sha256);
  const created = await client.confirm(capture.confirm as Parameters<typeof client.confirm>[0]);
  expect(created.status).toBe('DRAFT_CREATED'); expect(created.timeline_snapshot).toEqual(capture.created.timeline_snapshot);
  expect(created.timeline!.timeline).toEqual(capture.original_timeline.timeline);
  const [url, options] = fetcher.mock.calls[1];
  expect(url).toMatch(/\/production\/comic-handoffs$/); expect(JSON.parse(options.body)).toEqual(capture.confirm);
  expect(options.headers['X-Session-Token']).toBe(context.sessionToken);
  expect(client.ownerKey).not.toContain(context.sessionToken);
});
it.each(['scope', 'actor', 'version', 'loss', 'dispatch', 'unknown', 'page-order', 'request-digest', 'preview-digest'])('rejects substituted preview %s without publishing images', async change => {
  const value = copy(capture.preview_response);
  const report = value.preview;
  if (change === 'scope') report.scope_key = '0'.repeat(64);
  else if (change === 'actor') report.actor = 'other-actor';
  else if (change === 'version') report.pages[0].source.version++;
  else if (change === 'loss') report.losses.pop();
  else if (change === 'dispatch') report.automatic_dispatch = true;
  else if (change === 'unknown') Object.assign(report, { executable: true });
  else if (change === 'page-order') report.pages.reverse();
  else if (change === 'request-digest') report.request_digest = '0'.repeat(64);
  else report.preview_digest = '0'.repeat(64);
  fetcher.mockResolvedValue(reply(value)); await expect(api().preview(capture.request)).rejects.toBeTruthy();
});
it.each(['bytes', 'index', 'encoding', 'count'])('rejects actual PNG envelope %s corruption', async change => {
  const value = copy(capture.preview_response);
  if (change === 'bytes') value.pages[0].png_base64 = value.pages[0].png_base64.replace('iVBOR', 'jVBOR');
  else if (change === 'index') value.pages[0].index = 1;
  else if (change === 'encoding') value.pages[0].png_base64 += '\n';
  else value.pages.pop();
  fetcher.mockResolvedValue(reply(value)); await expect(api().preview(capture.request)).rejects.toBeTruthy();
});
it.each(['status', 'counter', 'snapshot', 'marker-null', 'marker-contract', 'marker-id', 'clip', 'effects', 'unknown'])('rejects HTTP 200 with invalid original receipt %s', async change => {
  const value = copy(capture.created);
  if (change === 'status') value.status = 'APPROVED';
  else if (change === 'counter') value.version--;
  else if (change === 'snapshot') value.timeline_snapshot.digest = '0'.repeat(64);
  else if (change === 'marker-null') Object.assign(value.timeline, { comic_handoff_origin: null });
  else if (change === 'marker-contract') value.timeline.comic_handoff_origin.contract = 'unknown/1';
  else if (change === 'marker-id') value.timeline.comic_handoff_origin.receipt_id = 'different';
  else if (change === 'clip') value.timeline.timeline.tracks[0].clips[0].out_ms++;
  else if (change === 'effects') value.model_called = true;
  else Object.assign(value, { execute: true });
  fetcher.mockResolvedValue(reply(value));
  await expect(api().confirm(capture.confirm as Parameters<ReturnType<typeof api>['confirm']>[0])).rejects.toBeTruthy();
});
it('reads and explicitly resumes only the exact original ID and current version', async () => {
  const partial = copy(capture.created);
  Object.assign(partial, { status: 'PLANNED', version: 2, timeline_snapshot: null });
  delete (partial as Partial<typeof partial>).timeline; delete (partial as Partial<typeof partial>).timeline_state;
  Object.assign(partial.steps[1], { state: 'PENDING', asset_version: null, observed_state: 'AWAITING_EXPLICIT_RESUME' });
  fetcher.mockResolvedValueOnce(reply(partial)).mockResolvedValueOnce(reply(capture.created));
  const client = api(), confirm = capture.confirm as Parameters<typeof client.confirm>[0];
  expect((await client.status(confirm.request_id, confirm)).version).toBe(2);
  expect((await client.resume(confirm, 2)).status).toBe('DRAFT_CREATED');
  expect(fetcher.mock.calls[0][1].method).toBe('GET');
  expect(fetcher.mock.calls[1][0]).toMatch(/\/http-create\/resume$/);
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ expected_version: 2 });
});
it('rejects malformed bounded input before fetch and does not create a new ID', async () => {
  for (const value of [{ ...capture.request, width: true }, { ...capture.request, pages: capture.request.pages.slice(0, 1).concat(capture.request.pages.slice(0, 1)) },
    { ...capture.request, pages: [{ ...capture.request.pages[0], duration_ms: 1.5 }] }, { ...capture.request, source_path: 'private-path' }]) {
    expect(() => checkedHandoffRequest(value)).toThrow();
  }
  expect(() => api().status('../private')).toThrow(); expect(fetcher).not.toHaveBeenCalled();
});
it.each(['resume', 'cancel'] as const)('rejects a structurally valid HTTP 200 with the wrong %s transition', async action => {
  const result = copy(capture.created);
  if (action === 'resume') {
    Object.assign(result, { status: 'CANCELLED', version: 3, timeline_snapshot: null });
    delete (result as Partial<typeof result>).timeline; delete (result as Partial<typeof result>).timeline_state;
    Object.assign(result.steps[1], { state: 'PENDING', asset_version: null, observed_state: 'AWAITING_EXPLICIT_RESUME' });
  }
  fetcher.mockResolvedValue(reply(result)); const client = api();
  await expect(client[action](capture.confirm as Parameters<typeof client.confirm>[0], 2)).rejects.toBeTruthy();
});
it('rejects an actually oversized streamed response even with a forged small Content-Length', async () => {
  const cancel = vi.fn();
  fetcher.mockResolvedValue(new Response(new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(12 * 1024 * 1024 + 1)); }, cancel }),
    { headers: { 'Content-Type': 'application/json', 'Content-Length': '1' } }));
  await expect(api().preview(capture.request)).rejects.toMatchObject({ problem: { code: 'DOWNLOAD_TOO_LARGE' } }); expect(cancel).toHaveBeenCalled();
});
it('does not expose a failed owner response body or interpret a 404 as permission to POST', async () => {
  fetcher.mockResolvedValue(new Response('private-canary-path-and-token', { status: 404 }));
  await expect(api().status('same-request')).rejects.toMatchObject({ status: 404 });
  expect(fetcher).toHaveBeenCalledTimes(1); expect(fetcher.mock.calls[0][1].method).toBe('GET');
});
it('stores only bounded immutable confirmation, rejects overwrites, and clears only the exact ID', () => {
  const values = new Map<string, string>();
  vi.stubGlobal('sessionStorage', { getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) });
  const client = api(), confirm = capture.confirm as Parameters<typeof client.confirm>[0];
  saveComicHandoffAttempt(client.ownerKey, confirm);
  expect(readComicHandoffAttempt(client.ownerKey)).toEqual(confirm);
  expect(handoffCanonical([...values])).not.toContain(context.sessionToken);
  expect(handoffCanonical([...values])).not.toContain('png_base64');
  expect(() => saveComicHandoffAttempt(client.ownerKey, { ...confirm, request_id: 'new-nonce' })).toThrow();
  expect(() => clearComicHandoffAttempt(client.ownerKey, 'other')).toThrow();
  clearComicHandoffAttempt(client.ownerKey, confirm.request_id); expect(readComicHandoffAttempt(client.ownerKey)).toBeUndefined();
});
