/**
 * UX-05 严格解码器。
 *
 * 每个函数都遵循既有 house style：拒绝未知键、给字符串上界、拒绝控制字符与
 * 越界整数、身份不符抛 `*_SCOPE_MISMATCH`，失败一律是 `ApiError` +
 * 稳定机器码 + 中文文案。**镜头/回执本身**不在这里重新实现：它们由原 owner 的
 * 前端契约 `creative/studioStoryboardContract.ts` 解码，本文件只补本工作区真正
 * 需要而那边没有的东西（显示顺序草稿、导演目标、送往草稿、连接信封）。
 */

import { ApiError } from '../api';
import {
  checkedDirectorAdvice, checkedStoryboardReceipt,
  type DirectorAdvice, type StoryboardReceipt, type StoryboardShot,
} from '../creative/studioStoryboardContract';
import type { DirectorNote } from '../creative/types';
import {
  DIRECTOR_PROPOSAL_STATUSES, SEND_TARGETS, STORYBOARD_OWNER_STALE_CODES,
  STORYBOARD_WORKSPACE_BOUNDS, STORYBOARD_WORKSPACE_ERROR_CODES,
  type DirectorGoal, type DirectorGoalDraft, type DirectorProposalStatus, type DirectorVisualTargetValue,
  type BoundShotTargetDraft, type SendTarget, type ShotImageBindingRef, type ShotOrderDraft,
  type ShotVideoBindingRef, type StoryboardScopeEnvelope,
} from './storyboardWorkspaceTypes';

const { responseInvalid, scopeMismatch } = STORYBOARD_WORKSPACE_ERROR_CODES;

export function storyboardWorkspaceInvalid(): never {
  throw new ApiError({
    status: 200, code: responseInvalid,
    message: '分镜工作区拿到的数据不完整或与契约不符，请读取原文档核对后重试。',
  });
}

function workspaceMismatch(): never {
  throw new ApiError({
    status: 403, code: scopeMismatch,
    message: '分镜工作区与当前项目、分支或文档不一致，请重新打开工作区。',
  });
}

export function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) storyboardWorkspaceInvalid();
  return value as Record<string, unknown>;
}

/** 未知键一律拒绝；`optional` 里的键允许缺席。 */
export function closed(row: Record<string, unknown>, required: readonly string[], optional: readonly string[] = []): void {
  if (required.some(key => !Object.hasOwn(row, key)) || Object.keys(row).some(key => !required.includes(key) && !optional.includes(key))) {
    storyboardWorkspaceInvalid();
  }
}

export function text(value: unknown, maximum: number, empty = false): string {
  if (typeof value !== 'string' || value.length > maximum || (!empty && !value.trim())) storyboardWorkspaceInvalid();
  return value;
}

export function resource(value: unknown, maximum = STORYBOARD_WORKSPACE_BOUNDS.identifier): string {
  const result = text(value, maximum);
  if (/[\u0000-\u001f\u007f]/.test(result)) storyboardWorkspaceInvalid();
  return result;
}

export function digest(value: unknown): string {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) storyboardWorkspaceInvalid();
  return value;
}

export function version(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1) storyboardWorkspaceInvalid();
  return value;
}

export function boundedInteger(value: unknown, minimum: number, maximum: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) storyboardWorkspaceInvalid();
  return value;
}

export function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') storyboardWorkspaceInvalid();
  return value;
}

export function array(value: unknown, maximum: number): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) storyboardWorkspaceInvalid();
  return value;
}

export function strings(value: unknown, maximumItems: number, maximumLength: number): string[] {
  const rows = array(value, maximumItems).map(item => text(item, maximumLength, true));
  if (new Set(rows).size !== rows.length) storyboardWorkspaceInvalid();
  return rows;
}

export function enumerated<T extends string>(value: unknown, allowed: readonly T[]): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) storyboardWorkspaceInvalid();
  return value as T;
}

