import { Buffer } from 'node:buffer';
import { createHash, webcrypto } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StudioAsset } from './studioClient';
import { checkedStoryboardReceipt } from './studioStoryboardContract';
import { newDocument, newScene, newShot, type CreativeDocument } from './types';
import {
  STORYBOARD_IMAGE_BYTES, STORYBOARD_IMAGE_READ_TIMEOUT_MS, loadStoryboardImage, readStoryboardImageReceipt,
  renderStoryboardImage, serializeStoryboardImage, verifyStoryboardImageDocument,
  type StoryboardImageAccess,
} from './storyboardImagePreview';

// The PNG bytes and raster admission are real. Bitmap decode and canvas encoding
// below are explicit browser-API mocks; these unit tests are not visual acceptance.
const PNG = Uint8Array.from(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAMAAAACCAYAAACddGYaAAAAE0lEQVR4nGMUsUlpYIACJgYkAAAb3gE4TuR+ggAAAABJRU5ErkJggg==', 'base64'));
const hash = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex');
const clone = <T>(value: T): T => structuredClone(value);
const rendered = () => new Blob(['derived preview'], { type: 'image/png' });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
function fixture(bytes = PNG) {
  const scene = { ...newScene(1), id: 'scene-1' }, shot = { ...newShot(1, 'scene-1'), id: 'shot-1', frame_prompt: 'Saved approved frame' };
  const source: CreativeDocument = { ...newDocument('STORYBOARD'), id: 'saved-board', title: 'Saved board', version: 4, status: 'DRAFT',
    created_at: '2026-10-18T00:00:00Z', updated_at: '2026-10-18T00:00:00Z', actor_id: 'author',
    scenes: [scene], shots: [shot], source_documents: { director: { version: 2, digest: 'd'.repeat(64) } }, source_evidence: { director: 'saved evidence' } };
  const asset: StudioAsset = { id: 'formal-image', novel_id: 'project', branch_id: 'branch', version: 3, filename: 'original.png', kind: 'image',
    media_type: 'image/png', size: bytes.length, sha256: hash(bytes), created_at: '2026-10-18T00:00:00Z', updated_at: '2026-10-18T00:00:00Z' };
  const receipt = checkedStoryboardReceipt({ contract: 'studio-storyboard/1', document_snapshot: { id: source.id, version: source.version, digest: 'a'.repeat(64) },
    content_digest: 'b'.repeat(64), approved: true, director_sources: [{ id: 'director', version: 2, digest: 'd'.repeat(64) }], model_called: false,
    product_acceptance: 'LOCAL_REQUIRED', shots: [{ shot_id: shot.id, shot_version: 2, shot_digest: 'c'.repeat(64), shot: clone(shot),
      image_asset: { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'image' } }] }, source.id);
  const events: string[] = [];
  const get = vi.fn(async (_id: string, _signal?: AbortSignal) => { events.push('document'); return clone(source); });
  const storyboardGet = vi.fn(async (_id: string, _signal?: AbortSignal) => { events.push('receipt'); return clone(receipt); });
  const assetRead = vi.fn(async (_id: string, _signal?: AbortSignal) => { events.push('asset'); return clone(asset); });
  const original = new Blob([bytes.slice()], { type: 'image/png' });
  const download = vi.fn(async (_id: string, _maximum: number, _signal?: AbortSignal) => { events.push('download'); return original; });
  let current = true;
  const isCurrent = () => current, controller = new AbortController();
  const access: StoryboardImageAccess = {
    projectId: 'project', branchId: 'branch', document: clone(source), client: { get, storyboardGet }, studio: { asset: assetRead, downloadBounded: download },
    available: true, isCurrent, read: async <T>(work: () => Promise<T>) => work(), onDenied: vi.fn(),
  };
  return { source, asset, receipt, row: receipt.shots[0], original, events, get, storyboardGet, assetRead, download, access, controller, isCurrent,
    stale: () => { current = false; }, load: (size: 320 | 1024 = 320) => loadStoryboardImage(access, receipt, receipt.shots[0], size, isCurrent, controller.signal) };
}

let bitmap: { width: number; height: number; close: ReturnType<typeof vi.fn> };
let canvas: { width: number; height: number; getContext: ReturnType<typeof vi.fn>; toBlob: ReturnType<typeof vi.fn> };
let drawImage: ReturnType<typeof vi.fn>, createElement: ReturnType<typeof vi.fn>, decode: ReturnType<typeof vi.fn>;
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto);
  bitmap = { width: 3, height: 2, close: vi.fn() };
  decode = vi.fn().mockResolvedValue(bitmap); vi.stubGlobal('createImageBitmap', decode);
  drawImage = vi.fn();
  canvas = { width: 0, height: 0, getContext: vi.fn(() => ({ drawImage })), toBlob: vi.fn((callback: BlobCallback) => callback(rendered())) };
  createElement = vi.fn(() => canvas); vi.stubGlobal('document', { createElement });
});
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const expectReleased = () => { expect(bitmap.close).toHaveBeenCalledOnce(); expect(canvas.width).toBe(0); expect(canvas.height).toBe(0); };

