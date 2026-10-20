import { createHash } from 'node:crypto';
import { afterEach, expect, it, vi } from 'vitest';
import { chapterWireId } from './chapterIds';
import { interopClient } from './client';

const scope = { workspace_id: 'w', project_id: 'p', storyline_id: 's', branch_id: 'b' };
const context = { sessionToken: 'host-session', scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'b' } };
const native = 'p:~b00000000-0000-0000-0000-000000000001';
const expected = 'chapter-' + createHash('sha256').update(JSON.stringify(['studio-chapter-v1', 'w', 'p', 's', 'b', native])).digest('hex');
afterEach(() => vi.unstubAllGlobals());

it('uses the exact Python-compatible canonical scope tuple without truncation or native ID disclosure', async () => {
  expect(await chapterWireId(scope, native)).toBe(expected);
  expect(expected).toHaveLength(72);
  for (const id of ['p:1', 'legacy-chapter_1', 'x'.repeat(128)]) expect(await chapterWireId(scope, id)).toBe(id);
  for (const id of ['x'.repeat(129), '~'.repeat(2000), '稿件😀', 'a\n', '../chapter']) {
    const result = await chapterWireId(scope, id);
    expect(result).toMatch(/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/);
    expect(result).not.toContain(id);
    expect(result).toHaveLength(72);
  }
  for (const key of Object.keys(scope)) expect(await chapterWireId({ ...scope, [key]: 'other' }, native)).not.toBe(expected);
  await expect(chapterWireId(undefined, native)).rejects.toThrow('CHAPTER_SCOPE_REQUIRED');
});

it('projects native connect and preview IDs while preserving selection consent and protocol-safe source choices', async () => {
  const calls: { url: string; body: Record<string, unknown>; init: RequestInit }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, body: JSON.parse(init.body as string), init });
    return new Response('{}', { status: 200 });
  }));
  const client = interopClient(context);
  await client.connect({ request_id: 'connect', endpoint: 'http://127.0.0.1:8052', project_id: 'p', scope, module: 'NOVEL', surface: 'editor', chapter_id: native });
  await client.preview({ request_id: 'preview', session_id: 'session', chapter_id: native, expected_chapter_version: 7,
    content_kind: 'SELECTION', selection_start: 1, selection_end: 9, context_ids: [expected, 'p:1'], metadata_fields: [] });
  expect(calls[0].body.chapter_id).toBe(expected);
  expect(calls[1].body).toEqual({ request_id: 'preview', session_id: 'session', chapter_id: expected, expected_chapter_version: 7,
    content_kind: 'SELECTION', selection_start: 1, selection_end: 9, context_ids: [expected, 'p:1'], metadata_fields: [] });
  expect(JSON.stringify(calls)).not.toContain(native);
  expect(calls.every(call => call.url.startsWith('/api/local-interop/'))).toBe(true);
  expect(calls[0].init.headers).toMatchObject({ 'X-Session-Token': 'host-session', 'X-Branch-Id': 'b' });
  expect(calls.some(call => call.body.confirmed)).toBe(false);
});

it('captures scope immutably and does not reinterpret already-valid peer handoff labels', async () => {
  const mutable = structuredClone(context);
  const calls: Record<string, any>[] = [];
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init: RequestInit) => {
    calls.push(JSON.parse(init.body as string));
    return new Response('{}', { status: 200 });
  }));
  const client = interopClient(mutable);
  mutable.scope.branchId = 'different';
  await client.preview({ request_id: 'preview', session_id: 'session', chapter_id: native, content_kind: 'NONE', metadata_fields: [] });
  expect(calls[0].chapter_id).toBe(expected);
  const target = { protocol_name: 'PoemSeed Local Interop' as const, protocol_version: '1.0' as const,
    action: 'OPEN_CHAPTER' as const, target_product_id: 'poemseed.creative.studio', chapter_id: expected, source_version: 'source' };
  await client.handoff('session', target, 'handoff');
  expect(calls[1].handoff).toEqual(target);
  expect(calls[1].explicit_click).toBe(true);
});