/** `{id, version, digest}` 版本针。原 owner 的 `OriginalSnapshot` / `PlanningSnapshot` 同形。 */
export function snapshot(value: unknown, maximum = STORYBOARD_WORKSPACE_BOUNDS.identifier): { id: string; version: number; digest: string } {
  const row = record(value);
  closed(row, ['id', 'version', 'digest']);
  return { id: resource(row.id, maximum), version: version(row.version), digest: digest(row.digest) };
}

/** 连接信封：只用来做身份/范围核对，不携带任何可执行内容。 */
export function storyboardScopeEnvelope(value: unknown, projectId: string, expected?: StoryboardScopeEnvelope): StoryboardScopeEnvelope {
  if (typeof projectId !== 'string' || !projectId.trim()) storyboardWorkspaceInvalid();
  const row = record(value);
  closed(row, ['novel_id', 'scope_key', 'document_id'], ['branch_id', 'mode']);
  const scope: StoryboardScopeEnvelope = {
    novel_id: resource(row.novel_id), scope_key: resource(row.scope_key),
    document_id: resource(row.document_id),
    branch_id: row.branch_id === undefined ? null : (row.branch_id === null ? null : resource(row.branch_id)),
    mode: row.mode === undefined ? null : enumerated(row.mode, ['local', 'collaboration'] as const),
  };
  if (scope.novel_id !== projectId) workspaceMismatch();
  if (expected && (scope.novel_id !== expected.novel_id || scope.scope_key !== expected.scope_key
    || scope.document_id !== expected.document_id || scope.branch_id !== expected.branch_id)) workspaceMismatch();
  return scope;
}

/**
 * 原分镜回执：仍然由既有的 `checkedStoryboardReceipt` 解码（不复制第二套镜头引擎），
 * 只是把它的失败留在同一个契约里，并额外核对"确实是我们要的那份文档"。
 */
export function workspaceReceipt(value: unknown, documentId: string): StoryboardReceipt {
  if (typeof documentId !== 'string' || !documentId.trim() || documentId.length > STORYBOARD_WORKSPACE_BOUNDS.identifier) {
    storyboardWorkspaceInvalid();
  }
  // `checkedStoryboardReceipt` 自己就会核对"回执里的文档身份 === 请求的文档身份"。
  return checkedStoryboardReceipt(value, documentId);
}

/** 导演调度建议回执。同样复用既有解码器。 */
export function workspaceDirectorAdvice(value: unknown, documentId: string): DirectorAdvice {
  if (typeof documentId !== 'string' || !documentId.trim() || documentId.length > STORYBOARD_WORKSPACE_BOUNDS.identifier) {
    storyboardWorkspaceInvalid();
  }
  return checkedDirectorAdvice(value, documentId);
}

/** 只有真正在回执里的镜头才存在；找不到就是身份不符，不补一个空镜头。 */
export function requireShot(receipt: StoryboardReceipt, shotId: string): StoryboardShot {
  const shot = receipt.shots.find(row => row.shot_id === shotId);
  if (!shot) storyboardWorkspaceInvalid();
  return shot;
}

/** 一次显示顺序调整。`before_shot_id` 为 `null` 表示移到末尾。 */
export type ShotMoveInput = { shot_id: string; before_shot_id: string | null };

export function shotMove(value: unknown): ShotMoveInput {
  const row = record(value);
  closed(row, ['shot_id', 'before_shot_id']);
  return {
    shot_id: resource(row.shot_id),
    before_shot_id: row.before_shot_id === null ? null : resource(row.before_shot_id),
  };
}

export function shotMoves(value: unknown, shotIds: readonly string[]): ShotMoveInput[] {
  const moves = array(value, STORYBOARD_WORKSPACE_BOUNDS.shots).map(shotMove);
  const known = new Set(shotIds);
  if (moves.some(move => !known.has(move.shot_id) || (move.before_shot_id !== null && !known.has(move.before_shot_id)))
    || moves.some(move => move.before_shot_id === move.shot_id)
    || new Set(moves.map(move => move.shot_id)).size !== moves.length) {
    storyboardWorkspaceInvalid();
  }
  return moves;
}

export function sendTarget(value: unknown): SendTarget {
  return enumerated(value, SEND_TARGETS);
}

