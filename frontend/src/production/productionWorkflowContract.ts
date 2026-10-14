import { ApiError } from '../api';
import {
  PRODUCTION_WORKFLOW_ASSET_KINDS, PRODUCTION_WORKFLOW_BOUNDS, PRODUCTION_WORKFLOW_CONTRACT,
  PRODUCTION_WORKFLOW_ERROR_CODES, PRODUCTION_WORKFLOW_INTENT_ID, PRODUCTION_WORKFLOW_INTENT_LIMIT,
  PRODUCTION_WORKFLOW_MODULES, PRODUCTION_WORKFLOW_PRESETS, PRODUCTION_WORKFLOW_SCHEMA_VERSION,
  PRODUCTION_WORKFLOW_STAGES_TOTAL, PRODUCTION_WORKFLOW_START_ACTION, PRODUCTION_WORKFLOW_START_STATES,
  PRODUCTION_WORKFLOW_STATUSES,
  type ProductionWorkflowAssetKind, type ProductionWorkflowAssetOverview, type ProductionWorkflowDashboard,
  type ProductionWorkflowIntent, type ProductionWorkflowIntentDraft, type ProductionWorkflowIntentValue,
  type ProductionWorkflowIntentValueInput, type ProductionWorkflowModule, type ProductionWorkflowPreset,
  type ProductionWorkflowProjection, type ProductionWorkflowProjectStart, type ProductionWorkflowScope,
} from './productionWorkflowTypes';

/**
 * Never trust the returned shape: unknown keys, unbounded text, control characters,
 * out-of-range integers, a duplicated module, a reordered module list, a foreign
 * project/scope or an internally inconsistent dashboard is a refused read.
 */
