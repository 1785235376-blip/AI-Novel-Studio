import { describe, expect, it } from 'vitest';
import { connectionIssue } from '../creative/graphDraft';
import { GRAPH_NODE_WIDTH, GRAPH_PORT_ROW_HEIGHT, GRAPH_NODE_HEADER_HEIGHT } from '../creative/graphCanvasGeometry';
import type {
  StudioGraphCatalog, StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId,
  StudioGraphEdge, StudioGraphNode, StudioGraphParameters, StudioGraphPort, StudioGraphPortType,
} from '../creative/studioGraphTypes';
import {
  CanvasOpsLocalError, autoLayout, blankLocalCanvasState, canvasEdgeBudget, canvasNodeBudget, canvasPortKey,
  classifyGraphChange, compatibleTargets, createLocalAnnotation, createLocalGroup, explainConnection,
  filterNodes, localCanvasStateIssue, marqueeSelection, nodeSearchIndex, normalizeLocalCanvasState,
  parseCanvasPortKey, pruneLocalCanvasState, removeLocalAnnotation, removeLocalGroup, renameLocalGroup,
  requiredInputGaps, staleReferenceNodeIds, toggleCollapse,
} from './canvasOps';

/* ------------------------------------------------------------------ *
 * 目录与图夹具（本地构造，不发任何请求）
 * ------------------------------------------------------------------ */
const port = (id: string, type: StudioGraphPortType, required = false): StudioGraphPort => ({ id, type, required, multiple: false });
const entry = (id: StudioGraphDefinitionId, inputs: StudioGraphPort[], outputs: StudioGraphPort[]): StudioGraphCatalogDefinition => ({
  id, version: 1, inputs, outputs, parameters_schema: { type: 'object', additionalProperties: false, properties: {} },
  default_parameters: {}, executable: true, model_called: false, blockers: [],
});
const definitions: StudioGraphCatalogDefinition[] = [
  entry('text_input', [], [port('text', 'TEXT')]),
  entry('text_reference', [port('text', 'TEXT', true)], [port('text', 'TEXT')]),
  entry('text_generate', [port('text', 'TEXT', true)], [port('draft', 'DRAFT')]),
  entry('draft_prepare', [port('text', 'TEXT', true), port('direction', 'DIRECTOR_NOTES')], [port('draft', 'DRAFT')]),
  entry('human_review', [port('draft', 'DRAFT', true)], [port('reviewed_draft', 'DRAFT')]),
  entry('director_note', [], [port('direction', 'DIRECTOR_NOTES')]),
  entry('asset_reference', [], [port('asset', 'ASSET_REF')]),
  entry('media_generate', [port('text', 'TEXT'), port('draft', 'DRAFT')], [port('candidate', 'MEDIA_CANDIDATE')]),
  entry('media_review', [port('candidate', 'MEDIA_CANDIDATE', true)], [port('asset', 'ASSET_REF')]),
  entry('image_prompt', [port('references', 'IMAGE_REFERENCES')], [port('prompt', 'IMAGE_PROMPT')]),
  entry('timeline_export', [port('candidate', 'VIDEO_CANDIDATE', true)], [port('candidate', 'VIDEO_CANDIDATE')]),
];
const catalog = (rows: StudioGraphCatalogDefinition[] = definitions): StudioGraphCatalog => ({
  definitions: rows,
  limits: { nodes: 16, edges: 40, definition_bytes: 96000, output_bytes: 64000, graphs: 25, runs: 100, history: 20, runtime_timeout_seconds: 3600, node_timeout_seconds: 5 },
  capabilities: {
    local_execution: true, chapter_required: false, model_execution: true, external_reference_execution: false,
    external_reference_detach: false, binary_cache: false, parallel_execution: false, automatic_retry: false,
    actor_private: true, cache_mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY',
  },
});
const mediaCatalog = (): StudioGraphCatalog => ({ ...catalog(), media_limits: { nodes: 24, generators: 4, history: 80 } });

function node(id: string, definitionId: StudioGraphDefinitionId = 'text_reference', parameters: StudioGraphParameters = {}): StudioGraphNode {
  return { id, definition_id: definitionId, definition_version: 1, enabled: true, position: { x: 24, y: 48 }, parameters };
}
function edge(id: string, source: string, target: string, sourcePort = 'text', targetPort = 'text'): StudioGraphEdge {
  return { id, source_node_id: source, source_port: sourcePort, target_node_id: target, target_port: targetPort };
}
function graph(overrides: Partial<StudioGraphDefinition> = {}): StudioGraphDefinition {
  return {
    schema_version: 1, title: '独立节点图', viewport: { x: 0, y: 0, zoom: 1 }, edges: [], nodes: [node('source', 'text_input')],
    ...overrides,
  };
}
const textGraph = (edges: StudioGraphEdge[] = []): StudioGraphDefinition => graph({
  nodes: [node('source', 'text_input'), node('first'), node('second')], edges,
});

