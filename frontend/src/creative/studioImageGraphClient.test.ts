import { describe, expect, it, vi } from 'vitest';
import { createStudioGraphClient } from './studioGraphClient';
import { graphCatalogForSchema } from './graphDraft';
import { imageGraphCatalog, imageGraphDefinition, imageGraphProject, imageGraphRecord, imageGraphRun } from './studioImageGraph.testFixtures';
import type { MediaCommand, ProductionPreview } from './studioProductionClient';
import type { StudioGraphRun } from './studioGraphTypes';

function previewedRun(): StudioGraphRun {
  const run = imageGraphRun(), digest = 'a'.repeat(64), source = { id: 'source', kind: 'ASSET' as const, asset_kind: 'image' as const, version: 2, digest, reference_only: true as const };
  const command: MediaCommand & { operation_id: 'm5.image.reference' } = { operation_id: 'm5.image.reference', request_id: 'graph-image-request', provider_id: 'image-provider', model_id: 'image-model',
    prompt: 'Independent image fixture prompt', parameters: { denoising_strength: 0.5 }, source_snapshots: [source], image_references: [{ source, weight: 0.75 }], allow_cloud: false, license_note: '' };
  const production: ProductionPreview = { contract: 'studio-production-preview/1', novel_id: imageGraphProject, branch_id: null, request_id: command.request_id,
    operation_id: command.operation_id, preview_digest: digest, request_digest: digest, command,
    provider: { provider_id: command.provider_id!, model_id: command.model_id!, local: true, route_digest: digest },
    execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: command.operation_id, adapter: 'COMFYUI_BUILTIN_IMAGE', recipe_digest: digest, automatic_fallback: false,
      parameters: command.parameters, workflow: { fixture: 'bounded-original-owner-recipe' }, image_recipe_id: 'comfy-flux1-v1', reference_weights: [0.75], reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION', mask_semantics: null },
    sources: [{ snapshot: source, measured: { media_type: 'image/png', width: 64, height: 64 } }], product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
  run.media_runtime = { schema_version: 1, contract: 'creative-graph-media/1', nodes: [{ node_id: 'generate', status: 'AWAITING_PREVIEW',
    preview: { node_id: 'generate', input_digest: digest, preview_digest: digest, command, production_preview: structuredClone(production) }, execution: null }],
    automatic_retry: false, automatic_poll: false, applied: false, product_acceptance: 'LOCAL_REQUIRED' }; return run;
}

describe('closed image-only schema 4 through the original Graph transport', () => {
  it('reads actual opt-in catalog without changing the original catalog URL or sending mutations', async () => {
    const json = vi.fn().mockResolvedValue(imageGraphCatalog()), client = createStudioGraphClient(imageGraphProject, {}, { json });
    const catalog = await client.imageCatalog(); expect(catalog.capabilities.image_graph).toBe(true);
    expect(graphCatalogForSchema(catalog.definitions, 4).map(row => row.id)).toEqual(['text_input', 'text_reference', 'asset_reference', 'media_review', 'image_reference', 'image_prompt', 'image_generate']);
    expect(graphCatalogForSchema(catalog.definitions, 3).some(row => row.id === 'image_generate')).toBe(false);
    expect(json).toHaveBeenLastCalledWith(`/api/projects/${imageGraphProject}/studio/graphs/catalog?include_image=true`, 'GET', undefined, undefined);
    await client.catalog(); expect(json).toHaveBeenLastCalledWith(`/api/projects/${imageGraphProject}/studio/graphs/catalog`, 'GET', undefined, undefined);
    expect(json.mock.calls.every(([, method]) => method === 'GET')).toBe(true);
  });
  it('saves source versions, weighted ports and closed image operations without creating or dispatching a run', async () => {
    const json = vi.fn().mockResolvedValue(imageGraphRecord()), client = createStudioGraphClient(imageGraphProject, {}, { json });
    const result = await client.create({ request_id: 'image-create', expected_version: 0, definition: imageGraphDefinition() });
    expect(result.definition).toEqual(imageGraphDefinition()); expect(json).toHaveBeenCalledTimes(1);
    expect(json.mock.calls[0][0]).toBe(`/api/projects/${imageGraphProject}/studio/graphs`);
  });
  it('decodes version-bound reference and prompt outputs only for remembered schema 4 owners', async () => {
    const json = vi.fn().mockResolvedValueOnce(imageGraphRecord()).mockResolvedValueOnce(imageGraphRun()), client = createStudioGraphClient(imageGraphProject, {}, { json });
    await client.get('image-graph'); const result = await client.getRun('image-run');
    expect(result.node_states.references.output?.references?.[0].weight).toBe(0.75);
    expect(result.node_states.prompt.output?.prompt?.references?.[0].asset.version).toBe(2); expect(result.model_called).toBe(false);
  });
  it.each([0, 1.01, Number.NaN, Number.POSITIVE_INFINITY])('rejects malformed image weight %s before sending', async weight => {
    const definition = imageGraphDefinition(); definition.nodes[1].parameters.bindings![0].weight = weight;
    const json = vi.fn(), client = createStudioGraphClient(imageGraphProject, {}, { json });
    await expect(Promise.resolve().then(() => client.create({ request_id: 'invalid-image', expected_version: 0, definition }))).rejects.toMatchObject({ problem: { code: 'STUDIO_GRAPH_INPUT_INVALID' } }); expect(json).not.toHaveBeenCalled();
  });
  it.each([1, 2, 3] as const)('does not silently accept image nodes in legacy schema %s', async schema_version => {
    const definition = { ...imageGraphDefinition(), schema_version }, json = vi.fn(), client = createStudioGraphClient(imageGraphProject, {}, { json });
    await expect(Promise.resolve().then(() => client.create({ request_id: 'old-image', expected_version: 0, definition }))).rejects.toMatchObject({ problem: { code: 'STUDIO_GRAPH_INPUT_INVALID' } }); expect(json).not.toHaveBeenCalled();
  });
  it('rejects Video/Timeline nodes, arbitrary image fields and non-image assets in schema 4', async () => {
    const definitions = [imageGraphDefinition(), imageGraphDefinition(), imageGraphDefinition()];
    definitions[0].nodes.push({ ...definitions[0].nodes[3], id: 'video', definition_id: 'media_generate' });
    definitions[1].nodes[3].parameters.prompt = 'not-owned-here'; definitions[2].nodes[0].parameters.kind = 'video';
    for (const definition of definitions) {
      const json = vi.fn(), client = createStudioGraphClient(imageGraphProject, {}, { json });
      await expect(Promise.resolve().then(() => client.create({ request_id: 'closed-image', expected_version: 0, definition }))).rejects.toMatchObject({ problem: { code: 'STUDIO_GRAPH_INPUT_INVALID' } }); expect(json).not.toHaveBeenCalled();
    }
  });
  it('hides stale outputs and rejects reference output under an unrelated node', async () => {
    const foreign = imageGraphRun(); foreign.node_states.prompt.output = foreign.node_states.references.output;
    const json = vi.fn().mockResolvedValueOnce(imageGraphRecord()).mockResolvedValueOnce(foreign).mockResolvedValueOnce({ ...imageGraphRun(), stale: true });
    const client = createStudioGraphClient(imageGraphProject, {}, { json }); await client.get('image-graph');
    await expect(client.getRun('image-run')).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
    const stale = await client.getRun('image-run'); expect(Object.values(stale.node_states).every(row => row.output === null)).toBe(true);
  });
  it('consumes source-bound schema 4 media preview on the original owner without dispatch', async () => {
    const json = vi.fn().mockResolvedValueOnce(imageGraphRecord()).mockResolvedValueOnce(previewedRun()), client = createStudioGraphClient(imageGraphProject, {}, { json });
    await client.get('image-graph'); const run = await client.previewMedia('image-run', { expected_version: 1, node_id: 'generate' });
    const command = run.media_runtime!.nodes[0].preview!.command;
    if (command.operation_id === 'm9.timeline.multitrack') throw new Error('Wrong fixture owner');
    expect(command.image_references?.[0].weight).toBe(0.75);
    expect(json.mock.calls.filter(([url]) => /\/(?:dispatch|execute|review)$/.test(url))).toHaveLength(0);
  });
  it('rejects different weights between Graph and production receipts even when both commands are individually valid', async () => {
    const run = previewedRun(), production = run.media_runtime!.nodes[0].preview!.production_preview;
    if (production.operation_id === 'm9.timeline.multitrack') throw new Error('Wrong fixture owner');
    production.command.image_references![0].weight = 0.25; production.execution_recipe.reference_weights = [0.25];
    const json = vi.fn().mockResolvedValueOnce(imageGraphRecord()).mockResolvedValueOnce(run), client = createStudioGraphClient(imageGraphProject, {}, { json });
    await client.get('image-graph'); await expect(client.getRun('image-run')).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });
});
