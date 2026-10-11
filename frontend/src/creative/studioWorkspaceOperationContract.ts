import { ApiError } from '../api';
import {
  STUDIO_PRODUCTION_OPERATION_IDS, STUDIO_PRODUCTION_STAGES, STUDIO_PRODUCTION_STAGE_LABELS,
  STUDIO_PRODUCTION_INTERFACE_KEYS, STUDIO_PRODUCTION_INTERFACE_REFERENCES,
  type StudioProductionActionContract, type StudioProductionOperation, type StudioProductionOperationId,
  type StudioProductionOwner, type StudioProductionScope, type StudioProductionStageId,
  type StudioWorkspaceProductionContracts, type StudioOperationStageProjection,
  type StudioProductionInterfaceKey, type StudioInterfaceSchema, type StudioSchemaValue,
} from './studioWorkspaceOperationTypes';

function invalid(): never {
  throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '制作操作契约不可用，请重新读取。' });
}
function mismatch(): never {
  throw new ApiError({ status: 403, code: 'STUDIO_RESPONSE_SCOPE_MISMATCH', message: '制作操作契约与当前项目或分支不一致，请重新打开。' });
}
function object(value: unknown, allowed: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !allowed.includes(key))) invalid();
  return row;
}
function text(value: unknown, maximum = 2000): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
function strings(value: unknown, maximum = 64): string[] {
  if (!Array.isArray(value) || value.length > maximum) invalid();
  return value.map(item => text(item));
}
function stage(value: unknown): StudioProductionStageId {
  if (!STUDIO_PRODUCTION_STAGES.includes(value as StudioProductionStageId)) invalid();
  return value as StudioProductionStageId;
}
function owner(value: unknown): StudioProductionOwner | null {
  if (value === null) return null;
  const row = object(value, ['module', 'class_name', 'methods']);
  return { module: text(row.module, 240), class_name: text(row.class_name, 240), methods: strings(row.methods, 32) };
}
function action(value: unknown): StudioProductionActionContract {
  const row = object(value, ['id', 'method', 'path', 'permission', 'input_schema', 'owner_method', 'requires_original_host_session', 'execution_grant', 'conditions']);
  if (!['GET', 'POST', 'PUT', 'DELETE'].includes(row.method as string)
    || !['domain.read', 'domain.write', 'domain.review'].includes(row.permission as string)
    || typeof row.requires_original_host_session !== 'boolean' || row.execution_grant !== false) invalid();
  const path = text(row.path, 2048);
  if (!path.startsWith('/api/') || path.includes('://') || path.includes('\\')) invalid();
  return {
    id: text(row.id, 120), method: row.method as StudioProductionActionContract['method'], path,
    permission: row.permission as StudioProductionActionContract['permission'],
    input_schema: row.input_schema === null ? null : text(row.input_schema, 240), owner_method: text(row.owner_method, 240),
    requires_original_host_session: row.requires_original_host_session, execution_grant: false, conditions: strings(row.conditions),
  };
}
function operation(value: unknown): StudioProductionOperation {
  const row = object(value, ['id', 'milestone', 'title', 'capability_status', 'acceptance_status', 'acceptance_evidence',
    'execution_available', 'blocked_reasons', 'owner', 'actions', 'input_requirements', 'source_requirements',
    'output_requirements', 'review_requirements', 'limitations', 'interface_contracts']);
  if (!STUDIO_PRODUCTION_OPERATION_IDS.includes(row.id as StudioProductionOperationId)
    || !['EXISTING_OWNER_CONTRACT', 'RESERVED_INTERFACE'].includes(row.capability_status as string)
    || row.acceptance_status !== 'LOCAL_REQUIRED' || row.acceptance_evidence !== 'NOT_EVALUATED_BY_THIS_ENDPOINT'
    || row.execution_available !== false || !Array.isArray(row.actions) || row.actions.length > 32) invalid();
  const milestone = stage(row.milestone), id = row.id as StudioProductionOperationId;
  if (!id.startsWith(`${milestone.toLowerCase()}.`)) invalid();
  const selectedOwner = owner(row.owner), actions = row.actions.map(action), blockers = strings(row.blocked_reasons);
  if (!blockers.length || new Set(actions.map(item => item.id)).size !== actions.length
    || row.capability_status === 'EXISTING_OWNER_CONTRACT' && !selectedOwner
    || row.capability_status === 'RESERVED_INTERFACE' && (selectedOwner !== null || actions.length !== 0)) invalid();
  const references = object(row.interface_contracts, Object.keys(STUDIO_PRODUCTION_INTERFACE_REFERENCES));
  for (const key of Object.keys(STUDIO_PRODUCTION_INTERFACE_REFERENCES) as (keyof typeof STUDIO_PRODUCTION_INTERFACE_REFERENCES)[]) {
    if (references[key] !== STUDIO_PRODUCTION_INTERFACE_REFERENCES[key]) invalid();
  }
  return {
    id, milestone, title: text(row.title, 240), capability_status: row.capability_status as StudioProductionOperation['capability_status'],
    acceptance_status: 'LOCAL_REQUIRED', acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT', execution_available: false,
    blocked_reasons: blockers, owner: selectedOwner, actions,
    input_requirements: strings(row.input_requirements), source_requirements: strings(row.source_requirements),
    output_requirements: strings(row.output_requirements), review_requirements: strings(row.review_requirements), limitations: strings(row.limitations),
    interface_contracts: { ...STUDIO_PRODUCTION_INTERFACE_REFERENCES },
  };
}