function invalid(): never {
  throw new ApiError({ status: 200, code: PRODUCTION_WORKFLOW_ERROR_CODES.responseInvalid, message: '制作工作流数据不可用，请重新读取。' });
}
function mismatch(): never {
  throw new ApiError({ status: 403, code: PRODUCTION_WORKFLOW_ERROR_CODES.scopeMismatch, message: '制作工作流与当前项目或分支不一致，请重新打开。' });
}
function object(value: unknown, allowed: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !allowed.includes(key))) invalid();
  return row;
}
function text(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
function optionalText(value: unknown, maximum: number): string | null {
  if (value === null) return null;
  return text(value, maximum);
}
function integer(value: unknown, maximum = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > maximum) invalid();
  return value;
}
function bool(value: unknown): boolean {
  if (typeof value !== 'boolean') invalid();
  return value;
}
function list(value: unknown, maximum: number): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) invalid();
  return value;
}
function strings(value: unknown, maximumItems: number, maximumLength: number): string[] {
  return list(value, maximumItems).map(item => text(item, maximumLength));
}
function enumerated<T extends string>(value: unknown, allowed: readonly T[]): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) invalid();
  return value as T;
}
function slug(value: unknown): string {
  if (typeof value !== 'string' || !PRODUCTION_WORKFLOW_INTENT_ID.test(value)) invalid();
  return value;
}
/** One bounded owner identity token (`file:<uuid4>` / `postgres:<id>`), never a raw path. */
function identity(value: unknown): string {
  const token = text(value, PRODUCTION_WORKFLOW_BOUNDS.incarnation);
  if (!/^[A-Za-z0-9][A-Za-z0-9:._-]*$/.test(token)) invalid();
  return token;
}
function timestamp(value: unknown): string {
  const stamp = text(value, PRODUCTION_WORKFLOW_BOUNDS.timestamp);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|\+00:00)$/.test(stamp) || Number.isNaN(Date.parse(stamp))) invalid();
  return stamp;
}
function scoped(value: unknown, projectId: string, expected?: ProductionWorkflowScope): ProductionWorkflowScope {
  const row = object(value, ['mode', 'novel_id', 'workspace_id', 'project_id', 'storyline_id', 'branch_id']);
  const scope: ProductionWorkflowScope = {
    mode: enumerated(row.mode, ['local', 'collaboration'] as const), novel_id: text(row.novel_id, PRODUCTION_WORKFLOW_BOUNDS.project_id),
  };
  for (const key of ['workspace_id', 'project_id', 'storyline_id', 'branch_id'] as const) {
    if (row[key] !== undefined) scope[key] = optionalText(row[key], PRODUCTION_WORKFLOW_BOUNDS.project_id);
  }
  if (scope.novel_id !== projectId) mismatch();
  const wanted = expected ?? { mode: 'local' as const, novel_id: projectId };
  if (scope.mode !== wanted.mode || scope.novel_id !== wanted.novel_id
    || (['workspace_id', 'project_id', 'storyline_id', 'branch_id'] as const).some(key => (scope[key] ?? null) !== (wanted[key] ?? null))) mismatch();
  return scope;
}
function start(value: unknown): ProductionWorkflowProjectStart {
  const row = object(value, ['state', 'entry_kind', 'incarnation', 'has_creative_documents', 'start_action']);
  if (row.entry_kind !== 'NEUTRAL_STUDIO') invalid();
  const action = object(row.start_action, ['method', 'path', 'requires_original_host_session']);
  if (action.method !== PRODUCTION_WORKFLOW_START_ACTION.method || action.path !== PRODUCTION_WORKFLOW_START_ACTION.path
    || action.requires_original_host_session !== true) invalid();
  return {
    state: enumerated(row.state, PRODUCTION_WORKFLOW_START_STATES), entry_kind: 'NEUTRAL_STUDIO',
    incarnation: row.incarnation === null ? null : identity(row.incarnation),
    has_creative_documents: bool(row.has_creative_documents),
    start_action: { method: 'POST', path: PRODUCTION_WORKFLOW_START_ACTION.path, requires_original_host_session: true },
  };
}
function intentValues(value: unknown): ProductionWorkflowIntentValue[] {
  const values = list(value, PRODUCTION_WORKFLOW_INTENT_LIMIT).map(item => {
    const row = object(item, ['intent_id', 'label', 'selected', 'custom']);
    return { intent_id: slug(row.intent_id), label: text(row.label, PRODUCTION_WORKFLOW_BOUNDS.label), selected: bool(row.selected), custom: bool(row.custom) };
  });
  if (new Set(values.map(item => item.intent_id)).size !== values.length) invalid();
  return values;
}
function modules(value: unknown): ProductionWorkflowModule[] {
  const rows = list(value, PRODUCTION_WORKFLOW_STAGES_TOTAL);
  if (rows.length !== PRODUCTION_WORKFLOW_STAGES_TOTAL) invalid();
  const checked = rows.map((item, index) => {
    const row = object(item, ['id', 'label', 'status', 'document_count', 'asset_count', 'job_count', 'blocked_reasons', 'owner', 'next_action']);
    const id = enumerated(row.id, PRODUCTION_WORKFLOW_MODULES);
    if (id !== PRODUCTION_WORKFLOW_MODULES[index]) invalid();
    return {
      id, label: text(row.label, PRODUCTION_WORKFLOW_BOUNDS.label), status: enumerated(row.status, PRODUCTION_WORKFLOW_STATUSES),
      document_count: integer(row.document_count), asset_count: integer(row.asset_count), job_count: integer(row.job_count),
      blocked_reasons: strings(row.blocked_reasons, PRODUCTION_WORKFLOW_BOUNDS.blocked_reasons, PRODUCTION_WORKFLOW_BOUNDS.blocked_reason),
      owner: text(row.owner, PRODUCTION_WORKFLOW_BOUNDS.owner), next_action: optionalText(row.next_action, PRODUCTION_WORKFLOW_BOUNDS.next_action),
    };
  });
  if (new Set(checked.map(item => item.id)).size !== checked.length) invalid();
  return checked;
}
function assets(value: unknown): ProductionWorkflowAssetOverview {
  const row = object(value, ['total', 'by_kind', 'private_pending_review', 'reviewed']);
  const kinds = object(row.by_kind, PRODUCTION_WORKFLOW_ASSET_KINDS);
  if (Object.keys(kinds).length !== PRODUCTION_WORKFLOW_ASSET_KINDS.length) invalid();
  const byKind = Object.fromEntries(PRODUCTION_WORKFLOW_ASSET_KINDS.map(kind => [kind, integer(kinds[kind])])) as Record<ProductionWorkflowAssetKind, number>;
  const total = integer(row.total), pending = integer(row.private_pending_review), reviewed = integer(row.reviewed);
  if (PRODUCTION_WORKFLOW_ASSET_KINDS.reduce((count, kind) => count + byKind[kind], 0) !== total
    || pending > total || reviewed > total || pending + reviewed > total) invalid();
  return { total, by_kind: byKind, private_pending_review: pending, reviewed };
}
/** Every counter is re-derived from the modules and the asset overview the same response declares. */
function dashboard(value: unknown, rows: ProductionWorkflowModule[], overview: ProductionWorkflowAssetOverview): ProductionWorkflowDashboard {
  const row = object(value, ['stages_total', 'stages_started', 'stages_reviewed', 'open_reviews', 'blocked_stages']);
  if (row.stages_total !== PRODUCTION_WORKFLOW_STAGES_TOTAL) invalid();
  const started = rows.filter(item => item.status !== 'NOT_STARTED').length;
  const reviewed = rows.filter(item => item.status === 'REVIEWED').length;
  const blocked = list(row.blocked_stages, PRODUCTION_WORKFLOW_STAGES_TOTAL).map(item => enumerated(item, PRODUCTION_WORKFLOW_MODULES));
  const reasons = new Set(rows.filter(item => item.blocked_reasons.length).map(item => item.id));
  if (integer(row.stages_started, PRODUCTION_WORKFLOW_STAGES_TOTAL) !== started
    || integer(row.stages_reviewed, PRODUCTION_WORKFLOW_STAGES_TOTAL) !== reviewed
    || integer(row.open_reviews) !== overview.private_pending_review
    || new Set(blocked).size !== blocked.length || blocked.length !== reasons.size
    || blocked.some(id => !reasons.has(id))) invalid();
  return { stages_total: 7, stages_started: started, stages_reviewed: reviewed, open_reviews: overview.private_pending_review, blocked_stages: blocked };
}

