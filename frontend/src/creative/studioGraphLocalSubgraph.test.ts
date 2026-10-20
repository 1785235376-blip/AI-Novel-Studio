import { expect, it, vi } from 'vitest';
import actual from './fixtures/localSubgraph.file-api.json';
import { checkedStudioGraphDraft, createStudioGraphClient } from './studioGraphClient';
import { buildLocalSubgraphParent, inspectLocalSubgraphSource, retainsLocalSubgraphTopology } from './graphLocalSubgraph';
import type { StudioGraphCatalog, StudioGraphRecord } from './studioGraphTypes';

const source = () => structuredClone(actual.child) as unknown as StudioGraphRecord;
const catalog = () => structuredClone(actual.catalog) as unknown as StudioGraphCatalog;

it('decodes the real File catalog, Save/reopen, preflight and original review run without model/media authority', async () => {
  const transport = { json: vi.fn().mockImplementation(async (url: string, method = 'GET') => {
    if (url.endsWith('/catalog?include_local_subgraph=true')) return actual.catalog;
    if (url.endsWith('/graphs?include_local_subgraph=true')) return { items: [actual.child, actual.parent] };
    if (url.endsWith('/preflight')) return actual.preflight;
    if (url.endsWith('/execute')) return actual.waiting;
    if (url.endsWith('/approve')) return actual.approved;
    if (url.endsWith('/runs') && method === 'POST') return actual.queued;
    if (url.includes('/graph-runs/')) return actual.masked_run;
    return actual.parent;
  }) };
  const client = createStudioGraphClient(actual.project, {}, transport);
  expect((await client.localSubgraphCatalog()).capabilities.model_execution).toBe(false);
  expect((await client.localSubgraphList()).items).toHaveLength(2);
  expect((await client.get(actual.parent.id)).capacity?.history_limit).toBe(20);
  expect((await client.preflight(actual.parent.id, { expected_version: 1, target_node_ids: [] })).local_subgraph_contract).toBe('creative-graph-local-subgraph/1');
  const run = await client.createRun(actual.parent.id, { expected_graph_version: 1, target_node_ids: [], reviewed_preflight_digest: actual.preflight.preflight_digest, request_id: 'explicit_run' });
  expect(run.local_subgraph_runtime?.cache_enabled).toBe(false);
  const waiting = await client.action(run.id, 'execute', { expected_version: run.version });
  expect(waiting.review?.draft.origin).toBe('USER_SUPPLIED');
  expect(waiting.cache).toMatchObject({ mode: 'DISABLED_LOCAL_SUBGRAPH_V1', hits: 0 });
  expect(waiting.model_runtime).toBeUndefined(); expect(waiting.media_runtime).toBeUndefined();
  expect((await client.action(run.id, 'approve', { expected_version: waiting.version, node_id: 'review', reviewed_output_digest: waiting.review!.output_digest })).reviewed).toBe(true);
  const masked = await client.getRun(run.id);
  expect(masked.review).toBeNull(); expect(Object.values(masked.node_states).every(row => row.output === null)).toBe(true);
  expect(masked.local_subgraph_runtime?.bindings).toEqual({});
  expect(transport.json.mock.calls.filter(row => row[0].includes('/execute'))).toHaveLength(1);
});

it('rejects mixed schemas, client authority injection, multiple calls and mixed catalog capabilities', async () => {
  const definition = checkedStudioGraphDraft(actual.parent.definition);
  for (const version of [1, 2, 3, 4, 5]) expect(() => checkedStudioGraphDraft({ ...definition, schema_version: version })).toThrow();
  for (const kind of ['asset_reference', 'text_generate', 'video_generate', 'media_generate']) {
    const invalid = structuredClone(definition); invalid.nodes[1].definition_id = kind as typeof invalid.nodes[number]['definition_id'];
    expect(() => checkedStudioGraphDraft(invalid)).toThrow();
  }
  const forged = structuredClone(definition); Object.assign(forged.nodes[1].parameters, { server_authorized: true });
  expect(() => checkedStudioGraphDraft(forged)).toThrow();
  const doubled = structuredClone(definition); doubled.nodes.push({ ...doubled.nodes[1], id: 'second_call' });
  expect(() => checkedStudioGraphDraft(doubled)).toThrow();
  const mixed = structuredClone(actual.catalog); mixed.capabilities.model_execution = true;
  const client = createStudioGraphClient(actual.project, {}, { json: vi.fn().mockResolvedValue(mixed) });
  await expect(client.localSubgraphCatalog()).rejects.toThrow();
});

