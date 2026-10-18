import {checkedModelCameras,checkedModelCameraSelection,checkedModelCameraExport,MODEL_CAMERA_EXPORT_CONTRACT,type ModelCameraSelection} from './studioModelCameraContract';
import { VIDEO_REFERENCE_PREVIEW, VIDEO_REFERENCE_ASSET, checkedVideoReferenceSource, checkedVideoReferenceWindow, checkedVideoReferencePreview, checkedVideoReferenceSaved, type VideoReferenceOrigin, type VideoReferencePreview, type VideoReferenceWindow } from './studioVideoReferenceContract';
import {CLAY_ASSET_CONTRACT,checkedClayAssetResult,type ClayAssetOrigin} from './studioModelClaySaveContract';
import type {ModelClayExport} from './studioModelClayContract';
import { checkedModelClay } from './studioModelClayContract';
import { checkedModelMaterials } from './studioModelMaterialsContract';
import { checkedDepthCamera, checkedModelDepth, type ModelDepthCamera } from './studioModelDepthContract';
import { checkedModelReferenceAsset, checkedModelReferenceInspection, checkedModelMeshPreview, checkedModelScenePreview, type ModelReferenceImport } from './studioModelReferenceContract';
import { ApiError, type Asset, type AssetProvenance, type AssetRelationship, type AssetRelationshipKind, type AssetRelationshipReference, type AssetRelationshipReferenceKind, type AssetRelationshipTarget, type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { isPackagedDesktopHost } from '../packagedHost';
import { createStudioGraphClient } from './studioGraphClient';
import { createStudioWorkspaceOperationClient } from './studioWorkspaceOperationClient';
import { checkedStudioPreferences } from './studioWorkspacePreferences';
import { checkedMaskInput, checkedMaskResult, maskSha256, type StudioMaskInput, type StudioMaskReceipt } from './studioManualMaskContract';

export type CreativeIntent = 'NOVEL_WRITING' | 'NOVEL_ADAPTATION' | 'AI_SHORT_FILM' | 'COMMERCIAL_CG'
  | 'ADVERTISEMENT' | 'MUSIC_VIDEO' | 'GAME_PREVIS' | 'IMAGE_DESIGN' | 'PODCAST_VOICE' | 'BLANK' | 'CUSTOM';
export type WorkspacePreset = 'BLANK' | 'TEXT' | 'IMAGE' | 'VIDEO' | 'AUDIO' | 'EDITING' | 'MIXED';
export type StudioAssetKind = 'image' | 'video' | 'audio';
export type StudioProject = { id: string; title: string };
export type StudioCreatedProject = StudioProject & { studio_ready: boolean; requires_scope_selection: boolean };
export type StudioPreferencesInput = { intents: CreativeIntent[]; preset: WorkspacePreset; custom_intent: string };
export type StudioPreferences = StudioPreferencesInput & { version: number };
export type StudioOverview = {
  project: StudioProject & { entry_kind: 'NEUTRAL_STUDIO' | 'LEGACY'; incarnation?: string };
  preferences: StudioPreferences;
  capabilities: {
    manual_import: boolean;
    manual_export: boolean;
    can_mutate: boolean;
    /** Missing review authority never grants permission to declare APPROVED_FOR. */
    can_review?: boolean;
    model_required: false;
    chapter_required: false;
    media_validator_configured: boolean;
    asset_kinds: StudioAssetKind[];
    intent_is_permission: false;
  };
};
// Activation confirms identity only; the full overview remains the state/permission owner.
export type StudioActivation = { project: StudioProject & { entry_kind: 'NEUTRAL_STUDIO' } };
export type StudioLicenseDeclaration = { label: string; source: string; note: string };
export type StudioLineageOrigin = 'ORIGINAL_INPUT' | 'GENERATED_RESULT' | 'DERIVED_PROCESSING' | 'EXTERNAL_IMPORT' | 'MANUAL_EDIT';
export type StudioLineageLink = { id?: string; label?: string; version?: number; digest?: string; state: string };
/** The existing production-lineage projection, not a second asset owner. */
export type ProductionLineage = AssetProvenance;
export type StudioAsset = Asset & { version: number; video_reference?: VideoReferenceOrigin; model_reference?: ClayAssetOrigin; manual_mask?: StudioMaskReceipt; provenance?: Asset['provenance'] & { source_task_id?: string | null } };
export type StudioReferenceKind = AssetRelationshipReferenceKind;
export type StudioReference = AssetRelationshipReference;
export type StudioReferences = { items: StudioReference[]; read_only: true; content_copied: false };
export type StudioRelationshipType = AssetRelationshipKind;
export type StudioRelationship = AssetRelationship;
export type StudioRelationshipInput = {
  expected_version: number;
  type: StudioRelationshipType;
  target: AssetRelationshipTarget;
  reason?: string;
};
export type StudioRelationshipGraphEdge = (StudioRelationship & { from: string; owner?: never })
  | ({ id: string; from: string; type: 'DERIVED_FROM'; owner: 'ASSET_LINEAGE' } & (
    { state: 'CURRENT' | 'STALE' | 'DELETED'; target: StudioReference }
    | { state: 'UNAVAILABLE'; target: { label: string } }
  ));
export type StudioRelationshipsGraph = {
  graph_kind: 'ASSET_RELATIONSHIPS';
  nodes: { id: string; kind: 'ASSET'; asset_kind: string; label: string; version: number; digest: string }[];
  edges: StudioRelationshipGraphEdge[];
  executable: false;
  knowledge_graph: false;
  automatic_regeneration: false;
};
export type StudioRelationshipGraph = StudioRelationshipsGraph;
export type StudioImportInput = { filename: string; kind: StudioAssetKind; content_base64: string; idempotency_key: string };
export type StudioLineageInput = {
  expected_version: number;
  origin: StudioLineageOrigin;
  parent_asset_ids?: string[];
  chapter_ids?: string[];
  license?: Partial<StudioLicenseDeclaration>;
  operation?: string;
};
export type StudioStorageAdmission = (
  { state: 'READY' | 'LOW_SPACE_OR_QUOTA'; available_import_bytes: number }
  | { state: 'UNAVAILABLE'; available_import_bytes: null }
) & {
  reserve_bytes: number;
  measurement: 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA';
  paths: {
    project: 'EXISTING_PROJECT_OWNER';
    assets: 'EXISTING_ASSET_LIBRARY';
    models: 'MODEL_CENTER_REFERENCES_ONLY';
    cache: 'EXISTING_CACHE_OWNER';
    exports: 'USER_SELECTED_DOWNLOAD';
  };
  external_model_scan: false;
  automatic_cleanup: false;
  automatic_migration: false;
};
export type StudioStorage = {
  assets: { count: number; bytes: number };
  trash: { count: number; bytes: number };
  limits: { asset_bytes: number; project_asset_bytes: number; project_assets: number };
  model_storage: 'EXTERNAL_READ_ONLY';
  cache_storage: 'SEPARATE_OWNER';
  export_storage: 'CLIENT_SELECTED_DOWNLOAD';
  physical_cleanup_available: false;
  admission?: StudioStorageAdmission;
};

function version(value: number, minimum: number): number {
  if (!Number.isSafeInteger(value) || value < minimum) {
    throw new ApiError({ status: 400, code: 'STUDIO_VERSION_INVALID', message: '请先读取当前记录版本，再重试此操作。' });
  }
  return value;
}

function checkedStorage(value: StudioStorage): StudioStorage {
  if (value.admission === undefined) return value;
  const invalid = (): never => {
    throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务返回的存储信息不可用，请重新读取。' });
  };
  const source: unknown = value.admission;
  if (!source || typeof source !== 'object' || Array.isArray(source)) invalid();
  const row = source as Record<string, unknown>;
  if (!['READY', 'LOW_SPACE_OR_QUOTA', 'UNAVAILABLE'].includes(row.state as string)
    || typeof row.reserve_bytes !== 'number' || !Number.isSafeInteger(row.reserve_bytes) || row.reserve_bytes < 0
    || row.measurement !== 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA'
    || row.external_model_scan !== false || row.automatic_cleanup !== false || row.automatic_migration !== false) invalid();
  const available = row.available_import_bytes;
  if (row.state === 'UNAVAILABLE' ? available !== null
    : typeof available !== 'number' || !Number.isSafeInteger(available) || available < 0) invalid();
  if (!row.paths || typeof row.paths !== 'object' || Array.isArray(row.paths)) invalid();
  const paths = row.paths as Record<string, unknown>;
  if (paths.project !== 'EXISTING_PROJECT_OWNER' || paths.assets !== 'EXISTING_ASSET_LIBRARY'
    || paths.models !== 'MODEL_CENTER_REFERENCES_ONLY' || paths.cache !== 'EXISTING_CACHE_OWNER'
    || paths.exports !== 'USER_SELECTED_DOWNLOAD') invalid();
  const admission: StudioStorageAdmission = {
    ...(row.state === 'UNAVAILABLE'
      ? { state: 'UNAVAILABLE' as const, available_import_bytes: null }
      : { state: row.state as 'READY' | 'LOW_SPACE_OR_QUOTA', available_import_bytes: available as number }),
    reserve_bytes: row.reserve_bytes as number,
    measurement: 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA',
    paths: { project: 'EXISTING_PROJECT_OWNER', assets: 'EXISTING_ASSET_LIBRARY', models: 'MODEL_CENTER_REFERENCES_ONLY', cache: 'EXISTING_CACHE_OWNER', exports: 'USER_SELECTED_DOWNLOAD' },
    external_model_scan: false, automatic_cleanup: false, automatic_migration: false,
  };
  return { ...value, admission };
}

const relationshipKinds: readonly StudioRelationshipType[] = ['SOURCE_OF', 'DERIVED_FROM', 'REFERENCES', 'USED_IN', 'ALTERNATE_VERSION', 'APPROVED_FOR', 'LINKED_CONTEXT'];
const referenceKinds: readonly StudioReferenceKind[] = ['ASSET', 'CHAPTER', 'SCREENPLAY'];
function relationshipInvalid(input = false): never {
  throw new ApiError({ status: input ? 400 : 200, code: input ? 'STUDIO_RELATIONSHIP_INPUT_INVALID' : 'STUDIO_RESPONSE_INVALID',
    message: input ? '关联输入不完整，请重新核对目标与版本。' : '服务返回的关联数据不可用，请重新读取。' });
}
function relationRecord(value: unknown, input = false): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) relationshipInvalid(input);
  return value as Record<string, unknown>;
}
function relationText(value: unknown, maximum: number, input = false, allowEmpty = false): string {
  if (typeof value !== 'string' || value.length > maximum || (!allowEmpty && !value.trim()) || (!allowEmpty && /[\u0000-\u001f\u007f]/.test(value))) relationshipInvalid(input);
  return value;
}
function referenceKind(value: unknown, input = false): StudioReferenceKind {
  if (!referenceKinds.includes(value as StudioReferenceKind)) relationshipInvalid(input);
  return value as StudioReferenceKind;
}
function relationshipKind(value: unknown, input = false): StudioRelationshipType {
  if (!relationshipKinds.includes(value as StudioRelationshipType)) relationshipInvalid(input);
  return value as StudioRelationshipType;
}
function relationVersion(value: unknown, input = false): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) relationshipInvalid(input);
  return value;
}
function relationDigest(value: unknown, input = false): string {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) relationshipInvalid(input);
  return value;
}
function referenceTarget(value: unknown, input = false): AssetRelationshipTarget {
  const row = relationRecord(value, input);
  return { kind: referenceKind(row.kind, input), id: relationText(row.id, 240, input),
    version: relationVersion(row.version, input), digest: relationDigest(row.digest, input) };
}
function relationshipReference(value: unknown): StudioReference {
  const row = relationRecord(value);
  if (typeof row.deleted !== 'boolean') relationshipInvalid();
  return { ...referenceTarget(row), label: relationText(row.label, 4096, false, true), deleted: row.deleted };
}
/** Pick only the public projection. Inaccessible targets must never carry their
 * hidden IDs, digests, author declarations or expected snapshots to consumers.
 */
