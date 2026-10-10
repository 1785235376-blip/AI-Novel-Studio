import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { studioClient } from './studioClient';
import type { StudioGraphAction, StudioGraphCatalog, StudioGraphDefinition, StudioGraphDefinitionId, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';

const projectId = 'project / one', graphId = 'graph / one', runId = 'run / one';
const root = '/api/projects/project%20%2F%20one/studio', graphUrl = `${root}/graphs/graph%20%2F%20one`, runUrl = `${root}/graph-runs/run%20%2F%20one`;
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
const run = (): StudioGraphRun => ({ ...owner(), id: runId, version: 2, graph_id: graphId, graph_version: 3, status: 'QUEUED', current_node_id: null,
  node_states: { source: { status: 'PENDING', output: null, error: null }, draft: { status: 'PENDING', output: null, error: null }, review: { status: 'PENDING', output: null, error: null } },
  review: null, cache: { hits: 0, misses: 0, mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' }, created_at: timestamp, updated_at: timestamp,
  model_called: false, external_calls: 0, applied: false, stale: false, reviewed: false, timeout_seconds: 3600, deadline_at: '2026-10-09T01:00:00Z' });
const preflight = () => ({ ...owner(), graph_id: graphId, valid: true, executable: true, issues: [], execution_order: ['source', 'draft', 'review'],
  selected_closure: ['source', 'draft', 'review'], definition_digest: sha, preflight_digest: sha, expected_version: 3,
  target_node_ids: ['source', 'draft', 'review'], model_called: false, external_calls: 0 });
function catalog(): StudioGraphCatalog {
  const specs: { id: StudioGraphDefinitionId; inputs: [string, 'TEXT' | 'DRAFT' | 'DIRECTOR_NOTES'][]; outputs: [string, 'TEXT' | 'DRAFT' | 'DIRECTOR_NOTES' | 'ASSET_REF'][]; parameter?: 'text' | 'result' | 'note' }[] = [
    { id: 'text_input', inputs: [], outputs: [['text', 'TEXT']], parameter: 'text' },
    { id: 'text_reference', inputs: [['text', 'TEXT']], outputs: [['text', 'TEXT']] },
    { id: 'draft_prepare', inputs: [['text', 'TEXT'], ['direction', 'DIRECTOR_NOTES']], outputs: [['draft', 'DRAFT']] },
    { id: 'manual_transform', inputs: [['text', 'TEXT'], ['direction', 'DIRECTOR_NOTES']], outputs: [['draft', 'DRAFT']], parameter: 'result' },
    { id: 'director_note', inputs: [], outputs: [['direction', 'DIRECTOR_NOTES']], parameter: 'note' },
    { id: 'human_review', inputs: [['draft', 'DRAFT']], outputs: [] },
    { id: 'asset_reference', inputs: [], outputs: [['asset', 'ASSET_REF']] },
  ];
  return { definitions: specs.map(spec => ({ id: spec.id, version: 1,
    inputs: spec.inputs.map(([id, type]) => ({ id, type, required: id !== 'direction', multiple: false })),
    outputs: spec.outputs.map(([id, type]) => ({ id, type, required: false, multiple: false })),
    parameters_schema: { type: 'object', additionalProperties: false, properties: spec.id === 'asset_reference'
      ? { asset_id: { type: 'string', minLength: 1, maxLength: 240 }, version: { type: 'integer', minimum: 1 }, digest: { type: 'string', pattern: '^[a-f0-9]{64}$' }, kind: { type: 'string', enum: ['image', 'video', 'audio'] } }
      : spec.parameter ? { [spec.parameter]: { type: 'string', default: '', maxLength: spec.parameter === 'note' ? 4000 : 8000 } } : {} },
    default_parameters: spec.id === 'asset_reference' ? null : spec.parameter ? { [spec.parameter]: '' } : {},
    executable: spec.id !== 'asset_reference', model_called: false,
    blockers: spec.id === 'asset_reference' ? ['CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED'] : [] })),
  limits: { nodes: 16, edges: 40, definition_bytes: 96000, output_bytes: 64000, graphs: 25, runs: 100, history: 20, runtime_timeout_seconds: 3600, node_timeout_seconds: 5 },
  capabilities: { local_execution: true, chapter_required: false, model_execution: false, external_reference_execution: false, external_reference_detach: false,
    binary_cache: false, parallel_execution: false, automatic_retry: false, actor_private: true, cache_mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' } };
}
const reply = (value: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => value });
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => { fetchMock = vi.fn().mockResolvedValue(reply(graph())); vi.stubGlobal('fetch', fetchMock); useLocalHostSession.setState({ token: '', actorId: '' }); });
afterEach(() => { vi.unstubAllGlobals(); useLocalHostSession.setState({ token: '', actorId: '' }); });

describe('scoped graph transport', () => {
  it('reuses captured Studio credentials and branch for all graph endpoints', async () => {
    const origin = context(), client = studioClient(projectId, origin).graphs, signal = new AbortController().signal;
    origin.sessionToken = 'later-session'; origin.scope!.branchId = 'later-branch'; origin.scope!.workspaceId = 'later-workspace';
    fetchMock.mockResolvedValueOnce(reply(catalog())).mockResolvedValueOnce(reply({ items: [graph()] }))
      .mockResolvedValueOnce(reply(graph())).mockResolvedValueOnce(reply(graph())).mockResolvedValueOnce(reply(graph()))
      .mockResolvedValueOnce(reply(preflight())).mockResolvedValueOnce(reply({ items: [run()] })).mockResolvedValueOnce(reply(run())).mockResolvedValueOnce(reply(run()));
    await client.catalog(signal); await client.list(signal);
    await client.create({ request_id: 'create_one', expected_version: 0, definition: definition() });
    await client.get(graphId, signal); await client.save(graphId, { expected_version: 3, definition: definition() });
    await client.preflight(graphId, { expected_version: 3, target_node_ids: [] }, signal);
    await client.runs(graphId, signal);
    await client.createRun(graphId, { request_id: 'run_one', expected_graph_version: 3, reviewed_preflight_digest: sha, target_node_ids: [] });
    await client.getRun(runId, signal);
    for (const action of ['execute', 'approve', 'reject', 'cancel', 'pause', 'resume'] as const) {
      fetchMock.mockResolvedValueOnce(reply(run()));
      await client.action(runId, action, { expected_version: 2, ...(action === 'approve' || action === 'reject' ? { node_id: 'review', reviewed_output_digest: sha } : {}) });
    }
    expect(fetchMock.mock.calls.map(([url, init]) => [url, init.method])).toEqual([
      [`${root}/graphs/catalog`, 'GET'], [`${root}/graphs`, 'GET'], [`${root}/graphs`, 'POST'], [graphUrl, 'GET'], [graphUrl, 'PUT'],
      [`${graphUrl}/preflight`, 'POST'], [`${graphUrl}/runs`, 'GET'], [`${graphUrl}/runs`, 'POST'], [runUrl, 'GET'],
      ...['execute', 'approve', 'reject', 'cancel', 'pause', 'resume'].map(action => [`${runUrl}/${action}`, 'POST']),
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init.headers).toMatchObject({ 'X-Session-Token': 'captured-session', 'X-Branch-Id': 'captured-branch' });
      if (init.method === 'GET') { expect(init.signal).toBe(signal); expect(init.headers).not.toHaveProperty('Idempotency-Key'); }
      else expect(init.headers['Idempotency-Key']).toEqual(expect.any(String));
    }
    expect(fetchMock.mock.calls[2][1].headers['Idempotency-Key']).toBe('create_one');
    expect(fetchMock.mock.calls[7][1].headers['Idempotency-Key']).toBe('run_one');
    expect(JSON.parse(fetchMock.mock.calls[10][1].body)).toEqual({ expected_version: 2, node_id: 'review', reviewed_output_digest: sha, note: '' });
  });

  it('captures the local-host token once without borrowing a later identity', async () => {
    useLocalHostSession.setState({ token: 'host-original' });
    const client = studioClient(projectId, { sessionToken: '' }).graphs;
    useLocalHostSession.setState({ token: 'host-later' });
    fetchMock.mockResolvedValue(reply({ ...graph(), scope: { mode: 'local', novel_id: projectId } }));
    await client.get(graphId);
    expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('host-original');
    await studioClient(projectId, { sessionToken: '', localHostToken: '' }).graphs.get(graphId);
    expect(fetchMock.mock.calls[1][1].headers).not.toHaveProperty('X-Session-Token');
  });

  it.each([{ project_id: 'foreign' }, { scope: { ...owner().scope, novel_id: 'foreign' } },
    { scope: { ...owner().scope, workspace_id: 'foreign' } }, { scope: { ...owner().scope, storyline_id: 'foreign' } },
    { scope: { ...owner().scope, branch_id: 'foreign' } }, { scope: { mode: 'local', novel_id: projectId } }, { id: 'foreign' }])('rejects foreign graph owners and record IDs: %j', async fields => {
    fetchMock.mockResolvedValue(reply({ ...graph(), ...fields }));
    await expect(studioClient(projectId, context()).graphs.get(graphId)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
  });

  it('checks run and preflight ownership, graph IDs, run IDs, and exact CAS snapshots', async () => {
    const client = studioClient(projectId, context()).graphs;
    fetchMock.mockResolvedValue(reply({ items: [{ ...run(), graph_id: 'foreign' }] }));
    await expect(client.runs(graphId)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
    fetchMock.mockResolvedValue(reply({ ...run(), id: 'foreign' }));
    await expect(client.getRun(runId)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
    fetchMock.mockResolvedValue(reply({ ...preflight(), expected_version: 4 }));
    await expect(client.preflight(graphId, { expected_version: 3, target_node_ids: [] })).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
    fetchMock.mockResolvedValue(reply({ ...preflight(), graph_id: 'foreign' }));
    await expect(client.preflight(graphId, { expected_version: 3, target_node_ids: [] })).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
  });

  it('accepts the server-expanded all-enabled selection and rejects a changed explicit selection', async () => {
    const client = studioClient(projectId, context()).graphs;
    await client.get(graphId);
    fetchMock.mockResolvedValue(reply(preflight()));
    expect((await client.preflight(graphId, { expected_version: 3, target_node_ids: [] })).target_node_ids).toEqual(['source', 'draft', 'review']);
    await expect(client.preflight(graphId, { expected_version: 3, target_node_ids: ['review'] })).rejects.toBeInstanceOf(ApiError);
  });
});

describe('bounded graph inputs', () => {
  it('sends only owned fields and retains explicitly supplied text without metadata', async () => {
    const value = definition();
    value.nodes[0].parameters = { text: 'Author source', provider: 'private-provider' } as typeof value.nodes[0]['parameters'];
    await studioClient(projectId, context()).graphs.create({ request_id: 'create_one', expected_version: 0, definition: { ...value, secret: 'private-secret' } } as never);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ request_id: 'create_one', expected_version: 0, definition: definition() });
    expect(fetchMock.mock.calls[0][1].body).not.toContain('private');
  });

  it.each([-1, 0, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, '3', true])('rejects invalid mutation CAS %j without sending', expected => {
    const client = studioClient(projectId, context()).graphs;
    expect(() => client.save(graphId, { expected_version: expected as number, definition: definition() })).toThrow(ApiError);
    expect(() => client.preflight(graphId, { expected_version: expected as number, target_node_ids: [] })).toThrow(ApiError);
    expect(() => client.createRun(graphId, { expected_graph_version: expected as number, reviewed_preflight_digest: sha, target_node_ids: [], request_id: 'run_one' })).toThrow(ApiError);
    expect(() => client.action(runId, 'cancel', { expected_version: expected as number })).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('rejects nonzero graph creation versions and malformed request/digest bindings', () => {
    const client = studioClient(projectId, context()).graphs;
    for (const expected of [1, false, '0', null]) expect(() => client.create({ request_id: 'new_graph', expected_version: expected, definition: definition() } as never)).toThrow(ApiError);
    for (const requestId of ['', 'id with spaces', '9leading', 'x'.repeat(65)]) expect(() => client.create({ request_id: requestId, expected_version: 0, definition: definition() })).toThrow(ApiError);
    for (const malformed of ['', 'a'.repeat(63), 'A'.repeat(64)]) expect(() => client.createRun(graphId, { request_id: 'new_run', expected_graph_version: 3, reviewed_preflight_digest: malformed, target_node_ids: [] })).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('requires exact output evidence only for review decisions', () => {
    const client = studioClient(projectId, context()).graphs;
    for (const action of ['approve', 'reject'] as const) {
      expect(() => client.action(runId, action, { expected_version: 2 })).toThrow(ApiError);
      expect(() => client.action(runId, action, { expected_version: 2, node_id: 'review' })).toThrow(ApiError);
    }
    expect(() => client.action(runId, 'cancel', { expected_version: 2, node_id: 'review', reviewed_output_digest: sha })).toThrow(ApiError);
    expect(() => client.action(runId, 'automatic_retry' as StudioGraphAction, { expected_version: 2 })).toThrow(ApiError);
    expect(() => client.action(runId, 'pause', { expected_version: 2, note: 'x'.repeat(1001) })).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('rejects duplicate targets, unknown definitions, invalid geometry, dangling edges, wrong ports and cycles', () => {
    const client = studioClient(projectId, context()).graphs;
    expect(() => client.preflight(graphId, { expected_version: 3, target_node_ids: ['source', 'source'] })).toThrow(ApiError);
    const variants: StudioGraphDefinition[] = [];
    let value = definition(); value.nodes[0].definition_id = 'dynamic_plugin' as StudioGraphDefinitionId; variants.push(value);
    value = definition(); value.viewport.zoom = 3; variants.push(value);
    value = definition(); value.nodes[0].position.x = Infinity; variants.push(value);
    value = definition(); value.nodes[0].parameters.text = 'x'.repeat(8001); variants.push(value);
    value = definition(); value.edges[0].source_node_id = 'missing'; variants.push(value);
    value = definition(); value.edges[0].target_port = 'direction'; variants.push(value);
    value = definition(); value.edges[0].source_port = 'constructor'; value.edges[0].target_port = 'constructor'; variants.push(value);
    value = definition(); value.nodes.push({ ...value.nodes[0] }); variants.push(value);
    value = definition(); value.nodes = Array.from({ length: 17 }, (_, index) => ({ ...value.nodes[0], id: `node_${index}` })); value.edges = []; variants.push(value);
    value = definition(); value.nodes = [{ ...value.nodes[0], id: 'loop', definition_id: 'text_reference', parameters: {} }];
    value.edges = [{ id: 'loop_edge', source_node_id: 'loop', source_port: 'text', target_node_id: 'loop', target_port: 'text' }]; variants.push(value);
    for (const graph of variants) expect(() => client.save(graphId, { expected_version: 3, definition: graph })).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('sanitized graph projections and redaction fences', () => {
  it('redacts inaccessible asset snapshots and prevents a full-save erasure even after caller mutation', async () => {
    const value = graph();
    value.definition.nodes.push({ id: 'hidden', definition_id: 'asset_reference', definition_version: 1, enabled: false, position: { x: 0, y: 100 },
      parameters: { asset_id: 'private-asset-id', version: 1, digest: sha, kind: 'image' } });
    value.reference_states = [{ node_id: 'hidden', state: 'UNAVAILABLE' }]; value.can_edit = false;
    fetchMock.mockResolvedValue(reply(value));
    const client = studioClient(projectId, context()).graphs, actual = await client.get(graphId);
    expect(actual.definition.nodes.at(-1)!.parameters).toEqual({});
    expect(JSON.stringify(actual)).not.toContain('private');
    actual.can_edit = true; actual.definition.nodes.pop();
    expect(() => client.save(graphId, { expected_version: 3, definition: actual.definition })).toThrowError(expect.objectContaining({ problem: expect.objectContaining({ code: 'STUDIO_GRAPH_REDACTED_SAVE_BLOCKED' }) }));
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('fails closed if a response incorrectly marks an unavailable projection editable', async () => {
    const value = graph();
    value.definition.nodes.push({ id: 'hidden', definition_id: 'asset_reference', definition_version: 1, enabled: true, position: { x: 0, y: 100 }, parameters: {} });
    value.reference_states = [{ node_id: 'hidden', state: 'UNAVAILABLE' }]; value.can_edit = true;
    fetchMock.mockResolvedValue(reply(value));
    expect((await studioClient(projectId, context()).graphs.get(graphId)).can_edit).toBe(false);
  });

  it('rejects redacted definitions in direct writes rather than silently losing asset bindings', () => {
    const value = definition();
    value.nodes.push({ id: 'hidden', definition_id: 'asset_reference', definition_version: 1, enabled: false, position: { x: 0, y: 0 }, parameters: {} });
    expect(() => studioClient(projectId, context()).graphs.save(graphId, { expected_version: 3, definition: value })).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('returns only graph contract fields and preserves allowed author parameters', async () => {
    const value = graph();
    fetchMock.mockResolvedValue(reply({ ...value, internal_incarnation: 'private-incarnation', created_by: 'private-actor', history: ['private-history'],
      definition: { ...value.definition, executable_code: 'private-code', nodes: value.definition.nodes.map(node => ({ ...node, private_path: '/private/file' })) } }));
    expect(await studioClient(projectId, context()).graphs.get(graphId)).toEqual(graph());
  });

  it('whitelists nested typed outputs, error codes and review drafts', async () => {
    const value = run();
    value.status = 'WAITING_APPROVAL'; value.current_node_id = 'review';
    const draft = { text: 'Author source', origin: 'USER_SUPPLIED' as const, plan: [{ sequence: 1, beat: 'Author source' }], direction: { note: 'Keep concise' } };
    value.node_states.source = { status: 'SUCCEEDED', output: { text: 'Author source' }, error: null };
    value.node_states.draft = { status: 'SUCCEEDED', output: { draft }, error: null };
    value.node_states.review.status = 'WAITING_APPROVAL'; value.review = { node_id: 'review', output_digest: sha, draft };
    fetchMock.mockResolvedValue(reply({ ...value, trace: 'private-trace', cache_keys: 'private-key', review: { ...value.review, internal: 'private-review' },
      node_states: { ...value.node_states, source: { ...value.node_states.source, output: { text: 'Author source', secret: 'private-secret' }, internal: 'private-node' } } }));
    expect(await studioClient(projectId, context()).graphs.getRun(runId)).toEqual(value);
  });

  it.each([{ stale: true }, { status: 'FAILED' }, { status: 'CANCELLED' }, { status: 'REJECTED' }])('suppresses all output and review for unsafe states: %j', async fields => {
    const value = { ...run(), ...fields, node_states: { source: { status: 'SUCCEEDED', output: { text: 'private-stale' }, error: null } },
      review: { draft: 'private-stale', output_digest: 'private-digest' } };
    fetchMock.mockResolvedValue(reply(value));
    const actual = await studioClient(projectId, context()).graphs.getRun(runId);
    expect(actual.node_states.source.output).toBeNull(); expect(actual.review).toBeNull();
    expect(JSON.stringify(actual)).not.toContain('private');
  });

  it('accepts the finite catalog while dropping executable/plugin metadata', async () => {
    const value = catalog();
    fetchMock.mockResolvedValue(reply({ ...value, dynamic_registry: 'private-registry', definitions: value.definitions.map(item => ({ ...item, handler: 'private-handler' })) }));
    expect(await studioClient(projectId, context()).graphs.catalog()).toEqual(value);
  });

  it.each([{ model_execution: true }, { external_reference_execution: true }, { actor_private: false }, { automatic_retry: true }])('rejects unimplemented capability claims: %j', async fields => {
    const value = catalog(); fetchMock.mockResolvedValue(reply({ ...value, capabilities: { ...value.capabilities, ...fields } }));
    await expect(studioClient(projectId, context()).graphs.catalog()).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });

  it.each([{ model_called: true }, { external_calls: 1 }, { applied: true }, { status: 'DYNAMIC_RUNNING' }, { version: 0 },
    { timeout_seconds: 30 }, { deadline_at: '2026-10-09T01:00:00' }, { deadline_at: 'tomorrow' },
    { cache: { hits: 0, misses: 0, mode: 'BINARY_GLOBAL_CACHE' } }])('rejects invalid run guarantees: %j', async fields => {
    fetchMock.mockResolvedValue(reply({ ...run(), ...fields }));
    await expect(studioClient(projectId, context()).graphs.getRun(runId)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });

  it('preserves sanitized HTTP conflicts and permission failures from the shared transport', async () => {
    for (const status of [403, 409]) {
      fetchMock.mockResolvedValue(reply({ code: status === 409 ? 'VERSION_CONFLICT' : 'PERMISSION_DENIED', detail: { snapshot: 'private-snapshot', message: 'private-provider-error' } }, status));
      const failure = await studioClient(projectId, context()).graphs.action(runId, 'cancel', { expected_version: 2 }).catch(error => error);
      expect(failure).toBeInstanceOf(ApiError); expect(failure.status).toBe(status); expect(JSON.stringify(failure.problem)).not.toContain('private');
    }
  });

  it('keeps aborted reads distinguishable and sanitizes transport/JSON failures', async () => {
    const signal = new AbortController().signal;
    fetchMock.mockRejectedValueOnce(new DOMException('private request', 'AbortError'));
    await expect(studioClient(projectId, context()).graphs.get(graphId, signal)).rejects.toMatchObject({ name: 'AbortError' });
    fetchMock.mockRejectedValueOnce(new Error('private url and credentials'));
    await expect(studioClient(projectId, context()).graphs.list()).rejects.toMatchObject({ problem: { code: 'STUDIO_NETWORK_FAILED' } });
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => { throw new Error('private html'); } });
    await expect(studioClient(projectId, context()).graphs.list()).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });
});
