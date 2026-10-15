// R3-I — read-only client for the Prompt adoption projection.
//
// Deliberately NARROW and READ-ONLY: it only GETs the adoption record for one storyboard
// document. It never writes, never adopts, and does not touch the existing read-only
// `storyboardWorkspaceClient`. The write path stays closed until the production switch is
// opened on the server.
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

export const ADOPTION_PROJECTION_CONTRACT = 'prompt-adoption/1';

export const ADOPTION_ERROR_CODES = { unavailable: 'PROMPT_ADOPTION_UNAVAILABLE' } as const;

export type AdoptionSource = {
  requestId: string;
  shotId: string;
  familyId: string;
  assetId: string;
  revision: number;
  digest: string;
  adoptedBy: string;
  adoptedAt: string;
  resultVersion: number | null;
  /** The shot still holds exactly the revision this adoption produced. */
  stillApplied: boolean;
  /** The family has a newer revision; the pinned reference has NOT moved. */
  newerRevisionAvailable: boolean;
  /** Whether the server actually reported the drift flag, as opposed to it being absent. */
  newerRevisionConfirmed: boolean;
  /** Display eligibility of the pinned revision right now. */
  sourceReadable: boolean;
  /** KNOWN when the revision's state could be confirmed, UNKNOWN when it could not. */
  sourceState: string;
  sourceRedacted: boolean;
};

export type AdoptionProjection = {
  contract: string;
  documentId: string;
  version: number;
  digest: string;
  adoptions: AdoptionSource[];
};

const BOUND = 240;
const segment = encodeURIComponent;

function text(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 4000) {
    throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
      message: `采用记录字段 ${field} 无效。` });
  }
  return value;
}

function optionalText(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function decodeSource(raw: unknown): AdoptionSource {
  if (typeof raw !== 'object' || raw === null) {
    throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
      message: '采用记录格式无效。' });
  }
  const row = raw as Record<string, unknown>;
  // An UNKNOWN source state means the server could NOT confirm this revision's state.
  const known = row.source_state === 'KNOWN';
  const revision = row.revision;
  if (typeof revision !== 'number' || !Number.isInteger(revision) || revision < 1) {
    throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
      message: '采用记录的修订号无效。' });
  }
  return {
    requestId: text(row.request_id, 'request_id'),
    shotId: text(row.shot_id, 'shot_id'),
    familyId: text(row.family_id, 'family_id'),
    assetId: text(row.asset_id, 'asset_id'),
    revision,
    digest: text(row.digest, 'digest'),
    adoptedBy: optionalText(row.adopted_by),
    adoptedAt: optionalText(row.adopted_at),
    resultVersion: typeof row.result_version === 'number' ? row.result_version : null,
    // Absent flags refuse to true: an unconfirmable source must never look applied. Readability
    // and drift are additionally gated on a CONFIRMED source state, so an UNKNOWN revision can
    // never be presented as displayable nor as "no newer version".
    stillApplied: row.still_applied === true,
    newerRevisionAvailable: known && row.newer_revision_available === true,
    newerRevisionConfirmed: known && typeof row.newer_revision_available === 'boolean',
    sourceReadable: known && row.source_readable === true && row.source_redacted !== true,
    sourceState: optionalText(row.source_state) || 'UNKNOWN',
    sourceRedacted: row.source_redacted === true,
  };
}

export function decodeAdoptionProjection(raw: unknown): AdoptionProjection {
  if (typeof raw !== 'object' || raw === null) {
    throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
      message: '采用记录格式无效。' });
  }
  const body = raw as Record<string, unknown>;
  if (body.contract !== ADOPTION_PROJECTION_CONTRACT) {
    throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
      message: '采用记录契约不匹配。' });
  }
  const version = body.version;
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) {
    throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
      message: '文档版本无效。' });
  }
  if (!Array.isArray(body.adoptions)) {
    // Silently treating this as [] would render "no adoption" for a malformed payload.
    throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
      message: '采用记录的 adoptions 字段缺失或格式无效。' });
  }
  const adoptions = body.adoptions.map(decodeSource);
  return {
    contract: ADOPTION_PROJECTION_CONTRACT,
    documentId: text(body.document_id, 'document_id'),
    version,
    digest: text(body.digest, 'digest'),
    adoptions,
  };
}

export type PromptAdoptionClient = {
  /** The adoption currently pinned to one shot, or null when the shot has none. */
  forShot(documentId: string, shotId: string, signal?: AbortSignal): Promise<AdoptionSource | null>;
  read(documentId: string, signal?: AbortSignal): Promise<AdoptionProjection>;
};

export function createPromptAdoptionClient(
  projectId: string, transport: StudioGraphTransport,
): PromptAdoptionClient {
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > BOUND) {
    throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
      message: '采用面板缺少有效的项目标识。' });
  }
  const root = `/api/projects/${segment(projectId)}/studio/documents`;

  function documentId(value: string): string {
    if (typeof value !== 'string' || !value.trim() || value.length > BOUND) {
      throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
        message: '采用面板缺少有效的分镜文档。' });
    }
    return segment(value);
  }

  return {
    async read(id, signal) {
      // Read-only GET. No body, no idempotency key, no write affordance.
      const raw = await transport.json<unknown>(
        `${root}/${documentId(id)}/prompt-adoption`, 'GET', undefined, signal);
      const projection = decodeAdoptionProjection(raw);
      // The projection must describe the document we asked about; anything else is refused
      // rather than displayed against the wrong board.
      if (projection.documentId !== id) {
        throw new ApiError({ status: 200, code: ADOPTION_ERROR_CODES.unavailable,
          message: '采用记录属于其他分镜文档。' });
      }
      return projection;
    },
    async forShot(id, shotId, signal) {
      const projection = await this.read(id, signal);
      // Proofs are APPENDED in order, so the CURRENT source for a shot is the LAST matching
      // record. Using find() returned the FIRST (oldest) adoption and presented a superseded
      // revision as the shot's current source. History is untouched: the full array is still
      // available from read().
      for (let index = projection.adoptions.length - 1; index >= 0; index -= 1) {
        if (projection.adoptions[index].shotId === shotId) return projection.adoptions[index];
      }
      return null;
    },
  };
}
