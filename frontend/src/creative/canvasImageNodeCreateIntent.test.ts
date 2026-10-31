// @vitest-environment jsdom
/** Recovery hints are untrusted authoring metadata; HTTP responses are software projections. */
import { createHash, webcrypto } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { canonicalImageNode } from './canvasImageNode';
import { createStudioGraphClient } from './studioGraphClient';
import { canvasImageNodeCreateHintKey, checkedCanvasImageNodeCreateIntent, clearCanvasImageNodeCreateHint,
  emptyImageNodeDefinition, persistCanvasImageNodeCreateHint, readCanvasImageNodeCreateHint,
  type CanvasImageNodeCreateIntent } from './canvasImageNodeCreateIntent';

const owner = { projectId: 'hint-project', incarnation: 'file:12345678-1234-1234-1234-123456789abc', actorId: 'hint-author',
  actorWorkspaceId: '', mode: 'local' as const, workspaceId: '', storylineId: '', branchId: '' };
const intent: CanvasImageNodeCreateIntent = { contract: 'studio-canvas-image-node-create/1', project_id: owner.projectId,
  scope: { mode: 'local', novel_id: owner.projectId }, incarnation: owner.incarnation, node_id: 'node-one', title: 'One node',
  position: { x: 24, y: 48 }, prompt_digest: 'a'.repeat(64) };
beforeEach(() => { localStorage.clear(); vi.stubGlobal('crypto', webcrypto); });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('bounded image-node creation recovery hints', () => {
  it('retains only explicit intent and actor identity, never prompt bytes or credentials', () => {
    const result = persistCanvasImageNodeCreateHint(owner, intent.node_id, 'node-create-one', intent);
    expect(result.state).toBe('present'); expect(readCanvasImageNodeCreateHint(owner, intent.node_id)).toEqual(result);
    expect(JSON.parse(result.raw)).toEqual({ schema_version: 1, owner, request_id: 'node-create-one', intent });
    expect(result.raw).not.toMatch(/sessionToken|localHostToken|Bearer|output_candidate|review_state|APPROVED/);
    expect(emptyImageNodeDefinition(intent)).toEqual({ schema_version: 1, title: intent.title, cards: [], viewport: { x: 0, y: 0, zoom: 1 } });
  });
  it.each(['actorId', 'projectId', 'incarnation', 'branchId'] as const)('does not read another %s hint', field => {
    persistCanvasImageNodeCreateHint(owner, intent.node_id, 'node-create-one', intent);
    const other = field === 'branchId'
      ? { ...owner, mode: 'collaboration' as const, actorWorkspaceId: 'w', workspaceId: 'w', storylineId: 's', branchId: 'other-branch' }
      : { ...owner, [field]: field === 'incarnation' ? 'file:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee' : 'other-owner' };
    expect(canvasImageNodeCreateHintKey(other, intent.node_id)).not.toBe(canvasImageNodeCreateHintKey(owner, intent.node_id));
    expect(readCanvasImageNodeCreateHint(other, intent.node_id).state).toBe('absent');
    expect(readCanvasImageNodeCreateHint(owner, 'other-node').state).toBe('absent');
  });
  it.each(['invalid-json', 'old-schema', 'extra-secret', 'wrong-owner', 'wrong-node', 'oversized'])('keeps %s evidence blocked and unchanged', kind => {
    const original = persistCanvasImageNodeCreateHint(owner, intent.node_id, 'node-create-one', intent), parsed = JSON.parse(original.raw);
    if (kind === 'old-schema') parsed.schema_version = 0;
    if (kind === 'extra-secret') parsed.sessionToken = 'must-never-be-replayed';
    if (kind === 'wrong-owner') parsed.owner.actorId = 'other-author';
    if (kind === 'wrong-node') parsed.intent.node_id = 'other-node';
    const raw = kind === 'invalid-json' ? '{broken' : kind === 'oversized' ? ' '.repeat(8193) : JSON.stringify(parsed);
    const key = canvasImageNodeCreateHintKey(owner, intent.node_id); localStorage.setItem(key, raw);
    expect(readCanvasImageNodeCreateHint(owner, intent.node_id).state).toBe('blocked');
    expect(() => persistCanvasImageNodeCreateHint(owner, intent.node_id, 'must-not-overwrite', intent)).toThrow();
    expect(localStorage.getItem(key)).toBe(raw);
  });
  it('refuses inaccessible storage and failed write readback before any caller may dispatch', () => {
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
    expect(() => persistCanvasImageNodeCreateHint(owner, intent.node_id, 'node-create-one', intent)).toThrow();
    expect(localStorage.length).toBe(0); set.mockRestore();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage denied'); });
    expect(readCanvasImageNodeCreateHint(owner, intent.node_id).state).toBe('blocked');
    expect(() => persistCanvasImageNodeCreateHint(owner, intent.node_id, 'node-create-one', intent)).toThrow();
  });
  it('does not overwrite a pending request or delete a different tab replacement', () => {
    const first = persistCanvasImageNodeCreateHint(owner, intent.node_id, 'node-create-one', intent);
    expect(() => persistCanvasImageNodeCreateHint(owner, intent.node_id, 'node-create-two', intent)).toThrow();
    const key = canvasImageNodeCreateHintKey(owner, intent.node_id), replacement = JSON.stringify({ ...first.hint, request_id: 'node-create-two' });
    localStorage.setItem(key, replacement);
    expect(clearCanvasImageNodeCreateHint(owner, intent.node_id, first.raw)).toBe(false); expect(localStorage.getItem(key)).toBe(replacement);
    expect(clearCanvasImageNodeCreateHint(owner, intent.node_id, replacement)).toBe(true); expect(localStorage.getItem(key)).toBeNull();
  });
  it('rejects wrong scope, coercible coordinates and an extra authority marker', () => {
    for (const changed of [{ ...intent, scope: { mode: 'local', novel_id: 'foreign-project' } },
      { ...intent, position: { x: true, y: 48 } }, { ...intent, approved: true }, { ...intent, contract: 'unknown/1' }]) {
      expect(() => checkedCanvasImageNodeCreateIntent(changed)).toThrow();
    }
  });
});

