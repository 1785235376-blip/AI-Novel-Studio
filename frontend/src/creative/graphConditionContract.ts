import { ApiError } from '../api';
import { GRAPH_CONDITIONS_CONTRACT, GRAPH_CONDITIONS_IDS, type GraphConditionalRuntime, type GraphConditionPredicate, type GraphConditionPlan, type StudioGraphDefinition, type StudioGraphNode, type StudioGraphRun, type StudioGraphParameterSchema, GRAPH_CONDITIONS_CACHE } from './studioGraphTypes';
export function conditionInvalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_GRAPH_CONDITION_RESPONSE_INVALID', message: '条件图、分支或原运行证明不一致，请读取原保存版本核对。' }); }
const obj = (v: unknown): Record<string, unknown> => v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : conditionInvalid();
export function conditionClosed(v: unknown, keys: string[]) { const row = obj(v); if (Object.keys(row).length !== keys.length || keys.some(key => !Object.hasOwn(row, key))) conditionInvalid(); return row; }
export function checkedConditionParameters(value: unknown): { predicate: GraphConditionPredicate } {
  const row = conditionClosed(value, ['predicate']), p = obj(row.predicate);
  if (p.kind === 'boolean') { conditionClosed(p, ['kind', 'value']); if (typeof p.value !== 'boolean') conditionInvalid(); return { predicate: { kind: 'boolean', value: p.value } }; }
  conditionClosed(p, ['kind', 'value', 'equals']); if (p.kind !== 'enum' || typeof p.value !== 'string' || !['A', 'B'].includes(p.value) || typeof p.equals !== 'string' || !['A', 'B'].includes(p.equals)) conditionInvalid();
  return { predicate: { kind: 'enum', value: p.value as 'A' | 'B', equals: p.equals as 'A' | 'B' } };
}
export function closedConditionalFields(value: unknown) {
  const r = obj(value); conditionClosed(r, ['schema_version', 'title', 'nodes', 'edges', 'viewport', ...(r.presentation === undefined ? [] : ['presentation'])]);
  if (!Array.isArray(r.nodes) || !Array.isArray(r.edges)) conditionInvalid();
  for (const value of r.nodes) { const n = conditionClosed(value, ['id', 'definition_id', 'definition_version', 'enabled', 'position', 'parameters']); conditionClosed(n.position, ['x', 'y']); const keys: Record<string, string[]> = { text_input: ['text'], local_condition: ['predicate'], text_reference: [], draft_prepare: [], manual_transform: ['result'], human_review: [] }; if (typeof n.definition_id !== 'string' || !keys[n.definition_id]) conditionInvalid(); conditionClosed(n.parameters, keys[n.definition_id]); }
  for (const value of r.edges) conditionClosed(value, ['id', 'source_node_id', 'source_port', 'target_node_id', 'target_port']);
  conditionClosed(r.viewport, ['x', 'y', 'zoom']);
}
/** Validate the saved finite topology; this does not advance or execute a node. */
export function conditionShape(definition: StudioGraphDefinition) {
  if (definition.schema_version !== 7 || definition.nodes.length > 16 || definition.nodes.some(n => !n.enabled || !GRAPH_CONDITIONS_IDS.some(id => id === n.definition_id))) conditionInvalid();
  const nodes = new Map(definition.nodes.map(n => [n.id, n])), sources = definition.nodes.filter(n => n.definition_id === 'text_input'), conditions = definition.nodes.filter(n => n.definition_id === 'local_condition');
  if (nodes.size !== definition.nodes.length || sources.length !== 1 || conditions.length !== 1) conditionInvalid();
  const incoming = new Map(definition.nodes.map(n => [n.id, definition.edges.filter(e => e.target_node_id === n.id)])), outgoing = new Map(definition.nodes.map(n => [n.id, definition.edges.filter(e => e.source_node_id === n.id)]));
  const source = sources[0], condition = conditions[0], link = outgoing.get(source.id)!;
  if (incoming.get(source.id)!.length || link.length !== 1 || link[0].target_node_id !== condition.id || link[0].source_port !== 'text' || link[0].target_port !== 'text' || incoming.get(condition.id)!.length !== 1) conditionInvalid();
  const roots = outgoing.get(condition.id)!;
  if (roots.length !== 2 || new Set(roots.map(e => e.source_port)).size !== 2 || roots.some(e => !['when_true', 'when_false'].includes(e.source_port))) conditionInvalid();
  const seen = new Set([source.id, condition.id]), arms: Record<string, string[]> = {};
  for (const root of roots) {
    const path: string[] = []; let edge = root;
    for (;;) {
      const node = nodes.get(edge.target_node_id); if (!node || seen.has(node.id) || incoming.get(node.id)!.length !== 1) conditionInvalid();
      seen.add(node.id); path.push(node.id); const next = outgoing.get(node.id)!;
      if (node.definition_id === 'human_review') { if (next.length || edge.target_port !== 'draft') conditionInvalid(); break; }
      if (!['text_reference', 'draft_prepare', 'manual_transform'].includes(node.definition_id) || edge.target_port !== 'text' || next.length !== 1) conditionInvalid(); edge = next[0];
    }
    arms[root.source_port] = path;
  }
  if (seen.size !== nodes.size) conditionInvalid();
  // Original WorkflowRun stable Kahn order: saved node/edge order, never locale sorting.
  const degrees = new Map(definition.nodes.map(n => [n.id, incoming.get(n.id)!.length])), ready = definition.nodes.filter(n => !degrees.get(n.id)).map(n => n.id), order: string[] = [];
  while (ready.length) { const id = ready.shift()!; order.push(id); for (const edge of outgoing.get(id)!) { const count = degrees.get(edge.target_node_id)! - 1; degrees.set(edge.target_node_id, count); if (!count) ready.push(edge.target_node_id); } }
  if (order.length !== nodes.size) conditionInvalid();
  const predicate = checkedConditionParameters(condition.parameters).predicate, selected = (predicate.kind === 'boolean' ? predicate.value : predicate.value === predicate.equals) ? 'when_true' : 'when_false';
  const active = new Set([source.id, condition.id, ...arms[selected]]);
  return { source, condition, selected: selected as 'when_true' | 'when_false', arms, order, active: order.filter(id => active.has(id)), skipped: order.filter(id => !active.has(id)) };
}
// Python store.canonical uses floats for Position/Viewport even at integral values.
// The only floats in this closed schema are x/y/zoom, including note positions.
export function conditionCanonical(value: unknown, key = ''): string {
  if (typeof value === 'number' && ['x', 'y', 'zoom'].includes(key)) {
    if (!Number.isFinite(value)) conditionInvalid(); if (Object.is(value, -0)) return '-0.0';
    if (Number.isInteger(value)) return value.toFixed(1);
    if (Math.abs(value) < 0.0001) { const [m, e] = value.toExponential().split('e'); return m + 'e' + (Number(e) < 0 ? '-' : '+') + String(Math.abs(Number(e))).padStart(2, '0'); }
  }
  if (Array.isArray(value)) return '[' + value.map(v => conditionCanonical(v)).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + conditionCanonical((value as Record<string, unknown>)[k], k)).join(',') + '}';
  if (value !== null && !['string', 'number', 'boolean'].includes(typeof value)) conditionInvalid();
  return JSON.stringify(value);
}
export const conditionSame = (a: unknown, b: unknown) => conditionCanonical(a) === conditionCanonical(b);
export async function conditionHash(value: unknown) { const bytes = new TextEncoder().encode(conditionCanonical(value)); if (bytes.length > 128000 || !crypto.subtle) conditionInvalid(); return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v => v.toString(16).padStart(2, '0')).join(''); }
export async function checkedConditionPlan(value: unknown, definition: StudioGraphDefinition): Promise<GraphConditionPlan> {
  const p = conditionClosed(value, ['contract', 'condition_node_id', 'selected_port', 'active_node_ids', 'skipped_node_ids', 'plan_digest']), shape = conditionShape(definition);
  const expected: Omit<GraphConditionPlan, 'plan_digest'> = { contract: GRAPH_CONDITIONS_CONTRACT, condition_node_id: shape.condition.id, selected_port: shape.selected, active_node_ids: shape.active, skipped_node_ids: shape.skipped };
  const { plan_digest: _digest, ...wire } = p;
  if (!conditionSame(wire, expected) || p.plan_digest !== await conditionHash([definition, expected])) conditionInvalid();
  return { ...expected, plan_digest: p.plan_digest as string };
}
export function buildConditionalStarter(title = '本地条件分支'): StudioGraphDefinition {
  const node = (id: string, kind: StudioGraphNode['definition_id'], x: number, y: number, parameters: StudioGraphNode['parameters'] = {}): StudioGraphNode => ({ id, definition_id: kind, definition_version: 1, enabled: true, position: { x, y }, parameters });
  const edge = (id: string, source: string, port: string, target: string, input: string) => ({ id, source_node_id: source, source_port: port, target_node_id: target, target_port: input });
  return { schema_version: 7, title, viewport: { x: 0, y: 0, zoom: 1 }, nodes: [node('input', 'text_input', 40, 240, { text: '' }), node('condition', 'local_condition', 300, 240, { predicate: { kind: 'boolean', value: true } }), node('yes', 'manual_transform', 560, 100, { result: '' }), node('yes_review', 'human_review', 820, 100), node('no', 'draft_prepare', 560, 400), node('no_review', 'human_review', 820, 400)], edges: [edge('in', 'input', 'text', 'condition', 'text'), edge('yes', 'condition', 'when_true', 'yes', 'text'), edge('yes_review', 'yes', 'draft', 'yes_review', 'draft'), edge('no', 'condition', 'when_false', 'no', 'text'), edge('no_review', 'no', 'draft', 'no_review', 'draft')] };
}

