import type {AssetProviderStatus} from '../api';
import type {CanvasTaskOwner} from '../rebuild/image/canvasTaskBinding';

type ImageParameter = string | number;
type ExecutionInput = Readonly<{
  provider_id: string; model_id: string; prompt: string;
  parameters: Readonly<Record<string, ImageParameter>>; allow_cloud_prompt: boolean;
  character_id?: string | null; scene_id?: string | null; images?: readonly [];
  size?: string; quality?: string; output_format?: string;
}>;

/** An in-memory observation of the original legacy row, not a server version or output digest. */
export type ImageJobExecutionSnapshot = Readonly<{
  owner: Readonly<CanvasTaskOwner>; jobId: string; novelId: string;
  branchId: string | null; ownerActorId: string | null;
  providerId: string; modelId: string; prompt: string;
  parameters: Readonly<Record<string, ImageParameter>>; allowCloudPrompt: boolean;
  requestSha256: string; attempt: number; updatedAt: string;
  input: ExecutionInput;
  /** Stable comparison text; contains the reviewed prompt/parameters. Never persist or display. */
  fingerprint: string;
}>;

const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const own = (value: Record<string, unknown>, key: string) => Object.hasOwn(value, key);
const ownerId = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 240
  && value.trim() === value && !/[\u0000-\u001f\u007f]/.test(value);
const jobId = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value);
const text = (value: unknown, limit: number): value is string => typeof value === 'string' && value.length > 0 && value.length <= limit
  && value.trim().length > 0 && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value);
const label = (value: unknown, limit: number): value is string => text(value, limit) && value.trim() === value && !/[\t\r\n]/.test(value);
const timestamp = (value: unknown): value is string => typeof value === 'string' && value.length <= 80
  && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const sizes = ['auto', '1024x1024', '1536x1024', '1024x1536'];
const qualities = ['auto', 'low', 'medium', 'high', 'standard', 'hd'];
const ownerKeys = ['mode', 'actorId', 'actorWorkspaceId', 'workspaceId', 'projectId', 'storylineId', 'branchId', 'novelId'] as const;

function checkedOwner(owner: CanvasTaskOwner): boolean {
  if (!object(owner) || !ownerId(owner.actorId) || !ownerId(owner.novelId) || owner.projectId !== owner.novelId) return false;
  if (owner.mode === 'local') return [owner.actorWorkspaceId, owner.workspaceId, owner.storylineId, owner.branchId].every(value => value === '');
  return owner.mode === 'collaboration' && [owner.actorWorkspaceId, owner.workspaceId, owner.storylineId, owner.branchId].every(ownerId)
    && owner.actorWorkspaceId === owner.workspaceId;
}

/** Mirror the existing legacy create parameter contract without silently coercing or adding defaults. */
function checkedParameters(value: unknown): Readonly<Record<string, ImageParameter>> | undefined {
  if (!object(value)) return;
  const result: Record<string, ImageParameter> = {};
  for (const key of Object.keys(value).sort()) {
    const item = value[key];
    if (key === 'size') { if (typeof item !== 'string' || !sizes.includes(item)) return; }
    else if (key === 'quality') { if (typeof item !== 'string' || !qualities.includes(item)) return; }
    else if (key === 'negative_prompt') { if (typeof item !== 'string' || item.length > 10000) return; }
    else if (key === 'width' || key === 'height') { if (typeof item !== 'number' || !Number.isInteger(item) || item < 64 || item > 2048 || item % 8 !== 0) return; }
    else if (key === 'steps') { if (typeof item !== 'number' || !Number.isInteger(item) || item < 1 || item > 150) return; }
    else if (key === 'seed') { if (typeof item !== 'number' || !Number.isInteger(item) || item < 0 || item > 2147483647) return; }
    else if (key === 'cfg') { if (typeof item !== 'number' || !Number.isFinite(item) || item < 0 || item > 100) return; }
    else if (key === 'denoising_strength') { if (typeof item !== 'number' || !Number.isFinite(item) || item <= 0 || item > 1) return; }
    else return;
    result[key] = item as ImageParameter;
  }
  return Object.freeze(result);
}

