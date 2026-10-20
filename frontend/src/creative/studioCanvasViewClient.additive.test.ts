import { describe, expect, it, vi } from 'vitest';
import { createStudioGraphClient } from './studioGraphClient';
import { checkedCanvasDefinition, type CanvasDefinition } from './studioCanvasViewClient';
const definition: CanvasDefinition = { schema_version: 1, title: 'Media', cards: [{ id: 'Card', position: { x: 0, y: 0 }, asset: { asset_id: 'asset', version: 1, digest: 'a'.repeat(64), kind: 'image' } }], viewport: { x: 0, y: 0, zoom: 1 } };
function row() { return { project_id: 'project', scope: { mode: 'local', novel_id: 'project' }, id: 'view', version: 1, definition: structuredClone(definition), definition_digest: 'b'.repeat(64), created_at: '2026-10-18', updated_at: '2026-10-18', reference_states: [{ card_id: 'Card', state: 'CURRENT_METADATA', filename: 'test.png' }], execution_authority: false, binary_content_verified: false, capacity: { history_used: 1, record_bytes: 1000 } }; }
function setup(value: unknown) { const json = vi.fn().mockResolvedValue(value); return { json, client: createStudioGraphClient('project', {}, { json }).canvasViews }; }
describe('original captured display client', () => {
  it('reads and writes only the closed original owner paths', async () => {
    const { json, client } = setup(row());
    expect((await client.get('view')).definition).toEqual(definition);
    expect(json).toHaveBeenCalledWith('/api/projects/project/studio/canvas-views/view', 'GET', undefined, undefined);
    await client.create(definition, 'request-1');
    expect(json).toHaveBeenLastCalledWith('/api/projects/project/studio/canvas-views', 'POST', { expected_version: 0, request_id: 'request-1', definition });
    json.mockResolvedValue({ ...row(), version: 2 }); await client.save('view', 1, definition);
    expect(json).toHaveBeenLastCalledWith('/api/projects/project/studio/canvas-views/view', 'PUT', { expected_version: 1, definition });
    expect(Object.keys(client).sort()).toEqual(['create', 'get', 'history', 'list', 'restore', 'save']);
  });
  it.each(['project', 'scope', 'id', 'execution', 'binary', 'state', 'filename', 'duplicate', 'port'])('rejects wrong or executable %s response', async kind => {
    const value: any = row();
    if (kind === 'project') value.project_id = 'other';
    if (kind === 'scope') value.scope.mode = 'collaboration';
    if (kind === 'id') value.id = 'other';
    if (kind === 'execution') value.execution_authority = true;
    if (kind === 'binary') value.binary_content_verified = true;
    if (kind === 'state') value.reference_states[0].card_id = 'other';
    if (kind === 'filename') value.reference_states[0].state = 'STALE';
    if (kind === 'duplicate') value.definition.cards.push(structuredClone(value.definition.cards[0]));
    if (kind === 'port') value.definition.cards[0].ports = [];
    await expect(setup(value).client.get('view')).rejects.toThrow();
  });
  it('keeps unavailable cards masked and rejects their direct save', async () => {
    const value: any = row(); delete value.definition.cards[0].asset;
    value.reference_states = [{ card_id: 'Card', state: 'UNAVAILABLE' }];
    const { client, json } = setup(value); const current = await client.get('view');
    await expect(client.save('view', 1, current.definition)).rejects.toThrow(); expect(json).toHaveBeenCalledTimes(1);
    current.definition.cards = []; json.mockResolvedValue({ ...row(), version: 2, definition: current.definition, reference_states: [] });
    await client.save('view', 1, current.definition);
  });
  it('rejects a mismatched captured project before any transport', async () => {
    const json = vi.fn(); const client = createStudioGraphClient('project', { scope: { projectId: 'other', workspaceId: 'w', storylineId: 's', branchId: 'b' } }, { json }).canvasViews;
    await expect(client.list()).rejects.toThrow(); expect(json).not.toHaveBeenCalled();
  });
  it('checks strict finite coordinates, bounds and unique 1000 card identities', () => {
    const large = structuredClone(definition); large.cards = Array.from({ length: 1000 }, (_, i) => ({ ...structuredClone(definition.cards[0]), id: `Card_${i}` }));
    expect(checkedCanvasDefinition(large, true).cards).toHaveLength(1000);
    large.cards.push({ ...large.cards[0], id: 'Overflow' }); expect(() => checkedCanvasDefinition(large)).toThrow();
    const bad = structuredClone(definition); bad.viewport.zoom = NaN; expect(() => checkedCanvasDefinition(bad)).toThrow();
  });
  it('rejects non-advancing save receipts and snapshots input before transport', async () => {
    const { client, json } = setup(row()); const draft = structuredClone(definition);
    const saving = client.save('view', 1, draft); draft.title = 'changed';
    expect((json.mock.calls[0][2] as any).definition.title).toBe('Media');
    await expect(saving).rejects.toThrow();
  });
});
