import wire from './videoReferenceWire.testFixture.json';
import type { StudioAsset } from './studioClient';
import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { checkedVideoReferencePreview, checkedVideoReferenceSaved, checkedVideoReferenceWindow, type VideoReferencePreview } from './studioVideoReferenceContract';
import { studioClient } from './studioClient';
import { resealVideoPreview, videoReferencePreview, videoReferenceSaved, videoReferenceSource as source } from './studioVideoReference.testFixtures';
beforeEach(() => vi.stubGlobal('crypto', webcrypto));
afterEach(() => vi.unstubAllGlobals());
it('validates genuine RGB PNG bytes, exact source PTS and canonical preview digest without creating assets', async () => {
  const review = videoReferencePreview();
  expect(await checkedVideoReferencePreview(review, source, review)).toEqual(review);
  expect(checkedVideoReferenceSaved(videoReferenceSaved(), source, review, 0)).toEqual(videoReferenceSaved());
});
it.each([
  { in_ms: 0, out_ms: 10001, sample_count: 4 }, { in_ms: 1.5, out_ms: 1000, sample_count: 4 },
  { in_ms: 0, out_ms: 60001, sample_count: 4 }, { in_ms: 1, out_ms: 1, sample_count: 4 },
  { in_ms: 0, out_ms: 1000, sample_count: 0 }, { in_ms: 0, out_ms: 1000, sample_count: 9 },
])('refuses unbounded/noninteger inputs %j', input => expect(() => checkedVideoReferenceWindow(input)).toThrow());
it('rejects source, scope, count, timing, false semantics and altered PNG even with resealed response digest', async () => {
  const changes = [
    (v: VideoReferencePreview) => { v.source.sha256 = 'b'.repeat(64); },
    (v: VideoReferencePreview) => { v.branch_id = 'other'; },
    (v: VideoReferencePreview) => { v.frames.pop(); },
    (v: VideoReferencePreview) => { v.frames[1].requested_ms++; },
    (v: VideoReferencePreview) => { v.frames[1].time_ms.num++; },
    (v: VideoReferencePreview) => { v.frames[1].time_ms = { num: 500, den: 2 }; },
    (v: VideoReferencePreview) => { v.frames[1].pts = 0; },
    (v: VideoReferencePreview) => { v.frames[1].png_sha256 = '0'.repeat(64); },
    (v: VideoReferencePreview) => { v.frames[1].width++; },
    (v: VideoReferencePreview) => { (v as unknown as {model_called:boolean}).model_called = true; },
    (v: VideoReferencePreview) => { (v as unknown as {semantic_analysis:boolean}).semantic_analysis = true; },
    (v: VideoReferencePreview) => { v.media.duration_ms = 60001; },
    (v: VideoReferencePreview) => { v.media.frame_count = 10001; },
    (v: VideoReferencePreview) => { Object.assign(v.frames[0], { semantic_keyframe: true }); },
  ];
  for (const change of changes) { const value = videoReferencePreview(); change(value); await expect(checkedVideoReferencePreview(resealVideoPreview(value), source, videoReferencePreview())).rejects.toThrow(); }
  const wrongDigest = videoReferencePreview(); wrongDigest.preview_digest = 'f'.repeat(64);
  await expect(checkedVideoReferencePreview(wrongDigest, source, wrongDigest)).rejects.toThrow();
});
it('detaches all reviewed bytes before asynchronous hashing', async () => {
  const value = videoReferencePreview(), expected = structuredClone(value), task = checkedVideoReferencePreview(value, source, value);
  value.frames[0].content_base64 = 'bad'; value.source.version++;
  expect(await task).toEqual(expected);
});
it('rejects forged image receipts and accepts only complementary replay state', () => {
  const review = videoReferencePreview();
  for (const change of [
    (v: ReturnType<typeof videoReferenceSaved>) => { v.receipt.replayed = true; },
    (v: ReturnType<typeof videoReferenceSaved>) => { v.asset.video_reference!.pts++; },
    (v: ReturnType<typeof videoReferenceSaved>) => { v.asset.provenance!.parents[0].digest = 'b'.repeat(64); },
    (v: ReturnType<typeof videoReferenceSaved>) => { v.asset.novel_id = 'other'; },
    (v: ReturnType<typeof videoReferenceSaved>) => { v.asset.size++; },
    (v: ReturnType<typeof videoReferenceSaved>) => { Object.assign(v.asset, { provider_id: 'model-provider' }); },
  ]) { const value = videoReferenceSaved(); change(value); expect(() => checkedVideoReferenceSaved(value, source, review, 0)).toThrow(); }
  const replay = videoReferenceSaved(); replay.receipt.replayed = true; replay.receipt.asset_created = false;
  expect(checkedVideoReferenceSaved(replay, source, review, 0).receipt.replayed).toBe(true);
});
it('uses pinned preview and explicit selected-frame save requests with unchanged idempotency key', async () => {
  const review = videoReferencePreview(), saved = videoReferenceSaved();
  const fetch = vi.fn(async (url: string, _init?: RequestInit) => new Response(JSON.stringify(url.endsWith('/preview') ? review : saved), { status: 200 })); vi.stubGlobal('fetch', fetch);
  const client = studioClient('project', { sessionToken: 'test-session' });
  expect(await client.previewVideoReference(source, review)).toEqual(review);
  await client.saveVideoReference(source, review, 0, 'same-save'); await client.saveVideoReference(source, review, 0, 'same-save');
  const bodies = fetch.mock.calls.map(([, init]) => JSON.parse(String(init?.body)));
  expect(bodies[0]).toEqual({ contract: 'studio-video-reference-preview/1', source_version: 1, source_sha256: source.sha256, in_ms: 0, out_ms: 1000, sample_count: 4 });
  expect(bodies[1]).toEqual({ contract: 'studio-video-reference-asset/1', source_version: 1, source_sha256: source.sha256, in_ms: 0, out_ms: 1000, sample_count: 4,
    selected_index: 0, reviewed_preview_digest: review.preview_digest, reviewed_png_sha256: review.frames[0].png_sha256, confirm_reference: true, idempotency_key: 'same-save' });
  expect(bodies[2]).toEqual(bodies[1]); expect(fetch.mock.calls[1][1]?.headers).toMatchObject({ 'Idempotency-Key': 'same-save' });
  const invalid = structuredClone(review); invalid.frames[0].png_sha256 = '0'.repeat(64);
  await expect(client.saveVideoReference(source, invalid, 0, 'same-save')).rejects.toThrow(); expect(fetch).toHaveBeenCalledTimes(3);
  await expect(client.saveVideoReference(source, review, 0, 'x'.repeat(101))).rejects.toThrow(); expect(fetch).toHaveBeenCalledTimes(3);
  const abort = new AbortController(); abort.abort(); await expect(client.saveVideoReference(source, review, 0, 'same-save', abort.signal)).rejects.toThrow(); expect(fetch).toHaveBeenCalledTimes(3);
});

it('accepts the genuine File-owner native FFmpeg preview and original Asset save wire fixture', async () => {
  const source = wire.source as StudioAsset, review = wire.review as VideoReferencePreview;
  expect(await checkedVideoReferencePreview(review, source, review)).toEqual(review);
  expect(checkedVideoReferenceSaved(wire.result, source, review, wire.result.receipt.selected_index)).toEqual(wire.result);
});
