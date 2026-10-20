import { describe, expect, it } from 'vitest';
import type { CollaborationContext } from '../api';
import { blankGraph } from './graphDraft';
import { modelGraph } from './studioGraphModel.testFixtures';
import { graphDraftBaselineMatches, graphDraftRecoverable, readStudioGraphLocalDraft, studioGraphDraftKey,
  studioGraphDraftOwner, type StudioGraphDraftOwner, type StudioGraphLocalDraft } from './studioGraphLocalDraft';

const owner = (): StudioGraphDraftOwner => ({ projectId: 'model_project', incarnation: 'file:original', actorId: 'author',
  actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' });
const snapshot = (): StudioGraphLocalDraft => ({ schema_version: 1, owner: owner(), saved_at: '2026-10-16T00:00:00Z',
  request_id: `graph_${'1'.repeat(32)}`, base: null, definition: modelGraph().definition, uncertain: false });
const team = (): CollaborationContext => ({ sessionToken: 'never-persist-credential', actor: { id: 'author', displayName: 'Author', workspaceId: 'work' },
  scope: { workspaceId: 'work', projectId: 'model_project', storylineId: 'story', branchId: 'branch' } });

describe('incarnation-bound graph recovery envelope', () => {
  it('requires a verified actor and original project incarnation, never a public ID alone', () => {
    expect(studioGraphDraftOwner('model_project', undefined, team(), { token: '', actorId: '' })).toBeUndefined();
    expect(studioGraphDraftOwner('model_project', 'file:original', { sessionToken: '' }, { token: '', actorId: '' })).toBeUndefined();
    expect(studioGraphDraftOwner('model_project', 'file:original', { sessionToken: '' }, { token: 'private', actorId: 'author' })).toEqual(owner());
    const incomplete = team(); incomplete.actor = undefined;
    expect(studioGraphDraftOwner('model_project', 'file:original', incomplete, { token: 'private', actorId: 'host' })).toBeUndefined();
  });
  it('separates every actor, project incarnation and branch scope without persisting tokens', () => {
    const first = studioGraphDraftOwner('model_project', 'postgres:original', team(), { token: '', actorId: '' })!;
    expect(JSON.stringify(first) + studioGraphDraftKey(first)).not.toContain('never-persist-credential');
    for (const patch of [{ actorId: 'other' }, { actorWorkspaceId: 'other' }, { projectId: 'other' }, { incarnation: 'postgres:replacement' },
      { workspaceId: 'other' }, { storylineId: 'other' }, { branchId: 'other' }]) expect(studioGraphDraftKey({ ...first, ...patch })).not.toBe(studioGraphDraftKey(first));
    const cross = team(); cross.scope!.workspaceId = 'foreign';
    expect(studioGraphDraftOwner('model_project', 'file:original', cross, { token: '', actorId: '' })).toBeUndefined();
  });
  it('round-trips text nodes, typed edges, viewport and original request identity through the canonical graph decoder', () => {
    const value = snapshot(); value.definition.viewport = { x: 112, y: -48, zoom: 1.2 }; value.uncertain = true;
    expect(readStudioGraphLocalDraft(JSON.stringify(value), owner())).toEqual(value);
    expect(() => readStudioGraphLocalDraft(JSON.stringify(value), { ...owner(), incarnation: 'file:replacement' })).toThrow('GRAPH_DRAFT_INVALID');
  });
  it('rejects malformed, oversized, cyclic and foreign-owner caches instead of converting them to requests', () => {
    expect(() => readStudioGraphLocalDraft('{', owner())).toThrow();
    expect(() => readStudioGraphLocalDraft(' '.repeat(110_001), owner())).toThrow('GRAPH_DRAFT_TOO_LARGE');
    const malformed = snapshot(); malformed.base = { id: 'saved', version: 0, definition_digest: 'a'.repeat(64), execution_digest: 'a'.repeat(64) };
    expect(() => readStudioGraphLocalDraft(JSON.stringify(malformed), owner())).toThrow('GRAPH_DRAFT_BASE_INVALID');
    const wrongPort = snapshot(); wrongPort.definition.edges[0].target_port = 'nonexistent';
    expect(() => readStudioGraphLocalDraft(JSON.stringify(wrongPort), owner())).toThrow();
    const cyclic = snapshot(); cyclic.definition = { ...blankGraph(), nodes: ['first', 'second'].map(id => ({
      id, definition_id: 'text_reference', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: {},
    })), edges: ['first', 'second'].map((source_node_id, index) => ({ id: `edge_${index}`, source_node_id, source_port: 'text',
      target_node_id: source_node_id === 'first' ? 'second' : 'first', target_port: 'text' })) };
    expect(() => readStudioGraphLocalDraft(JSON.stringify(cyclic), owner())).toThrow();
    const wrongRequest = snapshot(); wrongRequest.request_id = 'new-request';
    expect(() => readStudioGraphLocalDraft(JSON.stringify(wrongRequest), owner())).toThrow('GRAPH_DRAFT_INVALID');
  });
  it('keeps legacy external-binding exclusion while bound authoring requires separate fresh recovery checks', () => {
    expect(graphDraftRecoverable(blankGraph())).toBe(true);
    expect(graphDraftRecoverable({ ...blankGraph(), schema_version: 3 })).toBe(true); // authoring bytes only; source/catalog checks run before adoption.
    const definition = blankGraph(); definition.nodes.push({ id: 'asset', definition_id: 'asset_reference', definition_version: 1, enabled: true,
      position: { x: 0, y: 0 }, parameters: { asset_id: 'asset', version: 1, digest: 'a'.repeat(64), kind: 'image' } });
    expect(graphDraftRecoverable(definition)).toBe(false);
  });
  it('requires exact version, both digests and current edit permission for a saved graph baseline', () => {
    const graph = modelGraph(), draft = snapshot(); draft.base = { id: graph.id, version: graph.version, definition_digest: graph.definition_digest, execution_digest: graph.execution_digest };
    expect(graphDraftBaselineMatches(draft, graph)).toBe(true);
    for (const patch of [{ version: graph.version + 1 }, { definition_digest: 'b'.repeat(64) }, { execution_digest: 'b'.repeat(64) }, { can_edit: false }])
      expect(graphDraftBaselineMatches(draft, { ...graph, ...patch })).toBe(false);
  });
});
