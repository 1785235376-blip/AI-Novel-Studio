import { describe, expect, it, vi } from 'vitest';
import catalogFixture from './fixtures/phase4.video-catalog.json';
import storyboardFixture from './fixtures/phase4.file-api-storyboard.json';
import previewFixture from './fixtures/phase4.file-api-preview.json';
import candidateFixture from './fixtures/phase4.file-api-job-candidate.json';
import mountedGraphFixture from './fixtures/phase4.file-api-video-graph.json';
import mountedPreflightFixture from './fixtures/phase4.file-api-video-graph-preflight.json';
import mountedRunFixture from './fixtures/phase4.file-api-video-graph-run.json';
import imageCatalogFixture from './fixtures/imageGraph.catalog.json';
import { createStudioGraphClient } from './studioGraphClient';
import { connectionIssue, graphCatalogForSchema } from './graphDraft';
import type { StudioGraphDefinition, StudioGraphNode, StudioGraphRecord } from './studioGraphTypes';

const copy = <T,>(value: T): T => structuredClone(value);
const project = 'synthetic-video-graph', sha = 'a'.repeat(64), created = '2026-10-14T00:00:00Z';
const owner = { project_id: project, scope: { mode: 'local' as const, novel_id: project } };
const node = (id: string, definition_id: StudioGraphNode['definition_id'], parameters: StudioGraphNode['parameters'] = {}): StudioGraphNode =>
  ({ id, definition_id, definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters });
const edge = (source_node_id: string, source_port: string, target_node_id: string, target_port: string) => ({ id: `${source_node_id}_${target_node_id}`, source_node_id, source_port, target_node_id, target_port });
const definition = (): StudioGraphDefinition => ({ schema_version: 5, title: 'Synthetic Video graph', nodes: [
  node('board', 'storyboard_plan', { document_snapshot: copy(storyboardFixture.document_snapshot) }),
  node('shot', 'storyboard_shot', { shot_id: storyboardFixture.shots[0].shot_id, shot_version: storyboardFixture.shots[0].shot_version, shot_digest: storyboardFixture.shots[0].shot_digest }),
  node('generate', 'video_generate', { operation_id: 'm7.video.t2v', provider_id: previewFixture.command.provider_id, model_id: previewFixture.command.model_id, prompt: '', parameters: { width: 64, height: 64, duration_seconds: 1, frame_rate: 8 }, allow_cloud: false, license_note: '' }),
  node('review', 'media_review'),
], edges: [edge('board', 'storyboard', 'shot', 'storyboard'), edge('shot', 'shot', 'generate', 'shot'), edge('generate', 'candidate', 'review', 'candidate')], viewport: { x: 0, y: 0, zoom: 1 } });
const graph = (value = definition()): StudioGraphRecord => ({ ...owner, id: 'synthetic-graph', version: 1, definition: value, definition_digest: sha, execution_digest: sha,
  created_at: created, updated_at: created, can_edit: true, reference_states: value.nodes.filter(n => ['director_plan', 'storyboard_plan', 'asset_reference'].includes(n.definition_id)).map(n => ({ node_id: n.id, state: 'CURRENT' })) });
