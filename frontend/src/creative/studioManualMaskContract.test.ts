import { afterEach, describe, expect, it, vi } from 'vitest';
import { studioClient } from './studioClient';
import { checkedMaskInput, checkedMaskResult, maskSha256, type StudioMaskInput } from './studioManualMaskContract';
const sha = 'a'.repeat(64), out = 'b'.repeat(64), pixelSha = 'c'.repeat(64);
export const maskInput = (): StudioMaskInput => ({ contract: 'manual-binary-mask/1', source_version: 2, source_sha256: sha, width: 64, height: 64, bitplane_base64: btoa('\x80' + '\0'.repeat(511)), idempotency_key: 'explicit-key' });
export const maskResult = () => ({ asset: { id: 'mask', novel_id: 'p', branch_id: null, kind: 'image', media_type: 'image/png', filename: 'mask.png', size: 512, created_at: '', updated_at: '', version: 1, sha256: out,
  provenance: { id: 'mask', kind: 'image', deleted: false, origin: 'MANUAL_EDIT', version: 1, digest: out, integrity: 'VERIFIED', stale: false, generation: null, sources: [], parents: [{ id: 'source', version: 2, digest: sha, state: 'CURRENT' }], license: { label: 'UNSPECIFIED', source: '', note: '' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION' } },
  receipt: { contract: 'manual-binary-mask/1', source_asset_id: 'source', source_version: 2, source_sha256: sha, width: 64, height: 64, bitplane_sha256: pixelSha, keep_pixels: 1, remove_pixels: 4095, mask_sha256: out } });
const check = (result: unknown) => checkedMaskResult(result, 'source', maskInput(), pixelSha, 1, 'p', null);
afterEach(() => vi.unstubAllGlobals());
describe('closed manual mask contract', () => {
  it('copies exact input and computes MSB white count', () => { const input = maskInput(), parsed = checkedMaskInput(input); input.source_version = 9; expect(parsed.body.source_version).toBe(2); expect(parsed.keep).toBe(1); expect(parsed.bytes[0]).toBe(128); });
  it.each([
    { width: 63 }, { width: 1032 }, { width: 65 }, { height: Infinity }, { source_version: 0 }, { source_version: 1.5 },
    { source_sha256: 'A'.repeat(64) }, { contract: 'future' }, { idempotency_key: '' }, { idempotency_key: 'space key' }, { idempotency_key: '/unsafe' }, { idempotency_key: 'x'.repeat(121) },
    { bitplane_base64: btoa('\0'.repeat(512)) }, { bitplane_base64: btoa('\xff'.repeat(512)) }, { bitplane_base64: btoa('\x80' + '\0'.repeat(510)) },
    { bitplane_base64: maskInput().bitplane_base64 + '\n' }, { unknown: true },
  ])('rejects invalid input %j', change => expect(() => checkedMaskInput({ ...maskInput(), ...change })).toThrow());
  it('rejects inherited required input fields', () => expect(() => checkedMaskInput(Object.assign(Object.create({ contract: 'manual-binary-mask/1' }), { ...maskInput(), contract: undefined }))).toThrow());
  it('accepts complete current original-owner receipt', () => expect(check(maskResult())).toEqual(maskResult()));
  it.each(['source_asset_id', 'source_sha256', 'bitplane_sha256', 'mask_sha256'])('binds receipt %s', field => { const value = maskResult(); (value.receipt as Record<string, unknown>)[field] = 'wrong'; expect(() => check(value)).toThrow(); });
  it.each(['width', 'height', 'keep_pixels', 'remove_pixels', 'source_version'])('binds numeric receipt %s', field => { const value = maskResult(); (value.receipt as Record<string, unknown>)[field] = 99; expect(() => check(value)).toThrow(); });
  it.each(['origin', 'id', 'kind', 'digest', 'integrity', 'stale', 'deleted', 'version'])('binds durable proof %s', field => { const value = maskResult(); (value.asset.provenance as Record<string, unknown>)[field] = 'wrong'; expect(() => check(value)).toThrow(); });
  it.each(['id', 'version', 'digest', 'state'])('binds parent %s', field => { const value = maskResult(); (value.asset.provenance.parents[0] as Record<string, unknown>)[field] = 'wrong'; expect(() => check(value)).toThrow(); });
  it('rejects inherited Asset identity, extra receipt and foreign scope', () => {
    const inherited = maskResult(); const { id, ...fields } = inherited.asset; inherited.asset = Object.assign(Object.create({ id }), fields); expect(() => check(inherited)).toThrow();
    expect(() => check({ ...maskResult(), receipt: { ...maskResult().receipt, provider: 'extra' } })).toThrow();
    const foreign = maskResult(); foreign.asset.novel_id = 'other'; expect(() => check(foreign)).toThrow();
    expect(() => checkedMaskResult(maskResult(), 'source', maskInput(), pixelSha, 1, 'p', 'other')).toThrow();
  });
  it('permits a later mutable metadata version with the same durable parent', () => { const value = maskResult(); value.asset.version = value.asset.provenance.version = 3; expect(check(value).asset.version).toBe(3); });
  it('posts exact body/key through original captured authority and decodes actual wire', async () => {
    const value = maskResult(); value.receipt.bitplane_sha256 = await maskSha256(checkedMaskInput(maskInput()).bytes);
    const fetcher = vi.fn(async () => ({ ok: true, status: 200, json: async () => value })); vi.stubGlobal('fetch', fetcher);
    const client = studioClient('p', { sessionToken: 'synthetic-session' }); expect(await client.createMask('source', maskInput())).toEqual(value);
    expect(fetcher.mock.calls[0]).toEqual(['/api/projects/p/studio/assets/source/mask', expect.objectContaining({ method: 'POST', body: JSON.stringify(maskInput()), headers: expect.objectContaining({ 'Idempotency-Key': 'explicit-key', 'X-Session-Token': 'synthetic-session' }) })]);
  });
  it('preserves Promise rejection and avoids transport on bad/preaborted input', async () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); const client = studioClient('p', { sessionToken: '' });
    const abort = new AbortController(); abort.abort(); await expect(client.createMask('source', maskInput(), abort.signal)).rejects.toMatchObject({ name: 'AbortError' });
    await expect(client.createMask('source', { ...maskInput(), width: 65 })).rejects.toThrow(); expect(fetcher).not.toHaveBeenCalled();
  });
  it('does not send if aborted during the asynchronous pixel hash', async () => {
    const native = crypto.subtle.digest.bind(crypto.subtle), bytes = checkedMaskInput(maskInput()).bytes;
    const digest = await native('SHA-256', new Uint8Array(bytes)); let finish!: (value: ArrayBuffer) => void;
    const held = new Promise<ArrayBuffer>(resolve => { finish = resolve; }); const spy = vi.spyOn(crypto.subtle, 'digest').mockReturnValueOnce(held);
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); const abort = new AbortController();
    const pending = studioClient('p', { sessionToken: '' }).createMask('source', maskInput(), abort.signal);
    abort.abort(); finish(digest); await expect(pending).rejects.toMatchObject({ name: 'AbortError' }); expect(fetcher).not.toHaveBeenCalled(); spy.mockRestore();
  });
  it('drops an aborted late response body without decoding or adopting its result', async () => {
    let finish!: (value: unknown) => void; const body = new Promise(resolve => { finish = resolve; });
    const fetcher = vi.fn(async () => ({ ok: true, status: 200, json: () => body })); vi.stubGlobal('fetch', fetcher);
    const abort = new AbortController(); const pending = studioClient('p', { sessionToken: '' }).createMask('source', maskInput(), abort.signal);
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1)); abort.abort(); finish(maskResult());
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  });
  it('forwards optional download cancellation without changing the route', async () => {
    const blob = new Blob(); const fetcher = vi.fn(async () => ({ ok: true, status: 200, blob: async () => blob })); vi.stubGlobal('fetch', fetcher);
    const abort = new AbortController(); expect(await studioClient('p', { sessionToken: '' }).download('source', abort.signal)).toBe(blob);
    expect(fetcher.mock.calls[0]).toEqual(['/api/projects/p/studio/assets/source/download', expect.objectContaining({ signal: abort.signal, method: 'GET' })]);
  });
});