/** Recognize the exact finite discriminated schema; never accept arbitrary JSON schemas. */
const predicateSchema = {"$defs":{"BooleanCondition":{"additionalProperties":false,"properties":{"kind":{"const":"boolean","title":"Kind","type":"string"},"value":{"title":"Value","type":"boolean"}},"required":["kind","value"],"title":"BooleanCondition","type":"object"},"EnumCondition":{"additionalProperties":false,"properties":{"kind":{"const":"enum","title":"Kind","type":"string"},"value":{"enum":["A","B"],"title":"Value","type":"string"},"equals":{"enum":["A","B"],"title":"Equals","type":"string"}},"required":["kind","value","equals"],"title":"EnumCondition","type":"object"}},"additionalProperties":false,"properties":{"predicate":{"discriminator":{"mapping":{"boolean":"#/$defs/BooleanCondition","enum":"#/$defs/EnumCondition"},"propertyName":"kind"},"oneOf":[{"$ref":"#/$defs/BooleanCondition"},{"$ref":"#/$defs/EnumCondition"}],"title":"Predicate"}},"required":["predicate"],"title":"ConditionParameters","type":"object"};
export function checkedConditionSchema(value: unknown): StudioGraphParameterSchema {
  if (!conditionSame(value, predicateSchema)) conditionInvalid();
  return { type: 'object', additionalProperties: false, required: ['predicate'], properties: { predicate: { type: 'object', title: '布尔值或 A/B 等值条件' } } };
}
/** Proof validation against the observed saved graph. No node is dispatched here. */
export async function checkedConditionalRuntime(raw: unknown, run: StudioGraphRun, definition?: StudioGraphDefinition): Promise<GraphConditionalRuntime> {
  const wire = obj(raw), r = conditionClosed(wire.conditional_runtime, ['contract', 'cache_enabled', 'plan', 'skipped_dispatches', 'skipped_outputs']);
  if (r.contract !== GRAPH_CONDITIONS_CONTRACT || r.cache_enabled !== false || run.cache.mode !== GRAPH_CONDITIONS_CACHE || run.cache.hits !== 0
    || wire.model_runtime !== undefined || wire.media_runtime !== undefined || wire.local_subgraph_runtime !== undefined || wire.asset_output !== undefined || run.model_called) conditionInvalid();
  const states = obj(wire.node_states), hidden = run.stale || ['FAILED', 'CANCELLED', 'REJECTED'].includes(run.status);
  // Even redacted replies cannot smuggle private data back via dropped unknown fields.
  for (const state of Object.values(states)) { const s = conditionClosed(state, ['status', 'reviewed', 'output', 'error']); if (typeof s.reviewed !== 'boolean' || (hidden || !run.reviewed) && s.output !== null) conditionInvalid(); }
  if (hidden) {
    if (r.plan !== null || r.skipped_dispatches !== null || r.skipped_outputs !== null || wire.review !== null) conditionInvalid();
    return { contract: GRAPH_CONDITIONS_CONTRACT, cache_enabled: false as const, plan: null, skipped_dispatches: null, skipped_outputs: null };
  }
  if (!definition || r.skipped_dispatches !== 0 || r.skipped_outputs !== 0) conditionInvalid();
  const plan = await checkedConditionPlan(r.plan, definition), shape = conditionShape(definition);
  if (Object.keys(states).length !== definition.nodes.length || definition.nodes.some(n => !Object.hasOwn(states, n.id))) conditionInvalid();
  const terminalReview = shape.arms[shape.selected].at(-1)!;
  if (run.reviewed !== (run.status === 'SUCCEEDED') || run.current_node_id !== null && !shape.active.includes(run.current_node_id)) conditionInvalid();
  for (const node of definition.nodes) {
    const state = obj(states[node.id]), active = shape.active.includes(node.id);
    if (!active) { if (!conditionSame(state, { status: 'SKIPPED', reviewed: false, output: null, error: { code: 'CREATIVE_GRAPH_BRANCH_NOT_SELECTED' } })) conditionInvalid(); continue; }
    if (state.status === 'SKIPPED' || state.reviewed !== run.reviewed || state.error !== null) conditionInvalid();
    if (run.reviewed && state.status !== 'SUCCEEDED') conditionInvalid();
    if (state.output !== null) {
      if (node.definition_id === 'human_review') conditionInvalid();
      const keys = node.definition_id === 'local_condition' ? [shape.selected] : node.definition_id === 'text_input' || node.definition_id === 'text_reference' ? ['text'] : ['draft'];
      const output = conditionClosed(state.output, keys);
      if (keys[0] === 'text' && output.text !== shape.source.parameters.text || node.definition_id === 'local_condition' && output[shape.selected] !== shape.source.parameters.text) conditionInvalid();
      if (output.draft !== undefined) {
        const d = obj(output.draft); conditionClosed(d, node.definition_id === 'manual_transform' ? ['origin', 'text'] : ['origin', 'text', 'plan']);
        if (node.definition_id === 'manual_transform' ? d.origin !== 'MANUAL' || d.text !== node.parameters.result : d.origin !== 'USER_SUPPLIED' || d.text !== shape.source.parameters.text) conditionInvalid();
        if (node.definition_id === 'draft_prepare' && !validSourcePlan(d.plan, shape.source.parameters.text!)) conditionInvalid();
        if (!conditionSame(output, run.node_states[node.id]?.output)) conditionInvalid();
      }
    } else if (run.reviewed && node.definition_id !== 'human_review') conditionInvalid();
  }
  if (wire.review !== null) {
    const review = conditionClosed(wire.review, ['node_id', 'draft', 'output_digest']);
    if (run.status !== 'WAITING_APPROVAL' || review.node_id !== terminalReview || run.current_node_id !== terminalReview || obj(states[terminalReview]).status !== 'WAITING_APPROVAL'
      || await conditionHash([run.id, terminalReview, run.graph_version, review.draft]) !== review.output_digest || !conditionSame(review.draft, run.review?.draft)) conditionInvalid();
    const edge = definition.edges.find(e => e.target_node_id === terminalReview)!, parent = definition.nodes.find(n => n.id === edge.source_node_id)!;
    const d = obj(review.draft); conditionClosed(d, parent.definition_id === 'manual_transform' ? ['origin', 'text'] : ['origin', 'text', 'plan']);
    if (parent.definition_id === 'manual_transform' ? d.origin !== 'MANUAL' || d.text !== parent.parameters.result : d.origin !== 'USER_SUPPLIED' || d.text !== shape.source.parameters.text) conditionInvalid();
    if (parent.definition_id === 'draft_prepare' && !validSourcePlan(d.plan, shape.source.parameters.text!)) conditionInvalid();
  } else if (run.status === 'WAITING_APPROVAL') conditionInvalid();
  if (run.status === 'WAITING_APPROVAL' || run.reviewed) {
    if (shape.active.some(id => id !== terminalReview && obj(states[id]).status !== 'SUCCEEDED') || run.cache.misses !== shape.active.length - 1) conditionInvalid();
  }
  return { contract: GRAPH_CONDITIONS_CONTRACT, cache_enabled: false as const, plan, skipped_dispatches: 0, skipped_outputs: 0 };
}

function validSourcePlan(value: unknown, source: string): boolean {
  // Match the original Python recipe's Unicode splitlines/strip rules, including
  // preserving a literal BOM (JavaScript trim would silently remove it).
  const space = '[\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000]';
  const strip = new RegExp('^' + space + '+|' + space + '+$', 'g');
  const lines = source.split(/\r\n|[\n\r\v\f\u001c-\u001e\u0085\u2028\u2029]/).map(line => line.replace(strip, '')).filter(Boolean);
  return lines.length <= 100 && conditionSame(value, lines.map((beat, i) => ({ sequence: i + 1, beat })));
}