/** 显示顺序草稿的呈现形状（由 `orderShots` 产生，视图只读）。 */
export function orderDraft(value: unknown, shotIds: readonly string[]): ShotOrderDraft {
  const row = record(value);
  closed(row, ['shot_ids', 'saved', 'renumbered', 'approval_effect', 'invalidated_bindings']);
  const order = strings(row.shot_ids, STORYBOARD_WORKSPACE_BOUNDS.shots, STORYBOARD_WORKSPACE_BOUNDS.identifier);
  if (order.length !== shotIds.length || order.some((id, index) => id !== shotIds[index])) storyboardWorkspaceInvalid();
  const renumbered = strings(row.renumbered, STORYBOARD_WORKSPACE_BOUNDS.shots, STORYBOARD_WORKSPACE_BOUNDS.identifier);
  if (renumbered.some(id => !order.includes(id))) storyboardWorkspaceInvalid();
  const invalidated = strings(row.invalidated_bindings, STORYBOARD_WORKSPACE_BOUNDS.shots, STORYBOARD_WORKSPACE_BOUNDS.identifier);
  if (invalidated.some(id => !order.includes(id))) storyboardWorkspaceInvalid();
  return {
    shot_ids: order, saved: boolean(row.saved), renumbered,
    approval_effect: enumerated(row.approval_effect,
      ['REVOKES_APPROVAL_AND_DROPS_MISMATCHED_BINDINGS'] as const),
    invalidated_bindings: invalidated,
  };
}

/**
 * 送往草稿的复核：必须是"这一版本文档里的这一个版本镜头"，绑定必须与原文档里
 * 已经存在的那一条逐字段相等，否则本地就拒绝。返回的形状不会多出任何执行字段。
 */
export function targetDraft(value: unknown, target: SendTarget, receipt: StoryboardReceipt): BoundShotTargetDraft {
  const row = record(value);
  closed(row, ['target', 'document_version', 'shot_id', 'shot_version', 'source_digest', 'bindings', 'order_shot_ids']);
  if (row.shot_id === null || row.shot_id === undefined) storyboardWorkspaceInvalid();
  const shot = requireShot(receipt, resource(row.shot_id));
  if (enumerated(row.target, SEND_TARGETS) !== target) storyboardWorkspaceInvalid();
  const documentVersion = version(row.document_version);
  const shotVersion = version(row.shot_version);
  const sourceDigest = digest(row.source_digest);
  if (documentVersion !== receipt.document_snapshot.version || shotVersion !== shot.shot_version || sourceDigest !== shot.shot_digest) {
    storyboardWorkspaceInvalid();
  }
  const bindings = record(row.bindings);
  closed(bindings, ['IMAGE', 'VIDEO']);
  const order = strings(row.order_shot_ids, STORYBOARD_WORKSPACE_BOUNDS.timeline_shots, STORYBOARD_WORKSPACE_BOUNDS.identifier);
  if (new Set(order).size !== order.length || !order.includes(shot.shot_id)
    || order.some(id => !receipt.shots.some(other => other.shot_id === id))) storyboardWorkspaceInvalid();
  const image: ShotImageBindingRef | null = bindings.IMAGE === null ? null : (() => {
    const bound = record(bindings.IMAGE);
    closed(bound, ['asset_id', 'version', 'digest']);
    const result = { asset_id: resource(bound.asset_id), version: version(bound.version), digest: digest(bound.digest) };
    const actual = shot.image_asset;
    if (!actual || actual.asset_id !== result.asset_id || actual.version !== result.version || actual.digest !== result.digest) {
      storyboardWorkspaceInvalid();
    }
    return result;
  })();
  const video: ShotVideoBindingRef | null = bindings.VIDEO === null ? null : (() => {
    const bound = record(bindings.VIDEO);
    closed(bound, ['asset_id', 'version', 'digest', 'job', 'source_shot']);
    const job = record(bound.job);
    closed(job, ['id', 'version', 'request_digest', 'receipt_digest']);
    const source = record(bound.source_shot);
    closed(source, ['shot_id', 'shot_version', 'shot_digest']);
    const result: ShotVideoBindingRef = {
      asset_id: resource(bound.asset_id), version: version(bound.version), digest: digest(bound.digest),
      job: {
        id: resource(job.id), version: version(job.version),
        request_digest: digest(job.request_digest), receipt_digest: digest(job.receipt_digest),
      },
      source_shot: {
        shot_id: resource(source.shot_id), shot_version: version(source.shot_version), shot_digest: digest(source.shot_digest),
      },
    };
    const actual = shot.video_result;
    if (!actual || actual.asset.asset_id !== result.asset_id || actual.asset.version !== result.version
      || actual.asset.digest !== result.digest || actual.source_shot.shot_id !== result.source_shot.shot_id
      || actual.source_shot.shot_version !== result.source_shot.shot_version
      || actual.source_shot.shot_digest !== result.source_shot.shot_digest
      || actual.job.id !== result.job.id || actual.job.version !== result.job.version
      || actual.job.request_digest !== result.job.request_digest || actual.job.receipt_digest !== result.job.receipt_digest) {
      storyboardWorkspaceInvalid();
    }
    return result;
  })();
  return {
    target, document_version: documentVersion, shot_id: shot.shot_id, shot_version: shotVersion,
    source_digest: sourceDigest, bindings: { IMAGE: image, VIDEO: video }, order_shot_ids: order,
  };
}