function checkedRelationship(value: unknown): StudioRelationship {
  const row = relationRecord(value);
  const id = relationText(row.id, 240), type = relationshipKind(row.type);
  if (row.state === 'UNAVAILABLE') {
    return { id, type, state: 'UNAVAILABLE', target: { label: '关联内容不可用或无权访问' } };
  }
  if (!['CURRENT', 'STALE', 'DELETED'].includes(row.state as string) || row.semantics !== 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION') relationshipInvalid();
  return { id, type, state: row.state as 'CURRENT' | 'STALE' | 'DELETED', target: relationshipReference(row.target),
    expected: referenceTarget(row.expected), reason: relationText(row.reason, 1000, false, true),
    created_by: relationText(row.created_by, 240), created_at: relationText(row.created_at, 64),
    semantics: 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION' };
}
function relationshipPayload(value: StudioRelationshipInput): StudioRelationshipInput {
  const row = relationRecord(value, true);
  return { expected_version: version(row.expected_version as number, 1), type: relationshipKind(row.type, true),
    target: referenceTarget(row.target, true), reason: relationText(row.reason === undefined ? '' : row.reason, 1000, true, true) };
}
function checkedReferences(value: unknown, kind: StudioReferenceKind): StudioReferences {
  const row = relationRecord(value);
  if (row.read_only !== true || row.content_copied !== false || !Array.isArray(row.items) || row.items.length > 1000) relationshipInvalid();
  const items = row.items.map(relationshipReference);
  if (items.some(item => item.kind !== kind)) relationshipInvalid();
  return { items, read_only: true, content_copied: false };
}
function checkedRelationshipGraph(value: unknown): StudioRelationshipsGraph {
  const row = relationRecord(value);
  if (row.graph_kind !== 'ASSET_RELATIONSHIPS' || row.executable !== false || row.knowledge_graph !== false || row.automatic_regeneration !== false
    || !Array.isArray(row.nodes) || row.nodes.length > 1000 || !Array.isArray(row.edges)) relationshipInvalid();
  const nodes = row.nodes.map(value => {
    const node = relationRecord(value);
    if (node.kind !== 'ASSET') relationshipInvalid();
    return { id: relationText(node.id, 240), kind: 'ASSET' as const, asset_kind: relationText(node.asset_kind, 160),
      label: relationText(node.label, 4096, false, true), version: relationVersion(node.version), digest: relationDigest(node.digest) };
  });
  const nodeIDs = new Set(nodes.map(node => node.id));
  const edges: StudioRelationshipGraphEdge[] = row.edges.map((value): StudioRelationshipGraphEdge => {
    const edge = relationRecord(value), from = relationText(edge.from, 240);
    if (!nodeIDs.has(from)) relationshipInvalid();
    if (edge.owner === undefined) return { ...checkedRelationship(edge), from };
    if (edge.owner !== 'ASSET_LINEAGE' || edge.type !== 'DERIVED_FROM') relationshipInvalid();
    const base = { id: relationText(edge.id, 240), from, type: 'DERIVED_FROM' as const, owner: 'ASSET_LINEAGE' as const };
    if (edge.state === 'UNAVAILABLE') return { ...base, state: 'UNAVAILABLE', target: { label: '来源不可用或无权访问' } };
    if (!['CURRENT', 'STALE', 'DELETED'].includes(edge.state as string)) relationshipInvalid();
    return { ...base, state: edge.state as 'CURRENT' | 'STALE' | 'DELETED', target: relationshipReference(edge.target) };
  });
  return { graph_kind: 'ASSET_RELATIONSHIPS', nodes, edges, executable: false, knowledge_graph: false, automatic_regeneration: false };
}

export function studioTransport(context: CollaborationContext) {
  // Clone scope before any asynchronous work. Never read the active global
  // collaboration context or a later host session when a request is sent.
  const scope = context.scope ? { ...context.scope } : undefined;
  const token = context.sessionToken || (!scope && !context.actor && !isPackagedDesktopHost()
    ? (context.localHostToken ?? useLocalHostSession.getState().token) : '');
  const branch = scope?.branchId;

  // Only the preview-specific path opts into bounded bodies and redirect rejection.
  // Existing JSON and generic download callers retain their transport contract.
  function cancelBody(result: Response): void {
    try { void result.body?.cancel().catch(() => undefined); } catch { /* Best-effort cleanup, without exposing transport details. */ }
  }
  async function response(url: string, method = 'GET', body?: unknown, signal?: AbortSignal, idempotencyKey?: string, bounded = false): Promise<Response> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json', 'X-Request-ID': crypto.randomUUID() };
    if (token) headers['X-Session-Token'] = token;
    if (branch) headers['X-Branch-Id'] = branch;
    if (method !== 'GET') headers['Idempotency-Key'] = idempotencyKey ?? crypto.randomUUID();
    let result: Response;
    try {
      result = await fetch(url, { method, headers, signal, ...(bounded ? { redirect: 'error' as const } : {}), ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    } catch (error) {
      if (signal?.aborted || (error instanceof Error && error.name === 'AbortError')) {
        throw new DOMException('请求已取消。', 'AbortError');
      }
      throw new ApiError({ status: 0, code: 'STUDIO_NETWORK_FAILED', message: '连接未完成。请检查连接状态后重试。' });
    }
    if (bounded && (signal?.aborted || result.redirected || ['opaque', 'opaqueredirect', 'error'].includes(result.type))) {
      cancelBody(result);
      if (signal?.aborted) throw new DOMException('请求已取消。', 'AbortError');
      throw new ApiError({ status: result.status, code: 'STUDIO_RESPONSE_INVALID', message: '文件响应不可用，请重新读取。' });
    }
    if (!result.ok) {
      let raw: unknown;
      // Error bodies also must not bypass the preview byte limit.
      if (bounded) cancelBody(result);
      else try { raw = await result.json(); } catch { /* Never expose HTML, provider details or paths. */ }
      const record = raw && typeof raw === 'object' ? raw as Record<string, unknown> : undefined;
      const detail = record?.detail && typeof record.detail === 'object' ? record.detail as Record<string, unknown> : undefined;
      const code = record?.code ?? detail?.code;
      throw new ApiError({
        status: result.status,
        code: typeof code === 'string' && /^[A-Z][A-Z0-9_]{0,119}$/.test(code) ? code : 'STUDIO_REQUEST_FAILED',
        message: result.status === 507 && code === 'CREATIVE_STORAGE_LOW_SPACE' ? '资产所在磁盘的可用空间不足。请释放空间后重试导入。'
          : result.status === 507 && code === 'CREATIVE_STORAGE_UNAVAILABLE' ? '暂时无法确认资产存储的可用空间。请检查存储位置是否可访问后重试。'
          : result.status === 409 ? '版本或来源已经变化。当前草稿已保留，请核对服务端版本。'
          : result.status === 401 || result.status === 403 ? '当前会话无权访问此内容。请重新核对身份和分支。'
            : result.status === 404 ? '记录不可用，或此功能尚未启用。' : '请求未完成。请核对输入与连接状态。',
      });
    }
    return result;
  }

  return {
    async json<T>(url: string, method = 'GET', body?: unknown, signal?: AbortSignal, idempotencyKey?: string): Promise<T> {
      const result = await response(url, method, body, signal, idempotencyKey);
      try { return await result.json() as T; }
      catch { throw new ApiError({ status: result.status, code: 'STUDIO_RESPONSE_INVALID', message: '服务返回的数据不可用，请重新读取。' }); }
    },
    async blob(url: string, method = 'GET', body?: unknown, signal?: AbortSignal, idempotencyKey?: string): Promise<Blob> {
      const result = await response(url, method, body, signal, idempotencyKey);
      try { return await result.blob(); }
      catch { throw new ApiError({ status: result.status, code: 'STUDIO_RESPONSE_INVALID', message: '文件未能读取，请重试下载。' }); }
    },
    async boundedBlob(url: string, maxBytes: number, signal?: AbortSignal): Promise<Blob> {
      if (!Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 8 * 1024 * 1024) {
        throw new ApiError({ status: 400, code: 'STUDIO_DOWNLOAD_LIMIT_INVALID', message: '预览文件大小上限无效。' });
      }
      if (signal?.aborted) throw new DOMException('请求已取消。', 'AbortError');
      const result = await response(url, 'GET', undefined, signal, undefined, true);
      const tooLarge = () => new ApiError({ status: result.status, code: 'STUDIO_DOWNLOAD_TOO_LARGE', message: '文件超过预览大小上限。' });
      const invalid = () => new ApiError({ status: result.status, code: 'STUDIO_RESPONSE_INVALID', message: '文件未能安全读取，请重试预览。' });
      const declaredLength = result.headers.get('Content-Length');
      // A declared size can reject early; only actual streamed bytes can admit it.
      if (declaredLength !== null && /^\d+$/.test(declaredLength) && Number(declaredLength) > maxBytes) {
        cancelBody(result);
        throw tooLarge();
      }
      if (!result.body || typeof result.body.getReader !== 'function') {
        cancelBody(result);
        throw invalid();
      }
      let reader: ReadableStreamDefaultReader<Uint8Array>;
      try { reader = result.body.getReader(); }
      catch { cancelBody(result); throw invalid(); }
      let canceled = false;
      const cancelReader = () => {
        if (canceled) return;
        canceled = true;
        try { void reader.cancel().catch(() => undefined); } catch { /* Cleanup cannot replace the sanitized failure. */ }
      };
      let rejectAbort!: (reason: DOMException) => void;
      const aborted = new Promise<never>((_resolve, reject) => { rejectAbort = reject; });
      const onAbort = () => {
        cancelReader();
        rejectAbort(new DOMException('请求已取消。', 'AbortError'));
      };
      signal?.addEventListener('abort', onAbort, { once: true });
      try {
        const readBytes = async () => {
          let size = 0;
          // One capped buffer also bounds bookkeeping for tiny or empty chunks.
          // Copying admits no oversized or mutable external backing buffers.
          const bytes = new Uint8Array(maxBytes);
          while (true) {
            if (signal?.aborted) throw new DOMException('请求已取消。', 'AbortError');
            const { done, value } = await reader.read();
            if (signal?.aborted) throw new DOMException('请求已取消。', 'AbortError');
            if (done) break;
            if (!(value instanceof Uint8Array)) throw invalid();
            if (value.byteLength > maxBytes - size) throw tooLarge();
            bytes.set(value, size);
            size += value.byteLength;
          }
          return new Blob([bytes.subarray(0, size)], { type: result.headers.get('Content-Type') || '' });
        };
        // Race once, rather than retaining an abort-promise reaction per chunk.
        return await Promise.race([readBytes(), aborted]);
      } catch (error) {
        cancelReader();
        if (signal?.aborted || (error instanceof Error && error.name === 'AbortError')) throw new DOMException('请求已取消。', 'AbortError');
        if (error instanceof ApiError) throw error;
        throw invalid();
      } finally {
        signal?.removeEventListener('abort', onAbort);
        try { reader.releaseLock(); } catch { /* A broken reader must not mask the original result. */ }
      }
    },
  };
}

export function createStudioProject(title: string, context: CollaborationContext): Promise<StudioCreatedProject> {
  return studioTransport(context).json<StudioCreatedProject>('/api/experimental/projects', 'POST', { title });
}

export function studioClient(projectId: string, context: CollaborationContext) {
  const scope = context.scope ? { ...context.scope } : undefined;
  const transport = studioTransport({ ...context, scope });
  const base = `/api/projects/${encodeURIComponent(projectId)}/studio`;
  const assetUrl = (id: string) => `${base}/assets/${encodeURIComponent(id)}`;
  const branch = scope?.branchId || null;
  function mismatch(): never {
    throw new ApiError({ status: 403, code: 'STUDIO_RESPONSE_SCOPE_MISMATCH', message: '返回内容与当前项目或分支不一致，请重新读取。' });
  }
  function checkedAsset(asset: StudioAsset): StudioAsset {
    if (!asset || asset.novel_id !== projectId || (asset.branch_id ?? null) !== branch) mismatch();
    if (asset.relationships !== undefined) {
      if (!Array.isArray(asset.relationships) || asset.relationships.length > 100) relationshipInvalid();
      return { ...asset, relationships: asset.relationships.map(checkedRelationship) };
    }
    return asset;
  }
  function checkedProject<T extends { project: StudioProject }>(value: T): T {
    if (!value || value.project?.id !== projectId) mismatch();
    return value;
  }
  function checkedOverview<T extends StudioOverview>(value: T): T {
    checkedProject(value);
    return { ...value, preferences: checkedStudioPreferences(value.preferences) };
  }
  function checkedActivation(value: unknown): StudioActivation {
    // Activation needs its exact project acknowledgement, not workspace state.
    // Do not fabricate preference versions or treat response capabilities as grants.
    if (!value || typeof value !== 'object' || Array.isArray(value) || !Object.hasOwn(value, 'project')) mismatch();
    const row = value as Record<string, unknown>, project = row.project as Record<string, unknown> | null;
    if (!project || typeof project !== 'object' || Array.isArray(project)
      || !['id', 'title', 'entry_kind'].every(key => Object.hasOwn(project, key))
      || project.id !== projectId || typeof project.title !== 'string' || project.entry_kind !== 'NEUTRAL_STUDIO') mismatch();
    // An explicit malformed preference response is still rejected; absence is
    // not default state and full overview/preference reads remain strict.
    if (Object.hasOwn(row, 'preferences')) checkedStudioPreferences(row.preferences);
    return { project: { id: projectId, title: project!.title as string, entry_kind: 'NEUTRAL_STUDIO' } };
  }
  return {
    graphs: createStudioGraphClient(projectId, { scope }, transport),
    productionContracts: createStudioWorkspaceOperationClient(projectId, transport, scope).read,
    overview: (signal?: AbortSignal) => transport.json<StudioOverview>(base, 'GET', undefined, signal).then(checkedOverview),
    activate: () => transport.json<unknown>(`${base}/activate`, 'POST').then(checkedActivation),
    preferences: (signal?: AbortSignal) => transport.json<StudioPreferences>(`${base}/preferences`, 'GET', undefined, signal).then(checkedStudioPreferences),
    savePreferences: (value: StudioPreferencesInput, expectedVersion: number) => transport.json<StudioPreferences>(`${base}/preferences`, 'PUT', {
      intents: [...value.intents], preset: value.preset, custom_intent: value.custom_intent, expected_version: version(expectedVersion, 0),
    }).then(checkedStudioPreferences),
    assets: (includeDeleted = false, signal?: AbortSignal) => transport.json<{ items: StudioAsset[] }>(`${base}/assets?include_deleted=${includeDeleted ? 'true' : 'false'}`, 'GET', undefined, signal).then(value => {
      if (!value || !Array.isArray(value.items)) mismatch();
      return { items: value.items.map(checkedAsset) };
    }),
    importAsset: (body: StudioImportInput) => transport.json<StudioAsset>(`${base}/assets`, 'POST', body, undefined, body.idempotency_key).then(checkedAsset),
    previewVideoReference: async (asset: StudioAsset, input: VideoReferenceWindow, signal?: AbortSignal) => {
      const source = checkedVideoReferenceSource(checkedAsset(asset)), window = checkedVideoReferenceWindow(input);
      if (signal?.aborted) throw new DOMException('预览已取消。', 'AbortError');
      const value = await transport.json<unknown>(`${assetUrl(source.id)}/video-reference/preview`, 'POST', {
        contract: VIDEO_REFERENCE_PREVIEW, source_version: source.version, source_sha256: source.sha256, ...window,
      }, signal);
      return checkedVideoReferencePreview(value, source, window);
    },
    saveVideoReference: async (asset: StudioAsset, review: VideoReferencePreview, selectedIndex: number, key: string, signal?: AbortSignal) => {
      const source = checkedVideoReferenceSource(checkedAsset(asset));
      if (!Number.isSafeInteger(selectedIndex) || selectedIndex < 0 || selectedIndex >= review.sample_count
        || typeof key !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(key)) throw new Error('视频参考保存选择或请求标识无效。');
      const checked = await checkedVideoReferencePreview(review, source, review), frame = checked.frames[selectedIndex];
      if (signal?.aborted) throw new DOMException('保存已取消，请核对素材库。', 'AbortError');
      const value = await transport.json<unknown>(`${assetUrl(source.id)}/video-reference/save`, 'POST', {
        contract: VIDEO_REFERENCE_ASSET, source_version: source.version, source_sha256: source.sha256,
        in_ms: checked.in_ms, out_ms: checked.out_ms, sample_count: checked.sample_count, selected_index: selectedIndex,
        reviewed_preview_digest: checked.preview_digest, reviewed_png_sha256: frame.png_sha256, confirm_reference: true, idempotency_key: key,
      }, signal, key);
      const result = checkedVideoReferenceSaved(value, source, checked, selectedIndex); checkedAsset(result.asset); return result;
    },
    importModelReference: async (body: ModelReferenceImport) => {
      if(body.contract!=='studio-static-glb-import/1'||typeof body.filename!=='string'||!body.filename.toLowerCase().endsWith('.glb')||body.filename.length>255||typeof body.content_base64!=='string'||body.content_base64.length>4*Math.ceil(8*1024*1024/3)||typeof body.idempotency_key!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(body.idempotency_key)) throw new Error('GLB 导入输入无效。');
      let binary:string;try{binary=atob(body.content_base64);}catch{throw new Error('GLB 文件编码无效。');}
      if(binary.length<28||binary.length>8*1024*1024||btoa(binary)!==body.content_base64)throw new Error('GLB 文件编码或大小无效。');
      const hash=await maskSha256(Uint8Array.from(binary,char=>char.charCodeAt(0)));
      const result=checkedModelReferenceAsset(checkedAsset(await transport.json<StudioAsset>(`${base}/assets/model-reference`, 'POST', body, undefined, body.idempotency_key)));
      if(result.size!==binary.length||result.sha256!==hash)throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'导入回执与所选文件字节不一致；请核对原素材，未自动重试。'});
      return result;
    },
    inspectModelReference: (asset: StudioAsset, signal?: AbortSignal) => transport.json<unknown>(`${assetUrl(asset.id)}/model-reference`, 'GET', undefined, signal).then(value => checkedModelReferenceInspection(value,checkedAsset(asset))),
    inspectModelMesh: (asset: StudioAsset, signal?: AbortSignal) => transport.json<unknown>(`${assetUrl(asset.id)}/model-reference/mesh-preview`, 'GET', undefined, signal).then(value => checkedModelMeshPreview(value,checkedAsset(asset))),
    inspectModelMaterials: (asset: StudioAsset, signal?: AbortSignal) => transport.json<unknown>(`${assetUrl(asset.id)}/model-reference/materials`, 'GET', undefined, signal).then(value => checkedModelMaterials(value,checkedAsset(asset))),
    inspectModelCameras: async (asset: StudioAsset, signal?: AbortSignal) => {
      const source=structuredClone(checkedModelReferenceAsset(checkedAsset(asset)));
      if(signal?.aborted)throw new DOMException('读取已取消。','AbortError');
      const value=await transport.json<unknown>(`${assetUrl(source.id)}/model-reference/cameras`,'GET',undefined,signal);
      if(signal?.aborted)throw new DOMException('读取已取消。','AbortError');
      return checkedModelCameras(value,source);
    },
    exportModelCamera: async (asset: StudioAsset, selection: ModelCameraSelection, signal?: AbortSignal) => {
      const source=structuredClone(checkedModelReferenceAsset(checkedAsset(asset))),choice=checkedModelCameraSelection(selection);
      if(signal?.aborted)throw new DOMException('导出已取消。','AbortError');
      const value=await transport.json<unknown>(`${assetUrl(source.id)}/model-reference/camera-export`,'POST',{
        contract:MODEL_CAMERA_EXPORT_CONTRACT,source_version:source.version,source_sha256:source.sha256,
        scene_index:choice.scene_index,node_index:choice.camera.node_index,camera_index:choice.camera.camera_index,profile:'GLTF_2_CAMERA_ONLY',
      },signal);
      if(signal?.aborted)throw new DOMException('导出已取消。','AbortError');
      const result=await checkedModelCameraExport(value,source,choice);
      if(signal?.aborted)throw new DOMException('导出已取消。','AbortError');
      return result;
    },
    inspectModelScene: (asset: StudioAsset, signal?: AbortSignal) => transport.json<unknown>(`${assetUrl(asset.id)}/model-reference/scene-preview`, 'GET', undefined, signal).then(value => checkedModelScenePreview(value,checkedAsset(asset))),
    saveModelClay: async (asset: StudioAsset, review: ModelClayExport, key: string) => {
      const source=structuredClone(checkedModelReferenceAsset(checkedAsset(asset)));
      const checked=await checkedModelClay(review,source,{yaw:review.clay_export.yaw,pitch:review.clay_export.pitch});
      if(!/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(key))throw new Error('灰模保存请求标识无效。');
      const value=await transport.json<unknown>(`${assetUrl(source.id)}/model-reference/clay-save`,'POST',{
        contract:CLAY_ASSET_CONTRACT,source_version:source.version,source_sha256:source.sha256,
        yaw:checked.clay_export.yaw,pitch:checked.clay_export.pitch,reviewed_png_sha256:checked.clay_export.png_sha256,
        confirm_reference:true,idempotency_key:key},undefined,key);
      const result=checkedClayAssetResult(value,source,checked);checkedAsset(result.asset);return result;
    },
    exportModelClay: async (asset: StudioAsset, camera: ModelDepthCamera, signal?: AbortSignal) => {
      const source=structuredClone(checkedModelReferenceAsset(checkedAsset(asset))),view=checkedDepthCamera(camera);
      const value=await transport.json<unknown>(`${assetUrl(source.id)}/model-reference/clay-export`, 'POST', {contract:'studio-static-glb-clay-export/1',source_version:source.version,source_sha256:source.sha256,...view},signal);
      return checkedModelClay(value,source,view);
    },
    exportModelDepth: async (asset: StudioAsset, camera: ModelDepthCamera, signal?: AbortSignal) => {
      const source=structuredClone(checkedModelReferenceAsset(checkedAsset(asset))),view=checkedDepthCamera(camera);
      const value=await transport.json<unknown>(`${assetUrl(source.id)}/model-reference/depth-export`, 'POST', {contract:'studio-static-glb-depth-export/1',source_version:source.version,source_sha256:source.sha256,...view},signal);
      return checkedModelDepth(value,source,view);
    },
    asset: (id: string, signal?: AbortSignal) => transport.json<StudioAsset>(assetUrl(id), 'GET', undefined, signal).then(checkedAsset),
    lineage: (id: string, body: StudioLineageInput) => transport.json<StudioAsset>(`${assetUrl(id)}/lineage`, 'PUT', { ...body, expected_version: version(body.expected_version, 1) }).then(checkedAsset),
    download: (id: string, signal?: AbortSignal) => transport.blob(`${assetUrl(id)}/download`, 'GET', undefined, signal),
    downloadBounded: (id: string, maxBytes: number, signal?: AbortSignal) => transport.boundedBlob(`${assetUrl(id)}/download`, maxBytes, signal),
    createMask: async (sourceId: string, input: StudioMaskInput, signal?: AbortSignal) => {
      if (signal?.aborted) throw new DOMException('请求已取消。', 'AbortError');
      const id = relationText(sourceId, 240, true);
      const { body, bytes, keep } = checkedMaskInput(input);
      const sha = await maskSha256(bytes);
      if (signal?.aborted) throw new DOMException('请求已取消。', 'AbortError');
      const value = await transport.json<unknown>(`${assetUrl(id)}/mask`, 'POST', body, signal, body.idempotency_key);
      if (signal?.aborted) throw new DOMException('请求已取消。', 'AbortError');
      return checkedMaskResult(value, id, body, sha, keep, projectId, branch);
    },
    remove: (id: string, expectedVersion: number) => transport.json<StudioAsset>(`${assetUrl(id)}?expected_version=${version(expectedVersion, 1)}`, 'DELETE').then(checkedAsset),
    restore: (id: string, expectedVersion: number) => transport.json<StudioAsset>(`${assetUrl(id)}/restore`, 'POST', { expected_version: version(expectedVersion, 1) }).then(checkedAsset),
    storage: (signal?: AbortSignal) => transport.json<StudioStorage>(`${base}/storage`, 'GET', undefined, signal).then(checkedStorage),
    references: (kind: StudioReferenceKind, signal?: AbortSignal) => {
      const selected = referenceKind(kind, true);
      return transport.json<StudioReferences>(`${base}/references?kind=${encodeURIComponent(selected)}`, 'GET', undefined, signal).then(value => checkedReferences(value, selected));
    },
    relationships: (signal?: AbortSignal) => transport.json<StudioRelationshipsGraph>(`${base}/relationships`, 'GET', undefined, signal).then(checkedRelationshipGraph),
    addRelationship: (id: string, body: StudioRelationshipInput) => transport.json<StudioAsset>(`${assetUrl(relationText(id, 240, true))}/relationships`, 'POST', relationshipPayload(body)).then(checkedAsset),
    removeRelationship: (id: string, relationshipId: string, expectedVersion: number) => transport.json<StudioAsset>(`${assetUrl(relationText(id, 240, true))}/relationships/${encodeURIComponent(relationText(relationshipId, 240, true))}?expected_version=${version(expectedVersion, 1)}`, 'DELETE').then(checkedAsset),
  };
}
export type StudioClient = ReturnType<typeof studioClient>;