it('builds only three new parent nodes, preserves source content, and sends only fixed pin fields', () => {
  const child = source(), before = structuredClone(child), plan = inspectLocalSubgraphSource(child, catalog());
  expect(plan).toMatchObject({ input: 'entry', output: 'draft', childNodes: 2, totalNodes: 5 });
  const definition = buildLocalSubgraphParent(plan, 'Explicit parent text');
  expect(definition.nodes.map(node => node.definition_id)).toEqual(['text_input', 'local_subgraph', 'human_review']);
  expect(definition.nodes[1].parameters).toEqual({ graph_id: child.id, expected_version: 1, definition_digest: child.definition_digest,
    execution_digest: child.execution_digest, input_node_id: 'entry', input_port: 'text', output_node_id: 'draft', output_port: 'draft' });
  expect(definition.edges).toHaveLength(2); expect(child).toEqual(before);
  expect(JSON.stringify(definition)).not.toContain('binding_digest');
});

it('refuses hidden/disabled/missing dependencies and unavailable source without weakening the backend boundary', () => {
  const variants = [() => { const c = source(); c.definition.nodes.push({ ...c.definition.nodes[0], id: 'unused', definition_id: 'text_input', parameters: { text: 'hidden' } }); return c; },
    () => { const c = source(); c.definition.nodes[1].enabled = false; return c; },
    () => { const c = source(); c.definition.edges = []; return c; },
    () => { const c = source(); c.can_edit = false; return c; },
    () => { const c = source(); c.definition.nodes.push({ ...c.definition.nodes[0], id: 'review', definition_id: 'human_review' }); return c; }];
  for (const make of variants) expect(() => inspectLocalSubgraphSource(make(), catalog())).toThrow();
});

it('keeps schema6 topology and pins fixed while permitting parent text/title/layout edits', () => {
  const definition = buildLocalSubgraphParent(inspectLocalSubgraphSource(source(), catalog()), 'Before');
  const edited = structuredClone(definition); edited.title = 'After'; edited.nodes[0].parameters.text = 'Author edit'; edited.nodes[0].position.x = 32;
  expect(retainsLocalSubgraphTopology(definition, edited)).toBe(true);
  edited.nodes[1].parameters.expected_version = 2; expect(retainsLocalSubgraphTopology(definition, edited)).toBe(false);
  const removed = { ...definition, nodes: definition.nodes.slice(0, 2) }; expect(retainsLocalSubgraphTopology(definition, removed)).toBe(false);
});

it('requires cache-off pure receipts and never revives masked binding material', async () => {
  const bad = structuredClone(actual.waiting); bad.cache.hits = 1;
  const client = createStudioGraphClient(actual.project, {}, { json: vi.fn().mockResolvedValue(bad) });
  await expect(client.getRun(bad.id)).rejects.toThrow();
  const hidden = structuredClone(actual.masked_run); hidden.local_subgraph_runtime.bindings = actual.waiting.local_subgraph_runtime.bindings as typeof hidden.local_subgraph_runtime.bindings;
  const safe = createStudioGraphClient(actual.project, {}, { json: vi.fn().mockResolvedValue(hidden) });
  expect((await safe.getRun(hidden.id)).local_subgraph_runtime?.bindings).toEqual({});
  for (const mutate of [(run: typeof actual.waiting) => { run.local_subgraph_runtime.bindings.call.source.version = 2; },
    (run: typeof actual.waiting) => { Object.assign(run.local_subgraph_runtime, { receipts: {} }); }]) {
    const malformed = structuredClone(actual.waiting); mutate(malformed);
    const bound = createStudioGraphClient(actual.project, {}, { json: vi.fn().mockImplementation(async (url: string) =>
      url.includes('/graph-runs/') ? malformed : actual.parent) });
    await bound.get(actual.parent.id);
    await expect(bound.getRun(malformed.id)).rejects.toThrow();
  }
});