/* ------------------------------------------------------------------ *
 * 目录检索
 * ------------------------------------------------------------------ */
describe('canvas ops · catalogue search and categories', () => {
  it('indexes only the existing catalogue definitions, with labels and declared ports', () => {
    const rows = nodeSearchIndex(catalog());
    expect(rows.map(row => row.id)).toEqual(definitions.map(row => row.id));
    const palette = rows.find(row => row.id === 'draft_prepare')!;
    expect(palette.label).toBe('本地草稿整理');
    expect(palette.inputs.map(item => `${item.id}:${item.type}:${item.required}`)).toEqual(['text:TEXT:true', 'direction:DIRECTOR_NOTES:false']);
    expect(palette.outputs.map(item => item.id)).toEqual(['draft']);
    expect(palette.model_called).toBe(false);
  });

  it('returns an empty index for a missing catalogue and refuses an unknown node type', () => {
    expect(nodeSearchIndex(undefined)).toEqual([]);
    expect(nodeSearchIndex(null)).toEqual([]);
    expect(() => nodeSearchIndex(catalog([entry('not_a_real_node' as StudioGraphDefinitionId, [], [])])))
      .toThrow(CanvasOpsLocalError);
    expect(() => nodeSearchIndex(catalog([entry('text_input', [], []), entry('text_input', [], [])])))
      .toThrow('节点目录出现重复节点类型，请重新读取创作图目录。');
    expect(localCanvasStateIssue({ schema: 'canvasops-local/1', collapsed: [], groups: [], annotations: [], extra: 1 }))
      .toBe('本地画布状态不可用，已按空状态处理。');
  });

  it('ranks an exact machine-code hit first and keeps catalogue order for equal hits', () => {
    const rows = filterNodes(catalog(), 'text_reference');
    expect(rows[0].entry.id).toBe('text_reference');
    expect(rows[0].match).toBe('ID_EXACT');
    const prefix = filterNodes(catalog(), 'text');
    expect(prefix.filter(row => row.entry.id.startsWith('text')).map(row => row.entry.id))
      .toEqual(['text_input', 'text_reference', 'text_generate']);
    expect(prefix[0].match).toBe('ID_PREFIX');
  });

  it('matches every whitespace token and returns nothing when one token is missing', () => {
    expect(filterNodes(catalog(), '整理 必填').map(row => row.entry.id)).toEqual(['draft_prepare']);
    expect(filterNodes(catalog(), '整理 不存在的词')).toEqual([]);
  });

  it('filters by category and fails closed on an unknown category', () => {
    const image = filterNodes(catalog(), '', 'IMAGE');
    expect(image.map(row => row.entry.id)).toContain('image_prompt');
    expect(image.map(row => row.entry.id)).toContain('text_input');
    expect(image.map(row => row.entry.id)).not.toContain('human_review');
    expect(image.find(row => row.entry.id === 'image_prompt')!.entry.category).toBe('IMAGE');
    expect(nodeSearchIndex(catalog()).find(row => row.id === 'text_input')!.category).toBe('TEXT');
    expect(filterNodes(catalog(), '', 'NOPE' as never)).toEqual([]);
    expect(filterNodes(catalog(), '', 'ALL')).toHaveLength(definitions.length);
  });

  it('normalizes oversized or control-character queries instead of guessing', () => {
    expect(filterNodes(catalog(), 'a'.repeat(200))).toEqual([]);
    expect(filterNodes(catalog(), '草\u0000稿').map(row => row.entry.id))
      .toEqual(filterNodes(catalog(), '草 稿').map(row => row.entry.id));
    expect(filterNodes(catalog(), '   ')).toHaveLength(definitions.length);
    expect(filterNodes(catalog(), null as unknown as string)).toHaveLength(definitions.length);
  });

  it('reports the owner node/edge budget and never raises a limit', () => {
    expect(canvasNodeBudget(catalog(), graph()).limit).toBe(16);
    const media = canvasNodeBudget(mediaCatalog(), graph({ schema_version: 3 })).limit;
    expect(media).toBe(24);
    const full = canvasNodeBudget(catalog(), graph({ nodes: Array.from({ length: 16 }, (_, index) => node(`n${index}`, 'text_input')) }));
    expect(full.full).toBe(true);
    expect(full.message).toContain('拆分工作流');
    expect(canvasEdgeBudget(catalog(), graph({ edges: Array.from({ length: 40 }, (_, index) => edge(`e${index}`, 'a', 'b')) })).message)
      .toContain('拆分工作流');
  });
});

