import { ApiError, type CollaborationContext } from '../api';
import { studioTransport } from './studioClient';
import type { StudioTimeline, StudioTimelineRow } from './studioTimelineTypes';

export type ProductionOwner = 'image' | 'audio' | 'video' | 'timeline';
export type MediaOperation = 'm5.image.t2i' | 'm5.image.i2i' | 'm7.video.t2v' | 'm7.video.i2v' | 'm7.video.v2v' | 'm8.audio.speech' | 'm8.audio.music' | 'm8.audio.effects' | 'm8.audio.trim';
export type ProductionSource = { id: string; kind: 'ASSET'; version: number; digest: string; asset_kind: 'image' | 'video' | 'audio'; reference_only?: true };
export type MediaCommand = { operation_id: MediaOperation; request_id: string; provider_id?: string | null; model_id?: string | null; prompt: string;
  parameters: Record<string, string | number>; source_snapshots: ProductionSource[]; allow_cloud: boolean; license_note: string };
export type RecordedProductionSource = ProductionSource | { id: string; kind: 'CREATIVE_DOCUMENT'; version: number; digest: string; reference_only?: true };
export type RecordedMediaCommand = Omit<MediaCommand, 'source_snapshots'> & { source_snapshots: RecordedProductionSource[] };
export type ProductionProvider = { operation_id: MediaOperation; provider_id: string; model_id: string; local: boolean; route_digest: string; capability: string; supported_parameters: string[]; readiness: 'CONFIGURED_NOT_VERIFIED' };
export type ProductionPreview = { contract: 'studio-production-preview/1'; novel_id: string; branch_id: string | null; request_id: string; operation_id: MediaOperation;
  preview_digest: string; request_digest: string; command: MediaCommand; provider: { provider_id: string; model_id: string; local: boolean; route_digest: string } | null;
  execution_recipe: ProductionRecipe; product_acceptance: 'LOCAL_REQUIRED'; execution_available: true; automatic_dispatch: false; output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
export type ProductionRecipe = { contract: 'studio-execution-recipe/1'; operation_id: string; adapter: string; recipe_digest: string; automatic_fallback: false; [key: string]: unknown };
export type ProductionJob = { contract: 'studio-production-job/1'; owner: ProductionOwner; id: string; novel_id: string; branch_id: string | null; version: number;
  operation_id: string; request_id: string; status: 'QUEUED' | 'RUNNING' | 'SEND_RESERVED' | 'REMOTE_RUNNING' | 'RESULT_READY' | 'AWAITING_REVIEW' | 'SUCCEEDED' | 'REVIEWING' | 'APPROVED' | 'UNKNOWN' | 'FAILED' | 'CANCELLED';
  request_digest: string; receipt_digest: string | null; output_candidate: { id: string; version: number; digest: string; kind: 'image' | 'video' | 'audio' } | null;
  error_code?: string | null; review_state?: string | null; product_acceptance: 'LOCAL_REQUIRED'; automatic_replay: false; remote_compute_may_continue: boolean;
  timeline_snapshot: { id: string; version: number; digest: string } | null;
  sources: RecordedProductionSource[];
  command: RecordedMediaCommand | null;
  provider: { provider_id: string; model_id: string; local: boolean; route_digest: string } | null;
  execution_recipe: ProductionRecipe; approved_asset_version: number | null;
  needs_reconciliation?: boolean; execution_state?: string; created_at: string; updated_at: string };
export type ProductionAction = { expected_version: number; expected_request_digest: string };

const operations: MediaOperation[] = ['m5.image.t2i', 'm5.image.i2i', 'm7.video.t2v', 'm7.video.i2v', 'm7.video.v2v', 'm8.audio.speech', 'm8.audio.music', 'm8.audio.effects', 'm8.audio.trim'];
const owners: ProductionOwner[] = ['image', 'audio', 'video', 'timeline'];
const states = ['QUEUED', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING', 'APPROVED', 'UNKNOWN', 'FAILED', 'CANCELLED'];
const parameterKeys = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms'];
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const hex = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const identifier = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(v);
const revision = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 1;
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务回执不完整。请重新读取核对，勿重复发送。' }); }
function sources(v: unknown, limit: number): asserts v is RecordedProductionSource[] {
  if (!Array.isArray(v) || v.length > limit || v.some(s => !record(s) || !identifier(s.id) || !revision(s.version) || !hex(s.digest)
    || !['ASSET', 'CREATIVE_DOCUMENT'].includes(String(s.kind)) || s.reference_only !== undefined && s.reference_only !== true
    || Object.keys(s).some(k => !['id', 'kind', 'version', 'digest', 'asset_kind', 'reference_only'].includes(k))
    || (s.kind === 'ASSET' ? !['image', 'video', 'audio'].includes(String(s.asset_kind)) : s.asset_kind !== undefined))) invalid();
}
function recipe(v: unknown, operation: unknown): ProductionRecipe {
  if (!record(v) || v.contract !== 'studio-execution-recipe/1' || v.operation_id !== operation || !hex(v.recipe_digest)
    || v.automatic_fallback !== false || !['ORIGINAL_HTTP_PROVIDER', 'COMFYUI_BUILTIN_IMAGE', 'AUTOMATIC1111_IMAGE', 'LOCAL_FFMPEG'].includes(String(v.adapter))
    || Object.keys(v).some(k => !['contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback', 'parameters', 'workflow', 'defaults', 'denoising_strength', 'output_profile', 'timeline'].includes(k))
    || JSON.stringify(v).length > 131072) invalid();
  return v as ProductionRecipe;
}

export function studioProductionClient(projectId: string, context: CollaborationContext) {
  const capturedScope = context.scope ? { ...context.scope } : undefined;
  const original = studioTransport({ ...context, scope: capturedScope });
  function admitted() {
    if (capturedScope && capturedScope.projectId !== projectId) throw new ApiError({ status: 403,
      code: 'STUDIO_RESPONSE_SCOPE_MISMATCH', message: '制作任务与当前项目或分支不一致，请重新打开。' });
  }
  const transport = {
    json<T>(...args: Parameters<typeof original.json>) { admitted(); return original.json<T>(...args); },
    blob(...args: Parameters<typeof original.blob>) { admitted(); return original.blob(...args); },
  };
  const base = `/api/projects/${encodeURIComponent(projectId)}/studio/production`;
  const branch = context.scope?.branchId ?? null;
  const jobUrl = (owner: ProductionOwner, id: string) => `${base}/jobs/${owner}/${encodeURIComponent(id)}`;
  function scoped(v: Record<string, unknown>) { if (v.novel_id !== projectId || (v.branch_id ?? null) !== branch) invalid(); }
  function job(v: unknown): ProductionJob {
    if (!record(v)) invalid(); scoped(v);
    if (Object.keys(v).some(key => !['contract', 'owner', 'id', 'novel_id', 'branch_id', 'version', 'status', 'request_digest', 'receipt_digest',
      'attempt', 'created_at', 'updated_at', 'error_code', 'review_state', 'cancellation_mode', 'needs_reconciliation', 'execution_state', 'operation_id',
      'output_candidate', 'timeline_snapshot', 'sources', 'command', 'provider', 'execution_recipe', 'approved_asset_version', 'request_id',
      'product_acceptance', 'automatic_replay', 'remote_compute_may_continue'].includes(key))) invalid();
    if (v.contract !== 'studio-production-job/1' || !owners.includes(v.owner as ProductionOwner) || !identifier(v.id) || !revision(v.version)
      || !states.includes(String(v.status)) || !hex(v.request_digest) || (v.receipt_digest !== null && !hex(v.receipt_digest))
      || typeof v.request_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(v.request_id)
      || typeof v.operation_id !== 'string' || ![...operations, 'm9.timeline.multitrack'].includes(v.operation_id as MediaOperation)
      || v.product_acceptance !== 'LOCAL_REQUIRED' || v.automatic_replay !== false || typeof v.remote_compute_may_continue !== 'boolean') invalid();
    const expectedOwner = v.operation_id.startsWith('m5.') ? 'image' : v.operation_id.startsWith('m7.') ? 'video' : v.operation_id.startsWith('m8.') ? 'audio' : 'timeline';
    if (v.owner !== expectedOwner || typeof v.created_at !== 'string' || typeof v.updated_at !== 'string') invalid();
    if (v.output_candidate !== null) {
      const c = v.output_candidate;
      if (!record(c) || !identifier(c.id) || !revision(c.version) || !hex(c.digest) || !['image', 'video', 'audio'].includes(String(c.kind))) invalid();
    }
    sources(v.sources, 30);
    if (v.owner === 'timeline') {
      const s = v.timeline_snapshot;
      if (!record(s) || !identifier(s.id) || !revision(s.version) || !hex(s.digest) || v.operation_id !== 'm9.timeline.multitrack') invalid();
    } else if (v.timeline_snapshot !== null) invalid();
    recipe(v.execution_recipe, v.operation_id);
    if (v.approved_asset_version !== null && !revision(v.approved_asset_version)) invalid();
    if (v.owner === 'timeline') { if (v.command !== null || v.provider !== null) invalid(); }
    else {
      const c = v.command;
      if (!record(c) || c.operation_id !== v.operation_id || c.request_id !== v.request_id || typeof c.prompt !== 'string' || c.prompt.length > 16000
        || !record(c.parameters) || !Array.isArray(c.source_snapshots) || typeof c.allow_cloud !== 'boolean' || typeof c.license_note !== 'string' || c.license_note.length > 2000) invalid();
      if (Object.keys(c).some(key => !['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note'].includes(key))
        || Object.entries(c.parameters).some(([key, value]) => !parameterKeys.includes(key)
          || (typeof value === 'number' ? !Number.isFinite(value) : typeof value !== 'string' || value.length > 8000))) invalid();
      sources(c.source_snapshots, 8);
      if (c.source_snapshots.length !== v.sources.length || c.source_snapshots.some((s, index) => ['id', 'kind', 'version', 'digest', 'asset_kind'].some(key =>
        (s as Record<string, unknown>)[key] !== (v.sources as Array<Record<string, unknown>>)[index][key]))) invalid();
      if (c.operation_id === 'm8.audio.trim') { if (v.provider !== null) invalid(); }
      else if (!record(v.provider) || typeof c.provider_id !== 'string' || !c.provider_id || typeof c.model_id !== 'string' || !c.model_id
        || v.provider.provider_id !== c.provider_id || v.provider.model_id !== c.model_id || !hex(v.provider.route_digest) || typeof v.provider.local !== 'boolean'
        || Object.keys(v.provider).some(key => !['provider_id', 'model_id', 'route_digest', 'local'].includes(key))) invalid();
    }
    return v as unknown as ProductionJob;
  }
  function timeline(v: unknown): StudioTimelineRow {
    if (!record(v)) invalid(); scoped(v);
    if (!identifier(v.id) || !revision(v.version) || !hex(v.timeline_digest) || typeof v.title !== 'string' || v.title.length > 240 || !record(v.timeline)
      || !Array.isArray(v.timeline.tracks) || v.timeline.tracks.length > 8 || !Array.isArray(v.timeline.captions) || v.timeline.captions.length > 500) invalid();
    return { id: v.id, title: v.title, version: v.version, timeline_digest: v.timeline_digest, timeline: v.timeline as unknown as StudioTimeline,
      created_at: String(v.created_at), updated_at: String(v.updated_at) };
  }
  async function action(owner: ProductionOwner, id: string, operation: 'execute' | 'refresh' | 'cancel' | 'reconcile' | 'review', body: ProductionAction & { reviewed_output_digest?: string }) {
    const result = job(await transport.json<unknown>(`${jobUrl(owner, id)}/${operation}`, 'POST', body));
    if (result.owner !== owner || result.id !== id || result.request_digest !== body.expected_request_digest) invalid();
    return result;
  }
  return {
    async providers(signal?: AbortSignal): Promise<ProductionProvider[]> {
      const v = await transport.json<unknown>(`${base}/providers`, 'GET', undefined, signal);
      if (!record(v) || !Array.isArray(v.items) || v.items.length > 200 || v.health_probed !== false || v.credentials_read !== false) invalid();
      return v.items.map(row => {
        if (!record(row) || !operations.includes(row.operation_id as MediaOperation) || typeof row.provider_id !== 'string' || !row.provider_id || row.provider_id.length > 240
          || typeof row.model_id !== 'string' || !row.model_id || row.model_id.length > 240 || typeof row.local !== 'boolean' || !hex(row.route_digest) || row.readiness !== 'CONFIGURED_NOT_VERIFIED'
          || !Array.isArray(row.supported_parameters) || row.supported_parameters.length > 14 || row.supported_parameters.some(p => typeof p !== 'string'
            || !['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms'].includes(p))) invalid();
        return row as unknown as ProductionProvider;
      });
    },
    async preview(command: MediaCommand): Promise<ProductionPreview> {
      const v = await transport.json<unknown>(`${base}/preview`, 'POST', command);
      if (!record(v)) invalid(); scoped(v);
      recipe(v.execution_recipe, command.operation_id);
      if (v.contract !== 'studio-production-preview/1' || !hex(v.preview_digest) || !hex(v.request_digest) || v.request_id !== command.request_id || v.operation_id !== command.operation_id
        || v.product_acceptance !== 'LOCAL_REQUIRED' || v.execution_available !== true || v.automatic_dispatch !== false || v.output_policy !== 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW'
        || !record(v.command) || v.command.prompt !== command.prompt || v.command.operation_id !== command.operation_id || v.command.request_id !== command.request_id
        || (v.command.provider_id ?? null) !== (command.provider_id ?? null) || (v.command.model_id ?? null) !== (command.model_id ?? null)
        || v.command.allow_cloud !== command.allow_cloud || v.command.license_note !== command.license_note || !record(v.command.parameters)
        || Object.entries(command.parameters).some(([key, value]) => (v.command as Record<string, unknown>).parameters && ((v.command as Record<string, unknown>).parameters as Record<string, unknown>)[key] !== value)
        || !Array.isArray(v.command.source_snapshots) || v.command.source_snapshots.length !== command.source_snapshots.length
        || v.command.source_snapshots.some((s, index) => !record(s) || ['id', 'kind', 'version', 'digest', 'asset_kind'].some(key => s[key] !== command.source_snapshots[index][key as keyof ProductionSource]))) invalid();
      if (v.provider !== null && (!record(v.provider) || v.provider.provider_id !== command.provider_id || v.provider.model_id !== command.model_id || !hex(v.provider.route_digest) || typeof v.provider.local !== 'boolean')) invalid();
      return v as unknown as ProductionPreview;
    },
    async create(command: MediaCommand, reviewed_preview_digest: string) {
      const v = job(await transport.json<unknown>(`${base}/jobs`, 'POST', { command, reviewed_preview_digest }, undefined, command.request_id));
      if (v.request_id !== command.request_id || v.operation_id !== command.operation_id) invalid(); return v;
    },
    async list(signal?: AbortSignal) {
      const v = await transport.json<unknown>(`${base}/jobs`, 'GET', undefined, signal);
      if (!record(v) || !Array.isArray(v.items) || v.items.length > 1000) invalid(); return v.items.map(job);
    },
    async get(owner: ProductionOwner, id: string, signal?: AbortSignal) {
      const v = job(await transport.json<unknown>(jobUrl(owner, id), 'GET', undefined, signal)); if (v.owner !== owner || v.id !== id) invalid(); return v;
    },
    execute: (j: ProductionJob) => action(j.owner, j.id, 'execute', { expected_version: j.version, expected_request_digest: j.request_digest }),
    refresh: (j: ProductionJob) => action(j.owner, j.id, 'refresh', { expected_version: j.version, expected_request_digest: j.request_digest }),
    cancel: (j: ProductionJob) => action(j.owner, j.id, 'cancel', { expected_version: j.version, expected_request_digest: j.request_digest }),
    reconcile: (j: ProductionJob) => action(j.owner, j.id, 'reconcile', { expected_version: j.version, expected_request_digest: j.request_digest }),
    review: (j: ProductionJob) => action(j.owner, j.id, 'review', { expected_version: j.version, expected_request_digest: j.request_digest, reviewed_output_digest: j.output_candidate?.digest }),
    candidate: (j: ProductionJob) => transport.blob(`${jobUrl(j.owner, j.id)}/candidate`),
    async timelineList(signal?: AbortSignal) {
      const v = await transport.json<unknown>(`${base}/timelines`, 'GET', undefined, signal); if (!record(v) || !Array.isArray(v.items) || v.items.length > 25) invalid(); return { items: v.items.map(timeline) };
    },
    async timelineGet(id: string, signal?: AbortSignal) { return timeline(await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(id)}`, 'GET', undefined, signal)); },
    async timelineSave(id: string | undefined, body: { title: string; timeline: StudioTimeline; expected_version: number }) {
      return timeline(await transport.json<unknown>(id ? `${base}/timelines/${encodeURIComponent(id)}` : `${base}/timelines`, id ? 'PUT' : 'POST', body));
    },
    async timelineRender(id: string, body: { expected_version: number; reviewed_timeline_digest: string; request_id: string }) {
      return job(await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(id)}/render`, 'POST', body, undefined, body.request_id));
    },
  };
}
export type StudioProductionClient = ReturnType<typeof studioProductionClient>;
