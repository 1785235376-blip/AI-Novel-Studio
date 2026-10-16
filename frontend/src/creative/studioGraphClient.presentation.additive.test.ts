// Additive scenarios extracted from the pre-reconciliation suite.
// The protected original test file remains byte-for-byte unchanged.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { studioClient } from './studioClient';
import type { StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';

const projectId = 'project / one', graphId = 'graph / one';

const sha = 'a'.repeat(64), timestamp = '2026-10-09T00:00:00Z';
const context = (): CollaborationContext => ({ sessionToken: 'captured-session', actor: { id: 'author', displayName: 'Author', workspaceId: 'workspace' },
  scope: { workspaceId: 'workspace', projectId, storylineId: 'storyline', branchId: 'captured-branch' } });
const owner = () => ({ project_id: projectId, scope: { mode: 'collaboration' as const, novel_id: projectId, workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'captured-branch' } });
const definition = (): StudioGraphDefinition => ({ schema_version: 1, title: 'Local draft',
  nodes: [
    { id: 'source', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: 'Author source' } },
    { id: 'draft', definition_id: 'draft_prepare', definition_version: 1, enabled: true, position: { x: 250, y: 0 }, parameters: {} },
    { id: 'review', definition_id: 'human_review', definition_version: 1, enabled: true, position: { x: 500, y: 0 }, parameters: {} },
  ], edges: [
    { id: 'source_draft', source_node_id: 'source', source_port: 'text', target_node_id: 'draft', target_port: 'text' },
    { id: 'draft_review', source_node_id: 'draft', source_port: 'draft', target_node_id: 'review', target_port: 'draft' },
  ], viewport: { x: 0, y: 0, zoom: 1 } });
const graph = (): StudioGraphRecord => ({ ...owner(), id: graphId, version: 3, definition: definition(), definition_digest: sha, execution_digest: sha,
  created_at: timestamp, updated_at: timestamp, can_edit: true, reference_states: [] });

const reply = (value: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => value });
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => { fetchMock = vi.fn().mockResolvedValue(reply(graph())); vi.stubGlobal('fetch', fetchMock); useLocalHostSession.setState({ token: '', actorId: '' }); });
afterEach(() => { vi.unstubAllGlobals(); useLocalHostSession.setState({ token: '', actorId: '' }); });

