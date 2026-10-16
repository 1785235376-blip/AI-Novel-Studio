// @vitest-environment node
import { createHash } from 'node:crypto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { creativeClient } from './client';
import { newDocument, type CreativeDocument } from './types';
const source = { ...newDocument('SCREENPLAY'), id: 'doc / 1', version: 4 } as CreativeDocument;
const bytes = new TextEncoder().encode('Title: 源剧本\n\nEXT. PORT - NIGHT\n!Original action\n');
const hash = createHash('sha256').update(bytes).digest('hex');
function response(patch: Record<string, string> = {}, content: Uint8Array = bytes) { return new Response(Uint8Array.from(content).buffer, { headers: { 'Content-Type':'text/x-fountain; charset=utf-8', 'X-Creative-Document-Version':'4', 'X-Creative-Document-Digest':'a'.repeat(64), 'X-Content-SHA256':hash, ...patch } }); }
afterEach(() => vi.unstubAllGlobals());
describe('authenticated screenplay bytes and receipts', () => {
  it('uses the captured identity and verifies actual bytes before exposing a Blob', async () => {
    const fetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => response()); vi.stubGlobal('fetch', fetch);
    const client = creativeClient('project / 1', { sessionToken:'captured', scope:{workspaceId:'w', projectId:'p', storylineId:'s', branchId:'branch'} });
    const result = await client.screenplayExport(source, 'fountain');
    expect(fetch.mock.calls[0][0]).toContain('/documents/doc%20%2F%201/screenplay-export?format=fountain&expected_version=4');
    expect(fetch.mock.calls[0][1]?.headers).toMatchObject({ 'X-Session-Token':'captured','X-Branch-Id':'branch' });
    expect(fetch.mock.calls[0][1]?.headers).not.toHaveProperty('Idempotency-Key');
    expect(await result.blob.text()).toBe(new TextDecoder().decode(bytes)); expect(result.sha256).toBe(hash);
  });
  it.each<Record<string, string>>([{ 'X-Creative-Document-Version':'5' },{ 'X-Creative-Document-Digest':'bad' },{ 'X-Content-SHA256':'0'.repeat(64) },{ 'Content-Type':'text/html' },{ 'Content-Length':'8000001' }])('rejects mismatched receipt %j', async patch => {
    vi.stubGlobal('fetch', vi.fn(async () => response(patch))); await expect(creativeClient('n',{sessionToken:'s'}).screenplayExport(source,'fountain')).rejects.toMatchObject({problem:{code:'CREATIVE_EXPORT_RECEIPT_INVALID'}});
  });
  it('rejects corrupted bytes even with a syntactically valid receipt', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({},new TextEncoder().encode('modified')))); await expect(creativeClient('n',{sessionToken:'s'}).screenplayExport(source,'fountain')).rejects.toMatchObject({problem:{code:'CREATIVE_EXPORT_RECEIPT_INVALID'}});
  });
});
