// @vitest-environment node
import { createHash } from 'node:crypto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { creativeClient, type ScriptExportFormat } from './client';
import { newDocument, type CreativeDocument } from './types';
const source = { ...newDocument('SCREENPLAY'), id: 'saved / screenplay', version: 3 } as CreativeDocument;
// Binary receipt contract only; actual ZIP/XML is verified by the backend suite.
const bytes = Uint8Array.from([0x50, 0x4b, 3, 4, 0, 255, 128, 7]);
const hash = createHash('sha256').update(bytes).digest('hex');
function response(patch: Record<string, string> = {}, body = bytes) {
  return new Response(Uint8Array.from(body).buffer, { headers: { 'Content-Type': 'application/epub+zip',
    'X-Creative-Document-Version': '3', 'X-Creative-Document-Digest': 'a'.repeat(64), 'X-Content-SHA256': hash, ...patch } });
}
afterEach(() => vi.unstubAllGlobals());
describe('saved screenplay EPUB binary receipt', () => {
  it('uses the existing authenticated endpoint and returns exactly hashed bytes', async () => {
    const fetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => response()); vi.stubGlobal('fetch', fetch);
    const result = await creativeClient('project', { sessionToken: 'captured', scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'b' } }).screenplayExport(source, 'epub');
    expect(fetch.mock.calls[0][0]).toContain('/documents/saved%20%2F%20screenplay/screenplay-export?format=epub&expected_version=3');
    expect(fetch.mock.calls[0][1]?.headers).toMatchObject({ 'X-Session-Token': 'captured', 'X-Branch-Id': 'b' });
    expect(result.filename).toBe('creative-screenplay-v3.epub'); expect(result.blob.type).toBe('application/epub+zip');
    expect(new Uint8Array(await result.blob.arrayBuffer())).toEqual(bytes); expect(result.sha256).toBe(hash);
  });
  it.each<Record<string, string>>([{ 'Content-Type': 'text/html' }, { 'X-Creative-Document-Version': '4' }, { 'X-Content-SHA256': '0'.repeat(64) }, { 'Content-Length': '8000001' }])('rejects mismatched receipt %j', async patch => {
    vi.stubGlobal('fetch', vi.fn(async () => response(patch)));
    await expect(creativeClient('p', { sessionToken: 's' }).screenplayExport(source, 'epub')).rejects.toMatchObject({ problem: { code: 'CREATIVE_EXPORT_RECEIPT_INVALID' } });
  });
  it('does not expose corrupt binary bytes or silently enable Script EPUB', async () => {
    const fetch = vi.fn(async () => response({}, Uint8Array.from([1, 2, 3]))); vi.stubGlobal('fetch', fetch);
    const client = creativeClient('p', { sessionToken: 's' });
    await expect(client.screenplayExport(source, 'epub')).rejects.toMatchObject({ problem: { code: 'CREATIVE_EXPORT_RECEIPT_INVALID' } });
    fetch.mockClear();
    await expect(client.scriptExport({ ...source, mode: 'SCRIPT' }, 'epub' as ScriptExportFormat)).rejects.toMatchObject({ problem: { code: 'CREATIVE_EXPORT_RECEIPT_INVALID' } });
    expect(fetch).not.toHaveBeenCalled();
  });
});
