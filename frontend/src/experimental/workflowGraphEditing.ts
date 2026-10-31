import type { AuthoredWorkflow } from './declarativeAgentsClient';

type Edge = AuthoredWorkflow['edges'][number];
export type CheckpointEdit = { kind: 'insert'; source: string; target: string } | { kind: 'remove'; id: string };
export type GraphEditPreview = { definition: AuthoredWorkflow; removed: Edge[]; added: Edge[]; nodeId: string; kind: CheckpointEdit['kind'] };
const fail = (message: string): never => { throw new Error(message); };
const pair = (edge: Edge) => JSON.stringify([edge.source, edge.target]);

/** Local topology checks only. The original server still validates every save. */
function checkGraph(value: AuthoredWorkflow) {
  const { nodes, edges } = value;
  if (nodes.length < 3 || nodes.length > 16 || edges.length < 2 || edges.length > 40 ||
      !Number.isInteger(value.agent.max_steps) || value.agent.max_steps < 3 || value.agent.max_steps > 16 || nodes.length > value.agent.max_steps) fail('节点或连接超出原图与步骤预算；请在原编辑器核对。');
  const known = new Set(nodes.map(node => node.id));
  if (known.size !== nodes.length || nodes.some(node => !/^[a-zA-Z][a-zA-Z0-9_-]{0,39}$/.test(node.id))) fail('节点 ID 不唯一或格式不受支持。');
  const incoming = new Map(nodes.map(node => [node.id, [] as string[]]));
  const outgoing = new Map(nodes.map(node => [node.id, [] as string[]]));
  const seen = new Set<string>();
  for (const edge of edges) {
    if (Object.keys(edge).sort().join(',') !== 'source,target' || !known.has(edge.source) || !known.has(edge.target)) fail('连接结构或目标不受支持；不会丢弃额外字段。');
    if (edge.source === edge.target || seen.has(pair(edge))) fail('存在自连接或重复连接；请先用原连接编辑器核对。');
    seen.add(pair(edge)); incoming.get(edge.target)!.push(edge.source); outgoing.get(edge.source)!.push(edge.target);
  }
  const roots = nodes.filter(node => !incoming.get(node.id)!.length).map(node => node.id);
  if (roots.length !== 1) fail('只支持已有的单根连通 DAG。');
  const degrees = new Map([...incoming].map(([id, values]) => [id, values.length]));
  const ready = [...roots], order: string[] = [];
  while (ready.length) {
    const id = ready.shift()!; order.push(id);
    for (const target of outgoing.get(id)!) { const degree = degrees.get(target)! - 1; degrees.set(target, degree); if (!degree) ready.push(target); }
  }
  if (order.length !== nodes.length) fail('图包含环路；不会猜测重新连接。');
  const gates = nodes.filter(node => node.type === 'manual_approval'), artifacts = nodes.filter(node => node.type === 'review_artifact');
  if (gates.length !== 1 || artifacts.length !== 1) fail('原图必须保留唯一人工审核与末尾审核材料节点。');
  const gate = gates[0].id, artifact = artifacts[0].id;
  if (order.at(-2) !== gate || order.at(-1) !== artifact || incoming.get(artifact)!.length !== 1 || incoming.get(artifact)![0] !== gate ||
      outgoing.get(gate)!.length !== 1 || outgoing.get(gate)![0] !== artifact) fail('人工审核必须直接连接末尾审核材料，且所有分支先汇入审核。');
  const ancestors = new Set([gate]);
  for (const id of [...order].reverse()) if (ancestors.has(id)) for (const source of incoming.get(id)!) ancestors.add(source);
  if (ancestors.size !== nodes.length - 1) fail('所有分支必须先汇入人工审核。');
  return { incoming, outgoing };
}

export function previewCheckpointEdit(value: AuthoredWorkflow, edit: CheckpointEdit): GraphEditPreview {
  const { incoming, outgoing } = checkGraph(value);
  // Clone the entire authored definition; do not reconstruct only execution fields.
  const definition: AuthoredWorkflow = JSON.parse(JSON.stringify(value));
  let removed: Edge[], added: Edge[], nodeId: string;
  if (edit.kind === 'insert') {
    const index = value.edges.findIndex(edge => edge.source === edit.source && edge.target === edit.target);
    if (index < 0) fail('所选连接已不存在，请重新选择。');
    if (value.nodes.find(node => node.id === edit.source)?.type === 'manual_approval') fail('不能在人工审核与末尾审核材料之间插入检查点。');
    let number = 1; do { nodeId = 'checkpoint' + number++; } while (value.nodes.some(node => node.id === nodeId));
    removed = [definition.edges[index]]; added = [{ source: edit.source, target: nodeId }, { source: nodeId, target: edit.target }];
    definition.edges.splice(index, 1, ...added);
    definition.nodes.splice(definition.nodes.findIndex(node => node.id === edit.target), 0, { id: nodeId, type: 'checkpoint', name: '本地检查点' });
  } else {
    nodeId = edit.id;
    if (value.nodes.find(node => node.id === nodeId)?.type !== 'checkpoint') fail('只可移除自动检查点；人工审核与其他节点保持原样。');
    const before = incoming.get(nodeId)!, after = outgoing.get(nodeId)!;
    if (before.length !== 1 || after.length !== 1) fail('只可衔接恰好一条入边与一条出边的检查点；不会猜测多路连接。');
    const bridge = { source: before[0], target: after[0] };
    if (bridge.source === bridge.target || definition.edges.some(edge => pair(edge) === pair(bridge))) fail('衔接会产生自连接或重复连接；请在原连接编辑器明确处理。');
    removed = definition.edges.filter(edge => edge.source === nodeId || edge.target === nodeId); added = [bridge];
    const first = definition.edges.findIndex(edge => edge.source === nodeId || edge.target === nodeId);
    definition.edges = definition.edges.filter(edge => edge.source !== nodeId && edge.target !== nodeId);
    definition.edges.splice(first, 0, bridge); definition.nodes = definition.nodes.filter(node => node.id !== nodeId);
  }
  checkGraph(definition);
  return { definition, removed, added, nodeId, kind: edit.kind };
}
