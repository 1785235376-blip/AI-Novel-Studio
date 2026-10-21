import { expect, it } from 'vitest';
import { captureCanvasAudioWorkflowTemplate } from './canvasAudioWorkflowTemplate';
import { templateGraph, templateOwner } from './canvasAudioWorkflowTemplate.testFixtures';
const capture = (graph = templateGraph(), node = 'trim', owner = templateOwner) => captureCanvasAudioWorkflowTemplate(graph, node, owner);
const frozen = <T,>(value: T): T => { if (value && typeof value === 'object') { Object.freeze(value); Object.values(value).forEach(frozen); } return value; };

it('captures the original Graph namespace, exact saved pin and supported interval without mutation', () => {
  const graph = frozen(templateGraph()), before = JSON.stringify(graph), result = capture(graph);
  expect(result).toEqual({ contract: 'studio-canvas-audio-template/1', graph_id: graph.id, graph_version: 3,
    definition_digest: graph.definition_digest, execution_digest: graph.execution_digest, node_id: 'trim', parameters: { in_ms: 100, out_ms: 900 } });
  expect(JSON.stringify(graph)).toBe(before); expect(Object.isFrozen(result)).toBe(true); expect(Object.isFrozen(result.parameters)).toBe(true);
  expect(result).not.toHaveProperty('owner'); expect(result).not.toHaveProperty('source_snapshots'); expect(result).not.toHaveProperty('request_id');
});
it('uses original omitted trim defaults and returns a detached immutable parameter copy', () => {
  const graph = templateGraph(), result = capture(graph, 'trim_other');
  graph.definition.nodes[2].parameters.parameters!.in_ms = 777;
  expect(result.parameters).toEqual({ in_ms: 200, out_ms: 800 });
});
it('accepts only original saved Graph absent-parameter nulls without altering the recorded input or pin', () => {
  const graph = templateGraph(), values = graph.definition.nodes[1].parameters.parameters!;
  Object.assign(values, { width: null, height: null, steps: null, seed: null, cfg: null, negative_prompt: null, size: null,
    quality: null, duration_seconds: null, frame_rate: null, voice_id: null, speech_rate: null });
  const before = JSON.stringify(graph), result = capture(frozen(graph));
  expect(result.parameters).toEqual({ in_ms: 100, out_ms: 900 }); expect(result.definition_digest).toBe(graph.definition_digest);
  expect(JSON.stringify(graph)).toBe(before);
});
it('allows a matching collaboration scope with the original actor workspace', () => {
  const graph = templateGraph(), owner = { ...templateOwner, mode: 'collaboration' as const, actorWorkspaceId: 'workspace', workspaceId: 'workspace', storylineId: 'story', branchId: 'branch' };
  graph.scope = { mode: 'collaboration', novel_id: owner.projectId, workspace_id: 'workspace', storyline_id: 'story', branch_id: 'branch' };
  expect(capture(graph, 'trim', owner).node_id).toBe('trim');
  expect(() => capture(graph, 'trim', { ...owner, branchId: 'foreign' })).toThrow();
});
it.each(['schema2', 'schema4', 'missing-node', 'node-name', 'disabled', 'wrong-kind', 'wrong-operation', 'provider', 'model', 'cloud', 'prompt', 'gain-low', 'fade-too-long', 'extra', 'null-extra', 'missing-in', 'null-out', 'bool-in', 'fraction', 'negative', 'reversed', 'duration', 'absolute-range', 'duplicate-node', 'edge', 'cycle', 'missing-reference', 'stale-source', 'unavailable-source', 'duplicate-reference', 'unknown-reference', 'readonly', 'project', 'scope', 'local-branch', 'version', 'definition-digest', 'execution-digest', 'graph-id', 'incarnation', 'actor', 'owner-branch', 'owner-workspace'])('refuses %s through the original closed Graph and owner contracts', mode => {
  const graph = templateGraph(), owner = { ...templateOwner }, node = graph.definition.nodes[1], values = node.parameters.parameters!;
  let nodeId = 'trim';
  switch (mode) {
    case 'schema2': graph.definition.schema_version = 2; break;
    case 'schema4': graph.definition.schema_version = 4; break;
    case 'missing-node': nodeId = 'missing'; break;
    case 'node-name': nodeId = '../trim'; break;
    case 'disabled': node.enabled = false; break;
    case 'wrong-kind': nodeId = 'source'; break;
    case 'wrong-operation': node.parameters.operation_id = 'm8.audio.effects'; break;
    case 'provider': node.parameters.provider_id = 'provider'; break;
    case 'model': node.parameters.model_id = 'model'; break;
    case 'cloud': node.parameters.allow_cloud = true; break;
    case 'prompt': node.parameters.prompt = 'generate'; break;
    case 'gain-low': values.gain_db = -61; break;
    case 'fade-too-long': values.fade_in_ms = 801; break;
    case 'extra': (node.parameters as any).secret = 'unsupported'; break;
    case 'null-extra': values.gain_db = null; break;
    case 'missing-in': delete values.in_ms; break;
    case 'null-out': values.out_ms = null; break;
    case 'bool-in': (values as any).in_ms = true; break;
    case 'fraction': values.in_ms = 0.5; break;
    case 'negative': values.in_ms = -1; break;
    case 'reversed': values.out_ms = 50; break;
    case 'duration': values.out_ms = 120101; break;
    case 'absolute-range': values.out_ms = 600001; break;
    case 'duplicate-node': graph.definition.nodes.push(node); break;
    case 'edge': graph.definition.edges[0].source_node_id = 'missing'; break;
    case 'cycle': graph.definition.edges.push({ id: 'cycle', source_node_id: 'trim', source_port: 'candidate', target_node_id: 'trim', target_port: 'source' }); break;
    case 'missing-reference': graph.reference_states = []; break;
    case 'stale-source': graph.reference_states[0].state = 'STALE'; break;
    case 'unavailable-source': graph.reference_states[0].state = 'UNAVAILABLE'; break;
    case 'duplicate-reference': graph.reference_states.push(graph.reference_states[0]); break;
    case 'unknown-reference': graph.reference_states[0].node_id = 'trim'; break;
    case 'readonly': graph.can_edit = false; break;
    case 'project': graph.project_id = 'foreign'; break;
    case 'scope': graph.scope.novel_id = 'foreign'; break;
    case 'local-branch': (graph.scope as any).branch_id = 'foreign'; break;
    case 'version': graph.version = 0; break;
    case 'definition-digest': graph.definition_digest = 'z'.repeat(64); break;
    case 'execution-digest': graph.execution_digest = 'e'; break;
    case 'graph-id': graph.id = '../other'; break;
    case 'incarnation': owner.incarnation = 'unknown'; break;
    case 'actor': owner.actorId = ''; break;
    case 'owner-branch': owner.branchId = 'foreign'; break;
    case 'owner-workspace': owner.actorWorkspaceId = 'foreign'; break;
  }
  expect(() => capture(graph, nodeId, owner)).toThrow();
});