function visualTarget(value: unknown): DirectorVisualTargetValue {
  const row = record(value);
  closed(row, ['style', 'atmosphere', 'reference_works', 'color', 'rhythm']);
  return {
    style: text(row.style, 2000, true), atmosphere: text(row.atmosphere, 2000, true),
    reference_works: strings(row.reference_works, 20, 1000),
    color: text(row.color, 2000, true), rhythm: text(row.rhythm, 2000, true),
  };
}

const DIRECTOR_NOTE_KEYS = ['id', 'note', 'shot_size', 'camera_angle', 'camera_motion', 'duration_seconds', 'emotion', 'pacing', 'performance', 'blocking'] as const;
const DIRECTOR_NOTE_OPTIONAL = ['shot_suggestion', 'composition', 'lens', 'character_state', 'performances', 'lighting', 'color_palette', 'material', 'transition'] as const;

/**
 * 导演文档 → 目标投影。`value` 是原 DIRECTOR 文档本身（`CreativeDocument`），
 * `director_notes` 就是作者已经确定的内容；`source_documents` 是原 owner 记下的
 * 上游版本针，用来如实报告"来源是否已经变化"，绝不用来假装继承已经生效。
 */
export function directorGoalView(
  value: unknown, projectId: string, documentId: string, documentDigest: string | null,
): { goals: DirectorGoal[]; visual_target: DirectorVisualTargetValue | null; document: { id: string; version: number; digest: string }; sources: Record<string, { version: number; digest: string }> } {
  const row = record(value);
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > STORYBOARD_WORKSPACE_BOUNDS.identifier) {
    storyboardWorkspaceInvalid();
  }
  const required = ['id', 'version', 'mode', 'title', 'source_documents'];
  // 原 DIRECTOR 文档（`CreativeDocument`）的完整字段集。这里只读取目标需要的部分，
  // 但仍然要求整份文档的形状是已知的：多出未知字段就拒绝，而不是悄悄忽略。
  const optional = [
    'visual_target', 'status', 'scenes', 'shots', 'video_plan', 'director_notes',
    'source_chapter_ids', 'source_independent', 'provenance', 'source_evidence',
    'created_at', 'updated_at', 'actor_id', 'schema_version', 'source_privacy',
    'project_incarnation', 'history', 'script',
  ];
  const source_documents = row.source_documents === undefined ? {} : row.source_documents;
  const notes = row.director_notes === undefined ? [] : row.director_notes;
  closed(row, required, [...optional, 'director_notes']);
  if (row.mode !== 'DIRECTOR') storyboardWorkspaceInvalid();
  const id = resource(row.id);
  if (id !== documentId) workspaceMismatch();
  const documentVersion = version(row.version);
  const scenes = array(row.scenes === undefined ? [] : row.scenes, STORYBOARD_WORKSPACE_BOUNDS.shots);
  const goals = array(notes, STORYBOARD_WORKSPACE_BOUNDS.shots).map<DirectorGoal>(note => {
    const item = record(note);
    // 这里同时接受文档内的 `DirectorSceneNote`（带 `scene_id`/`number`）与
    // `DirectorNote`（导演建议投影里的形状），两种形状都由原 owner 定义。
    closed(item, [...DIRECTOR_NOTE_KEYS], [...DIRECTOR_NOTE_OPTIONAL, 'scene_id', 'number']);
    const scene_id = item.scene_id === undefined || item.scene_id === null ? '' : resource(item.scene_id);
    const number = item.number === undefined || item.number === null ? null : boundedInteger(item.number, 1, 10000);
    return {
      kind: number === null ? 'SHOT_ALIGNED' : 'SCENE', scene_id, note_id: resource(item.id), number: number ?? 0,
      source_document: null,
      adopted: {
        note: text(item.note, 8000, true), shot_size: text(item.shot_size, 80, true),
        camera_angle: text(item.camera_angle, 80, true), camera_motion: text(item.camera_motion, 80, true),
        duration_seconds: boundedInteger(item.duration_seconds, STORYBOARD_WORKSPACE_BOUNDS.duration_seconds_min, STORYBOARD_WORKSPACE_BOUNDS.duration_seconds_max),
        emotion: text(item.emotion, 2000, true), pacing: text(item.pacing, 2000, true),
        performance: text(item.performance, 4000, true), blocking: text(item.blocking, 4000, true),
      },
      suggestion: null,
    };
  });
  if (new Set(goals.map(goal => goal.note_id)).size !== goals.length
    || goals.some((goal, index) => index > 0 && goal.number !== 0 && goal.number <= goals[index - 1].number)) {
    storyboardWorkspaceInvalid();
  }
  if (argScenesInvalid(scenes)) storyboardWorkspaceInvalid();
  const sources = record(source_documents);
  if (Object.keys(sources).length > 8) storyboardWorkspaceInvalid();
  const checkedSources: Record<string, { version: number; digest: string }> = {};
  for (const [key, entry] of Object.entries(sources)) {
    const bind = record(entry);
    closed(bind, ['version', 'digest']);
    checkedSources[resource(key)] = { version: version(bind.version), digest: digest(bind.digest) };
  }
  /** 上游来源只如实复制原 owner 记下的那一条；没有来源就明说是 `null`。 */
  const upstream = Object.entries(checkedSources);
  const sourceDocument = upstream.length === 1 ? { id: upstream[0][0], ...upstream[0][1] } : null;
  return {
    goals: goals.map(goal => ({ ...goal, source_document: sourceDocument })),
    visual_target: row.visual_target === undefined || row.visual_target === null ? null : visualTarget(row.visual_target),
    document: { id, version: documentVersion, digest: documentDigest === null ? '' : digest(documentDigest) },
    sources: checkedSources,
  };
}
function argScenesInvalid(scenes: unknown[]): boolean {
  const ids = scenes.map(scene => {
    const row = record(scene);
    if (row.id === undefined) storyboardWorkspaceInvalid();
    return resource(row.id);
  });
  return new Set(ids).size !== ids.length;
}

