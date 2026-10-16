import { describe, expect, it, vi } from 'vitest';
import type { CollaborationContext } from '../api';
import { createStudioGraphClient } from './studioGraphClient';
import { modelCapabilities, modelGraph } from './studioGraphModel.testFixtures';
import { providerCatalog, taskMatch, taskRequirement } from './studioProvider.testFixtures';

const base = '/api/projects/model_project/studio';
const collaborationScope = () => ({ projectId: 'model_project', workspaceId: 'workspace', storylineId: 'storyline', branchId: 'branch' });

function setup(value: unknown, context: Pick<CollaborationContext, 'scope'> = {}) {
  const transport = { json: vi.fn().mockResolvedValue(value), blob: vi.fn().mockResolvedValue(new Blob(['candidate'])) };
  return { transport, client: createStudioGraphClient('model_project', context, transport) };
}

describe('graph admission transport argument forwarding', () => {
  it('keeps omitted optional arguments omitted and invokes JSON on the original receiver', async () => {
    const graph = modelGraph(), { client, transport } = setup(graph);
    const input = { expected_version: graph.version, definition: graph.definition };

    expect(await client.save(graph.id, input)).toEqual(graph);

    expect(transport.json.mock.calls).toEqual([[`${base}/graphs/${graph.id}`, 'PUT', input]]);
    expect(transport.json.mock.calls[0]).toHaveLength(3);
    expect(transport.json.mock.contexts).toEqual([transport]);
  });

  it('preserves explicitly supplied undefined options without appending another one', async () => {
    const capabilities = modelCapabilities(), { client, transport } = setup(capabilities);

    expect(await client.modelCapabilities()).toEqual(capabilities);
    expect(await client.modelCapabilities(undefined)).toEqual(capabilities);

    // These endpoints explicitly supply both body and signal to the transport.
    expect(transport.json.mock.calls).toEqual([
      [`${base}/graphs/model-capabilities`, 'GET', undefined, undefined],
      [`${base}/graphs/model-capabilities`, 'GET', undefined, undefined],
    ]);
    expect(transport.json.mock.calls.every(args => args.length === 4)).toBe(true);
    expect(transport.json.mock.contexts).toEqual([transport, transport]);
  });

  it('forwards the exact AbortSignal without adding an idempotency argument', async () => {
    const capabilities = modelCapabilities(), { client, transport } = setup(capabilities);
    const signal = new AbortController().signal;

    expect(await client.modelCapabilities(signal)).toEqual(capabilities);

    expect(transport.json.mock.calls).toEqual([[`${base}/graphs/model-capabilities`, 'GET', undefined, signal]]);
    expect(transport.json.mock.calls[0][3]).toBe(signal);
    expect(transport.json.mock.contexts).toEqual([transport]);
  });

  it('keeps the idempotency key and its explicit undefined signal placeholder', async () => {
    const graph = modelGraph(), { client, transport } = setup(graph);
    const input = { request_id: 'create_request', expected_version: 0 as const, definition: graph.definition };

    expect(await client.create(input)).toEqual(graph);

    expect(transport.json.mock.calls).toEqual([[`${base}/graphs`, 'POST', input, undefined, input.request_id]]);
    expect(transport.json.mock.calls[0]).toHaveLength(5);
    expect(transport.json.mock.contexts).toEqual([transport]);
  });

  it('preserves the provider extension transport contract for reads and advisory POSTs', async () => {
    const catalog = providerCatalog(), { client, transport } = setup(catalog);
    const signal = new AbortController().signal, requirement = taskRequirement(), match = taskMatch(requirement);

    expect(await client.providerContracts(signal)).toEqual(catalog);
    transport.json.mockResolvedValue(match);
    expect(await client.modelMatch(requirement)).toEqual(match);

    expect(transport.json.mock.calls).toEqual([
      [`${base}/graphs/provider-contracts`, 'GET', undefined, signal],
      [`${base}/graphs/model-match`, 'POST', requirement, undefined],
    ]);
    expect(transport.json.mock.contexts).toEqual([transport, transport]);
  });

  it('preserves the blob transport receiver and one-argument call', async () => {
    const { client, transport } = setup(modelGraph());

    expect(await client.mediaCandidate('model_run', 'generate')).toBeInstanceOf(Blob);

    expect(transport.blob.mock.calls).toEqual([[`${base}/graph-runs/model_run/media/candidate/generate`]]);
    expect(transport.blob.mock.contexts).toEqual([transport]);
    expect(transport.json).not.toHaveBeenCalled();
  });

  it('rejects a captured wrong project before any transport call even after scope mutation', () => {
    const scope = { ...collaborationScope(), projectId: 'foreign_project' };
    const graph = modelGraph(), { client, transport } = setup(graph, { scope });
    scope.projectId = 'model_project';

    for (const request of [
      () => client.catalog(),
      () => client.modelCapabilities(new AbortController().signal),
      () => client.save(graph.id, { expected_version: graph.version, definition: graph.definition }),
      () => client.create({ request_id: 'create_request', expected_version: 0, definition: graph.definition }),
      () => client.providerContracts(),
      () => client.modelMatch(taskRequirement()),
      () => client.mediaCandidate('model_run', 'generate'),
    ]) {
      expect(request).toThrowError(expect.objectContaining({ problem: expect.objectContaining({ status: 403, code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' }) }));
    }
    expect(transport.json).not.toHaveBeenCalled();
    expect(transport.blob).not.toHaveBeenCalled();
  });

  it('retains the admitted captured scope and rejects a response from a later branch', async () => {
    const scope = collaborationScope(), graph = { ...modelGraph(), scope: {
      mode: 'collaboration' as const, novel_id: scope.projectId, workspace_id: scope.workspaceId,
      storyline_id: scope.storylineId, branch_id: scope.branchId,
    } };
    const { client, transport } = setup(graph, { scope });
    scope.projectId = 'foreign_project';
    scope.branchId = 'later_branch';

    expect(await client.get(graph.id)).toEqual(graph);
    transport.json.mockResolvedValue({ ...graph, scope: { ...graph.scope, branch_id: scope.branchId } });
    await expect(client.get(graph.id)).rejects.toMatchObject({ problem: { status: 403, code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });

    expect(transport.json.mock.calls).toEqual([
      [`${base}/graphs/${graph.id}`, 'GET', undefined, undefined],
      [`${base}/graphs/${graph.id}`, 'GET', undefined, undefined],
    ]);
    expect(transport.json.mock.contexts).toEqual([transport, transport]);
  });
});
