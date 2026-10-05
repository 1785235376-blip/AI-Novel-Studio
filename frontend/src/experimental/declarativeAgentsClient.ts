import type { ExperimentalClient } from './api';
export type SchemaField = { name: string; type: 'string' | 'number' | 'boolean'; required: boolean; max_length: number };
export type AuthoredWorkflow = { agent: { title: string; purpose: string; role_prompt: string; input_schema: { fields: SchemaField[] }; output_schema: { fields: SchemaField[] }; allowed_tools: string[]; model_route: string | null; review_required: true; max_steps: number; timeout_seconds: number; max_output_bytes: number; max_cost_microusd: 0 }; nodes: { id: string; type: string; name: string }[]; edges: { source: string; target: string }[] };
export type AgentDefinition = { id: string; version: number; definition: AuthoredWorkflow; definition_digest: string };
export type AgentPreflight = { valid: boolean; definition_digest: string; topological_order: string[]; execution_available: boolean; blockers: string[] };
export type AgentRun = { id: string; version: number; status: string; stale: boolean; definition_id: string; definition_version: number; input: Record<string, unknown>; node_states: Record<string, { status: string; output: unknown; error: unknown }>; agent_output: unknown; current_node_id?: string; trace: { action: string; status: string; at: string }[]; dispatch_trace: { node_id: string; type: string; at: string }[]; applied: false; model_called: false; error?: { code: string }; attempt: number };
export type AgentCatalog = { tools: string[]; node_types: string[]; model_routes: { id: string; model_id: string; provider_id: string; available: false; reason: string }[]; default_definition: AuthoredWorkflow; chapters: { id: string; title: string; version: number }[]; model_dependency: string };
export function declarativeAgentsClient(client: ExperimentalClient) {
  const base = '/declarative-agents'; const segment = encodeURIComponent;
  return {
    catalog: (signal?: AbortSignal) => client.get<AgentCatalog>(base + '/catalog', signal),
    definitions: (signal?: AbortSignal) => client.get<{ items: AgentDefinition[] }>(base + '/definitions', signal),
    preflight: (definition: AuthoredWorkflow) => client.post<AgentPreflight>(base + '/preflight', definition),
    save: (definition: AuthoredWorkflow, row?: AgentDefinition) => row ? client.put<AgentDefinition>(base + '/definitions/' + segment(row.id), { definition, expected_version: row.version }) : client.post<AgentDefinition>(base + '/definitions', { definition, expected_version: 0 }),
    createRun: (row: AgentDefinition, input: Record<string, unknown>, chapterId: string, requestId: string, sourceVersion: number | null) => client.post<AgentRun>(base + '/definitions/' + segment(row.id) + '/runs', { expected_version: row.version, input, chapter_ids: chapterId ? [chapterId] : [], request_id: requestId, reviewed_definition_digest: row.definition_digest, source_version: sourceVersion }),
    runs: (signal?: AbortSignal) => client.get<{ items: AgentRun[] }>(base + '/runs', signal),
    run: (id: string) => client.get<AgentRun>(base + '/runs/' + segment(id)),
    transition: (row: AgentRun, action: string, note: string) => client.post<AgentRun>(base + '/runs/' + segment(row.id) + '/' + action, { expected_version: row.version, note }),
  };
}
