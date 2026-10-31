// @vitest-environment jsdom
/** Untrusted browser hints and declared software HTTP receipts only. */
import { createHash, webcrypto } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { canonicalImageNode, type CanvasImageNodeBinding } from './canvasImageNode';
import { canvasImageNodeQueueHintKey, clearCanvasImageNodeQueueHint, persistCanvasImageNodeQueueHint, readCanvasImageNodeQueueHint } from './canvasImageNodeQueueIntent';
import { studioProductionClient, type ProductionJob } from './studioProductionClient';

const sha = (value: string) => createHash('sha256').update(value).digest('hex');
const owner = { projectId: 'queue-hint-project', incarnation: 'file:12345678-1234-4234-8234-123456789abc', actorId: 'queue-hint-author', actorWorkspaceId: '',
  mode: 'local' as const, workspaceId: '', storylineId: '', branchId: '' };
const binding: CanvasImageNodeBinding = { contract: 'studio-canvas-image-node/1', project_id: owner.projectId, scope: { mode: 'local', novel_id: owner.projectId },
  incarnation: owner.incarnation, canvas_id: 'original-empty-view', canvas_version: 1, canvas_digest: 'a'.repeat(64), node_id: 'original-node',
  title: 'One original node', position: { x: 24, y: 48 }, prompt_digest: sha('A lighthouse') };
const digest = 'b'.repeat(64), requestId = 'the-original-queue-request';
beforeEach(() => { localStorage.clear(); vi.stubGlobal('crypto', webcrypto); });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('formal node queue recovery hint', () => {
  it('persists only owner, target and original queue identity, without prompt or credentials', () => {
    const hint = persistCanvasImageNodeQueueHint(owner, binding.node_id, requestId, digest, binding);
    expect(hint.state).toBe('present'); expect(readCanvasImageNodeQueueHint(owner, binding.node_id)).toEqual(hint);
    expect(JSON.parse(hint.raw)).toEqual({ schema_version: 1, owner, request_id: requestId, request_digest: digest, binding });
    expect(hint.raw).not.toMatch(/sessionToken|localHostToken|Bearer|provider_binding|output_candidate|APPROVED|A lighthouse/);
  });
  it.each(['actorId', 'projectId', 'incarnation'] as const)('does not import another %s recovery hint', field => {
    persistCanvasImageNodeQueueHint(owner, binding.node_id, requestId, digest, binding);
    const other = { ...owner, [field]: field === 'incarnation' ? 'file:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee' : 'other-owner' };
    expect(canvasImageNodeQueueHintKey(other, binding.node_id)).not.toBe(canvasImageNodeQueueHintKey(owner, binding.node_id));
    expect(readCanvasImageNodeQueueHint(other, binding.node_id).state).toBe('absent');
    expect(readCanvasImageNodeQueueHint(owner, 'other-node').state).toBe('absent');
  });
  it.each(['invalid-json', 'old-format', 'extra-authority', 'wrong-request-digest', 'wrong-node', 'oversized'])('keeps %s evidence blocked without overwriting it', kind => {
    const saved = persistCanvasImageNodeQueueHint(owner, binding.node_id, requestId, digest, binding), parsed = JSON.parse(saved.raw);
    if (kind === 'old-format') parsed.schema_version = 0;
    if (kind === 'extra-authority') parsed.canExecute = true;
    if (kind === 'wrong-request-digest') parsed.request_digest = 'not-a-digest';
    if (kind === 'wrong-node') parsed.binding.node_id = 'other-node';
    const raw = kind === 'invalid-json' ? '{broken' : kind === 'oversized' ? ' '.repeat(16385) : JSON.stringify(parsed);
    const key = canvasImageNodeQueueHintKey(owner, binding.node_id); localStorage.setItem(key, raw);
    expect(readCanvasImageNodeQueueHint(owner, binding.node_id).state).toBe('blocked');
    expect(() => persistCanvasImageNodeQueueHint(owner, binding.node_id, 'new-request', digest, binding)).toThrow();
    expect(localStorage.getItem(key)).toBe(raw);
  });
  it('requires exact write readback and does not erase another window replacement', () => {
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
    expect(() => persistCanvasImageNodeQueueHint(owner, binding.node_id, requestId, digest, binding)).toThrow(); set.mockRestore();
    const first = persistCanvasImageNodeQueueHint(owner, binding.node_id, requestId, digest, binding);
    const replacement = canonicalImageNode({ ...first.hint, request_id: 'other-window-request' });
    localStorage.setItem(canvasImageNodeQueueHintKey(owner, binding.node_id), replacement);
    expect(clearCanvasImageNodeQueueHint(owner, binding.node_id, first.raw)).toBe(false);
    expect(localStorage.getItem(canvasImageNodeQueueHintKey(owner, binding.node_id))).toBe(replacement);
    expect(clearCanvasImageNodeQueueHint(owner, binding.node_id, replacement)).toBe(true);
  });
  it('rejects a target from another node, project or incarnation before storage', () => {
    for (const changed of [{ ...binding, node_id: 'other-node' }, { ...binding, project_id: 'other-project', scope: { mode: 'local' as const, novel_id: 'other-project' } },
      { ...binding, incarnation: 'file:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee' }]) {
      expect(() => persistCanvasImageNodeQueueHint(owner, binding.node_id, requestId, digest, changed)).toThrow();
    }
    expect(localStorage.length).toBe(0);
  });
});

