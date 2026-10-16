import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { decodeAdoptionProjection, type AdoptionProjection } from './promptAdoptionClient';

export type PromptAdoptionTarget = { documentId: string; shotId: string; version: number; digest: string };
export type PromptAdoptionRequest = {
  shot_id: string; family_id: string; asset_id: string; revision: number;
  expected_digest: string; expected_version: number; expected_digest_target: string; request_id: string;
};
export type PromptAdoptionCommit = {
  documentId: string; shotId: string; version: number; digest: string;
  resultVersion: number; replayed: boolean; requestId: string;
};
export type PromptAdoptionCapability = AdoptionProjection & { writeEnabled: boolean };

function invalid(): never {
  throw new ApiError({ status: 200, code: 'PROMPT_ADOPTION_RESPONSE_INVALID',
    message: '无法核实 Prompt 采用回执，请重新读取原分镜与采用来源。' });
}
function identifier(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= 240;
}
function digest(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
}
function positive(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  return value as Record<string, unknown>;
}

/** Capability is a server observation, never a front-end flag or permission grant. */
export function checkedAdoptionCapability(raw: unknown, documentId: string): PromptAdoptionCapability {
  const row = record(raw), projection = decodeAdoptionProjection(raw);
  if (projection.documentId !== documentId || !digest(projection.digest)
      || row.write_enabled !== undefined && typeof row.write_enabled !== 'boolean') invalid();
  return { ...projection, writeEnabled: row.write_enabled === true };
}

/** Whitelist only the original closed DTO. Client text and provenance never cross this boundary. */
export function adoptionRequestBody(value: PromptAdoptionRequest): PromptAdoptionRequest {
  if (![value.shot_id, value.family_id, value.asset_id, value.request_id].every(identifier)
      || !positive(value.revision) || value.revision > 100000 || !positive(value.expected_version)
      || !digest(value.expected_digest) || !digest(value.expected_digest_target)) invalid();
  return { shot_id: value.shot_id, family_id: value.family_id, asset_id: value.asset_id,
    revision: value.revision, expected_digest: value.expected_digest,
    expected_version: value.expected_version, expected_digest_target: value.expected_digest_target,
    request_id: value.request_id };
}

export function checkedAdoptionCommit(raw: unknown, target: PromptAdoptionTarget,
                                      request: PromptAdoptionRequest): PromptAdoptionCommit {
  const row = record(raw), proof = record(row.adoption);
  const resultVersion = request.expected_version + 1;
  if (row.committed !== true || typeof row.replayed !== 'boolean'
      || row.document_id !== target.documentId || row.shot_id !== target.shotId
      || !positive(row.version) || !digest(row.digest)
      || (row.replayed ? row.version < resultVersion : row.version !== resultVersion)
      || proof.contract !== 'prompt-adoption/1' || proof.document_id !== target.documentId
      || proof.shot_id !== target.shotId || proof.request_id !== request.request_id
      || proof.family_id !== request.family_id || proof.asset_id !== request.asset_id
      || proof.revision !== request.revision || proof.digest !== request.expected_digest
      || proof.target_version !== request.expected_version
      || proof.target_digest !== request.expected_digest_target || proof.result_version !== resultVersion
      || proof.field !== 'frame_prompt' || proof.digest_of !== 'ORIGINAL_BYTES'
      || proof.source_binding_contract !== 'prompt-adoption-bindings/1'
      || proof.source_bindings_verified !== true) invalid();
  return { documentId: target.documentId, shotId: target.shotId, version: row.version,
    digest: row.digest, resultVersion, replayed: row.replayed, requestId: request.request_id };
}

export function createPromptAdoptionWriteClient(projectId: string, transport: StudioGraphTransport) {
  if (!identifier(projectId)) invalid();
  const root = `/api/projects/${encodeURIComponent(projectId)}/studio/documents`;
  const path = (id: string) => { if (!identifier(id)) invalid(); return `${root}/${encodeURIComponent(id)}`; };
  return {
    async read(documentId: string, signal?: AbortSignal) {
      return checkedAdoptionCapability(await transport.json<unknown>(
        `${path(documentId)}/prompt-adoption`, 'GET', undefined, signal), documentId);
    },
    async adopt(target: PromptAdoptionTarget, request: PromptAdoptionRequest) {
      const body = adoptionRequestBody(request);
      if (!identifier(target.shotId) || target.shotId !== body.shot_id
          || target.version !== body.expected_version || target.digest !== body.expected_digest_target) invalid();
      const raw = await transport.json<unknown>(
        `${path(target.documentId)}/shots/${encodeURIComponent(target.shotId)}/prompt-adoption`,
        'POST', body, undefined, body.request_id);
      return checkedAdoptionCommit(raw, target, body);
    },
  };
}
