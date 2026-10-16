import { afterEach, describe, expect, it, vi } from 'vitest';
import * as graphDraft from './graphDraft';
afterEach(() => vi.restoreAllMocks());
import { blankGraph } from './graphDraft';
import { graphSelectionCopy } from './graphSelectionCopy';
import { modelCatalog } from './studioGraphModel.testFixtures';
import type { StudioGraphDefinition } from './studioGraphTypes';
const graph = (): StudioGraphDefinition => ({ ...blankGraph(), nodes: ['a', 'b', 'c'].map((id, i) => ({ id, definition_id: (i === 0 ? 'text_input' : i === 1 ? 'draft_prepare' : 'human_review'), definition_version: 1, enabled: true, parameters: i === 0 ? { text: id } : {}, position: { x: i * 100, y: 0 } })), edges: [{ id: 'ab', source_node_id: 'a', source_port: 'text', target_node_id: 'b', target_port: 'text' }, { id: 'bc', source_node_id: 'b', source_port: 'draft', target_node_id: 'c', target_port: 'draft' }] });
describe('same graph copy planning', () => {
  it('deep copies exact parameters with new IDs and only remapped internal edges', () => {
    const source = graph(); source.nodes[0].parameters = { document_snapshot: { id: 'doc', version: 7, digest: 'a'.repeat(64) }, asset_id: 'asset', version: 2, digest: 'b'.repeat(64) };
    const before = structuredClone(source), result = graphSelectionCopy(source, ['a', 'b'], modelCatalog());
    expect(source).toEqual(before); expect(result.nodeCount).toBe(2); expect(result.edgeCount).toBe(1); expect(result.excludedEdges).toBe(1);
    expect(result.definition.nodes.slice(0, 3)).toEqual(source.nodes);
    expect(result.definition.nodes[3].parameters).toEqual(source.nodes[0].parameters);
    expect(result.definition.nodes[3].parameters).not.toBe(source.nodes[0].parameters);
    expect(result.definition.edges[2]).toMatchObject({ source_node_id: result.selected[0], target_node_id: result.selected[1], source_port: 'text', target_port: 'text' });
    expect(new Set([...result.definition.nodes, ...result.definition.edges].map(row => row.id)).size).toBe(8);
  });
  it('preserves relative offsets at positive and negative boundaries', () => {
    const source = graph(); source.nodes[0].position.x = 100000; source.nodes[1].position.x = 99980;
    const result = graphSelectionCopy(source, ['a', 'b'], modelCatalog());
    expect(result.delta.x).toBe(-32); expect(result.definition.nodes[3].position.x - result.definition.nodes[4].position.x).toBe(20);
    source.nodes[1].position.x = -100000;
    expect(graphSelectionCopy(source, ['a', 'b'], modelCatalog()).delta.x).toBe(0);
  });
  it.each(['nodes', 'edges', 'definition_bytes'] as const)('rejects %s overflow atomically', key => {
    const source = graph(), before = structuredClone(source), catalog = structuredClone(modelCatalog());
    Object.assign(catalog.limits, { [key]: 1 });
    expect(() => graphSelectionCopy(source, ['a', 'b'], catalog)).toThrow(); expect(source).toEqual(before);
  });
  it('rejects missing selection, invalid coordinates and media generator overflow', () => {
    const source = graph(); expect(() => graphSelectionCopy(source, ['missing'], modelCatalog())).toThrow();
    source.nodes[0].position.x = Infinity; expect(() => graphSelectionCopy(source, ['a'], modelCatalog())).toThrow();
    source.nodes = Array.from({ length: 4 }, (_, i) => ({ ...graph().nodes[0], id: String(i), definition_id: 'media_generate' }));
    expect(() => graphSelectionCopy(source, ['0'], modelCatalog())).toThrow(/媒体生成/);
  });
  it('rejects a generated ID collision without mutation', () => {
    const source = graph(), before = structuredClone(source);
    vi.spyOn(graphDraft, 'graphId').mockReturnValue('a');
    expect(() => graphSelectionCopy(source, ['a'], modelCatalog())).toThrow(/标识冲突/);
    expect(source).toEqual(before);
  });
  it.each([1, 3] as const)('accepts exactly the schema %s node budget and rejects one over', schema => {
    const source = graph(), limit = schema === 1 ? 16 : 24;
    source.schema_version = schema;
    source.nodes = Array.from({ length: limit - 1 }, (_, i) => ({ ...graph().nodes[0], id: 'node_' + i })); source.edges = [];
    const result = graphSelectionCopy(source, ['node_0'], modelCatalog());
    expect(result.definition.nodes).toHaveLength(limit);
    expect(() => graphSelectionCopy(result.definition, ['node_0'], modelCatalog())).toThrow(/数量限制/);
  });
  it('accepts exactly 40 edges and rejects 41 before application', () => {
    const source = graph();
    // A budget-only fixture: topology validity remains the original save owner's job.
    source.edges = Array.from({ length: 20 }, (_, i) => ({ ...graph().edges[0], id: 'edge_' + i }));
    expect(graphSelectionCopy(source, ['a', 'b'], modelCatalog()).definition.edges).toHaveLength(40);
    source.edges.push({ ...graph().edges[1], id: 'external' });
    expect(() => graphSelectionCopy(source, ['a', 'b'], modelCatalog())).toThrow(/数量限制/);
  });

});