/* ------------------------------------------------------------------ *
 * 框选（复用 graphCanvasGeometry）
 * ------------------------------------------------------------------ */
describe('canvas ops · marquee selection', () => {
  const nodes = [node('inside'), node('far'), node('boundary')];
  nodes[0].position = { x: 10, y: 10 };
  nodes[1].position = { x: 2000, y: 2000 };
  nodes[2].position = { x: 400, y: 300 };
  const geometry = (zoom: number, end = { x: 400, y: 300 }) => ({
    start: { x: 0, y: 0 }, end, viewport: { x: 0, y: 0, zoom }, definitions,
  });

  it('returns the nodes whose box intersects the marquee rectangle', () => {
    expect(marqueeSelection(geometry(1), nodes)).toEqual(['inside', 'boundary']);
  });

  it('accounts for zoom exactly like the existing geometry helper', () => {
    const zoomed = [{ ...nodes[0], position: { x: 700, y: 500 } }, { ...nodes[1], position: { x: 900, y: 500 } }];
    expect(marqueeSelection(geometry(0.5), zoomed)).toEqual(['inside']);
  });

  it('treats a click-sized or non-finite marquee as empty rather than guessing', () => {
    expect(marqueeSelection(geometry(1, { x: 0, y: 0 }), nodes)).toEqual([]);
    expect(marqueeSelection({ start: { x: Number.NaN, y: 0 }, end: { x: 10, y: 10 }, viewport: { x: 0, y: 0, zoom: 1 }, definitions }, nodes)).toEqual([]);
    expect(marqueeSelection({ start: { x: 0, y: 0 }, viewport: { x: 0, y: 0, zoom: 1 }, definitions } as never, nodes)).toEqual([]);
    expect(marqueeSelection({ start: { x: 0, y: 0 }, end: { x: 10, y: 10 }, viewport: { x: Number.NaN, y: 0, zoom: 1 }, definitions }, nodes)).toEqual([]);
  });
});

/* ------------------------------------------------------------------ *
 * 自动布局
 * ------------------------------------------------------------------ */
describe('canvas ops · deterministic auto layout', () => {
  const chain = (): StudioGraphDefinition => graph({
    nodes: [node('isolated', 'text_input'), node('a', 'text_input'), node('b'), node('c')],
    edges: [edge('e1', 'a', 'b'), edge('e2', 'b', 'c')],
  });

  it('is stable across runs and changes node positions only', () => {
    const before = chain();
    const once = autoLayout(before), twice = autoLayout(before);
    expect(twice).toEqual(once);
    expect(once.edges).toBe(before.edges);
    expect(once.title).toBe(before.title);
    expect(once.schema_version).toBe(before.schema_version);
    expect(once.viewport).toBe(before.viewport);
    expect(once.nodes.map(row => row.id)).toEqual(before.nodes.map(row => row.id));
    expect(once.nodes.map(row => row.parameters)).toEqual(before.nodes.map(row => row.parameters));
    expect(once.nodes[0].parameters).toBe(before.nodes[0].parameters);
    expect(before.nodes[0].position).toEqual({ x: 24, y: 48 });
    const rowStride = GRAPH_NODE_HEADER_HEIGHT + GRAPH_PORT_ROW_HEIGHT + 48;
    expect(once.nodes.map(row => row.position)).toEqual([
      { x: 0, y: 0 }, { x: 0, y: rowStride }, { x: GRAPH_NODE_WIDTH + 96, y: 0 }, { x: 2 * (GRAPH_NODE_WIDTH + 96), y: 0 },
    ]);
  });

  it('returns a new definition and never mutates the input', () => {
    const before = chain(), snapshot = JSON.stringify(before);
    const after = autoLayout(before);
    expect(after).not.toBe(before);
    expect(JSON.stringify(before)).toBe(snapshot);
  });

  it('is deterministic and bounded on cycles and on unknown option values', () => {
    const cyclic = graph({ nodes: [node('a'), node('b')], edges: [edge('e1', 'a', 'b'), edge('e2', 'b', 'a')] });
    const once = autoLayout(cyclic, { origin: { x: -1_000_000, y: Number.NaN }, column_gap: Number.POSITIVE_INFINITY, row_gap: -50 });
    expect(once).toEqual(autoLayout(cyclic, { origin: { x: -1_000_000, y: Number.NaN }, column_gap: Number.POSITIVE_INFINITY, row_gap: -50 }));
    expect(once.nodes.every(row => Number.isFinite(row.position.x) && Number.isFinite(row.position.y))).toBe(true);
    expect(classifyGraphChange(cyclic, once).verdict).toBe('PRESENTATION');
  });

  it('labels an auto layout draft difference as presentation-only, proven against the classifier', () => {
    const before = chain();
    expect(classifyGraphChange(before, autoLayout(before))).toMatchObject({ verdict: 'PRESENTATION', reasonCodes: ['POSITION_CHANGED'] });
  });
});