/** Bounded schema metadata only. Never evaluate references, defaults, URLs or expressions. */
function schemas(value: unknown): Record<StudioProductionInterfaceKey, StudioInterfaceSchema> {
  const catalog = object(value, STUDIO_PRODUCTION_INTERFACE_KEYS);
  if (Object.keys(catalog).length !== STUDIO_PRODUCTION_INTERFACE_KEYS.length) invalid();
  const budget = { nodes: 0 };
  function metadata(value: unknown, depth = 0): StudioSchemaValue {
    if (++budget.nodes > 16_384 || depth > 24) invalid();
    if (value === null || typeof value === 'boolean') return value;
    if (typeof value === 'number') { if (!Number.isFinite(value)) invalid(); return value; }
    if (typeof value === 'string') { if (value.length > 16_000) invalid(); return value; }
    if (Array.isArray(value)) { if (value.length > 1024) invalid(); return value.map(item => metadata(item, depth + 1)); }
    if (!value || typeof value !== 'object') invalid();
    const entries = Object.entries(value);
    if (entries.length > 256 || entries.some(([key]) => key.length > 240 || ['__proto__', 'prototype', 'constructor'].includes(key))) invalid();
    return Object.fromEntries(entries.map(([key, item]) => [key, metadata(item, depth + 1)]));
  }
  return Object.fromEntries(STUDIO_PRODUCTION_INTERFACE_KEYS.map(key => {
    const source = catalog[key];
    if (!source || typeof source !== 'object' || Array.isArray(source)) invalid();
    const checked = metadata(source) as StudioInterfaceSchema;
    if (checked.type !== 'object' || checked.additionalProperties !== false) invalid();
    return [key, checked];
  })) as Record<StudioProductionInterfaceKey, StudioInterfaceSchema>;
}

/** Validate the public owner description without turning endpoint metadata into commands. */
export function studioProductionContracts(value: unknown, projectId: string, expectedScope?: StudioProductionScope): StudioWorkspaceProductionContracts {
  const row = object(value, ['schema_version', 'contract', 'project_id', 'scope', 'studio_entry_kind', 'advisory_only',
    'execution_authority', 'acceptance_sequence', 'acceptance_evidence', 'operations', 'interface_schemas']);
  if (row.schema_version !== 1 || row.contract !== 'studio-production-operation-contracts/1'
    || row.studio_entry_kind !== 'NEUTRAL_STUDIO' || row.advisory_only !== true || row.execution_authority !== false
    || row.acceptance_evidence !== 'NOT_EVALUATED_BY_THIS_ENDPOINT' || !Array.isArray(row.acceptance_sequence)
    || row.acceptance_sequence.length !== STUDIO_PRODUCTION_STAGES.length
    || row.acceptance_sequence.some((item, index) => item !== STUDIO_PRODUCTION_STAGES[index])
    || !Array.isArray(row.operations) || row.operations.length > STUDIO_PRODUCTION_OPERATION_IDS.length) invalid();
  if (text(row.project_id, 240) !== projectId) mismatch();
  const rawScope = object(row.scope, ['mode', 'novel_id', 'workspace_id', 'project_id', 'storyline_id', 'branch_id']);
  if (rawScope.mode !== 'local' && rawScope.mode !== 'collaboration') invalid();
  const scope: StudioProductionScope = { mode: rawScope.mode, novel_id: text(rawScope.novel_id, 240) };
  for (const key of ['workspace_id', 'project_id', 'storyline_id', 'branch_id'] as const) {
    if (rawScope[key] !== undefined) scope[key] = rawScope[key] === null ? null : text(rawScope[key], 240);
  }
  if (scope.novel_id !== projectId) mismatch();
  const expected = expectedScope ?? { mode: 'local', novel_id: projectId };
  if (scope.mode !== expected.mode || scope.novel_id !== expected.novel_id
    || (['workspace_id', 'project_id', 'storyline_id', 'branch_id'] as const).some(key => (scope[key] ?? null) !== (expected[key] ?? null))) mismatch();
  const operations = row.operations.map(operation);
  if (new Set(operations.map(item => item.id)).size !== operations.length) invalid();
  return { schema_version: 1, contract: 'studio-production-operation-contracts/1', project_id: projectId, scope,
    studio_entry_kind: 'NEUTRAL_STUDIO', advisory_only: true, execution_authority: false,
    acceptance_sequence: [...STUDIO_PRODUCTION_STAGES], acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT', operations,
    interface_schemas: schemas(row.interface_schemas) };
}

/** This projection has no runtime status and cannot promote planned operations to acceptance. */
export function productionStageProjection(value: StudioWorkspaceProductionContracts | undefined, id: StudioProductionStageId): StudioOperationStageProjection {
  return { id, label: STUDIO_PRODUCTION_STAGE_LABELS[id], operations: value?.operations.filter(item => item.milestone === id) ?? [],
    execution_available: false, acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT' };
}
