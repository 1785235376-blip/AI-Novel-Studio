import type {CanvasTaskBinding} from './canvasTaskBinding';
import type {CanvasTaskCandidate} from './canvasTaskCandidate';

export type CanvasCandidateAsset = Readonly<{
  assetId: string; novelId: string; branchId: string | null; sourceJobId: string;
  assetVersion: number; assetSha256: string; providerId: string; modelId: string; size: number; mediaType: string;
}>;
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
export function canvasCandidateMediaType(value: string): string | undefined {
  const type = value.split(';')[0].trim().toLowerCase();
  return /^image\/(?:png|jpeg|jpg|webp|gif)$/.test(type) ? type === 'image/jpg' ? 'image/jpeg' : type : undefined;
}

/** Actual asset metadata, not a version inferred from legacy Job timestamps. */
export function checkedCanvasCandidateAsset(binding: CanvasTaskBinding, candidate: CanvasTaskCandidate, value: unknown): CanvasCandidateAsset | undefined {
  if (candidate.approvalStatus !== 'APPROVED' || candidate.previewKind !== 'asset' || !candidate.assetId
    || candidate.jobId !== binding.taskId || candidate.nodeId !== binding.nodeId || candidate.novelId !== binding.owner.novelId
    || !object(value) || value.id !== candidate.assetId || value.novel_id !== candidate.novelId
    || value.source_job_id !== candidate.jobId || value.kind !== 'image' || value.deleted_at != null
    || value.provider_id !== candidate.providerId || value.model_id !== candidate.modelId
    || value.branch_id !== (binding.owner.mode === 'collaboration' ? binding.owner.branchId : null)
    || typeof value.version !== 'number' || !Number.isSafeInteger(value.version) || value.version < 1
    || typeof value.size !== 'number' || !Number.isSafeInteger(value.size) || value.size < 1 || value.size > 36 * 1024 * 1024
    || typeof value.media_type !== 'string' || !canvasCandidateMediaType(value.media_type)
    || typeof value.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.sha256)) return;
  return Object.freeze({assetId: value.id as string, novelId: value.novel_id as string,
    branchId: value.branch_id as string | null, sourceJobId: value.source_job_id as string,
    assetVersion: value.version, assetSha256: value.sha256, providerId: value.provider_id as string,
    modelId: value.model_id as string, size: value.size, mediaType: canvasCandidateMediaType(value.media_type)!});
}

export function sameCanvasCandidateAsset(left: CanvasCandidateAsset, right: CanvasCandidateAsset): boolean {
  return (['assetId', 'novelId', 'branchId', 'sourceJobId', 'assetVersion', 'assetSha256', 'providerId', 'modelId', 'size', 'mediaType'] as const).every(key => left[key] === right[key]);
}

export const canvasCandidateCryptoAvailable = () => typeof globalThis.crypto?.subtle?.digest === 'function';
const hex = (bytes: ArrayBuffer) => Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
export async function canvasCandidateBlobSha256(blob: Blob): Promise<string> {
  if (!canvasCandidateCryptoAvailable()) throw new Error('WebCrypto SHA-256 unavailable');
  return hex(await globalThis.crypto.subtle.digest('SHA-256', await blob.arrayBuffer()));
}

/** Local observation fingerprint only: not an immutable Job revision or an asset digest.
 * URI and prompt contribute to equality but are never returned or persisted here.
 */
export async function canvasCandidateObservationSha256(candidate: CanvasTaskCandidate): Promise<string> {
  if (!canvasCandidateCryptoAvailable()) throw new Error('WebCrypto SHA-256 unavailable');
  const observed = ['canvas-candidate-observation/1', ...(['jobId', 'novelId', 'nodeId', 'providerId', 'modelId', 'prompt',
    'requestSha256', 'attempt', 'updatedAt', 'approvalStatus', 'assetId', 'sourceUri', 'previewKind', 'previewUri'] as const)
    .map(key => candidate[key] ?? null)];
  return hex(await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(observed))));
}

/** Real fetches receive this same signal; the race also retires a non-cooperative read. */
export function abortableCanvasCandidateRead<T>(read: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) return Promise.reject(new Error('Candidate read aborted'));
  return new Promise<T>((resolve, reject) => {
    const aborted = () => reject(new Error('Candidate read aborted'));
    signal.addEventListener('abort', aborted, {once: true});
    read.then(value => { signal.removeEventListener('abort', aborted); resolve(value); }, reason => {
      signal.removeEventListener('abort', aborted); reject(reason);
    });
  });
}