/* ------------------------------------------------------------------ *
 * 兼容目标（connectionIssue 是唯一合法性权威）
 * ------------------------------------------------------------------ */
describe('canvas ops · compatible targets defer to connectionIssue', () => {
  const graphForTargets = (edges: StudioGraphEdge[] = []): StudioGraphDefinition => graph({
    nodes: [node('source', 'text_input'), node('ref'), node('prepare', 'draft_prepare'), node('note', 'director_note')],
    edges,
  });

  it('offers only ports declared with the same type, and every verdict equals connectionIssue', () => {
    const definition = graphForTargets();
    const rows = compatibleTargets(definition, catalog(), 'source', 'text');
    expect(rows.map(row => `${row.nodeId}.${row.portId}`)).toEqual(['ref.text', 'prepare.text']);
    expect(rows.every(row => row.legal)).toBe(true);
    for (const row of rows) {
      const probe = edge('probe', 'source', row.nodeId, 'text', row.portId);
      expect(row.issue).toBe(connectionIssue(definition, catalog().definitions, probe) ?? null);
      expect(row.legal).toBe(connectionIssue(definition, catalog().definitions, probe) === undefined);
    }
    expect(rows.every(row => row.portType === 'TEXT')).toBe(true);
  });

  it('never reports an occupied input port as legal, using the owner wording verbatim', () => {
    const definition = graph({
      nodes: [node('source', 'text_input'), node('source2', 'text_input'), node('ref'), node('prepare', 'draft_prepare')],
      edges: [edge('e1', 'source2', 'ref', 'text', 'text')],
    });
    const rows = compatibleTargets(definition, catalog(), 'source', 'text');
    const occupied = rows.find(row => row.nodeId === 'ref')!;
    expect(occupied.occupied).toBe(true);
    expect(occupied.legal).toBe(false);
    expect(occupied.issue).toBe('该输入端口只接受一个连接。');
    expect(occupied.explanation.code).toBe('INPUT_OCCUPIED');
    expect(rows.filter(row => row.legal).map(row => row.nodeId)).toEqual(['prepare']);
  });

  it('lets the owner duplicate-edge wording win over the occupied-port wording, exactly as connectionIssue orders them', () => {
    const definition = graphForTargets([edge('e1', 'source', 'ref', 'text', 'text')]);
    const occupied = compatibleTargets(definition, catalog(), 'source', 'text').find(row => row.nodeId === 'ref')!;
    expect(occupied.issue).toBe('此连接已经存在。');
    expect(occupied.explanation.code).toBe('DUPLICATE_EDGE');
    expect(occupied.legal).toBe(false);
  });

  it('filters the catalogue through graphCatalogForSchema before offering candidates', () => {
    const definition = graph({ schema_version: 2, nodes: [node('review', 'human_review'), node('ref')] });
    expect(catalog().definitions.find(row => row.id === 'human_review')!.outputs.map(item => item.id)).toEqual(['reviewed_draft']);
    expect(compatibleTargets(definition, catalog(), 'review', 'reviewed_draft')).toEqual([]);
    const mediaSchema = graph({ schema_version: 3, nodes: [node('gen', 'media_generate'), node('review', 'media_review')] });
    const rows = compatibleTargets(mediaSchema, catalog(), 'gen', 'candidate');
    expect(rows.map(row => `${row.nodeId}.${row.portId}`)).toEqual(['review.candidate']);
    expect(rows[0].required).toBe(true);
    const imageSchema = graph({ schema_version: 4, nodes: [node('gen', 'media_generate'), node('review', 'media_review')] });
    expect(compatibleTargets(imageSchema, catalog(), 'gen', 'candidate')).toEqual([]);
  });

  it('returns nothing when the source node, port or catalogue is unavailable', () => {
    const definition = graphForTargets();
    expect(compatibleTargets(definition, catalog(), 'missing', 'text')).toEqual([]);
    expect(compatibleTargets(definition, catalog(), 'source', 'nope')).toEqual([]);
    expect(compatibleTargets(definition, undefined, 'source', 'text')).toEqual([]);
  });

  it('lists required input gaps from the owner port declarations and clears them once connected', () => {
    const definition = graphForTargets();
    expect(requiredInputGaps(definition, catalog(), ['ref'])).toEqual([{ nodeId: 'ref', portId: 'text' }]);
    expect(requiredInputGaps(definition, catalog(), ['note'])).toEqual([]);
    expect(requiredInputGaps(graphForTargets([edge('e1', 'source', 'ref', 'text', 'text')]), catalog(), ['ref'])).toEqual([]);
    expect(requiredInputGaps(definition, undefined)).toEqual([]);
  });

  it('decodes the editor port key and refuses anything it cannot prove', () => {
    expect(canvasPortKey('node_1', 'text')).toBe('["node_1","text"]');
    expect(parseCanvasPortKey('["node_1","text"]')).toEqual({ nodeId: 'node_1', portId: 'text' });
    expect(parseCanvasPortKey('node_1.text')).toBeNull();
    expect(parseCanvasPortKey('["node_1"]')).toBeNull();
    expect(parseCanvasPortKey('["node_1","text","extra"]')).toBeNull();
    expect(parseCanvasPortKey(JSON.stringify(['a\u0000b', 'text']))).toBeNull();
    expect(parseCanvasPortKey(7 as unknown as string)).toBeNull();
  });
});