/** Caller must uniquely select the requested job ID from its fresh original-owner GET response. */
export function checkedQueuedImageJob(owner: CanvasTaskOwner, value: unknown): ImageJobExecutionSnapshot | undefined {
  if (!checkedOwner(owner) || !object(value) || !jobId(value.id) || value.novel_id !== owner.novelId
    || value.status !== 'QUEUED' || value.contract !== undefined) return;
  const branchId = owner.mode === 'local' ? null : owner.branchId;
  const ownerActorId = owner.mode === 'local' ? null : owner.actorId;
  if (value.branch_id !== branchId || value.owner_actor_id !== ownerActorId) return;
  if (!label(value.provider_id, 240) || !label(value.model_id, 2048) || !text(value.prompt, 8000)
    || typeof value.allow_cloud_prompt !== 'boolean' || typeof value.request_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.request_sha256)
    || typeof value.attempt !== 'number' || !Number.isSafeInteger(value.attempt) || value.attempt < 0 || !timestamp(value.updated_at)) return;
  // Only the known manual text-to-image input is supported by this confirmation surface.
  if (own(value, 'images') && (!Array.isArray(value.images) || value.images.length !== 0)) return;
  for (const field of ['character_id', 'scene_id']) if (own(value, field) && value[field] !== null && !ownerId(value[field])) return;
  if (own(value, 'size') && (typeof value.size !== 'string' || !sizes.includes(value.size))) return;
  if (own(value, 'quality') && (typeof value.quality !== 'string' || !qualities.includes(value.quality))) return;
  if (own(value, 'output_format') && (typeof value.output_format !== 'string' || !['png', 'jpeg', 'webp'].includes(value.output_format))) return;
  const parameters = checkedParameters(value.parameters);
  if (!parameters) return;
  const input = Object.freeze({provider_id: value.provider_id, model_id: value.model_id, prompt: value.prompt, parameters,
    allow_cloud_prompt: value.allow_cloud_prompt,
    ...(own(value, 'character_id') ? {character_id: value.character_id as string | null} : {}),
    ...(own(value, 'scene_id') ? {scene_id: value.scene_id as string | null} : {}),
    ...(own(value, 'images') ? {images: Object.freeze([]) as readonly []} : {}),
    ...(own(value, 'size') ? {size: value.size as string} : {}),
    ...(own(value, 'quality') ? {quality: value.quality as string} : {}),
    ...(own(value, 'output_format') ? {output_format: value.output_format as string} : {})});
  const ownerSnapshot = Object.freeze(Object.fromEntries(ownerKeys.map(key => [key, owner[key]])) as CanvasTaskOwner);
  const fingerprint = JSON.stringify([ownerKeys.map(key => ownerSnapshot[key]), value.id, value.novel_id, branchId, ownerActorId,
    value.request_sha256, value.attempt, value.updated_at, input]);
  return Object.freeze({owner: ownerSnapshot, jobId: value.id, novelId: owner.novelId, branchId, ownerActorId,
    providerId: value.provider_id, modelId: value.model_id, prompt: value.prompt, parameters, allowCloudPrompt: value.allow_cloud_prompt,
    requestSha256: value.request_sha256, attempt: value.attempt, updatedAt: value.updated_at, input, fingerprint});
}

export const sameExecutionSnapshot = (left: ImageJobExecutionSnapshot | undefined, right: ImageJobExecutionSnapshot | undefined): boolean =>
  !!left && !!right && left.fingerprint === right.fingerprint;

/** Configuration capability only: this does not probe the actual model or call a provider. */
export function matchingExecutionProvider(snapshot: ImageJobExecutionSnapshot, items: unknown): Readonly<AssetProviderStatus> | undefined {
  if (!Array.isArray(items)) return;
  const matches = items.filter(value => object(value) && value.provider_id === snapshot.providerId);
  if (matches.length !== 1) return;
  const value = matches[0] as Record<string, unknown>;
  if (value.default_model !== snapshot.modelId || value.configured !== true || value.registered !== true || value.reachable !== true
    || value.enabled === false || typeof value.local !== 'boolean' || typeof value.api_style !== 'string'
    || !['openai', 'comfyui', 'automatic1111'].includes(value.api_style)) return;
  const supported = value.api_style === 'openai' ? ['size', 'quality'] : ['width', 'height', 'steps', 'seed', 'negative_prompt'];
  if (Object.keys(snapshot.parameters).some(key => !supported.includes(key))) return;
  if (value.enabled !== undefined && typeof value.enabled !== 'boolean'
    || own(value, 'requires_credential') && typeof value.requires_credential !== 'boolean'
    || own(value, 'credential_configured') && typeof value.credential_configured !== 'boolean'
    || own(value, 'endpoint') && typeof value.endpoint !== 'string'
    || own(value, 'display_name') && typeof value.display_name !== 'string') return;
  return Object.freeze({provider_id: snapshot.providerId, default_model: snapshot.modelId,
    configured: true, registered: true, reachable: true, local: value.local,
    api_style: value.api_style as AssetProviderStatus['api_style'],
    ...(own(value, 'endpoint') ? {endpoint: value.endpoint as string} : {}),
    ...(own(value, 'enabled') ? {enabled: value.enabled as boolean} : {}),
    ...(own(value, 'requires_credential') ? {requires_credential: value.requires_credential as boolean} : {}),
    ...(own(value, 'credential_configured') ? {credential_configured: value.credential_configured as boolean} : {}),
    ...(own(value, 'display_name') ? {display_name: value.display_name as string} : {})});
}

/** A local host is verified by the caller; a permission response cannot establish local authority. */
export function hasImageJobExecutionPermission(owner: CanvasTaskOwner, value: unknown): boolean {
  return checkedOwner(owner) && owner.mode === 'collaboration' && object(value) && value.actor_id === owner.actorId
    && value.domain === 'NOVEL' && object(value.capabilities) && value.capabilities['domain.write'] === true;
}
