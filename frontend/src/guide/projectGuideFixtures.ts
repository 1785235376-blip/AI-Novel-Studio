/**
 * UX-08 测试夹具：用**真实的** `ProductionWorkflowProjection` 形状构造事实。
 *
 * 这里不发明任何字段：夹具先拼出原 owner 的线上形状，再交给原 owner 自己的
 * `productionWorkflowProjection()` 解码一次，因此夹具本身也受契约检查
 * （字段名或一致性写错，夹具会先失败）。
 */
import { productionWorkflowProjection } from '../production/productionWorkflowContract';
import {
  PRODUCTION_WORKFLOW_MODULES, PRODUCTION_WORKFLOW_MODULE_LABELS,
  type ProductionWorkflowAssetOverview, type ProductionWorkflowModule, type ProductionWorkflowModuleId,
  type ProductionWorkflowProjection, type ProductionWorkflowStatus,
} from '../production/productionWorkflowTypes';

export const PROJECT = 'guide-fixture-project';
export const IDENTITY = 'local-author:file:guide-fixture';

export const EMPTY_OVERVIEW: ProductionWorkflowAssetOverview = {
  total: 0, by_kind: { image: 0, audio: 0, video: 0, text: 0, other: 0 },
  private_pending_review: 0, reviewed: 0,
};

const MODULE_STATUS: Readonly<Record<ProductionWorkflowModuleId, ProductionWorkflowStatus>> = {
  director: 'PLANNED', storyboard: 'NOT_STARTED', image: 'NOT_STARTED', video: 'NOT_STARTED',
  audio: 'NOT_STARTED', timeline: 'NOT_STARTED', asset: 'NOT_STARTED',
};

export type ModuleOverride = {
  status?: ProductionWorkflowStatus;
  blocked_reasons?: string[];
  asset_count?: number;
  document_count?: number;
  job_count?: number;
};

/** 七个模块按原 owner 的冻结顺序生成；`override` 只改指定模块。 */
export function modules(override: Partial<Record<ProductionWorkflowModuleId, ModuleOverride>> = {}): ProductionWorkflowModule[] {
  return PRODUCTION_WORKFLOW_MODULES.map((id, index) => {
    const patch = override[id] ?? {};
    return {
      id, label: PRODUCTION_WORKFLOW_MODULE_LABELS[id], status: patch.status ?? MODULE_STATUS[id],
      document_count: patch.document_count ?? (index === 0 ? 2 : 0),
      asset_count: patch.asset_count ?? 0, job_count: patch.job_count ?? 0,
      blocked_reasons: patch.blocked_reasons ?? [],
      owner: PRODUCTION_WORKFLOW_MODULE_LABELS[id],
      next_action: patch.blocked_reasons?.length ? '回原模块处理阻塞原因' : null,
    };
  });
}

export function intentValues(selected: readonly string[] = []) {
  return [
    { intent_id: 'novel_writing', label: '小说创作', selected: selected.includes('novel_writing'), custom: false },
    { intent_id: 'image_design', label: '图片设计', selected: selected.includes('image_design'), custom: false },
    { intent_id: 'custom', label: '我的短片', selected: selected.includes('custom'), custom: true },
  ];
}

export type ProjectionOptions = {
  version?: number;
  selected?: readonly string[];
  override?: Partial<Record<ProductionWorkflowModuleId, ModuleOverride>>;
  overview?: ProductionWorkflowAssetOverview;
};

/** 原 owner 自己的解码器核对过的完整投影（字段与 `studio-production-workflow/1` 一致）。 */
export function projection(options: ProjectionOptions = {}): ProductionWorkflowProjection {
  const rows = modules(options.override);
  const overview = options.overview ?? EMPTY_OVERVIEW;
  const started = rows.filter(row => row.status !== 'NOT_STARTED').length;
  const reviewed = rows.filter(row => row.status === 'REVIEWED').length;
  return productionWorkflowProjection({
    schema_version: 1, contract: 'studio-production-workflow/1', project_id: PROJECT,
    scope: { mode: 'local', novel_id: PROJECT },
    advisory_only: true, execution_authority: false,
    generated_at: '2026-10-14T00:00:00Z',
    project_start: {
      state: 'STARTED', entry_kind: 'NEUTRAL_STUDIO', incarnation: 'file:guide-fixture',
      has_creative_documents: true,
      start_action: { method: 'POST', path: '/api/experimental/projects', requires_original_host_session: true },
    },
    creative_intent: {
      version: options.version ?? 1, preset: null, values: intentValues(options.selected),
      editable: true, history_retained: true,
    },
    modules: rows,
    asset_overview: overview,
    dashboard: {
      stages_total: 7, stages_started: started, stages_reviewed: reviewed,
      open_reviews: overview.private_pending_review,
      blocked_stages: rows.filter(row => row.blocked_reasons.length > 0).map(row => row.id),
    },
  }, PROJECT, { mode: 'local', novel_id: PROJECT });
}

