import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import actual from './fixtures/conditions.file-api.json';
import enumActual from './fixtures/conditions-enum.file-api.json';
import { createStudioGraphClient, checkedStudioGraphDraft } from './studioGraphClient';
import { buildConditionalStarter, checkedConditionPlan, conditionShape } from './graphConditionContract';
import type { CollaborationContext } from '../api';
beforeEach(() => vi.stubGlobal('crypto', webcrypto));
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const context = { scope: { projectId: actual.graph.project_id, workspaceId: actual.graph.scope.workspace_id, storylineId: actual.graph.scope.storyline_id, branchId: actual.graph.scope.branch_id } } as CollaborationContext;
function bound(read: (url: string) => unknown) { const json = vi.fn(async <T,>(url: string): Promise<T> => structuredClone(read(url)) as T); return { json, client: createStudioGraphClient(actual.graph.project_id, context, { json: async <T,>(url: string) => json(url) as Promise<T> }) }; }
const copy = <T,>(value: T): T => structuredClone(value);
it('decodes actual File/API opt-in discovery, Save/reopen, whole preflight, create, execute and original human review', async () => {
  const { client, json } = bound(url => url.endsWith('/catalog?include_local_conditions=true') ? actual.catalog : url.endsWith('/graphs?include_local_conditions=true') ? { items: [actual.graph] } : url.endsWith('/preflight') ? actual.preflight : url.endsWith('/execute') ? actual.waiting : url.endsWith('/approve') ? actual.approved : url.endsWith('/runs') ? actual.queued : actual.graph);
  expect((await client.conditionsCatalog()).capabilities.whole_graph_required).toBe(true);
  expect((await client.conditionsList()).items).toHaveLength(1);
  const saved = await client.get(actual.graph.id); expect(saved.definition.schema_version).toBe(7);
  expect((await client.preflight(saved.id, { expected_version: saved.version, target_node_ids: [] })).conditional_plan).toEqual(actual.preflight.conditional_plan);
  const queued = await client.createRun(saved.id, { ...actual.create_body }); expect(queued.conditional_runtime?.cache_enabled).toBe(false);
  const waiting = await client.action(queued.id, 'execute', { expected_version: queued.version }); expect(waiting.review?.node_id).toBe('yes_review');
  expect(Object.values(waiting.node_states).every(s => s.output === null)).toBe(true);
  const approved = await client.action(queued.id, 'approve', { expected_version: waiting.version, node_id: waiting.review!.node_id, reviewed_output_digest: waiting.review!.output_digest });
  expect(approved.reviewed).toBe(true); expect(approved.node_states.no).toEqual({ ...actual.approved.node_states.no });
  expect(approved.node_states.condition.output).toEqual({ when_true: 'Pinned authored source' });
  expect(json.mock.calls.filter(([u]) => u.endsWith('/execute'))).toHaveLength(1);
});
it('keeps the default catalog closed and rejects non-finite schemas, coerced predicates, authority fields and structural mixtures', async () => {
  await expect(bound(() => actual.catalog).client.catalog()).rejects.toThrow();
  for (const mutate of [(v: ReturnType<typeof copy<typeof actual.catalog>>) => { v.capabilities.model_execution = true; }, (v: typeof actual.catalog) => { Object.assign(v.definitions[0], { blockers: ['EXTERNAL_ALLOWED'] }); }, (v: typeof actual.catalog) => { Object.assign(v.capabilities, { eval_script: true }); }]) {
    const value = copy(actual.catalog); mutate(value); await expect(bound(() => value).client.conditionsCatalog()).rejects.toThrow();
  }
  for (const mutate of [(v: ReturnType<typeof buildConditionalStarter>) => { Object.assign(v, { server_authorized: true }); }, (v: ReturnType<typeof buildConditionalStarter>) => { Object.assign(v.nodes[1].parameters.predicate!, { value: 'true' }); }, (v: ReturnType<typeof buildConditionalStarter>) => { Object.assign(v.nodes[0].parameters, { allow_cloud: true }); }, (v: ReturnType<typeof buildConditionalStarter>) => { v.nodes[2].enabled = false; }, (v: ReturnType<typeof buildConditionalStarter>) => { v.schema_version = 1; }, (v: ReturnType<typeof buildConditionalStarter>) => { v.edges[2].target_node_id = 'no_review'; }]) {
    const value = buildConditionalStarter(); mutate(value); expect(() => checkedStudioGraphDraft(value)).toThrow();
  }
  const value = buildConditionalStarter(); value.nodes[1].parameters.predicate = { kind: 'enum', value: 'A', equals: 'B' };
  expect(conditionShape(checkedStudioGraphDraft(value)).selected).toBe('when_false');
});
it('checks plan digest, saved source, selected port/order and whole-graph scope instead of trusting server labels', async () => {
  for (const mutate of [(v: typeof actual.preflight) => { v.conditional_plan.selected_port = 'when_false'; }, (v: typeof actual.preflight) => { v.conditional_plan.plan_digest = 'a'.repeat(64); }, (v: typeof actual.preflight) => { v.conditional_plan.active_node_ids.reverse(); }, (v: typeof actual.preflight) => { v.expected_version++; }, (v: typeof actual.preflight) => { v.scope.branch_id = 'different'; }, (v: typeof actual.preflight) => { Object.assign(v, { trusted: true }); }]) {
    const value = copy(actual.preflight); mutate(value); const { client } = bound(url => url.endsWith('/preflight') ? value : actual.graph); await client.get(actual.graph.id);
    await expect(client.preflight(actual.graph.id, { expected_version: 2, target_node_ids: [] })).rejects.toThrow();
  }
  await expect(checkedConditionPlan(actual.preflight.conditional_plan, { ...checkedStudioGraphDraft(actual.graph.definition), title: 'Changed source' })).rejects.toThrow();
});
it('rejects skipped output/dispatch, cache enablement, fake human review and unreviewed output before accepting a run', async () => {
  const mutations = [(v: typeof actual.approved) => { Object.assign(v.node_states.no, { output: { draft: { text: 'leak', origin: 'MANUAL' } } }); }, (v: typeof actual.approved) => { v.conditional_runtime.skipped_dispatches = 1; }, (v: typeof actual.approved) => { v.cache.hits = 1; }, (v: typeof actual.approved) => { v.node_states.yes_review.reviewed = false; }, (v: typeof actual.approved) => { v.graph_version++; }, (v: typeof actual.approved) => { Object.assign(v.node_states.condition.output!, { text: 'extra' }); }, (v: typeof actual.approved) => { v.reviewed = false; }];
  for (const mutate of mutations) { const value = copy(actual.approved); mutate(value); const { client, json } = bound(url => url.includes('/graph-runs/') ? value : actual.graph); await client.get(actual.graph.id);
    json.mockClear(); await expect(client.getRun(value.id)).rejects.toThrow(); expect(json).toHaveBeenCalledTimes(1); expect(json.mock.calls[0][0]).toContain('/graph-runs/');
  }
  const waiting = copy(actual.waiting); waiting.review.output_digest = 'b'.repeat(64); const { client } = bound(url => url.includes('/graph-runs/') ? waiting : actual.graph); await client.get(actual.graph.id); await expect(client.getRun(waiting.id)).rejects.toThrow();
});
it('requires a redacted hidden runtime and closes old schema responses without conditional proof', async () => {
  const hidden = { ...copy(actual.approved), stale: true, review: null, conditional_runtime: { ...actual.approved.conditional_runtime, plan: null, skipped_dispatches: null, skipped_outputs: null }, node_states: Object.fromEntries(Object.entries(actual.approved.node_states).map(([id, s]) => [id, { ...s, output: null }])) };
  const { client } = bound(url => url.includes('/graph-runs/') ? hidden : actual.graph); await client.get(actual.graph.id); expect((await client.getRun(hidden.id)).conditional_runtime?.plan).toBeNull();
  Object.assign(hidden.node_states.input, { output: { text: 'private' } }); await expect(client.getRun(hidden.id)).rejects.toThrow();
  const missing = copy(actual.approved) as Partial<typeof actual.approved>; delete missing.conditional_runtime;
  const missingClient = bound(url => url.includes('/graph-runs/') ? missing : actual.graph).client; await missingClient.get(actual.graph.id); await expect(missingClient.getRun(actual.approved.id)).rejects.toThrow();
});

