import { describe, expect, it } from 'vitest';
import { connectionIssue, retainsSavedAssetBindings } from './graphDraft';
import type {
  StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId,
  StudioGraphEdge, StudioGraphNode, StudioGraphParameters, StudioGraphPort, StudioGraphPortType,
} from './studioGraphTypes';

const digest = 'a'.repeat(64);
const port = (id: string, type: StudioGraphPortType, required = false): StudioGraphPort => ({ id, type, required, multiple: false });
const catalogEntry = (id: StudioGraphDefinitionId, inputs: StudioGraphPort[], outputs: StudioGraphPort[]): StudioGraphCatalogDefinition => ({
  id, version: 1, inputs, outputs, parameters_schema: { type: 'object', additionalProperties: false, properties: {} },
  default_parameters: id === 'asset_reference' ? null : {}, executable: id !== 'asset_reference', model_called: false,
  blockers: id === 'asset_reference' ? ['CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED'] : [],
});
const catalog: StudioGraphCatalogDefinition[] = [
  catalogEntry('text_input', [], [port('text', 'TEXT')]),
  catalogEntry('text_reference', [port('text', 'TEXT', true)], [port('text', 'TEXT')]),
  catalogEntry('draft_prepare', [port('text', 'TEXT', true), port('direction', 'DIRECTOR_NOTES')], [port('draft', 'DRAFT')]),
  catalogEntry('manual_transform', [port('text', 'TEXT', true), port('direction', 'DIRECTOR_NOTES')], [port('draft', 'DRAFT')]),
  catalogEntry('director_note', [], [port('direction', 'DIRECTOR_NOTES')]),
  catalogEntry('human_review', [port('draft', 'DRAFT', true)], []),
  catalogEntry('asset_reference', [], [port('asset', 'ASSET_REF')]),
];
function node(id: string, definition_id: StudioGraphDefinitionId = 'text_reference'): StudioGraphNode {
  const parameters: StudioGraphParameters = definition_id === 'asset_reference' ? { asset_id: 'asset-one', version: 2, digest, kind: 'image' }
    : definition_id === 'text_input' ? { text: '本地文本' }
      : definition_id === 'director_note' ? { note: '可选导演备注' }
        : definition_id === 'manual_transform' ? { result: '手工结果' } : {};
  return { id, definition_id, definition_version: 1, enabled: true, position: { x: 24, y: 48 }, parameters };
}
const edge = (id: string, source: string, target: string, source_port = 'text', target_port = 'text'): StudioGraphEdge => ({
  id, source_node_id: source, source_port, target_node_id: target, target_port,
});
function graph(edges: StudioGraphEdge[] = []): StudioGraphDefinition {
  return { schema_version: 1, title: '独立节点图', viewport: { x: 0, y: 0, zoom: 1 }, edges, nodes: [
    node('source', 'text_input'), node('first'), node('second'), node('third'), node('prepare', 'draft_prepare'),
    node('manual', 'manual_transform'), node('director', 'director_note'), node('review', 'human_review'), node('asset', 'asset_reference'),
  ] };
}

