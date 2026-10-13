import { describe, expect, it, vi } from 'vitest';
import catalogFixture from './fixtures/productionGraph.catalog.json';
import planningFixture from './fixtures/productionGraph.planning-run.json';
import { createStudioGraphClient } from './studioGraphClient';
import { checkedPlanningProjection } from './studioProductionGraphContract';
import type { PlanningProjection } from './studioProductionGraphContract';
import { checkedImageRecipeFields, checkedImageRuntimeInputs, checkedImageUpscaleProof, sameImageRuntimeInputs } from './studioImageRuntimeContract';
import { connectionIssue, retainsSavedAssetBindings } from './graphDraft';
import type { StudioGraphRun, StudioGraphRecord } from './studioGraphTypes';

const graph = planningFixture.graph as unknown as StudioGraphRecord, run = planningFixture.run as unknown as StudioGraphRun;
const project = graph.project_id;
const snapshot = { id: 'source', kind: 'ASSET' as const, asset_kind: 'image' as const, version: 1, digest: 'a'.repeat(64) };
const directorProjection = () => structuredClone(run.node_states.director.output!.direction!) as PlanningProjection;
describe('Production Graph projections from actual mounted API fixtures', () => {
  it('reads the additive catalog explicitly and preserves typed production ports', async () => {
    const json = vi.fn().mockResolvedValue(structuredClone(catalogFixture)), client = createStudioGraphClient(project, {}, { json });
    const catalog = await client.productionCatalog(); expect(catalog.capabilities.production_graph).toBe(true); expect(catalog.capabilities.image_upscale_execution).toBe(true);
    expect(catalog.definitions.find(row => row.id === 'storyboard_plan')?.outputs[0].type).toBe('STORYBOARD_DATA');
    expect(json).toHaveBeenCalledWith(`/api/projects/${project}/studio/graphs/catalog?include_image=true&include_production=true`, 'GET', undefined, undefined);
  });
  it('decodes original saved Director and Storyboard, their style prompt and exact source pins', async () => {
    const json = vi.fn().mockResolvedValueOnce(structuredClone(graph)).mockResolvedValueOnce(structuredClone(run)), client = createStudioGraphClient(project, {}, { json });
    await client.get(graph.id); const actual = await client.getRun(run.id);
    expect(actual.node_states.director.output?.direction).toEqual(run.node_states.director.output?.direction);
    expect(actual.node_states.board.output?.storyboard).toEqual(run.node_states.board.output?.storyboard);
    expect(actual.node_states.style.output?.prompt?.document_sources?.[0]).toMatchObject({ kind: 'CREATIVE_DOCUMENT', ...graph.definition.nodes.find(node => node.id === 'board')!.parameters.document_snapshot });
    expect(actual.model_called).toBe(false); expect(actual.applied).toBe(false);
    expect(json.mock.calls.every(([, method]) => method === undefined || method === 'GET')).toBe(true);
  });
  it('rejects arbitrary nested planning output and wrong modes', () => {
    const direction = structuredClone(run.node_states.director.output!.direction!);
    expect(() => checkedPlanningProjection({ ...direction, content: { ...('content' in direction ? direction.content : {}), unknown: 'command' } }, 'DIRECTOR')).toThrow();
    expect(() => checkedPlanningProjection(direction, 'STORYBOARD')).toThrow();
  });
  it('preserves valid original Scene.characters duplicates within the original bounds', () => {
    const projection = directorProjection(); projection.content.scenes[0].characters = ['same-character', 'same-character'];
    projection.content.scenes[0].action = 'a'.repeat(32000); projection.content.scenes[0].emotion = 'e'.repeat(4000);
    expect(checkedPlanningProjection(projection, 'DIRECTOR').content.scenes[0].characters).toEqual(['same-character', 'same-character']);
    expect(() => checkedPlanningProjection({ ...projection, content: { ...projection.content, scenes: [{ ...projection.content.scenes[0], characters: Array(101).fill('same-character') }] } }, 'DIRECTOR')).toThrow();
  });
  it('enforces the original 2000-character DirectorNote emotion limit', () => {
    const projection = directorProjection(); projection.content.director_notes[0].emotion = 'e'.repeat(2000);
    expect(() => checkedPlanningProjection(projection, 'DIRECTOR')).not.toThrow();
    projection.content.director_notes[0].emotion += 'e'; expect(() => checkedPlanningProjection(projection, 'DIRECTOR')).toThrow();
  });
  it('enforces the 4000-character performance action limit and distinct performers', () => {
    const projection = directorProjection(); const performer = { character: 'character', action: 'a'.repeat(4000), expression: '', state: '' };
    projection.content.director_notes[0].performances = [performer]; expect(() => checkedPlanningProjection(projection, 'DIRECTOR')).not.toThrow();
    performer.action += 'a'; expect(() => checkedPlanningProjection(projection, 'DIRECTOR')).toThrow();
    performer.action = ''; projection.content.director_notes[0].performances = [performer, performer]; expect(() => checkedPlanningProjection(projection, 'DIRECTOR')).toThrow();
  });
  it('continues rejecting duplicate newly authored Shot.characters', () => {
    const projection = structuredClone(run.node_states.board.output!.storyboard!) as PlanningProjection;
    projection.content.shots[0].characters = ['character', 'character']; expect(() => checkedPlanningProjection(projection, 'STORYBOARD')).toThrow();
  });
  it.each(['atmosphere', 'color_palette'] as const)('uses the original ImageStyle %s bound before transport', async field => {
    const definition = structuredClone(graph.definition), style = definition.nodes.find(node => node.definition_id === 'image_style')!;
    style.parameters[field] = 'a'.repeat(1000); const json = vi.fn().mockResolvedValue(graph), client = createStudioGraphClient(project, {}, { json });
    await client.create({ request_id: 'style-boundary', expected_version: 0, definition }); expect(json).toHaveBeenCalledTimes(1);
    style.parameters[field] += 'a'; await expect(Promise.resolve().then(() => client.create({ request_id: 'style-over-limit', expected_version: 0, definition }))).rejects.toBeTruthy(); expect(json).toHaveBeenCalledTimes(1);
  });
  it('retains the distinct 2000-character ImageStyle style bound', async () => {
    const definition = structuredClone(graph.definition), style = definition.nodes.find(node => node.definition_id === 'image_style')!;
    style.parameters.style = 's'.repeat(2000); const json = vi.fn().mockResolvedValue(graph), client = createStudioGraphClient(project, {}, { json });
    await client.create({ request_id: 'style-max', expected_version: 0, definition }); style.parameters.style += 's';
    await expect(Promise.resolve().then(() => client.create({ request_id: 'style-over-max', expected_version: 0, definition }))).rejects.toBeTruthy(); expect(json).toHaveBeenCalledTimes(1);
  });
  it.each([1, 2, 3] as const)('rejects production nodes in legacy schema %s before sending', async schema_version => {
    const definition = { ...structuredClone(graph.definition), schema_version }, json = vi.fn(), client = createStudioGraphClient(project, {}, { json });
    await expect(Promise.resolve().then(() => client.create({ request_id: 'legacy-reject', expected_version: 0, definition }))).rejects.toBeTruthy(); expect(json).not.toHaveBeenCalled();
  });
  it('reads document references under original scope and rejects another project', async () => {
    const document = graph.definition.nodes[0].parameters.document_snapshot!, row = { ...document, title: 'Synthetic Director', mode: 'DIRECTOR' };
    const json = vi.fn().mockResolvedValueOnce({ project_id: project, scope: graph.scope, documents: [row] }).mockResolvedValueOnce({ project_id: 'other', scope: graph.scope, documents: [row] });
    const client = createStudioGraphClient(project, {}, { json }); expect((await client.planningDocuments()).documents[0]).toEqual(row);
    await expect(client.planningDocuments()).rejects.toMatchObject({ status: 403 });
  });
  it('protects saved document bindings and rejects incompatible typed connections', async () => {
    expect(retainsSavedAssetBindings(graph.definition.nodes, graph.definition.nodes.slice(1))).toBe(false);
    const rebound = structuredClone(graph.definition.nodes); rebound[0].parameters.document_snapshot!.version++;
    expect(retainsSavedAssetBindings(graph.definition.nodes, rebound)).toBe(false);
    const client = createStudioGraphClient(project, {}, { json: vi.fn().mockResolvedValue(catalogFixture) }), catalog = await client.productionCatalog();
    expect(connectionIssue(graph.definition, catalog.definitions, { id: 'bad', source_node_id: 'director', source_port: 'direction', target_node_id: 'style', target_port: 'prompt' })).toMatch(/类型不匹配/);
  });
});
describe('Exact upscale and reference metadata contracts', () => {
  const recipe = () => ({ parameters: { scale: 2 }, image_recipe_id: 'comfy-upscale-model-v1', reference_weights: [1], reference_semantics: 'SINGLE_IMAGE_INITIALIZATION', mask_semantics: null, source_dimensions: { width: 64, height: 64 }, target_dimensions: { width: 128, height: 128 } });
  const proof = () => ({ contract: 'studio-image-upscale-proof/1', source_sha256: snapshot.digest, source_width: 64, source_height: 64, scale: 2, output_width: 128, output_height: 128, output_sha256: 'b'.repeat(64), output_bytes: 1024 });
  it('requires one exact base version and accepts bounded explicit upscale proof', () => {
    expect(checkedImageRuntimeInputs({ image_source: snapshot }, [snapshot], 'm5.image.upscale')).toEqual({ image_source: snapshot });
    expect(() => checkedImageRuntimeInputs({}, [snapshot], 'm5.image.upscale')).toThrow();
    checkedImageRecipeFields(recipe(), 'm5.image.upscale');
    expect(checkedImageUpscaleProof(proof(), { source_snapshots: [snapshot], parameters: { scale: 2 } }, { digest: 'b'.repeat(64), kind: 'image' }).scale).toBe(2);
    expect(() => checkedImageRecipeFields({ ...recipe(), target_dimensions: { width: 129, height: 128 } }, 'm5.image.upscale')).toThrow();
    expect(() => checkedImageUpscaleProof({ ...proof(), output_sha256: 'c'.repeat(64) }, { source_snapshots: [snapshot], parameters: { scale: 2 } }, { digest: 'b'.repeat(64), kind: 'image' })).toThrow();
  });
  it('omits metadata for old requests and binds purpose/source notes into equality', () => {
    const old = { image_references: [{ source: snapshot, weight: 1 }] };
    expect(checkedImageRuntimeInputs(old, [snapshot], 'm5.image.reference')).toEqual(old);
    const rich = { image_references: [{ source: snapshot, weight: 1, purpose: 'character' as const, source_note: 'authored synthetic reference' }] };
    expect(checkedImageRuntimeInputs(rich, [snapshot], 'm5.image.reference')).toEqual(rich);
    expect(sameImageRuntimeInputs(rich, old)).toBe(false);
    expect(() => checkedImageRuntimeInputs({ image_references: [{ source: snapshot, weight: 1, source_note: '' }] }, [snapshot], 'm5.image.reference')).toThrow();
    expect(() => checkedImageRuntimeInputs({ image_references: [{ source: snapshot, weight: 1, purpose: 'unknown' }] }, [snapshot], 'm5.image.reference')).toThrow();
  });
});