function queued(): ProductionJob {
  const command = { operation_id: 'm5.image.t2i' as const, request_id: requestId, provider_id: 'software-local-image', model_id: 'software-model',
    prompt: 'A lighthouse', parameters: { steps: 1, seed: 42 }, source_snapshots: [], allow_cloud: false, license_note: '', canvas_image_node: structuredClone(binding) };
  return { contract: 'studio-production-job/1', owner: 'image', id: 'original-queued-job', novel_id: owner.projectId, branch_id: null, version: 1, status: 'QUEUED',
    operation_id: 'm5.image.t2i', request_id: requestId, request_digest: digest, receipt_digest: null, output_candidate: null, approved_asset_version: null,
    sources: [], timeline_snapshot: null, command, provider: { provider_id: 'software-local-image', model_id: 'software-model', local: true, route_digest: 'c'.repeat(64) },
    execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: 'm5.image.t2i', adapter: 'AUTOMATIC1111_IMAGE', parameters: command.parameters,
      automatic_fallback: false, recipe_digest: 'd'.repeat(64) }, product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false,
    created_at: '2026-10-24T00:00:00Z', updated_at: '2026-10-24T00:00:00Z' };
}
describe('original production queue resolve HTTP identity', () => {
  it.each(['valid', 'request', 'digest', 'binding', 'owner'])('checks the exact request and %s returned identity without queueing', async kind => {
    const reply = queued();
    if (kind === 'request') reply.request_id = 'other-request';
    if (kind === 'digest') reply.request_digest = 'e'.repeat(64);
    if (kind === 'binding') reply.command!.canvas_image_node!.node_id = 'other-node';
    if (kind === 'owner') reply.novel_id = 'other-project';
    const fetcher = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(reply), { headers: { 'Content-Type': 'application/json' } })); vi.stubGlobal('fetch', fetcher);
    const client = studioProductionClient(owner.projectId, { sessionToken: '' }), signal = new AbortController().signal;
    const reading = client.resolveImageNodeCreate(requestId, digest, binding, signal);
    await Promise.resolve();
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toBe(`/api/projects/${owner.projectId}/studio/production/jobs/image/resolve-create`);
    const init = (fetcher.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(init.method).toBe('POST'); expect(init.signal).toBe(signal);
    expect(JSON.parse(String(init.body))).toEqual({ request_id: requestId, request_digest: digest, canvas_image_node: binding });
    if (kind === 'valid') expect((await reading).id).toBe('original-queued-job'); else await expect(reading).rejects.toThrow();
    expect(fetcher).toHaveBeenCalledOnce();
  });
});