/**
 * 待审建议（`GET /director-proposals` 的一行）。它在界面上必须与"已采用内容"
 * 分区显示：`status` 不是 `APPROVED` 时这里连 `adopted` 都不给。
 */
export function directorProposalSuggestion(value: unknown, sourceDocumentId: string): NonNullable<DirectorGoal['suggestion']> {
  const row = record(value);
  const required = ['id', 'version', 'status', 'source_document_id', 'source_version', 'title', 'director_notes', 'output_digest', 'provenance'];
  const optional = ['visual_target', 'model_preview', 'model_execution', 'document_id', 'unavailable_reason', 'reviewed_by', 'reviewed_at', 'created_at', 'created_by', 'novel_id', 'scope', 'history', 'project_incarnation'];
  closed(row, required, optional);
  if (resource(row.source_document_id) !== sourceDocumentId) workspaceMismatch();
  const provenance = record(row.provenance);
  const notes = array(row.director_notes, STORYBOARD_WORKSPACE_BOUNDS.shots).map<DirectorNote>(note => {
    const item = record(note);
    closed(item, [...DIRECTOR_NOTE_KEYS], [...DIRECTOR_NOTE_OPTIONAL, 'scene_id', 'number']);
    return {
      id: resource(item.id), note: text(item.note, 8000, true), shot_size: text(item.shot_size, 80, true),
      camera_angle: text(item.camera_angle, 80, true), camera_motion: text(item.camera_motion, 80, true),
      duration_seconds: boundedInteger(item.duration_seconds, 1, 600),
      emotion: text(item.emotion, 2000, true), pacing: text(item.pacing, 2000, true),
      performance: text(item.performance, 4000, true), blocking: text(item.blocking, 4000, true),
      lens: item.lens === undefined || item.lens === null ? null : text(item.lens, 1000, true),
      composition: item.composition === undefined || item.composition === null ? null : text(item.composition, 4000, true),
      lighting: item.lighting === undefined || item.lighting === null ? null : text(item.lighting, 4000, true),
      color_palette: item.color_palette === undefined || item.color_palette === null ? null : text(item.color_palette, 2000, true),
      transition: item.transition === undefined || item.transition === null ? null : text(item.transition, 2000, true),
    };
  });
  if (new Set(notes.map(note => note.id)).size !== notes.length) storyboardWorkspaceInvalid();
  const status: DirectorProposalStatus = enumerated(row.status, DIRECTOR_PROPOSAL_STATUSES);
  return {
    id: resource(row.id), status,
    output_digest: status === 'MODEL_UNAVAILABLE' || status === 'CANCELLED' ? null : digest(row.output_digest),
    quality_verification: provenance.quality_verification === 'HUMAN_REVIEW_REQUIRED' ? 'HUMAN_REVIEW_REQUIRED' : null,
    model_called: boolean(provenance.model_called ?? false),
    visual_target: row.visual_target === undefined || row.visual_target === null ? null : visualTarget(row.visual_target),
    notes,
  };
}

