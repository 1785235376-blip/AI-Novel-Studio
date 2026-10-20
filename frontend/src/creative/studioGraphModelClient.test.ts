import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { createStudioGraphClient } from './studioGraphClient';
import { modelAdmittedRun, modelCapabilities, modelCatalog, modelDigest, modelGraph, modelPreviewRun, modelRun } from './studioGraphModel.testFixtures';

function setup(value: unknown) {
  const json = vi.fn().mockResolvedValue(value), client = createStudioGraphClient('model_project', {}, { json });
  return { client, json };
}
describe('versioned optional graph model contract', () => {
  it('retains exactly seven definitions and the unchanged local capability projection when off', async () => {
    const catalog = modelCatalog(false), { client } = setup(catalog);
    expect(await client.catalog()).toEqual(catalog); expect(catalog.definitions).toHaveLength(7);
    expect(catalog.capabilities).not.toHaveProperty('model_execution_contract');
  });
  it('accepts only the explicitly versioned eight-definition enabled catalog', async () => {
    const catalog = modelCatalog(), { client, json } = setup(catalog);
    expect(await client.catalog()).toEqual(catalog);
    json.mockResolvedValue({ ...catalog, capabilities: { ...catalog.capabilities, model_execution_contract: 'future/2' } });
    await expect(client.catalog()).rejects.toBeInstanceOf(ApiError);
    json.mockResolvedValue({ ...catalog, capabilities: modelCatalog(false).capabilities });
    await expect(client.catalog()).rejects.toBeInstanceOf(ApiError);
    json.mockResolvedValue({ ...catalog, definitions: catalog.definitions.slice(0, 7) });
    await expect(client.catalog()).rejects.toBeInstanceOf(ApiError);
  });
  it('normalizes finite model parameters without executable metadata', async () => {
    const graph = modelGraph(), { client, json } = setup(graph);
    const parameters = graph.definition.nodes[1].parameters;
    await client.create({ expected_version: 0, request_id: 'new_graph', definition: graph.definition });
    expect(json.mock.calls[0][2].definition.nodes[1].parameters).toEqual(parameters);
    for (const value of [0, 2049, 1.5, '512', true]) {
      graph.definition.nodes[1].parameters.max_output_tokens = value as number;
      expect(() => client.save(graph.id, { expected_version: 1, definition: graph.definition })).toThrow(ApiError);
    }
    graph.definition.nodes[1].parameters = { instruction: 'x'.repeat(4001), max_output_tokens: 512 };
    expect(() => client.save(graph.id, { expected_version: 1, definition: graph.definition })).toThrow(ApiError);
    expect(json).toHaveBeenCalledTimes(1);
  });
  it('requires an explicit schema-2 graph for text_generate and never widens schema 1', async () => {
    const graph = modelGraph(), { client, json } = setup(graph);
    expect(() => client.create({ expected_version: 0, request_id: 'new_graph', definition: { ...graph.definition, schema_version: 1 } })).toThrow(ApiError);
    expect(json).not.toHaveBeenCalled(); json.mockResolvedValue({ ...graph, definition: { ...graph.definition, schema_version: 1 } });
    await expect(client.get(graph.id)).rejects.toBeInstanceOf(ApiError);
  });
  it('exposes captured scoped capabilities without importing credentials or accepting provider authority metadata', async () => {
    const raw = { ...modelCapabilities(), secret: 'private-secret', routes: modelCapabilities().routes.map(item => ({ ...item, endpoint: 'private-endpoint', authorization: true })) };
    const { client, json } = setup(raw), result = await client.modelCapabilities();
    expect(result).toEqual(modelCapabilities()); expect(JSON.stringify(result)).not.toContain('private');
    expect(json).toHaveBeenCalledWith('/api/projects/model_project/studio/graphs/model-capabilities', 'GET', undefined, undefined);
  });
  it.each([
    (value: any) => { value.project_id = 'other'; },
    (value: any) => { value.scope.novel_id = 'other'; },
    (value: any) => { value.scope.mode = 'collaboration'; },
    (value: any) => { value.local_only = false; },
    (value: any) => { value.automatic_fallback = true; },
    (value: any) => { value.api_provider.execution_available = true; },
    (value: any) => { value.quality_verification = 'PASSED'; },
    (value: any) => { value.routes.push(value.routes[0]); },
    (value: any) => { value.routes[0].available = 'true'; },
    (value: any) => { value.limits.model_nodes = 2; },
  ])('fails closed for malformed or broadened model capability facts %j', async mutate => {
    const raw = modelCapabilities(); mutate(raw); const { client } = setup(raw); await expect(client.modelCapabilities()).rejects.toBeInstanceOf(ApiError);
  });
  it('sends only exact CAS and reviewed evidence to separate model actions, without dispatch on preview', async () => {
    const { client, json } = setup(modelPreviewRun());
    await client.previewModel('model_run', { expected_version: 2, route_id: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', allow_synthetic: false, provider: 'untrusted' } as never);
    expect(json).toHaveBeenCalledTimes(1);
    expect(json.mock.calls[0]).toEqual(['/api/projects/model_project/studio/graph-runs/model_run/model/preview', 'POST', { expected_version: 2, route_id: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', allow_synthetic: false }]);
    json.mockResolvedValue(modelAdmittedRun());
    await client.dispatchModel('model_run', { expected_version: 3, reviewed_preview_digest: modelDigest });
    expect(json.mock.calls[1]).toEqual(['/api/projects/model_project/studio/graph-runs/model_run/model/dispatch', 'POST', { expected_version: 3, reviewed_preview_digest: modelDigest }]);
    await client.refreshModel('model_run', { expected_version: 4 });
    expect(json.mock.calls[2]).toEqual(['/api/projects/model_project/studio/graph-runs/model_run/model/refresh', 'POST', { expected_version: 4 }]);
  });
  it('rejects malformed action evidence without sending', () => {
    const { client, json } = setup(modelRun());
    for (const expected of [0, '1', true, Infinity, 1.1]) {
      expect(() => client.previewModel('model_run', { expected_version: expected, route_id: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', allow_synthetic: false } as never)).toThrow(ApiError);
      expect(() => client.dispatchModel('model_run', { expected_version: expected, reviewed_preview_digest: modelDigest } as never)).toThrow(ApiError);
      expect(() => client.refreshModel('model_run', { expected_version: expected } as never)).toThrow(ApiError);
    }
    expect(() => client.previewModel('model_run', { expected_version: 2, route_id: 'route', allow_synthetic: 'true' } as never)).toThrow(ApiError);
    expect(() => client.dispatchModel('model_run', { expected_version: 2, reviewed_preview_digest: 'guessed' })).toThrow(ApiError);
    expect(json).not.toHaveBeenCalled();
  });
  it('rejects oversized UTF-8 prompts even below the character limit', async () => {
    const raw = modelPreviewRun(); raw.model_runtime!.preview!.prompt = '文'.repeat(10667);
    const { client } = setup(raw); await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
  });
  it('rejects model-origin results without recorded model execution or a review stage', async () => {
    const raw = modelRun(); raw.node_states.generate.output = { draft: { text: 'Unproven output', origin: 'MODEL_PROPOSAL' } };
    const { client, json } = setup(raw); await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
    const admitted = modelAdmittedRun(); admitted.model_called = true; admitted.model_runtime!.execution!.model_called = true;
    admitted.node_states.generate.output = raw.node_states.generate.output; json.mockResolvedValue(admitted);
    await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
  });
  it('rejects wrong selected routes, unsolicited synthetic routes and legacy receipts from model actions', async () => {
    const raw = modelPreviewRun(true), { client, json } = setup(raw);
    await expect(client.previewModel(raw.id, { expected_version: 2, route_id: 'd'.repeat(64), allow_synthetic: true })).rejects.toBeInstanceOf(ApiError);
    await expect(client.previewModel(raw.id, { expected_version: 2, route_id: 'e'.repeat(64), allow_synthetic: false })).rejects.toBeInstanceOf(ApiError);
    const legacy = modelRun(); delete legacy.model_runtime; json.mockResolvedValue(legacy);
    await expect(client.refreshModel(raw.id, { expected_version: 3 })).rejects.toBeInstanceOf(ApiError);
  });
  it('does not let a model action change the previously read graph identity for a run', async () => {
    const { client, json } = setup(modelRun()); await client.getRun('model_run');
    json.mockResolvedValue({ ...modelPreviewRun(), graph_id: 'different_graph' });
    await expect(client.previewModel('model_run', { expected_version: 2, route_id: 'd'.repeat(64), allow_synthetic: false })).rejects.toBeInstanceOf(ApiError);
  });
  it.each([
    (value: any) => { value.model_runtime.contract = 'other'; },
    (value: any) => { value.model_runtime.schema_version = '1'; },
    (value: any) => { value.model_runtime.node_id = 'missing'; },
    (value: any) => { value.model_runtime.automatic_retry = true; },
    (value: any) => { value.model_runtime.applied = true; },
    (value: any) => { value.model_runtime.preview.node_id = 'other'; },
    (value: any) => { value.model_runtime.preview.route = null; },
    (value: any) => { value.model_runtime.preview.reasons = ['UNAVAILABLE']; },
    (value: any) => { value.model_runtime.preview.limits.timeout_seconds = 181; },
    (value: any) => { value.model_runtime.preview.input_digest = 'bad'; },
    (value: any) => { value.model_called = true; },
    (value: any) => { value.external_calls = 1; },
  ])('rejects inconsistent model runtime projections %j', async mutate => {
    const raw = modelPreviewRun(); mutate(raw); const { client } = setup(raw); await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
  });
  it('never accepts model calls or model-origin output through an unversioned legacy receipt', async () => {
    const raw = modelRun(); delete raw.model_runtime; raw.model_called = true;
    const { client, json } = setup(raw); await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
    raw.model_called = false; raw.node_states.generate.output = { draft: { text: 'Cannot smuggle model output', origin: 'MODEL_PROPOSAL' } };
    json.mockResolvedValue(raw); await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
  });
  it('whitelists model proposal output and hides all private prompt/output material after cancellation or staleness', async () => {
    const raw = modelAdmittedRun(); raw.model_called = true; raw.model_runtime!.execution!.model_called = true;
    raw.model_runtime!.status = 'RESULT_REVIEW'; raw.status = 'WAITING_APPROVAL'; raw.current_node_id = 'review';
    raw.review = { node_id: 'review', output_digest: modelDigest, draft: { text: 'Candidate output', origin: 'MODEL_PROPOSAL' } };
    raw.node_states.generate.output = { draft: { text: 'Candidate output', origin: 'MODEL_PROPOSAL' } };
    const { client, json } = setup(raw); expect((await client.getRun(raw.id)).review?.draft.origin).toBe('MODEL_PROPOSAL');
    for (const fields of [{ status: 'CANCELLED' }, { stale: true }, { status: 'FAILED' }, { status: 'REJECTED' }]) {
      json.mockResolvedValue({ ...raw, ...fields }); const result = await client.getRun(raw.id);
      expect(result.review).toBeNull(); expect(result.node_states.generate.output).toBeNull(); expect(result.model_runtime?.preview).toBeNull();
      expect(JSON.stringify(result)).not.toContain('Candidate output'); expect(JSON.stringify(result)).not.toContain('Complete reviewed author input');
    }
  });
  it('validates returned run identity on all model action endpoints', async () => {
    const { client } = setup({ ...modelPreviewRun(), id: 'other_run' });
    await expect(client.previewModel('model_run', { expected_version: 2, route_id: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', allow_synthetic: false })).rejects.toBeInstanceOf(ApiError);
    await expect(client.dispatchModel('model_run', { expected_version: 3, reviewed_preview_digest: modelDigest })).rejects.toBeInstanceOf(ApiError);
    await expect(client.refreshModel('model_run', { expected_version: 4 })).rejects.toBeInstanceOf(ApiError);
  });
});