describe('explicit original CanvasView resolve HTTP contract', () => {
  function envelope() {
    const definition = emptyImageNodeDefinition(intent);
    return { contract: 'studio-canvas-image-node-resolve/1', request_id: 'node-create-one', image_node_intent: intent, incarnation: owner.incarnation,
      canvas: { project_id: owner.projectId, scope: intent.scope, id: 'original-view', version: 1, definition,
        definition_digest: createHash('sha256').update(canonicalImageNode(definition)).digest('hex'), created_at: 'now', updated_at: 'now', reference_states: [],
        execution_authority: false, binary_content_verified: false, capacity: { history_used: 0, record_bytes: 1024 } } };
  }
  it.each(['valid', 'request', 'intent', 'incarnation', 'version', 'definition'])('checks exact lookup and %s response without a write retry', async kind => {
    const response = structuredClone(envelope());
    if (kind === 'request') response.request_id = 'different-request';
    if (kind === 'intent') response.image_node_intent.node_id = 'different-node';
    if (kind === 'incarnation') response.incarnation = 'file:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
    if (kind === 'version') response.canvas.version = 2;
    if (kind === 'definition') response.canvas.definition.title = 'Changed title';
    const json = vi.fn().mockResolvedValue(response), client = createStudioGraphClient(owner.projectId, {}, { json }).canvasViews;
    const resolving = client.resolveImageNodeCreate('node-create-one', intent);
    expect(json).toHaveBeenCalledOnce();
    expect(json.mock.calls[0].slice(0, 3)).toEqual([`/api/projects/${owner.projectId}/studio/canvas-views/resolve-create`, 'POST',
      { request_id: 'node-create-one', expected_incarnation: owner.incarnation, image_node_intent: intent }]);
    if (kind === 'valid') expect((await resolving).id).toBe('original-view'); else await expect(resolving).rejects.toThrow();
    expect(json).toHaveBeenCalledOnce();
  });
});