describe('saved storyboard source and receipt checks', () => {
  it('uses a valid receipt and verifies the full saved source before and after its read', async () => {
    const f = fixture();
    expect(await readStoryboardImageReceipt(f.access, f.isCurrent, f.controller.signal)).toEqual(f.receipt);
    expect(f.events).toEqual(['document', 'receipt', 'document']);
    expect(f.get).toHaveBeenNthCalledWith(1, f.source.id, expect.any(AbortSignal));
    expect(f.get).toHaveBeenNthCalledWith(2, f.source.id, expect.any(AbortSignal));
    expect(f.storyboardGet).toHaveBeenCalledWith(f.source.id, expect.any(AbortSignal));
    expect(f.download).not.toHaveBeenCalled(); expect(decode).not.toHaveBeenCalled();
  });

  it.each([
    ['identity', (row: CreativeDocument) => { row.id = 'another-board'; }],
    ['version', (row: CreativeDocument) => { row.version++; }],
    ['mode', (row: CreativeDocument) => { row.mode = 'DIRECTOR'; }],
    ['archive', (row: CreativeDocument) => { row.status = 'ARCHIVED'; }],
    ['title', (row: CreativeDocument) => { row.title = 'changed'; }],
    ['scene', (row: CreativeDocument) => { row.scenes[0].action = 'changed'; }],
    ['shot', (row: CreativeDocument) => { row.shots[0].frame_prompt = 'changed'; }],
    ['source pin', (row: CreativeDocument) => { row.source_documents!.director.digest = 'e'.repeat(64); }],
    ['source evidence', (row: CreativeDocument) => { row.source_evidence = { changed: true }; }],
  ] as const)('rejects changed source %s before admitting a receipt', async (_name, change) => {
    const f = fixture(), changed = clone(f.source); change(changed); f.get.mockResolvedValue(changed);
    await expect(readStoryboardImageReceipt(f.access, f.isCurrent, f.controller.signal)).rejects.toMatchObject({ code: 'SOURCE_CHANGED' });
    expect(f.storyboardGet).not.toHaveBeenCalled(); expect(f.download).not.toHaveBeenCalled();
  });

  it.each(['version', 'shot'] as const)('rejects receipt %s drift from the saved document', async field => {
    const f = fixture(), receipt = clone(f.receipt);
    if (field === 'version') receipt.document_snapshot.version++;
    else receipt.shots[0].shot.action = 'changed';
    f.storyboardGet.mockResolvedValue(receipt);
    await expect(readStoryboardImageReceipt(f.access, f.isCurrent, f.controller.signal)).rejects.toMatchObject({ code: 'SOURCE_CHANGED' });
    expect(f.download).not.toHaveBeenCalled();
  });

  it('rejects a receipt for a different document', async () => {
    const f = fixture(), receipt = clone(f.receipt); receipt.document_snapshot.id = 'other'; f.storyboardGet.mockResolvedValue(receipt);
    await expect(readStoryboardImageReceipt(f.access, f.isCurrent, f.controller.signal)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });

  it('rejects a source archived while its receipt was being read', async () => {
    const f = fixture(); f.get.mockResolvedValueOnce(clone(f.source)).mockResolvedValueOnce({ ...clone(f.source), status: 'ARCHIVED' });
    await expect(readStoryboardImageReceipt(f.access, f.isCurrent, f.controller.signal)).rejects.toMatchObject({ code: 'SOURCE_CHANGED' });
    expect(f.get).toHaveBeenCalledTimes(2); expect(f.download).not.toHaveBeenCalled();
  });

  it.each(['epoch', 'abort'] as const)('does not begin source reads after %s invalidation', async kind => {
    const f = fixture(); if (kind === 'epoch') f.stale(); else f.controller.abort();
    await expect(verifyStoryboardImageDocument(f.access, f.isCurrent, f.controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
    expect(f.get).not.toHaveBeenCalled();
  });

  it('discards a late source read after the source epoch changes', async () => {
    const f = fixture(); f.get.mockImplementation(async () => { f.stale(); return clone(f.source); });
    await expect(readStoryboardImageReceipt(f.access, f.isCurrent, f.controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
    expect(f.storyboardGet).not.toHaveBeenCalled();
  });
});

describe('exact approved Asset and downloaded-byte checks', () => {
  it('revalidates source and exact Asset around the bounded download and emits only a derived image', async () => {
    const f = fixture(); decode.mockImplementation(async () => { f.events.push('decode'); return bitmap; });
    const result = await f.load();
    expect(f.events).toEqual(['document', 'asset', 'download', 'decode', 'asset', 'document']);
    expect(f.assetRead).toHaveBeenNthCalledWith(1, 'formal-image', expect.any(AbortSignal));
    expect(f.assetRead).toHaveBeenNthCalledWith(2, 'formal-image', expect.any(AbortSignal));
    expect(f.download).toHaveBeenCalledOnce();
    expect(f.download).toHaveBeenCalledWith('formal-image', STORYBOARD_IMAGE_BYTES, expect.any(AbortSignal));
    expect(result).not.toBe(f.original); expect(await result.text()).toBe('derived preview');
    expect(new Uint8Array(await f.original.arrayBuffer())).toEqual(PNG);
    expectReleased();
  });

  it('rejects a row differing from its admitted receipt before any read', async () => {
    const f = fixture(), row = clone(f.row); row.image_asset!.version++;
    await expect(loadStoryboardImage(f.access, f.receipt, row, 320, f.isCurrent, f.controller.signal)).rejects.toMatchObject({ code: 'SOURCE_CHANGED' });
    expect(f.get).not.toHaveBeenCalled(); expect(f.download).not.toHaveBeenCalled();
  });

  for (const phase of ['before', 'after'] as const) {
    it.each([
      ['project', { novel_id: 'other-project' }], ['branch', { branch_id: 'other-branch' }], ['unscoped branch', { branch_id: null }],
      ['identity', { id: 'other-asset' }], ['version', { version: 4 }], ['digest', { sha256: 'e'.repeat(64) }],
      ['kind', { kind: 'video' }], ['deletion', { deleted_at: '2026-10-18T00:00:01Z' }],
    ] satisfies [string, Partial<StudioAsset>][])('rejects Asset %s drift ' + phase + ' download', async (_name, patch) => {
      const f = fixture(), changed = { ...f.asset, ...patch };
      if (phase === 'before') f.assetRead.mockResolvedValue(changed);
      else f.assetRead.mockResolvedValueOnce(clone(f.asset)).mockResolvedValueOnce(changed);
      await expect(f.load()).rejects.toMatchObject({ code: 'ASSET_CHANGED' });
      expect(f.download).toHaveBeenCalledTimes(phase === 'before' ? 0 : 1);
      expect(decode).toHaveBeenCalledTimes(phase === 'before' ? 0 : 1);
      if (phase === 'after') expectReleased();
    });
  }

  it.each([{ size: STORYBOARD_IMAGE_BYTES + 1 }, { media_type: 'image/gif' }])('rejects unsupported source Asset %j before downloading', async patch => {
    const f = fixture(); f.assetRead.mockResolvedValue({ ...f.asset, ...patch });
    await expect(f.load()).rejects.toMatchObject({ code: 'UNSUPPORTED' });
    expect(f.download).not.toHaveBeenCalled(); expect(decode).not.toHaveBeenCalled();
  });

  it.each(['size', 'mime', 'digest'] as const)('rejects downloaded content %s mismatch before native decode', async mismatch => {
    const f = fixture(), bytes = PNG.slice(); bytes[bytes.length - 1] ^= 1;
    f.download.mockResolvedValue(mismatch === 'size' ? new Blob([PNG.slice(1)], { type: 'image/png' })
      : mismatch === 'mime' ? new Blob([PNG], { type: 'image/jpeg' }) : new Blob([bytes], { type: 'image/png' }));
    await expect(f.load()).rejects.toMatchObject({ code: 'INTEGRITY' });
    expect(decode).not.toHaveBeenCalled(); expect(f.assetRead).toHaveBeenCalledOnce();
  });

  it.each(['size', 'mime'] as const)('rejects metadata %s changes observed after rendering', async field => {
    const f = fixture(); f.assetRead.mockResolvedValueOnce(clone(f.asset)).mockResolvedValueOnce({ ...f.asset, ...(field === 'size' ? { size: f.asset.size + 1 } : { media_type: 'image/jpeg' }) });
    await expect(f.load()).rejects.toMatchObject({ code: 'ASSET_CHANGED' }); expectReleased();
  });

  it.each(['changed', 'archived'] as const)('discards a rendition when the saved source is %s after the download', async change => {
    const f = fixture(); f.get.mockResolvedValueOnce(clone(f.source)).mockResolvedValueOnce({ ...clone(f.source), ...(change === 'changed' ? { title: 'new title' } : { status: 'ARCHIVED' }) });
    await expect(f.load()).rejects.toMatchObject({ code: 'SOURCE_CHANGED' }); expectReleased();
  });

  it.each(['epoch', 'abort'] as const)('discards a download after %s invalidation', async kind => {
    const f = fixture(); f.download.mockImplementation(async () => { if (kind === 'epoch') f.stale(); else f.controller.abort(); return f.original; });
    await expect(f.load()).rejects.toMatchObject({ name: 'AbortError' }); expect(decode).not.toHaveBeenCalled();
  });

  it('fails closed when SHA-256 verification is unavailable', async () => {
    const f = fixture(); vi.stubGlobal('crypto', {});
    await expect(f.load()).rejects.toMatchObject({ code: 'UNSUPPORTED' }); expect(decode).not.toHaveBeenCalled();
  });

  it.each([[4097, 2], [3000, 2000]])('checks PNG pixel/side limits before native decode (%i × %i)', async (width, height) => {
    const bytes = PNG.slice(), view = new DataView(bytes.buffer); view.setUint32(16, width); view.setUint32(20, height);
    let crc = 0xffffffff;
    for (const byte of bytes.subarray(12, 29)) { crc ^= byte; for (let bit = 0; bit < 8; bit++) crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1; }
    view.setUint32(29, (crc ^ 0xffffffff) >>> 0);
    const f = fixture(bytes);
    await expect(f.load()).rejects.toMatchObject({ code: 'UNSUPPORTED' });
    expect(f.download).toHaveBeenCalledOnce(); expect(decode).not.toHaveBeenCalled(); expect(createElement).not.toHaveBeenCalled();
  });
});

describe('bounded browser rendition and resource cleanup (mocked browser APIs)', () => {
  it.each([[640, 320, 320, 320, 160], [2048, 1024, 1024, 1024, 512], [3, 2, 320, 3, 2]] as const)('fits %ix%i into %i without upscaling', async (width, height, size, expectedWidth, expectedHeight) => {
    bitmap.width = width; bitmap.height = height;
    const result = await renderStoryboardImage(new Blob([PNG]), { width, height }, size, () => true, new AbortController().signal);
    expect(result.type).toBe('image/png');
    expect(drawImage).toHaveBeenCalledWith(bitmap, 0, 0, expectedWidth, expectedHeight);
    expect(canvas.toBlob).toHaveBeenCalledWith(expect.any(Function), 'image/png'); expectReleased();
  });

  it('closes a bitmap whose decoded dimensions differ from the inspected bytes', async () => {
    await expect(renderStoryboardImage(new Blob([PNG]), { width: 4, height: 2 }, 320, () => true, new AbortController().signal)).rejects.toMatchObject({ code: 'INTEGRITY' });
    expect(bitmap.close).toHaveBeenCalledOnce(); expect(createElement).not.toHaveBeenCalled();
  });

  it.each(['epoch', 'abort'] as const)('closes a late decoded bitmap after %s invalidation', async kind => {
    const f = fixture(); decode.mockImplementation(async () => { if (kind === 'epoch') f.stale(); else f.controller.abort(); return bitmap; });
    await expect(f.load()).rejects.toMatchObject({ name: 'AbortError' });
    expect(bitmap.close).toHaveBeenCalledOnce(); expect(createElement).not.toHaveBeenCalled();
  });

  it('fails closed without native bitmap decoding', async () => {
    vi.stubGlobal('createImageBitmap', undefined);
    await expect(fixture().load()).rejects.toMatchObject({ code: 'UNSUPPORTED' }); expect(createElement).not.toHaveBeenCalled();
  });

  it.each(['context', 'draw', 'encode-null', 'encode-mime', 'encode-empty', 'encode-large'] as const)('closes bitmap and clears canvas on %s failure', async mode => {
    if (mode === 'context') canvas.getContext.mockReturnValue(null);
    if (mode === 'draw') drawImage.mockImplementation(() => { throw new Error('draw failed'); });
    if (mode === 'encode-null') canvas.toBlob.mockImplementation((callback: BlobCallback) => callback(null));
    if (mode === 'encode-mime') canvas.toBlob.mockImplementation((callback: BlobCallback) => callback(new Blob(['x'], { type: 'image/jpeg' })));
    if (mode === 'encode-empty') canvas.toBlob.mockImplementation((callback: BlobCallback) => callback(new Blob([], { type: 'image/png' })));
    if (mode === 'encode-large') canvas.toBlob.mockImplementation((callback: BlobCallback) => callback(new Blob([new Uint8Array(512 * 1024 + 1)], { type: 'image/png' })));
    await expect(fixture().load()).rejects.toBeInstanceOf(Error); expectReleased();
  });

  it('rejects an expanded rendition over 5 MiB and releases resources', async () => {
    canvas.toBlob.mockImplementation((callback: BlobCallback) => callback(new Blob([new Uint8Array(5 * 1024 * 1024 + 1)], { type: 'image/png' })));
    await expect(fixture().load(1024)).rejects.toMatchObject({ code: 'INTEGRITY' }); expectReleased();
  });

  it('closes the bitmap and clears the canvas after an encoding timeout', async () => {
    vi.useFakeTimers(); canvas.toBlob.mockImplementation(() => undefined);
    const pending = renderStoryboardImage(new Blob([PNG]), { width: 3, height: 2 }, 320, () => true, new AbortController().signal);
    const rejected = expect(pending).rejects.toMatchObject({ code: 'UNSUPPORTED' });
    await vi.advanceTimersByTimeAsync(15000); await rejected; expectReleased(); expect(vi.getTimerCount()).toBe(0);
  });

  it('closes the bitmap and clears the canvas when the epoch changes during encoding', async () => {
    const f = fixture(); canvas.toBlob.mockImplementation((callback: BlobCallback) => { f.stale(); callback(rendered()); });
    await expect(f.load()).rejects.toMatchObject({ name: 'AbortError' }); expectReleased();
  });

  it('clears its encoding timeout when toBlob throws synchronously', async () => {
    vi.useFakeTimers(); canvas.toBlob.mockImplementation(() => { throw new Error('encoding failed'); });
    await expect(renderStoryboardImage(new Blob([PNG]), { width: 3, height: 2 }, 320, () => true, new AbortController().signal)).rejects.toThrow('encoding failed');
    expectReleased(); expect(vi.getTimerCount()).toBe(0);
  });
});

describe('one serial rendering pipeline', () => {
  it('holds later decode work until an earlier stale native decode settles, then recovers', async () => {
    const late = deferred<typeof bitmap>(), first = fixture(), second = fixture();
    decode.mockImplementationOnce(() => late.promise).mockResolvedValue(bitmap);
    const firstPending = serializeStoryboardImage(() => first.load());
    const firstRejected = expect(firstPending).rejects.toMatchObject({ name: 'AbortError' });
    await vi.waitFor(() => expect(decode).toHaveBeenCalledOnce());
    first.stale();
    const secondPending = serializeStoryboardImage(() => second.load());
    await Promise.resolve(); await Promise.resolve();
    expect(decode).toHaveBeenCalledOnce(); expect(second.get).not.toHaveBeenCalled();
    late.resolve(bitmap); await firstRejected;
    expect((await secondPending).type).toBe('image/png');
    expect(decode).toHaveBeenCalledTimes(2); expect(bitmap.close).toHaveBeenCalledTimes(2);
    expect(canvas.width).toBe(0); expect(canvas.height).toBe(0);
  });

  it('never overlaps queued work and continues after a failed operation', async () => {
    const gate = deferred<void>(); let active = 0, maximum = 0;
    const work = vi.fn(async () => { active++; maximum = Math.max(maximum, active); await gate.promise; active--; throw new Error('first failed'); });
    const first = serializeStoryboardImage(work), rejected = expect(first).rejects.toThrow('first failed');
    const second = serializeStoryboardImage(async () => { active++; maximum = Math.max(maximum, active); active--; return 'second done'; });
    await Promise.resolve(); expect(work).toHaveBeenCalledOnce(); expect(active).toBe(1);
    gate.resolve(); await rejected; expect(await second).toBe('second done'); expect(maximum).toBe(1);
  });
});

describe('bounded metadata and download waits', () => {
  function stalled(kind: 'document' | 'download') {
    const f = fixture();
    const documentResult = deferred<CreativeDocument>(), blobResult = deferred<Blob>();
    if (kind === 'document') f.get.mockImplementation(() => documentResult.promise);
    else f.download.mockImplementation(() => blobResult.promise);
    return { f, requestSignal: () => kind === 'document' ? f.get.mock.calls[0]?.[1] : f.download.mock.calls[0]?.[2],
      finishLate: () => { documentResult.resolve(clone(f.source)); blobResult.resolve(f.original); } };
  }
  function watchListeners(signal: AbortSignal) {
    const added = vi.spyOn(signal, 'addEventListener'), removed = vi.spyOn(signal, 'removeEventListener');
    return () => {
      const callbacks = added.mock.calls.filter(([type]) => type === 'abort').map(([, callback]) => callback);
      expect(callbacks.length).toBeGreaterThan(0);
      expect(removed.mock.calls.filter(([type]) => type === 'abort')).toHaveLength(callbacks.length);
      for (const callback of callbacks) expect(removed).toHaveBeenCalledWith('abort', callback);
    };
  }

  it.each(['document', 'download'] as const)('aborts a stalled %s request at 30 seconds, cleans up, and ignores its late result', async kind => {
    vi.useFakeTimers();
    const { f, requestSignal, finishLate } = stalled(kind), listenersCleaned = watchListeners(f.controller.signal);
    const pending = f.load(), rejected = expect(pending).rejects.toMatchObject({ code: 'TIMEOUT' });
    let settled = false; void pending.then(() => { settled = true; }, () => { settled = true; });
    await vi.advanceTimersByTimeAsync(0);
    expect(STORYBOARD_IMAGE_READ_TIMEOUT_MS).toBe(30000);
    expect(requestSignal()).toBeInstanceOf(AbortSignal); expect(requestSignal()).not.toBe(f.controller.signal);
    expect(requestSignal()!.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(STORYBOARD_IMAGE_READ_TIMEOUT_MS - 1);
    expect(settled).toBe(false); expect(requestSignal()!.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1); await rejected;
    expect(requestSignal()!.aborted).toBe(true); expect(f.controller.signal.aborted).toBe(false);
    expect(decode).not.toHaveBeenCalled(); expect(createElement).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0); listenersCleaned();
    finishLate(); await vi.advanceTimersByTimeAsync(0);
    expect(decode).not.toHaveBeenCalled(); expect(f.assetRead).toHaveBeenCalledTimes(kind === 'document' ? 0 : 1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(['document', 'download'] as const)('parent abort immediately settles a stalled %s read and aborts the owned request', async kind => {
    vi.useFakeTimers();
    const { f, requestSignal, finishLate } = stalled(kind), listenersCleaned = watchListeners(f.controller.signal);
    const pending = f.load(), rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    await vi.advanceTimersByTimeAsync(0);
    expect(requestSignal()!.aborted).toBe(false);
    f.controller.abort('private cancellation reason');
    await rejected;
    expect(requestSignal()!.aborted).toBe(true); expect(vi.getTimerCount()).toBe(0); listenersCleaned();
    finishLate(); await vi.advanceTimersByTimeAsync(0);
    expect(decode).not.toHaveBeenCalled(); expect(createElement).not.toHaveBeenCalled();
  });

  it.each(['document', 'download'] as const)('releases the serial pipeline after a stalled %s times out', async kind => {
    vi.useFakeTimers();
    const { f, finishLate } = stalled(kind), next = vi.fn(async () => 'next task completed');
    const first = serializeStoryboardImage(() => f.load()), rejected = expect(first).rejects.toMatchObject({ code: 'TIMEOUT' });
    const second = serializeStoryboardImage(next);
    await vi.advanceTimersByTimeAsync(0); expect(next).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(STORYBOARD_IMAGE_READ_TIMEOUT_MS); await rejected;
    expect(await second).toBe('next task completed'); expect(next).toHaveBeenCalledOnce();
    finishLate(); await vi.advanceTimersByTimeAsync(0);
    expect(next).toHaveBeenCalledOnce(); expect(decode).not.toHaveBeenCalled(); expect(vi.getTimerCount()).toBe(0);
  });

  it('cleans timers and abort listeners after each successful source/receipt read', async () => {
    vi.useFakeTimers();
    const f = fixture(), listenersCleaned = watchListeners(f.controller.signal);
    expect(await readStoryboardImageReceipt(f.access, f.isCurrent, f.controller.signal)).toEqual(f.receipt);
    expect(vi.getTimerCount()).toBe(0); listenersCleaned();
    const signals = [f.get.mock.calls[0][1], f.storyboardGet.mock.calls[0][1], f.get.mock.calls[1][1]];
    expect(new Set(signals).size).toBe(3);
    for (const signal of signals) { expect(signal).toBeInstanceOf(AbortSignal); expect(signal).not.toBe(f.controller.signal); }
  });

  it.each(['receipt', 'asset'] as const)('also bounds stalled %s metadata without decoding', async kind => {
    vi.useFakeTimers(); const f = fixture();
    if (kind === 'receipt') f.storyboardGet.mockImplementation(() => new Promise(() => undefined));
    else f.assetRead.mockImplementation(() => new Promise(() => undefined));
    const pending = kind === 'receipt' ? readStoryboardImageReceipt(f.access, f.isCurrent, f.controller.signal) : f.load();
    const rejected = expect(pending).rejects.toMatchObject({ code: 'TIMEOUT' });
    await vi.advanceTimersByTimeAsync(STORYBOARD_IMAGE_READ_TIMEOUT_MS); await rejected;
    const signal = kind === 'receipt' ? f.storyboardGet.mock.calls[0][1] : f.assetRead.mock.calls[0][1];
    expect(signal!.aborted).toBe(true); expect(f.download).not.toHaveBeenCalled(); expect(decode).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('reports TIMEOUT when the underlying request rejects immediately upon owned-signal abort', async () => {
    vi.useFakeTimers(); const f = fixture();
    f.access.read = <T>(work: () => Promise<T>) => work();
    f.get.mockImplementation((_id, signal) => new Promise((_resolve, reject) => {
      signal!.addEventListener('abort', () => reject(new DOMException('native request canceled', 'AbortError')), { once: true });
    }));
    const pending = verifyStoryboardImageDocument(f.access, f.isCurrent, f.controller.signal);
    const outcome = pending.catch(reason => reason);
    await vi.advanceTimersByTimeAsync(STORYBOARD_IMAGE_READ_TIMEOUT_MS); expect(await outcome).toMatchObject({ code: 'TIMEOUT' });
    expect(f.get.mock.calls[0][1]!.aborted).toBe(true); expect(decode).not.toHaveBeenCalled(); expect(vi.getTimerCount()).toBe(0);
  });
});
