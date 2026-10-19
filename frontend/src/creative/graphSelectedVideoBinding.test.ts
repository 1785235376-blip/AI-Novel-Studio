import { describe, expect, it } from 'vitest';
import { graphSelectedVideoBinding, selectedVideoBindingNodes } from './graphSelectedVideoBinding';
import { uniqueGraphProviders } from './graphProviderChoices';
import { checkedStudioGraphDraft } from './studioGraphClient';
import { videoBindingCatalog, videoBindingGraph, videoBindingNode, videoBindingProvider } from './graphSelectedVideoBinding.testFixtures';
import type { StudioGraphParameters } from './studioGraphTypes';

describe('bounded selected video binding: preserve authored content', () => {
  it('changes exactly three fields per selected node, retaining different parameters, sources and edges', () => {
    const source = videoBindingGraph(), provider = videoBindingProvider();
    source.nodes.push({ id: 'shot', definition_id: 'storyboard_shot', definition_version: 1, enabled: true, position: { x: 0, y: 0 },
      parameters: { shot_id: 'original-shot', shot_version: 9, shot_digest: 'f'.repeat(64) } });
    source.edges.push({ id: 'shot-edge', source_node_id: 'shot', source_port: 'shot', target_node_id: 'video-1', target_port: 'shot' });
    const before = structuredClone(source), expected = structuredClone(source);
    for (const node of expected.nodes.filter(node => ['video-1', 'video-3'].includes(node.id))) Object.assign(node.parameters, { provider_id: provider.provider_id, model_id: provider.model_id, allow_cloud: false });
    const result = graphSelectedVideoBinding(source, ['video-3', 'video-1'], videoBindingCatalog(), provider);
    expect(result.definition).toEqual(expected); expect(source).toEqual(before);
    expect(JSON.stringify(result.definition)).toBe(JSON.stringify(expected));
    expect(result.changes.map(row => row.nodeId)).toEqual(['video-3', 'video-1']);
    expect(result.definition.nodes[1]).toBe(source.nodes[1]); expect(result.definition.edges).toBe(source.edges);
  });
  it('binds one branch while other empty bindings remain local drafts and full Save still rejects them', () => {
    const source = videoBindingGraph(); source.nodes.forEach(node => Object.assign(node.parameters, { provider_id: '', model_id: '', allow_cloud: false }));
    const next = graphSelectedVideoBinding(source, ['video-1'], videoBindingCatalog(), videoBindingProvider()).definition;
    expect(next.nodes[1].parameters.provider_id).toBe(''); expect(() => checkedStudioGraphDraft(next)).toThrow();
  });
  it.each([1, 2, 3, 4])('permits exactly %i selected video nodes', count => {
    const graph = videoBindingGraph(); expect(graphSelectedVideoBinding(graph, graph.nodes.slice(0, count).map(n => n.id), videoBindingCatalog(), videoBindingProvider()).changes).toHaveLength(count);
  });
  it.each([[], ['video-1', 'video-1'], ['missing'], ['video-1', 'video-2', 'video-3', 'video-4', 'video-5']].map(selected => ({ selected })))('rejects invalid selection $selected', ({ selected }) => {
    expect(() => selectedVideoBindingNodes(videoBindingGraph(), selected)).toThrow();
  });
  it('rejects mixed definitions, duplicate source IDs, schema and operations', () => {
    const graph = videoBindingGraph(); graph.nodes[1].definition_id = 'media_review'; expect(() => selectedVideoBindingNodes(graph, ['video-1', 'video-2'])).toThrow(/video-2/);
    graph.nodes[1] = videoBindingNode('video-1'); expect(() => selectedVideoBindingNodes(graph, ['video-1'])).toThrow();
    graph.nodes[1] = videoBindingNode('video-2'); graph.nodes[1].parameters.operation_id = 'm7.video.i2v'; expect(() => selectedVideoBindingNodes(graph, ['video-1', 'video-2'])).toThrow(/operation/);
    graph.schema_version = 4; expect(() => selectedVideoBindingNodes(graph, ['video-1'])).toThrow();
  });
  it('rejects cloud/wrong-operation providers and ambiguous tuples, including identical duplicates', () => {
    const provider = videoBindingProvider(), second = videoBindingProvider('second');
    expect(uniqueGraphProviders([provider, { ...provider }, second])).toEqual([second]);
    expect(uniqueGraphProviders([provider, { ...provider, route_digest: 'b'.repeat(64) }])).toEqual([]);
    for (const row of [{ ...provider, local: false }, { ...provider, operation_id: 'm7.video.i2v' as const }])
      expect(() => graphSelectedVideoBinding(videoBindingGraph(), ['video-1'], videoBindingCatalog(), row)).toThrow();
  });
  it('names the node and unsupported field, preserves every value, and rejects the whole batch', () => {
    const source = videoBindingGraph(), before = structuredClone(source), provider = videoBindingProvider();
    provider.supported_parameters = provider.supported_parameters.filter(name => name !== 'duration_seconds');
    expect(() => graphSelectedVideoBinding(source, ['video-2', 'video-1'], videoBindingCatalog(), provider)).toThrow(/video-2.*parameters.duration_seconds/);
    expect(source).toEqual(before);
  });
  it.each<NonNullable<StudioGraphParameters['parameters']>>([{ seed: -1 }, { frame_rate: 61 }, { duration_seconds: 601 }, { width: 512 }, { width: 512.5, height: 512 }])('reuses typed Save rules for %j', parameters => {
    const source = videoBindingGraph(); source.nodes[0].parameters.parameters = parameters;
    expect(() => graphSelectedVideoBinding(source, ['video-1'], videoBindingCatalog(), videoBindingProvider())).toThrow(/video-1.*原保存规则/);
  });
  it('does not normalize nulls or omitted author fields', () => {
    const graph = videoBindingGraph(); delete graph.nodes[0].parameters.prompt; graph.nodes[0].parameters.parameters = { seed: null };
    const next = graphSelectedVideoBinding(graph, ['video-1'], videoBindingCatalog(), videoBindingProvider()).definition;
    expect(next.nodes[0].parameters).not.toHaveProperty('prompt'); expect(next.nodes[0].parameters.parameters).toEqual({ seed: null });
  });
  it('rejects no-change applications without creating an alternate draft', () => {
    const source = videoBindingGraph(), provider = videoBindingProvider();
    source.nodes.forEach(node => Object.assign(node.parameters, { provider_id: provider.provider_id, model_id: provider.model_id, allow_cloud: false }));
    expect(() => graphSelectedVideoBinding(source, ['video-1', 'video-2'], videoBindingCatalog(), provider)).toThrow(/没有可应用/);
  });
  it('enforces generator, node and edge limits without full-graph parameter validation', () => {
    for (const kind of ['generator', 'node', 'edge']) {
      const graph = videoBindingGraph();
      if (kind === 'generator') graph.nodes.push(videoBindingNode('fifth'));
      if (kind === 'node') while (graph.nodes.length < 25) graph.nodes.push({ ...videoBindingNode(`note-${graph.nodes.length}`), definition_id: 'director_note', parameters: { note: '' } });
      if (kind === 'edge') graph.edges = Array.from({ length: 41 }, (_, i) => ({ id: `e-${i}`, source_node_id: 'video-1', source_port: 'candidate', target_node_id: 'video-2', target_port: 'shot' }));
      expect(() => graphSelectedVideoBinding(graph, ['video-1'], videoBindingCatalog(), videoBindingProvider())).toThrow(/容量/);
    }
  });
  it('measures UTF-8 bytes, including unchanged Chinese author content', () => {
    const graph = videoBindingGraph(); graph.nodes.forEach(node => { node.parameters.prompt = '中'.repeat(8000); });
    expect(JSON.stringify(graph).length).toBeLessThan(96_000);
    expect(() => graphSelectedVideoBinding(graph, ['video-1'], videoBindingCatalog(), videoBindingProvider())).toThrow(/字节容量/);
  });
});