describe('local typed graph connection feedback', () => {
  it('accepts a typed connection while unrelated nodes remain disconnected', () => {
    const definition = graph();
    expect(connectionIssue(definition, catalog, edge('new', 'source', 'first'))).toBeUndefined();
    expect(definition.nodes.some(item => item.id === 'director')).toBe(true);
    expect(definition.nodes.some(item => item.id === 'asset')).toBe(true);
    expect(definition.edges).toEqual([]);
  });

  it.each([
    ['source', 'prepare', 'text', 'text'],
    ['source', 'manual', 'text', 'text'],
    ['director', 'prepare', 'direction', 'direction'],
    ['director', 'manual', 'direction', 'direction'],
    ['prepare', 'review', 'draft', 'draft'],
    ['manual', 'review', 'draft', 'draft'],
  ])('accepts declared compatible ports %s → %s (%s / %s)', (source, target, output, input) => {
    expect(connectionIssue(graph(), catalog, edge('new', source, target, output, input))).toBeUndefined();
  });

  it('allows a text-only preparation path without a Director node or connection', () => {
    const definition = graph(); definition.nodes = definition.nodes.filter(item => item.id !== 'director');
    expect(connectionIssue(definition, catalog, edge('new', 'source', 'prepare'))).toBeUndefined();
  });

  it.each([
    ['missing', 'first'], ['source', 'missing'],
  ])('rejects nodes outside the current definition: %s → %s', (source, target) => {
    expect(connectionIssue(graph(), catalog, edge('new', source, target))).toBe('请选择当前图中的两个节点。');
  });

  it('rejects a self-link even when the node has compatible input and output ports', () => {
    expect(connectionIssue(graph(), catalog, edge('new', 'first', 'first'))).toBe('节点不能连接自身。');
  });

  it.each([
    ['source', 'first', 'missing', 'text'],
    ['source', 'first', 'text', 'missing'],
    ['prepare', 'first', 'text', 'text'],
    ['source', 'source', 'text', 'text'],
    ['first', 'source', 'text', 'text'],
  ])('rejects nonexistent or reversed port directions: %s / %s / %s / %s', (source, target, output, input) => {
    const result = connectionIssue(graph(), catalog, edge('new', source, target, output, input));
    expect(result).toBe(source === target ? '节点不能连接自身。' : '请选择真实的输出端口和输入端口。');
  });

  it.each(['text_input', 'text_reference'])('fails closed when a node definition is missing from the catalog: %s', missing => {
    expect(connectionIssue(graph(), catalog.filter(item => item.id !== missing), edge('new', 'source', 'first'))).toBe('请选择真实的输出端口和输入端口。');
  });

  it.each([
    ['source', 'prepare', 'text', 'direction', 'TEXT', 'DIRECTOR_NOTES'],
    ['director', 'first', 'direction', 'text', 'DIRECTOR_NOTES', 'TEXT'],
    ['prepare', 'first', 'draft', 'text', 'DRAFT', 'TEXT'],
    ['asset', 'first', 'asset', 'text', 'ASSET_REF', 'TEXT'],
  ])('reports both mismatched types: %s → %s', (source, target, output, input, sourceType, targetType) => {
    expect(connectionIssue(graph(), catalog, edge('new', source, target, output, input))).toBe(`端口类型不匹配：${sourceType} → ${targetType}。`);
  });

  it('rejects the same connection under a different edge id before cardinality feedback', () => {
    const definition = graph([edge('existing', 'source', 'first')]);
    expect(connectionIssue(definition, catalog, edge('different-id', 'source', 'first'))).toBe('此连接已经存在。');
  });

  it('rejects a second source connected to an occupied single-input port', () => {
    const definition = graph([edge('existing', 'source', 'prepare')]);
    expect(connectionIssue(definition, catalog, edge('new', 'first', 'prepare'))).toBe('该输入端口只接受一个连接。');
  });

  it('allows distinct typed inputs on the same node and fan-out from one output', () => {
    const definition = graph([edge('text-input', 'source', 'prepare'), edge('first-output', 'source', 'first')]);
    expect(connectionIssue(definition, catalog, edge('optional-direction', 'director', 'prepare', 'direction', 'direction'))).toBeUndefined();
    expect(connectionIssue(definition, catalog, edge('second-output', 'source', 'second'))).toBeUndefined();
  });

  it('rejects a two-node cycle with otherwise valid free typed ports', () => {
    const definition = graph([edge('forward', 'first', 'second')]);
    expect(connectionIssue(definition, catalog, edge('back', 'second', 'first'))).toBe('此连接会形成循环，无法保存。');
  });

  it('rejects a transitive cycle without mistaking valid downstream reachability for one', () => {
    const definition = graph([edge('first-second', 'first', 'second'), edge('second-third', 'second', 'third')]);
    expect(connectionIssue(definition, catalog, edge('cycle', 'third', 'first'))).toBe('此连接会形成循环，无法保存。');
    expect(connectionIssue(definition, catalog, edge('upstream', 'source', 'first'))).toBeUndefined();
  });

  it('does not modify the graph, candidate connection or catalog while validating', () => {
    const definition = graph([edge('existing', 'source', 'first')]), candidate = edge('new', 'first', 'second');
    const before = JSON.stringify({ definition, candidate, catalog });
    expect(connectionIssue(definition, catalog, candidate)).toBeUndefined();
    expect(JSON.stringify({ definition, candidate, catalog })).toBe(before);
  });
});

