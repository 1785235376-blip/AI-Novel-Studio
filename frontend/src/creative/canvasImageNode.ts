import { ApiError } from '../api';
import type { StudioGraphScope } from './studioGraphTypes';
import type { CanvasAssetReference, CanvasViewRecord } from './studioCanvasViewClient';
import type { ProductionJob, RecordedMediaCommand } from './studioProductionClient';
import type { StudioAsset } from './studioClient';

/** A single explicit placement over the original CanvasView and production owners. */
export type CanvasImageNodeBinding = { contract: 'studio-canvas-image-node/1'; project_id: string; scope: StudioGraphScope;
  incarnation: string; canvas_id: string; canvas_version: number; canvas_digest: string;
  node_id: string; title: string; position: { x: number; y: number }; prompt_digest: string };
export type CanvasImageNodeOrigin = { contract: 'studio-canvas-image-node-result/1'; target: CanvasImageNodeBinding;
  job_id: string; job_version: number; job_request_digest: string; asset: CanvasAssetReference };
export type CanvasImageNodeTaskBinding = { binding: CanvasImageNodeBinding; initialPrompt: string; isCurrent: () => boolean };
const obj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const exact = (v: Record<string, unknown>, keys: string[]) => Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k));
const id = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(v);
const hex = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const rev = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 1;
export const canonicalImageNode = (v: unknown) => JSON.stringify(v, (_k, x) => obj(x) ? Object.fromEntries(Object.entries(x).sort(([a], [b]) => a.localeCompare(b))) : x);
function invalid(): never { throw new ApiError({ status: 422, code: 'STUDIO_CANVAS_IMAGE_NODE_INVALID', message: '原图片节点、正式任务或保存位置已改变，请重新读取核对。' }); }
export function checkedCanvasImageNodeBinding(v: unknown): CanvasImageNodeBinding {
  if (!obj(v) || !exact(v, ['contract', 'project_id', 'scope', 'incarnation', 'canvas_id', 'canvas_version', 'canvas_digest', 'node_id', 'title', 'position', 'prompt_digest'])
    || v.contract !== 'studio-canvas-image-node/1' || !id(v.project_id) || !id(v.canvas_id) || !rev(v.canvas_version)
    || !hex(v.canvas_digest) || !hex(v.prompt_digest) || typeof v.node_id !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(v.node_id)
    || typeof v.title !== 'string' || !v.title.trim() || [...v.title].length > 160
    || typeof v.incarnation !== 'string' || !/^(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(v.incarnation)
    || !obj(v.position) || !exact(v.position, ['x', 'y']) || Object.values(v.position).some(n => typeof n !== 'number' || !Number.isFinite(n) || Math.abs(n) > 100_000)) invalid();
  const scope = v.scope;
  if (!obj(scope) || scope.novel_id !== v.project_id || (scope.mode === 'local'
    ? !exact(scope, ['mode', 'novel_id']) : scope.mode !== 'collaboration' || !exact(scope, ['mode', 'novel_id', 'workspace_id', 'storyline_id', 'branch_id']) || ![scope.workspace_id, scope.storyline_id, scope.branch_id].every(id))) invalid();
  return structuredClone(v) as CanvasImageNodeBinding;
}
export function canvasImageNodeInCommand(command: unknown): CanvasImageNodeBinding | undefined {
  if (!obj(command) || !Object.hasOwn(command, 'canvas_image_node')) return;
  const binding = checkedCanvasImageNodeBinding(command.canvas_image_node);
  if (command.operation_id !== 'm5.image.t2i' || command.allow_cloud !== false || !Array.isArray(command.source_snapshots) || command.source_snapshots.length
    || typeof command.prompt !== 'string' || !command.prompt.trim() || command.prompt.length > 16000
    || ['canvas_return', 'image_source', 'image_references', 'mask_source', 'video_reference', 'video_frames', 'storyboard_shot', 'storyboard_speech', 'audio_profile', 'image_layers'].some(k => Object.hasOwn(command, k))) invalid();
  return binding;
}
export function sameCanvasImageNode(a: unknown, b: unknown): boolean {
  return canonicalImageNode(canvasImageNodeInCommand(a)) === canonicalImageNode(canvasImageNodeInCommand(b));
}
export async function imageNodePromptDigest(prompt: string): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error('当前环境无法核对提示词摘要，未准备正式节点任务。');
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(prompt))), b => b.toString(16).padStart(2, '0')).join('');
}
export async function verifyCanvasImageNodePrompt(command: RecordedMediaCommand): Promise<void> {
  const binding = canvasImageNodeInCommand(command);
  if (binding && await imageNodePromptDigest(command.prompt) !== binding.prompt_digest) invalid();
}
export function checkedCanvasImageNodeOrigin(v: unknown): CanvasImageNodeOrigin {
  if (!obj(v) || !exact(v, ['contract', 'target', 'job_id', 'job_version', 'job_request_digest', 'asset']) || v.contract !== 'studio-canvas-image-node-result/1'
    || !id(v.job_id) || !rev(v.job_version) || !hex(v.job_request_digest) || !obj(v.asset) || !exact(v.asset, ['asset_id', 'version', 'digest', 'kind'])
    || !id(v.asset.asset_id) || !rev(v.asset.version) || !hex(v.asset.digest) || v.asset.kind !== 'image') invalid();
  return { ...structuredClone(v), target: checkedCanvasImageNodeBinding(v.target) } as CanvasImageNodeOrigin;
}
export function assertCanvasImageNodeJob(binding: CanvasImageNodeBinding, job: ProductionJob): void {
  if (job.owner !== 'image' || job.novel_id !== binding.project_id || job.branch_id !== (binding.scope.mode === 'collaboration' ? binding.scope.branch_id : null)
    || job.operation_id !== 'm5.image.t2i' || job.provider?.local !== true || job.sources.length
    || canonicalImageNode(canvasImageNodeInCommand(job.command)) !== canonicalImageNode(binding)) invalid();
}
export function imageNodeApprovedPin(binding: CanvasImageNodeBinding, job: ProductionJob, asset: StudioAsset): CanvasAssetReference {
  assertCanvasImageNodeJob(binding, job);
  if (job.status !== 'APPROVED' || !job.output_candidate || job.output_candidate.kind !== 'image' || asset.kind !== 'image' || asset.deleted_at
    || asset.novel_id !== binding.project_id || (asset.branch_id ?? null) !== job.branch_id || asset.id !== job.output_candidate.id
    || asset.version !== job.approved_asset_version || asset.sha256 !== job.output_candidate.digest || !rev(asset.version) || !hex(asset.sha256)) invalid();
  return { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'image' };
}
export function assertSavedImageNode(record: CanvasViewRecord, binding: CanvasImageNodeBinding, job?: ProductionJob, pin?: CanvasAssetReference, initialPosition = false): void {
  const origin = checkedCanvasImageNodeOrigin(record.definition.image_node_origin), card = record.definition.cards.find(c=>c.id===binding.node_id);
  if (record.project_id !== binding.project_id || record.id !== binding.canvas_id || canonicalImageNode(record.scope) !== canonicalImageNode(binding.scope)
    || canonicalImageNode(origin.target) !== canonicalImageNode(binding) || initialPosition&&record.definition.cards.length !== 1 || card?.id !== binding.node_id
    || initialPosition && canonicalImageNode(card.position) !== canonicalImageNode(binding.position) || canonicalImageNode(card.asset) !== canonicalImageNode(origin.asset)
    || record.reference_states.find(s=>s.card_id===binding.node_id)?.state !== 'CURRENT_METADATA'
    || job && (origin.job_id !== job.id || origin.job_version !== job.version || origin.job_request_digest !== job.request_digest)
    || pin && canonicalImageNode(origin.asset) !== canonicalImageNode(pin)) invalid();
}