describe('scoped graph transport', () => {
  it('accepts exact optional original capacity metadata and leaves legacy unknown', async () => {
    const client = studioClient(projectId, context()).graphs;
    expect(await client.get(graphId)).not.toHaveProperty('capacity');
    const original = { ...graph(), capacity: { history_used: 2, history_limit: 20, record_bytes: 12345, record_limit_bytes: 2000000 } };
    fetchMock.mockResolvedValue(reply(original)); expect((await client.get(graphId)).capacity).toEqual(original.capacity);
  });
  it.each([{ history_used: -1 }, { history_used: 21 }, { history_limit: 80 }, { record_bytes: 2000001 }, { record_limit_bytes: 3000000 }, { unexpected: true }])('rejects malformed original capacity %j', patch => {
    fetchMock.mockResolvedValue(reply({ ...graph(), capacity: { history_used: 2, history_limit: 20, record_bytes: 12345, record_limit_bytes: 2000000, ...patch } }));
    return expect(studioClient(projectId, context()).graphs.get(graphId)).rejects.toThrow();
  });
  it.each([1, 2, 3, 4, 5] as const)('roundtrips optional presentation through original transport schema %s', async schema_version => {
    const original = graph(); original.definition = { ...definition(), schema_version, nodes: [], edges: [] };
    fetchMock.mockResolvedValue(reply(original));
    const client = studioClient(projectId, context()).graphs;
    expect((await client.get(graphId)).definition).toEqual(original.definition);
    expect((await client.get(graphId)).definition).not.toHaveProperty('presentation');
    original.definition.presentation = { comment: '🎬'.repeat(2000), view: { show_grid: false, snap: true, grid_step: 32, show_minimap: false } };
    fetchMock.mockResolvedValue(reply(original));
    expect((await client.get(graphId)).definition).toEqual(original.definition);
    expect((await client.save(graphId, { expected_version: 3, definition: original.definition })).definition).toEqual(original.definition);
    expect(JSON.parse(fetchMock.mock.calls.at(-1)![1].body).definition).toEqual(original.definition);
  });
  it.each([1, 2, 3, 4, 5] as const)('roundtrips 128 display notes in schema %s independently of DAG', async schema_version => {
    const original = graph(); original.definition = { ...definition(), schema_version, nodes: [], edges: [],
      presentation: { notes: Array.from({ length: 128 }, (_, i) => ({ id: `n${i}`, text: `Scene ${i} 🎬 <b>plain</b>`, position: { x: i * 300, y: 0 } })) } };
    fetchMock.mockResolvedValue(reply(original));
    const client = studioClient(projectId, context()).graphs;
    expect((await client.get(graphId)).definition).toEqual(original.definition);
    await client.save(graphId, { expected_version: 3, definition: original.definition });
    expect(JSON.parse(fetchMock.mock.calls.at(-1)![1].body).definition).toEqual(original.definition);
  });
  it.each([1, 2, 3, 4, 5] as const)('roundtrips 1024 concise Chinese display notes through original save/get in schema %s', async schema_version => {
    const original = graph(); original.definition = { ...definition(), schema_version, nodes: [], edges: [],
      presentation: { notes: Array.from({ length: 1024 }, (_, i) => ({ id: `note_${i + 1}`, text: `雨夜·镜头${String(i + 1).padStart(4, '0')}`, position: { x: (i % 40) * 320, y: Math.floor(i / 40) * 220 } })) } };
    fetchMock.mockResolvedValue(reply(original)); const client = studioClient(projectId, context()).graphs;
    expect((await client.get(graphId)).definition).toEqual(original.definition);
    await client.save(graphId, { expected_version: 3, definition: original.definition });
    expect(JSON.parse(fetchMock.mock.calls.at(-1)![1].body).definition).toEqual(original.definition);
  });
  it.each([null, [], [{}], ...['n\n', 'n\r'].map(id => ({ id, text: '', position: { x: 0, y: 0 } })).map(note => [note]), [{ id: 'n', text: '🎬'.repeat(257), position: { x: 0, y: 0 } }],
    [{ id: 'n', text: '', position: { x: 100001, y: 0 } }],
    [{ id: 'n', text: '', position: { x: 0, y: 0 }, ports: [] }],
    Array.from({ length: 1025 }, (_, i) => ({ id: `n${i}`, text: '', position: { x: 0, y: 0 } })),
    Array.from({ length: 47 }, (_, i) => ({ id: `n${i}`, text: 'a'.repeat(256), position: { x: 0, y: 0 } })),
    [{ id: 'n', text: '', position: { x: 0, y: 0 } }, { id: 'n', text: '', position: { x: 0, y: 0 } }]])('rejects malformed display notes %j', async notes => {
    const original = graph();
    fetchMock.mockResolvedValue(reply({ ...original, definition: { ...original.definition, presentation: { notes } } }));
    await expect(studioClient(projectId, context()).graphs.get(graphId)).rejects.toThrow();
  });
  it.each([null, {}, { show_grid: 1, snap: false, grid_step: 24, show_minimap: true },
    { show_grid: true, snap: false, grid_step: 48, show_minimap: true },
    { show_grid: true, snap: false, grid_step: NaN, show_minimap: true },
    { show_grid: true, snap: false, grid_step: Infinity, show_minimap: true },
    { show_grid: true, snap: false, grid_step: '２４', show_minimap: true },
    { show_grid: true, snap: false, grid_step: 24, show_minimap: true, execute: true }])('rejects invalid view preferences %j', async view => {
    const value = graph();
    fetchMock.mockResolvedValue(reply({ ...value, definition: { ...value.definition, presentation: { view } } }));
    await expect(studioClient(projectId, context()).graphs.get(graphId)).rejects.toBeInstanceOf(ApiError);
  });
  it.each([null, {}, { comment: 1 }, { comment: 'x'.repeat(2001) }, { comment: '🎬'.repeat(2001) }, { comment: 'x', groups: [] }])('rejects malformed annotation from transport: %j', async presentation => {
    const value = graph();
    fetchMock.mockResolvedValue(reply({ ...value, definition: { ...value.definition, presentation } }));
    await expect(studioClient(projectId, context()).graphs.get(graphId)).rejects.toBeInstanceOf(ApiError);
  });

  it.each([1, 2, 3, 4, 5] as const)('roundtrips groups and exact annotations in schema %s', async schema_version => {
    const value = graph(); value.definition = { ...definition(), schema_version, nodes: [definition().nodes[0]], edges: [],
      presentation: { comment: '  🎬\n', groups: [{ id: 'g', name: '🎬'.repeat(80), node_ids: ['source'] }] } };
    fetchMock.mockResolvedValue(reply(value));
    const client = studioClient(projectId, context()).graphs;
    expect((await client.get(graphId)).definition).toEqual(value.definition);
    expect((await client.save(graphId, { expected_version: 3, definition: value.definition })).definition).toEqual(value.definition);
    expect(JSON.parse(fetchMock.mock.calls.at(-1)![1].body).definition).toEqual(value.definition);
  });
  it.each([1, 2, 3, 4, 5] as const)('roundtrips two-level presentation only in schema %s', async schema_version => {
    const value = graph(); value.definition = { ...definition(), schema_version, nodes: [definition().nodes[0], { ...definition().nodes[0], id: 'draft' }], edges: [],
      presentation: { groups: [{ id: 'root', name: 'Root', node_ids: ['source'] }, { id: 'child', name: 'Child', node_ids: ['draft'], parent_id: 'root' }] } };
    fetchMock.mockResolvedValue(reply(value));
    expect((await studioClient(projectId, context()).graphs.get(graphId)).definition).toEqual(value.definition);
  });
  it.each(['missing', 'g', null, 1])('rejects invalid parent %j', async parent_id => {
    const value = graph();
    fetchMock.mockResolvedValue(reply({ ...value, definition: { ...value.definition,
      presentation: { groups: [{ id: 'g', name: 'Group', node_ids: ['source'], parent_id }] } } }));
    await expect(studioClient(projectId, context()).graphs.get(graphId)).rejects.toBeInstanceOf(ApiError);
  });
  it('rejects cyclic parent links from transport', async () => {
    const value = graph();
    fetchMock.mockResolvedValue(reply({ ...value, definition: { ...value.definition,
      presentation: { groups: [{ id: 'g', name: 'Group', node_ids: ['source'], parent_id: 'h' },
        { id: 'h', name: 'Other', node_ids: ['draft'], parent_id: 'g' }] } } }));
    await expect(studioClient(projectId, context()).graphs.get(graphId)).rejects.toBeInstanceOf(ApiError);
  });
  it.each([null, [], {}, [null],
    [{ id: 'g', name: '', node_ids: ['source'] }], [{ id: 'g', name: ' ', node_ids: ['source'] }],
    [{ id: 'g', name: '🎬'.repeat(81), node_ids: ['source'] }], [{ id: '1g', name: 'Name', node_ids: ['source'] }],
    [{ id: 'g', name: 'Name', node_ids: [] }], [{ id: 'g', name: 'Name', node_ids: ['missing'] }],
    [{ id: 'g', name: 'Name', node_ids: ['source', 'source'] }],
    [{ id: 'g', name: 'Name', node_ids: ['source'], collapsed: true }],
    [{ id: 'g', name: 'Name', node_ids: ['source'] }, { id: 'other', name: 'Other', node_ids: ['source'] }],
    [{ id: 'g', name: 'Name', node_ids: ['source'] }, { id: 'g', name: 'Other', node_ids: ['draft'] }],
    Array.from({ length: 25 }, () => ({ id: 'g', name: 'Name', node_ids: ['source'] })),
  ])('rejects invalid groups in original transport: %j', async groups => {
    const value = graph();
    fetchMock.mockResolvedValue(reply({ ...value, definition: { ...value.definition, presentation: { groups } } }));
    await expect(studioClient(projectId, context()).graphs.get(graphId)).rejects.toBeInstanceOf(ApiError);
  });
});