describe('saved asset-reference binding protection', () => {
  it('allows a saved reference to move or be disabled without changing its binding', () => {
    const saved = node('asset', 'asset_reference');
    const moved = { ...saved, enabled: false, position: { x: -48, y: 96 }, parameters: { ...saved.parameters } };
    expect(retainsSavedAssetBindings([saved], [moved])).toBe(true);
  });

  it('preserves a semantically identical binding regardless of parameter key insertion order', () => {
    const saved = node('asset', 'asset_reference');
    const { asset_id, version, digest: savedDigest, kind } = saved.parameters;
    const reordered = { ...saved, parameters: { kind, digest: savedDigest, version, asset_id } };
    expect(retainsSavedAssetBindings([saved], [reordered])).toBe(true);
  });

  it('rejects removing or renaming a saved reference, or retyping its node', () => {
    const saved = node('asset', 'asset_reference');
    expect(retainsSavedAssetBindings([saved], [])).toBe(false);
    expect(retainsSavedAssetBindings([saved], [{ ...saved, id: 'replacement' }])).toBe(false);
    expect(retainsSavedAssetBindings([saved], [node('asset', 'text_input')])).toBe(false);
  });

  const changedBindings: [string, Partial<StudioGraphParameters>][] = [
    ['asset id', { asset_id: 'asset-two' }], ['version', { version: 3 }],
    ['digest', { digest: 'b'.repeat(64) }], ['kind', { kind: 'video' }],
  ];
  it.each(changedBindings)('rejects rebinding a saved reference by changing its %s', (_name, patch) => {
    const saved = node('asset', 'asset_reference');
    expect(retainsSavedAssetBindings([saved], [{ ...saved, parameters: { ...saved.parameters, ...patch } }])).toBe(false);
  });

  it('requires every saved reference to remain present', () => {
    const first = node('asset-one', 'asset_reference');
    const second = { ...node('asset-two', 'asset_reference'), parameters: { asset_id: 'second-file', version: 1, digest, kind: 'audio' as const } };
    expect(retainsSavedAssetBindings([first, second], [first])).toBe(false);
    expect(retainsSavedAssetBindings([first, second], [second, first])).toBe(true);
  });

  it('allows optional Director and ordinary text nodes to be removed while keeping a saved asset', () => {
    const asset = node('asset', 'asset_reference'), director = node('director', 'director_note'), text = node('source', 'text_input');
    expect(retainsSavedAssetBindings([asset, director, text], [asset])).toBe(true);
    expect(retainsSavedAssetBindings([director, text], [])).toBe(true);
  });

  it('allows adding and removing a draft-only asset reference without protecting it as saved', () => {
    const saved = node('saved', 'asset_reference'), draftOnly = node('unsaved', 'asset_reference');
    expect(retainsSavedAssetBindings([saved], [saved, draftOnly])).toBe(true);
    expect(retainsSavedAssetBindings([saved], [saved])).toBe(true);
    expect(retainsSavedAssetBindings([], [])).toBe(true);
  });

  it('does not mutate saved or proposed nodes during the protection check', () => {
    const saved = [node('asset', 'asset_reference')], next = [{ ...saved[0], enabled: false }];
    const before = JSON.stringify({ saved, next });
    expect(retainsSavedAssetBindings(saved, next)).toBe(true);
    expect(JSON.stringify({ saved, next })).toBe(before);
  });
});