it.each([
  {gain_db:0}, {gain_db:-60}, {gain_db:12}, {fade_in_ms:0,fade_out_ms:0},
  {gain_db:-6,fade_in_ms:100,fade_out_ms:200}, {fade_in_ms:800},
])('captures real optional effects without injecting absent fields: %j', effects => {
  const graph=templateGraph();Object.assign(graph.definition.nodes[1].parameters.parameters!,effects);
  const before=JSON.stringify(graph),result=capture(frozen(graph));
  expect(result.parameters).toEqual({in_ms:100,out_ms:900,...effects});expect(Object.isFrozen(result.parameters)).toBe(true);expect(JSON.stringify(graph)).toBe(before);
  for(const key of ['gain_db','fade_in_ms','fade_out_ms'])expect(Object.hasOwn(result.parameters,key)).toBe(Object.hasOwn(effects,key));
});
it.each([
  {gain_db:null},{gain_db:true},{gain_db:NaN},{gain_db:Infinity},{gain_db:12.01},{gain_db:-60.01},
  {fade_in_ms:null},{fade_in_ms:false},{fade_in_ms:0.5},{fade_in_ms:-1},{fade_in_ms:120001},
  {fade_out_ms:NaN},{fade_out_ms:Infinity},{fade_out_ms:801},{fade_in_ms:500,fade_out_ms:301},
  {sample_rate:48000},{channels:2},{output_format:'FLAC'},
])('rejects unsupported or invalid effects through the original parser: %j', effects => {
  const graph=templateGraph();Object.assign(graph.definition.nodes[1].parameters.parameters!,effects);
  expect(()=>capture(graph)).toThrow();
});
