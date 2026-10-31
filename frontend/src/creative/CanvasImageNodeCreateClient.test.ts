// Software HTTP contract replay only; real File recovery is tested separately.
import { describe, expect, it, vi } from 'vitest';
import { createStudioGraphClient } from './studioGraphClient';
import { emptyImageNodeDefinition, type CanvasImageNodeCreateIntent } from './canvasImageNodeCreateIntent';

const intent: CanvasImageNodeCreateIntent = { contract: 'studio-canvas-image-node-create/1', project_id: 'project',
  scope: { mode: 'local', novel_id: 'project' }, incarnation: 'file:12345678-1234-4234-8234-123456789abc',
  node_id: 'node-one', title: 'One explicit node', position: { x: 24, y: 48 }, prompt_digest: 'a'.repeat(64) };
function canvas() { return { project_id: 'project', scope: intent.scope, id: 'saved-empty-view', version: 1,
  definition: emptyImageNodeDefinition(intent), definition_digest: 'b'.repeat(64), reference_states: [],
  created_at: '2026-10-24', updated_at: '2026-10-24', execution_authority: false, binary_content_verified: false,
  capacity: { history_used: 0, record_bytes: 1024 } }; }
function envelope() { return { contract: 'studio-canvas-image-node-resolve/1', request_id: 'creation-request',
  image_node_intent: structuredClone(intent), incarnation: intent.incarnation, canvas: canvas() }; }
function rig(value: unknown) { const json = vi.fn().mockResolvedValue(value);
  return { json, client: createStudioGraphClient('project', {}, { json }).canvasViews }; }
describe('original Canvas create intent and explicit resolver HTTP contract', () => {
  it('sends the exact tracked create and explicit read body with the captured abort signal', async () => {
    const e = rig(canvas()), signal = new AbortController().signal;
    await e.client.create(emptyImageNodeDefinition(intent), 'creation-request', intent, signal);
    expect(e.json).toHaveBeenLastCalledWith('/api/projects/project/studio/canvas-views', 'POST', {
      request_id: 'creation-request', expected_version: 0, definition: emptyImageNodeDefinition(intent), image_node_intent: intent }, signal);
    e.json.mockResolvedValue(envelope()); expect((await e.client.resolveImageNodeCreate('creation-request', intent, signal)).id).toBe('saved-empty-view');
    expect(e.json).toHaveBeenLastCalledWith('/api/projects/project/studio/canvas-views/resolve-create', 'POST', {
      request_id: 'creation-request', expected_incarnation: intent.incarnation, image_node_intent: intent }, signal);
    expect(e.json).toHaveBeenCalledTimes(2);
  });
  it.each(['scope', 'history', 'extra'])('rejects mismatched %s recovery without another request', async kind => {
    const reply = envelope();
    if (kind === 'scope') reply.canvas.scope = { mode: 'local', novel_id: 'other-project' };
    if (kind === 'history') reply.canvas.capacity.history_used = 1;
    if (kind === 'extra') Object.assign(reply, { latest_canvas: canvas() });
    const e = rig(reply); await expect(e.client.resolveImageNodeCreate('creation-request', intent)).rejects.toThrow();
    expect(e.json).toHaveBeenCalledTimes(1);
  });
  it('rejects foreign intent before transport and propagates not-found without fallback creation', async () => {
    const e = rig(envelope());
    await expect(e.client.resolveImageNodeCreate('creation-request', { ...intent, project_id: 'other', scope: { mode: 'local', novel_id: 'other' } })).rejects.toThrow();
    expect(e.json).not.toHaveBeenCalled();
    e.json.mockRejectedValue(new Error('CREATIVE_CANVAS_CREATE_NOT_FOUND'));
    await expect(e.client.resolveImageNodeCreate('creation-request', intent)).rejects.toThrow('CREATIVE_CANVAS_CREATE_NOT_FOUND');
    expect(e.json).toHaveBeenCalledTimes(1);
  });
});