/* ------------------------------------------------------------------ *
 * explainConnection 真值表
 * ------------------------------------------------------------------ */
describe('canvas ops · explainConnection maps owner results without inventing legality', () => {
  it('treats a missing issue as a local pass only, and never claims server authority', () => {
    const legal = explainConnection(undefined);
    expect(legal.code).toBe('CONNECTION_LEGAL');
    expect(legal.category).toBe('LEGAL');
    expect(legal.legal).toBe(true);
    expect(legal.ownerMessage).toBeNull();
    expect(legal.message).toContain('服务端校验');
    expect(explainConnection('').legal).toBe(true);
    expect(explainConnection(null).legal).toBe(true);
  });

  it.each([
    ['端口类型不匹配：TEXT → DRAFT。', 'PORT_TYPE_MISMATCH', 'TYPE_MISMATCH'],
    ['图片候选须连接原媒体审核节点，审核后才输出正式素材。', 'CANDIDATE_REVIEW_REQUIRED', 'UNAPPROVED_CANDIDATE_INPUT'],
    ['视频候选必须通过原媒体审核节点。', 'CANDIDATE_REVIEW_REQUIRED', 'UNAPPROVED_CANDIDATE_INPUT'],
    ['时间线导出候选须连接原媒体审核节点，审核后才可作为正式视频素材。', 'CANDIDATE_REVIEW_REQUIRED', 'UNAPPROVED_CANDIDATE_INPUT'],
    ['先连接原文字模型的 draft 到人工审核，再将该审核节点的 reviewed_draft 连接到媒体 draft；未审核模型提案不能直接进入媒体。', 'UNREVIEWED_PROPOSAL', 'UNAPPROVED_CANDIDATE_INPUT'],
    ['媒体节点的文本与已审核草稿输入互斥，请先明确移除另一条输入连接。', 'EXCLUSIVE_INPUT', 'LOCAL_STRUCTURE'],
    ['该输入端口只接受一个连接。', 'INPUT_OCCUPIED', 'LOCAL_STRUCTURE'],
    ['此连接已经存在。', 'DUPLICATE_EDGE', 'LOCAL_STRUCTURE'],
    ['此连接会形成循环，无法保存。', 'CYCLE', 'LOCAL_STRUCTURE'],
    ['节点不能连接自身。', 'SELF_CONNECTION', 'LOCAL_STRUCTURE'],
    ['请选择真实的输出端口和输入端口。', 'PORT_UNKNOWN', 'LOCAL_STRUCTURE'],
    ['请选择当前图中的两个节点。', 'NODES_MISSING', 'LOCAL_STRUCTURE'],
    ['图片节点需要明确采用图片图 v4。', 'SCHEMA_VERSION_REQUIRED', 'SCHEMA_VERSION_REQUIRED'],
    ['视频节点需要明确采用视频图 v5。', 'SCHEMA_VERSION_REQUIRED', 'SCHEMA_VERSION_REQUIRED'],
    ['时间线剪辑与导出需要明确升级为媒体图 v3。', 'SCHEMA_VERSION_REQUIRED', 'SCHEMA_VERSION_REQUIRED'],
  ])('maps %s', (issue, code, category) => {
    const explanation = explainConnection(issue);
    expect(explanation.code).toBe(code);
    expect(explanation.category).toBe(category);
    expect(explanation.legal).toBe(false);
    expect(explanation.ownerMessage).toBe(issue);
    expect(explanation.message.length).toBeGreaterThan(0);
  });

  it('keeps the port types verbatim and always offers a concrete next step on a mismatch', () => {
    const explanation = explainConnection('端口类型不匹配：MEDIA_CANDIDATE → TEXT。');
    expect(explanation.message).toContain('MEDIA_CANDIDATE → TEXT');
    expect(explanation.hints.join('')).toContain('兼容目标');
  });

  it('never swallows an unrecognized or non-string owner result', () => {
    const unknown = explainConnection('服务端新增了本地不认识的检查。');
    expect(unknown.code).toBe('UNCLASSIFIED_LOCAL_ISSUE');
    expect(unknown.category).toBe('UNKNOWN');
    expect(unknown.legal).toBe(false);
    expect(unknown.message).toContain('服务端新增了本地不认识的检查。');
    const odd = explainConnection({ code: 'X' });
    expect(odd.code).toBe('UNCLASSIFIED_LOCAL_ISSUE');
    expect(odd.legal).toBe(false);
    expect(odd.ownerMessage).toBeNull();
  });

  it('reports stale source bindings and missing required inputs as owner facts, not as a legality verdict', () => {
    const stale = explainConnection(undefined, { staleSourceNodeIds: ['asset_one'] });
    expect(stale.code).toBe('SOURCE_BINDING_STALE');
    expect(stale.category).toBe('STALE_SOURCE_BINDING');
    expect(stale.legal).toBe(true);
    expect(stale.message).toContain('asset_one');
    expect(stale.hints.join('')).toContain('重新绑定');
    const gap = explainConnection(undefined, { missingRequiredInputNodeIds: ['review.candidate'] });
    expect(gap.code).toBe('REQUIRED_INPUT_MISSING');
    expect(gap.category).toBe('MISSING_REQUIRED_INPUT');
    expect(gap.legal).toBe(true);
    const both = explainConnection(undefined, { staleSourceNodeIds: ['a'], missingRequiredInputNodeIds: ['b.c'] });
    expect(both.code).toBe('SOURCE_BINDING_STALE');
    const rejected = explainConnection('此连接会形成循环，无法保存。', { staleSourceNodeIds: ['a'] });
    expect(rejected.code).toBe('CYCLE');
  });

  it('reads stale bindings only from the owner reference states', () => {
    expect(staleReferenceNodeIds([{ node_id: 'a', state: 'STALE' }, { node_id: 'b', state: 'CURRENT' }, { node_id: 'a', state: 'STALE' }]))
      .toEqual(['a']);
    expect(staleReferenceNodeIds(undefined)).toEqual([]);
  });
});