it('retires a late proof hash after the observed graph changes, including same-ID rereads', async () => {
  const original = webcrypto.subtle.digest.bind(webcrypto.subtle); let resolve!: () => void;
  vi.stubGlobal('crypto', { subtle: { digest: async (...args: Parameters<typeof original>) => { await new Promise<void>(r => { resolve = r; }); return original(...args); } } });
  const { client } = bound(url => url.includes('/graph-runs/') ? actual.queued : actual.graph); await client.get(actual.graph.id);
  const pending = client.getRun(actual.queued.id); await vi.waitFor(() => expect(resolve).toBeTypeOf('function'));
  await client.get(actual.graph.id); const first = resolve; first();
  await vi.waitFor(() => expect(resolve).not.toBe(first)); resolve();
  await expect(pending).rejects.toThrow();
});

it('accepts the real A/B false arm through original review and rejects an altered source plan', async () => {
  let value: unknown = enumActual.waiting;
  const scope = enumActual.graph.scope, client = createStudioGraphClient(enumActual.graph.project_id, { scope: { projectId: enumActual.graph.project_id, workspaceId: scope.workspace_id, storylineId: scope.storyline_id, branchId: scope.branch_id } }, { json: async <T,>(url: string) => structuredClone(url.includes('/graph-runs/') ? value : enumActual.graph) as T });
  await client.get(enumActual.graph.id);
  expect((await client.getRun(enumActual.waiting.id)).conditional_runtime?.plan?.selected_port).toBe('when_false');
  value = enumActual.approved; expect((await client.getRun(enumActual.approved.id)).node_states.no.output?.draft?.origin).toBe('USER_SUPPLIED');
  const changed = copy(enumActual.approved); changed.node_states.no.output.draft.plan[0].beat = 'Other source'; value = changed;
  await expect(client.getRun(enumActual.approved.id)).rejects.toThrow();
});
it('accepts the original read-only saved projection without treating absent capacity as write authority', async () => {
  const readOnly = { ...copy(actual.graph), can_edit: false } as Partial<typeof actual.graph>; delete readOnly.capacity;
  const client = bound(() => readOnly).client; expect((await client.get(actual.graph.id)).can_edit).toBe(false);
  expect(() => client.save(actual.graph.id, { expected_version: 2, definition: checkedStudioGraphDraft(actual.graph.definition) })).toThrow();
});