/** 原 `TaskCenterTasksProjection` 的最小真实形状（含 owner 自己声明的三条事实）。 */
export function tasksProjection(items: Array<{ id: string; status?: string; stale?: boolean; progress?: unknown }> = []) {
  return {
    project_id: PROJECT,
    scope_verified: true,
    items: items.map(item => ({
      authority: 'workspace_tools', id: item.id, label: item.id, feature: 'image_generation',
      status: item.status ?? 'RUNNING', raw_status: item.status ?? 'RUNNING', stage_label: '运行中',
      version: null, progress: item.progress === undefined ? { completed: 1, total: 4, unit: 'node' } : item.progress,
      history: [], stale: item.stale ?? false,
      cost: { estimate: null, actual: null, state: 'UNKNOWN' },
      error_code: null, provider_id: null, model_id: null, route_state: 'UNKNOWN',
      actions: ['open_source'], action_limits: { cancel: null, retry: 'SOURCE_PREFLIGHT_REQUIRED', resume: 'SOURCE_RECOVERY_REQUIRED', review: 'SOURCE_REVIEW_REQUIRED' },
      retry_policy: 'SOURCE_AUTHORITY_ONLY', lifecycle: 'RUNNING', source: null, owner_navigation: null,
      navigation_contract: null, source_domain: null, revision: 'a'.repeat(64),
    })),
    unavailable: [],
    truncated: false,
    executor: false as const,
    refresh: 'MANUAL' as const,
    automatic_retries: false as const,
  };
}

/** 原 `ReviewInboxProjection` 的最小真实形状。 */
export function inboxProjection(items: Array<{ id: string; status?: string; stale?: boolean }> = [], unavailable: Array<{ domain: string; reason: string }> = []) {
  return {
    project_id: PROJECT,
    items: items.map(item => ({
      id: item.id, domain: 'media_review', status: item.status ?? 'PENDING', stale: item.stale ?? false,
      preview: { kind: 'text' as const, text: '候选预览' }, target: [], target_navigation_contract: null,
      version: 3, allowed_actions: ['approve', 'reject'], batch_actions: ['approve'], batch_safe: true,
      source: 'media', source_versions: [], source_hash: 'b'.repeat(64), privacy_state: 'PRIVATE',
      risk: 'LOW', created_by: 'local-author', recovery_state: null, promotion_recovery_required: false,
      novel_id: PROJECT, project: PROJECT, workspace: null, branch: null,
      scope: { mode: 'local' as const, novel_id: PROJECT },
    })),
    total: items.length + unavailable.length,
    unavailable,
    approval_authority: 'DOMAIN_SERVICE' as const,
    batch_semantics: 'PER_ITEM_CHECKPOINT' as const,
  };
}

/** 素材浏览器行（`AssetBrowserRow`）：只给提示助手要读的字段，其余按 owner 形状给值。 */
export function assetRows(rows: Array<{ id: string; media_kind: 'image' | 'video' | 'audio' | null; deleted?: boolean }> = []) {
  return rows.map(row => ({
    id: row.id, filename: `${row.id}.bin`, kind: row.media_kind ?? 'other', media_kind: row.media_kind,
    media_type: 'application/octet-stream', size: 1024, digest: 'c'.repeat(64), version: 1,
    review_state: 'UNREVIEWED', created_at: '2026-10-14T00:00:00Z', created_at_ms: null,
    created_bucket: 'TODAY', tags: [], integrity: 'VERIFIED', stale: false, license_label: null,
    license_verification: null, deleted: row.deleted ?? false, reference_counts: null,
  }));
}

/** 已保存图定义里提示助手会读的部分。 */
export function graphFacts(nodes: Array<{ id: string; enabled?: boolean }> = [],
  edges: Array<{ id: string }> = [], referenceStates: Array<{ node_id: string; state: 'CURRENT' | 'STALE' | 'UNAVAILABLE' }> = []) {
  return {
    nodes: nodes.map(node => ({ id: node.id, definition_id: 'text.draft', enabled: node.enabled ?? true })),
    edges: edges.map(edge => ({ id: edge.id, source_node_id: 'n1', source_port: 'out', target_node_id: 'n2', target_port: 'in' })),
    reference_states: referenceStates,
  };
}

/** 已保存时间线里提示助手会读的部分。 */
export function timelineFacts(tracks: number, clips: number) {
  return {
    tracks: Array.from({ length: tracks }, (_, index) => ({ id: `t${index}`, kind: 'video' })),
    clips: Array.from({ length: clips }, (_, index) => ({ id: `c${index}`, track_id: 't0', start_ms: index * 1000 })),
  };
}

/** 原分镜回执的真实形状（`studio-storyboard/1`）：镜头按 owner 契约自洽。 */export function storyboardReceipt(shotCount = 1, approved = false) {
  const shots = Array.from({ length: shotCount }, (_, index) => {
    const shotId = `shot-${index + 1}`;
    return {
      shot_id: shotId, shot_version: 1, shot_digest: 'f'.repeat(64),
      shot: {
        id: shotId, number: index + 1, scene_id: 'scene-1', shot_size: 'MEDIUM',
        camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 3,
        frame_prompt: '只读夹具：本提示助手不解析镜头内容', composition: '', lens: '',
        lighting: '', environment: '', sound: '', color: '', action: '', dialogue: [],
        sound_effect: '', director_notes: [],
        continuity: { characters: '', outfit: '', environment: '', camera: '' },
      },
      image_asset: null,
    };
  });
  return {
    contract: 'studio-storyboard/1',
    document_snapshot: { id: IDENTITY, version: 1, digest: 'd'.repeat(64) },
    content_digest: 'e'.repeat(64), approved, shots,
    director_sources: [], model_called: false, product_acceptance: 'LOCAL_REQUIRED',
  };
}