/** Validate one `creative_intent` value (the GET projection fields and the POST response body). */
export function productionWorkflowIntent(value: unknown): ProductionWorkflowIntent {
  const row = object(value, ['version', 'preset', 'values', 'editable', 'history_retained']);
  if (row.editable !== true || row.history_retained !== true) invalid();
  return {
    version: integer(row.version), preset: row.preset === undefined ? null : (row.preset === null ? null : enumerated<ProductionWorkflowPreset>(row.preset, PRODUCTION_WORKFLOW_PRESETS)),
    values: intentValues(row.values), editable: true, history_retained: true,
  };
}

/** Validate the outgoing replacement: the original owner forbids unknown keys and bounds every field. */
export function productionWorkflowIntentRequest(value: unknown): ProductionWorkflowIntentDraft {
  const row = object(value, ['expected_version', 'values', 'preset']);
  const values = list(row.values, PRODUCTION_WORKFLOW_INTENT_LIMIT).map(item => {
    const entry = object(item, ['intent_id', 'label', 'selected']);
    return { intent_id: slug(entry.intent_id), label: text(entry.label, PRODUCTION_WORKFLOW_BOUNDS.label), selected: bool(entry.selected) } as ProductionWorkflowIntentValueInput;
  });
  if (new Set(values.map(item => item.intent_id)).size !== values.length) invalid();
  const request: ProductionWorkflowIntentDraft = { expected_version: row.expected_version === null ? null : integer(row.expected_version), values };
  if (row.preset !== undefined) request.preset = row.preset === null ? null : enumerated<ProductionWorkflowPreset>(row.preset, PRODUCTION_WORKFLOW_PRESETS);
  return request;
}

/** Read-only workflow projection. Nothing here can be promoted to execution or acceptance. */
export function productionWorkflowProjection(value: unknown, projectId: string, expectedScope?: ProductionWorkflowScope): ProductionWorkflowProjection {
  if (typeof projectId !== 'string' || !projectId) invalid();
  const row = object(value, ['schema_version', 'contract', 'project_id', 'scope', 'advisory_only', 'execution_authority',
    'generated_at', 'project_start', 'creative_intent', 'modules', 'asset_overview', 'dashboard']);
  if (row.schema_version !== PRODUCTION_WORKFLOW_SCHEMA_VERSION || row.contract !== PRODUCTION_WORKFLOW_CONTRACT
    || row.advisory_only !== true || row.execution_authority !== false) invalid();
  if (text(row.project_id, PRODUCTION_WORKFLOW_BOUNDS.project_id) !== projectId) mismatch();
  const scope = scoped(row.scope, projectId, expectedScope);
  const checkedModules = modules(row.modules), overview = assets(row.asset_overview);
  return {
    schema_version: 1, contract: 'studio-production-workflow/1', project_id: projectId, scope,
    advisory_only: true, execution_authority: false, generated_at: timestamp(row.generated_at),
    project_start: start(row.project_start), creative_intent: productionWorkflowIntent(row.creative_intent),
    modules: checkedModules, asset_overview: overview, dashboard: dashboard(row.dashboard, checkedModules, overview),
  };
}