/** 目标编辑草稿：只在本地存在，`duration_seconds` 仍受 owner 的 1–600 约束。 */
export function directorGoalDraft(value: unknown): DirectorGoalDraft {
  const row = record(value);
  const keys = ['scene_id', 'note_id', 'shot_size', 'camera_angle', 'camera_motion', 'duration_seconds', 'emotion', 'pacing', 'performance'] as const;
  closed(row, keys);
  const seconds = text(row.duration_seconds, 8);
  if (!/^\d{1,3}$/.test(seconds)) storyboardWorkspaceInvalid();
  return {
    scene_id: resource(row.scene_id), note_id: resource(row.note_id),
    shot_size: text(row.shot_size, 80, true), camera_angle: text(row.camera_angle, 80, true),
    camera_motion: text(row.camera_motion, 80, true), duration_seconds: seconds,
    emotion: text(row.emotion, 2000, true), pacing: text(row.pacing, 2000, true),
    performance: text(row.performance, 4000, true),
  };
}

/** 一个已有绑定是否与当前镜头版本一致：只有 owner 事实，没有"连续性保证"。 */
export function bindingMatchesShot(shot: StoryboardShot): { image: boolean; video: boolean } {
  return {
    image: shot.image_asset !== null,
    video: shot.video_result !== undefined
      && shot.video_result.source_shot.shot_id === shot.shot_id
      && shot.video_result.source_shot.shot_version === shot.shot_version
      && shot.video_result.source_shot.shot_digest === shot.shot_digest,
  };
}

export function isOwnerStaleCode(code: string): boolean {
  return STORYBOARD_OWNER_STALE_CODES.includes(code);
}