/* ------------------------------------------------------------------ *
 * 变更分类真值表
 * ------------------------------------------------------------------ */
describe('canvas ops · conservative change classification', () => {
  const base = (): StudioGraphDefinition => graph({
    nodes: [node('source', 'text_input', { text: '本地文本' }), node('asset', 'asset_reference', { asset_id: 'asset-one', version: 2, digest: 'a'.repeat(64), kind: 'image' })],
    edges: [edge('e1', 'source', 'asset', 'text', 'asset')],
  });
  const withNodes = (definition: StudioGraphDefinition, mapper: (rows: StudioGraphNode[]) => StudioGraphNode[]) =>
    ({ ...definition, nodes: mapper(definition.nodes) });

  it.each([
    ['an identical reference', () => base(), 'NO_CHANGE'],
    ['a node position', () => withNodes(base(), rows => rows.map((row, index) => index === 0 ? { ...row, position: { x: 900, y: 12 } } : row)), 'POSITION_CHANGED'],
    ['the canvas viewport', () => ({ ...base(), viewport: { x: 120, y: -40, zoom: 1.25 } }), 'VIEWPORT_CHANGED'],
  ])('labels %s as presentation-only', (_label, mutate, code) => {
    const after = mutate();
    const result = classifyGraphChange(base(), after);
    expect(result.verdict).toBe('PRESENTATION');
    expect(result.reasonCodes).toEqual([code]);
    expect(result.localOnly).toBe(true);
  });

  it.each([
    ['an added node', () => withNodes(base(), rows => [...rows, node('third')])],
    ['a removed node', () => withNodes(base(), rows => rows.slice(0, 1))],
    ['a reordered node list', () => withNodes(base(), rows => [rows[1], rows[0]])],
    ['a changed definition type', () => withNodes(base(), rows => rows.map((row, index) => index === 0 ? { ...row, definition_id: 'text_reference' as const } : row))],
    ['a changed definition version', () => withNodes(base(), rows => rows.map((row, index) => index === 0 ? { ...row, definition_version: 2 as never } : row))],
    ['a changed enabled flag', () => withNodes(base(), rows => rows.map((row, index) => index === 0 ? { ...row, enabled: false } : row))],
    ['changed parameters', () => withNodes(base(), rows => rows.map((row, index) => index === 0 ? { ...row, parameters: { text: '改过的文本' } } : row))],
    ['changed source bindings', () => withNodes(base(), rows => rows.map((row, index) => index === 1 ? { ...row, parameters: { ...row.parameters, version: 3 } } : row))],
    ['changed source digests', () => withNodes(base(), rows => rows.map((row, index) => index === 1 ? { ...row, parameters: { ...row.parameters, digest: 'b'.repeat(64) } } : row))],
    ['an unknown node field', () => withNodes(base(), rows => rows.map((row, index) => index === 0 ? { ...row, extra: 'x' } as unknown as StudioGraphNode : row))],
    ['an added edge', () => ({ ...base(), edges: [...base().edges, edge('e2', 'source', 'asset', 'text', 'asset')] })],
    ['a removed edge', () => ({ ...base(), edges: [] })],
    ['a changed edge endpoint', () => ({ ...base(), edges: [{ ...base().edges[0], target_port: 'asset_id' }] })],
    ['a reordered edge list', () => ({ ...base(), edges: [edge('e0', 'source', 'asset', 'text', 'asset'), ...base().edges] })],
    ['a changed schema version', () => ({ ...base(), schema_version: 3 as const })],
    ['a changed title', () => ({ ...base(), title: '另一个标题' })],
    ['an unknown top level field', () => ({ ...base(), notes: 'x' } as unknown as StudioGraphDefinition)],
  ])('labels %s as generation affecting', (_label, mutate) => {
    const result = classifyGraphChange(base(), mutate());
    expect(result.verdict).toBe('GENERATION_AFFECTING');
    expect(result.reasonCodes.length).toBeGreaterThan(0);
    expect(result.messages.length).toBe(result.reasonCodes.length);
  });

  it('is conservative on anything it cannot compare', () => {
    expect(classifyGraphChange(undefined, base())).toMatchObject({ verdict: 'GENERATION_AFFECTING', reasonCodes: ['NOT_COMPARABLE'] });
    expect(classifyGraphChange(base(), undefined)).toMatchObject({ verdict: 'GENERATION_AFFECTING', reasonCodes: ['NOT_COMPARABLE'] });
    expect(classifyGraphChange(null as unknown as StudioGraphDefinition, base()).verdict).toBe('GENERATION_AFFECTING');
    expect(classifyGraphChange({} as StudioGraphDefinition, base()).verdict).toBe('GENERATION_AFFECTING');
    const broken = { ...base(), nodes: 'nope' } as unknown as StudioGraphDefinition;
    expect(classifyGraphChange(base(), broken).verdict).toBe('GENERATION_AFFECTING');
  });

  it('mixes reasons deterministically and keeps a position change alongside a parameter change generation affecting', () => {
    const after = withNodes(base(), rows => rows.map((row, index) => index === 0
      ? { ...row, position: { x: 1, y: 1 }, parameters: { text: 'x' } } : row));
    const result = classifyGraphChange(base(), after);
    expect(result.verdict).toBe('GENERATION_AFFECTING');
    expect(result.reasonCodes).toEqual(['POSITION_CHANGED', 'NODE_PARAMETERS_CHANGED']);
    expect(classifyGraphChange(base(), after)).toEqual(result);
  });
});