// Only the catalog/shot bytes are API captures. This run is a unit transport fixture.
const run = () => ({ ...owner, id: 'synthetic-run', version: 2, graph_id: 'synthetic-graph', graph_version: 1, status: 'QUEUED', current_node_id: null,
  node_states: {
    board: { status: 'PENDING', output: null, error: null },
    shot: { status: 'SUCCEEDED', output: { shot: { ...copy(storyboardFixture.shots[0]), document_snapshot: copy(storyboardFixture.document_snapshot), approved: true } }, error: null },
    generate: { status: 'PENDING', output: null, error: null }, review: { status: 'PENDING', output: null, error: null },
  }, review: null, cache: { hits: 0, misses: 0, mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' }, created_at: created, updated_at: created,
  model_called: false, external_calls: 0, applied: false, stale: false, reviewed: false, timeout_seconds: 3600, deadline_at: '2026-10-14T01:00:00Z' });

describe('Actual mounted Video catalog is an explicit schema 5 boundary', () => {
  it('reads nine finite definitions and typed Video candidate/review/export ports', async () => {
    const json = vi.fn().mockResolvedValue(copy(catalogFixture)), client = createStudioGraphClient(project, {}, { json }), signal = new AbortController().signal;
    const catalog = await client.videoCatalog(signal);
    expect(json).toHaveBeenCalledWith(`/api/projects/${project}/studio/graphs/catalog?include_video=true`, 'GET', undefined, signal);
    expect(catalog.definitions.map(row => row.id)).toEqual(['text_input', 'text_reference', 'asset_reference', 'media_review', 'timeline_export', 'director_plan', 'storyboard_plan', 'storyboard_shot', 'video_generate']);
    expect(catalog.capabilities).toMatchObject({ video_graph: true, video_graph_schema_version: 5, video_graph_evidence: 'LOCAL_REQUIRED', storyboard_video_approval_required: true, automatic_video_dispatch: false });
    expect(catalog.definitions.find(row => row.id === 'storyboard_shot')?.outputs[0].type).toBe('STORYBOARD_SHOT');
    expect(catalog.definitions.find(row => row.id === 'video_generate')?.outputs[0].type).toBe('VIDEO_CANDIDATE');
    expect(catalog.definitions.find(row => row.id === 'media_review')?.inputs[0].type).toBe('VIDEO_CANDIDATE');
    expect(catalog.definitions.find(row => row.id === 'timeline_export')?.outputs[0].type).toBe('VIDEO_CANDIDATE');
  });
  it.each([
    { automatic_video_dispatch: true }, { storyboard_video_approval_required: false }, { video_graph_schema_version: 4 }, { video_graph_evidence: 'PASS' },
  ])('rejects weakened Video catalog guarantees %j', async fields => {
    const fixture = { ...copy(catalogFixture), capabilities: { ...catalogFixture.capabilities, ...fields } };
    await expect(createStudioGraphClient(project, {}, { json: vi.fn().mockResolvedValue(fixture) }).videoCatalog()).rejects.toBeTruthy();
  });
  it('rejects MEDIA_CANDIDATE in a Video review port', async () => {
    const fixture = copy(catalogFixture); fixture.definitions.find(row => row.id === 'media_review')!.inputs[0].type = 'MEDIA_CANDIDATE';
    await expect(createStudioGraphClient(project, {}, { json: vi.fn().mockResolvedValue(fixture) }).videoCatalog()).rejects.toBeTruthy();
  });
  it('accepts only the typed storyboard/shot/video/review path and prevents candidate bypass', async () => {
    const catalog = await createStudioGraphClient(project, {}, { json: vi.fn().mockResolvedValue(catalogFixture) }).videoCatalog();
    const value = definition(), empty = { ...value, edges: [] };
    for (const connection of value.edges) expect(connectionIssue(empty, catalog.definitions, connection)).toBeUndefined();
    const withTimeline = { ...empty, nodes: [...empty.nodes, node('timeline', 'timeline_export')] };
    expect(connectionIssue(withTimeline, catalog.definitions, edge('generate', 'candidate', 'timeline', 'source_1'))).toMatch(/类型不匹配/);
    expect(connectionIssue(withTimeline, catalog.definitions, edge('timeline', 'candidate', 'review', 'candidate'))).toBeUndefined();
    expect(connectionIssue(empty, catalog.definitions, edge('board', 'storyboard', 'generate', 'text'))).toMatch(/类型不匹配/);
  });
  it('keeps Image schema 4 candidate ports while schema 5 uses Video candidate ports', async () => {
    const image = await createStudioGraphClient(project, {}, { json: vi.fn().mockResolvedValue(imageCatalogFixture) }).imageCatalog();
    const video = await createStudioGraphClient(project, {}, { json: vi.fn().mockResolvedValue(catalogFixture) }).videoCatalog();
    expect(graphCatalogForSchema(image.definitions, 4).find(row => row.id === 'media_review')?.inputs[0].type).toBe('MEDIA_CANDIDATE');
    expect(graphCatalogForSchema(video.definitions, 5).find(row => row.id === 'media_review')?.inputs[0].type).toBe('VIDEO_CANDIDATE');
    expect(graphCatalogForSchema(video.definitions, 4).some(row => row.id === 'video_generate')).toBe(false);
  });
});

describe('Video Graph authoring preserves old schemas and exact history pins', () => {
  it('strictly decodes actual mounted schema 5 Graph, preflight and waiting-preview run without provider dispatch', async () => {
    const json = vi.fn().mockResolvedValueOnce(copy(mountedGraphFixture)).mockResolvedValueOnce(copy(mountedPreflightFixture)).mockResolvedValueOnce(copy(mountedRunFixture));
    const client = createStudioGraphClient(mountedGraphFixture.project_id, {}, { json }), graph = await client.get(mountedGraphFixture.id);
    const preflight = await client.preflight(graph.id, { expected_version: graph.version, target_node_ids: [] }), result = await client.getRun(mountedRunFixture.id);
    expect(graph.definition.schema_version).toBe(5); expect(graph.reference_states).toEqual([{ node_id: 'board', state: 'CURRENT' }]);
    expect(graph.definition.nodes.find(node => node.id === 'board')!.parameters.document_snapshot).toEqual(mountedRunFixture.node_states.shot.output.shot.document_snapshot);
    expect(preflight.executable).toBe(true); expect(preflight.definition_digest).toBe(graph.definition_digest);
    expect(preflight.selected_closure).toEqual(['board', 'shot', 'video', 'review']);
    expect(result.node_states.shot.output?.shot).toEqual(mountedRunFixture.node_states.shot.output.shot);
    expect(result.media_runtime?.nodes).toEqual([{ node_id: 'video', status: 'AWAITING_PREVIEW', preview: null, execution: null }]);
    expect(result.status).toBe('WAITING_APPROVAL'); expect(result.model_called).toBe(false); expect(result.external_calls).toBe(0); expect(result.applied).toBe(false);
    expect(json).toHaveBeenCalledTimes(3); expect(json.mock.calls.every(([url]) => !String(url).includes('/media/') && !String(url).includes('/jobs'))).toBe(true);
  });
  it('saves schema 5 typed inputs through the original create endpoint', async () => {
    const value = definition(), json = vi.fn().mockResolvedValue(graph(value)), client = createStudioGraphClient(project, {}, { json });
    const result = await client.create({ request_id: 'explicit-video', expected_version: 0, definition: value });
    expect(result.definition).toEqual(value); expect(json.mock.calls[0][2]).toEqual({ request_id: 'explicit-video', expected_version: 0, definition: value });
  });
  it.each([1, 2, 3, 4] as const)('rejects new Video nodes in legacy schema %s before sending', async schema_version => {
    const value = { ...definition(), schema_version }, json = vi.fn(), client = createStudioGraphClient(project, {}, { json });
    await expect(Promise.resolve().then(() => client.create({ request_id: 'legacy-reject', expected_version: 0, definition: value }))).rejects.toBeTruthy();
    expect(json).not.toHaveBeenCalled();
  });
  it.each([1, 2, 3, 4] as const)('continues saving original schema %s definitions', async schema_version => {
    const value: StudioGraphDefinition = { schema_version, title: 'Original contract', nodes: [schema_version === 4 ? node('prompt', 'image_prompt', { prompt: 'Synthetic image' }) : node('text', 'text_input', { text: 'Synthetic text' })], edges: [], viewport: { x: 0, y: 0, zoom: 1 } };
    const json = vi.fn().mockResolvedValue(graph(value));
    expect((await createStudioGraphClient(project, {}, { json }).create({ request_id: 'old-schema', expected_version: 0, definition: value })).definition.schema_version).toBe(schema_version);
  });
  it.each([
    { shot_version: 0 }, { shot_digest: 'bad' }, { shot_id: '' }, { unsafe_payload: { command: 'execute' } },
  ])('rejects malformed Shot parameters %j before sending', async fields => {
    const value = definition(); Object.assign(value.nodes[1].parameters, fields); const json = vi.fn();
    await expect(Promise.resolve().then(() => createStudioGraphClient(project, {}, { json }).create({ request_id: 'invalid-shot', expected_version: 0, definition: value }))).rejects.toBeTruthy();
    expect(json).not.toHaveBeenCalled();
  });
  it('decodes a Shot output with exact observed document and shot history pins', async () => {
    const fixture = run(), json = vi.fn().mockResolvedValueOnce(graph()).mockResolvedValueOnce(fixture), client = createStudioGraphClient(project, {}, { json });
    await client.get('synthetic-graph'); const result = await client.getRun('synthetic-run');
    expect(result.node_states.shot.output?.shot).toEqual(fixture.node_states.shot.output.shot);
    expect(result.applied).toBe(false); expect(result.model_called).toBe(false);
  });
  it.each(['shot_id', 'shot_version', 'shot_digest', 'document_version', 'document_digest'] as const)('rejects a changed observed Shot output %s', async field => {
    const fixture = run(), output = fixture.node_states.shot.output.shot;
    if (field === 'shot_id') { output.shot_id = 'other-shot'; output.shot.id = 'other-shot'; }
    else if (field === 'shot_version') output.shot_version++;
    else if (field === 'shot_digest') output.shot_digest = 'b'.repeat(64);
    else if (field === 'document_version') output.document_snapshot.version++;
    else output.document_snapshot.digest = 'b'.repeat(64);
    const json = vi.fn().mockResolvedValueOnce(graph()).mockResolvedValueOnce(fixture), client = createStudioGraphClient(project, {}, { json });
    await client.get('synthetic-graph'); await expect(client.getRun('synthetic-run')).rejects.toBeTruthy();
  });
  it.each(['video', 'image'] as const)('requires a Video candidate to carry a video Asset rather than %s', async kind => {
    const fixture = run(), states = fixture.node_states as Record<string, { status: string; output: unknown; error: null }>;
    states.generate = { status: 'SUCCEEDED', output: { candidate: { owner: 'video', job_id: candidateFixture.id, job_version: candidateFixture.version,
      request_digest: candidateFixture.request_digest, asset: { asset_id: candidateFixture.output_candidate.id, version: candidateFixture.output_candidate.version,
        digest: candidateFixture.output_candidate.digest, kind } } }, error: null };
    const json = vi.fn().mockResolvedValueOnce(graph()).mockResolvedValueOnce(fixture), client = createStudioGraphClient(project, {}, { json });
    await client.get('synthetic-graph');
    if (kind === 'video') expect((await client.getRun('synthetic-run')).node_states.generate.output?.candidate?.asset.kind).toBe('video');
    else await expect(client.getRun('synthetic-run')).rejects.toBeTruthy();
  });
  it('reads the original storyboard endpoint and rejects a foreign document response', async () => {
    const json = vi.fn().mockResolvedValueOnce(copy(storyboardFixture)).mockResolvedValueOnce({ ...copy(storyboardFixture), document_snapshot: { ...storyboardFixture.document_snapshot, id: 'foreign' } });
    const client = createStudioGraphClient(project, {}, { json }); expect((await client.videoStoryboard(storyboardFixture.document_snapshot.id)).shots).toHaveLength(2);
    expect(json.mock.calls[0][0]).toBe(`/api/novels/${project}/experimental/creative/documents/${storyboardFixture.document_snapshot.id}/storyboard`);
    await expect(client.videoStoryboard(storyboardFixture.document_snapshot.id)).rejects.toBeTruthy();
  });
});