/* ------------------------------------------------------------------ *
 * 会话内呈现状态
 * ------------------------------------------------------------------ */
describe('canvas ops · session-local grouping, annotation and collapse', () => {
  it('starts from a validated blank structure and round-trips through JSON', () => {
    const blank = blankLocalCanvasState();
    expect(blank).toEqual({ schema: 'canvasops-local/1', collapsed: [], groups: [], annotations: [] });
    expect(localCanvasStateIssue(blank)).toBeUndefined();
    const withGroup = createLocalGroup(blank, 'group_a', '第一组', ['node_a', 'node_b']).state;
    expect(localCanvasStateIssue(JSON.parse(JSON.stringify(withGroup)))).toBeUndefined();
    expect(normalizeLocalCanvasState(withGroup).state).toEqual(withGroup);
  });

  it('rejects unbounded, control-character or duplicated local content without dropping it silently', () => {
    expect(localCanvasStateIssue({ schema: 'canvasops-local/1', collapsed: [], groups: [], annotations: [], extra: true })).toBeDefined();
    expect(localCanvasStateIssue({ schema: 'other/1', collapsed: [], groups: [], annotations: [] })).toBeDefined();
    expect(localCanvasStateIssue({ schema: 'canvasops-local/1', collapsed: ['node a'], groups: [], annotations: [] })).toBeDefined();
    expect(localCanvasStateIssue({ schema: 'canvasops-local/1', collapsed: ['node_a', 'node_a'], groups: [], annotations: [] })).toBeDefined();
    expect(createLocalGroup(blankLocalCanvasState(), 'g', 'x'.repeat(61), []).issue).toContain('1–60');
    expect(createLocalAnnotation(blankLocalCanvasState(), 'a1', '坏\u0000文本', null).issue).toContain('1–400');
    const normalized = normalizeLocalCanvasState({ schema: 'wrong', collapsed: [], groups: [], annotations: [] });
    expect(normalized.state).toEqual(blankLocalCanvasState());
    expect(normalized.issue).toBeDefined();
  });

  it('explains the local limit and suggests splitting the workflow instead of raising it', () => {
    let state = blankLocalCanvasState();
    for (let index = 0; index < 24; index += 1) state = createLocalGroup(state, `g${index}`, `组 ${index}`, []).state;
    const blocked = createLocalGroup(state, 'g99', '溢出组', []);
    expect(blocked.state.groups).toHaveLength(24);
    expect(blocked.issue).toContain('拆分工作流');
    expect(blocked.issue).toContain('不会被抬高');
    let annotations = blankLocalCanvasState();
    for (let index = 0; index < 64; index += 1) annotations = createLocalAnnotation(annotations, `a${index}`, '标注', null).state;
    expect(createLocalAnnotation(annotations, 'a99', '溢出', null).issue).toContain('拆分工作流');
  });

  it('toggles collapse, renames and removes groups, and prunes dangling references', () => {
    const blank = blankLocalCanvasState();
    const collapsed = toggleCollapse(blank, 'node_a').state;
    expect(collapsed.collapsed).toEqual(['node_a']);
    expect(toggleCollapse(collapsed, 'node_a').state.collapsed).toEqual([]);
    expect(toggleCollapse(blank, 'bad id!').issue).toBeDefined();
    const grouped = createLocalGroup(createLocalGroup(blank, 'g1', '组一', ['node_a', 'node_b']).state, 'g2', '组二', ['node_c']).state;
    expect(renameLocalGroup(grouped, 'g1', '组一改名').state.groups[0].label).toBe('组一改名');
    expect(renameLocalGroup(grouped, 'nope', 'x').issue).toBeDefined();
    expect(removeLocalGroup(grouped, 'g1').state.groups.map(row => row.id)).toEqual(['g2']);
    const annotated = createLocalAnnotation(grouped, 'a1', '这里是标注', 'node_c').state;
    expect(annotated.annotations[0].anchor_node_id).toBe('node_c');
    expect(removeLocalAnnotation(annotated, 'a1').state.annotations).toEqual([]);
    const pruned = pruneLocalCanvasState(annotated, ['node_c']);
    expect(pruned.groups[0].node_ids).toEqual([]);
    expect(pruned.groups[1].node_ids).toEqual(['node_c']);
    expect(pruned.annotations[0].anchor_node_id).toBe('node_c');
    expect(pruneLocalCanvasState(createLocalAnnotation(blank, 'a2', '锚点会消失', 'node_z').state, []).annotations[0].anchor_node_id).toBeNull();
    expect(createLocalGroup(blank, 'g1', '重复', []).issue).toBeUndefined();
    expect(createLocalGroup(createLocalGroup(blank, 'g1', '重复', []).state, 'g1', '重复', []).issue).toContain('已存在');
  });

  it('keeps the local structure out of the persisted graph contract', () => {
    const serialized = JSON.stringify(graph({ nodes: [node('a')] }));
    expect(serialized).not.toContain('canvasops-local');
    expect(Object.keys(blankLocalCanvasState())).toEqual(['schema', 'collapsed', 'groups', 'annotations']);
  });
});
