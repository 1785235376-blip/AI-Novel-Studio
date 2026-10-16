/**
 * UX-05 纯函数层。这里的每个函数都不发请求、不读时钟、不碰原文档：
 *
 *  - 重排只改**显示序号**，`shot_id` 是这个镜头唯一的身份，永不因为拖动而改变。
 *  - `shotSummary` 只报告 owner 真的给了什么；没有的事实一律 `null`/空数组，
 *    并且把"哪些字段缺席"一并写出来，界面无法凭想象补值。
 *  - `directorVsShotOverride` 只做只读对比，明确写出哪一侧生效，绝不写回导演文档。
 *  - `sendToDraft` 产出的是一张 DRAFT 卡片（目标 + 原版本），不是一次执行。
 *  - `sourceStaleness` 只报告有证据的不一致，绝不承诺"连续性没问题"。
 */

import { ApiError } from '../api';
import type { CreativeShot, DirectorNote } from '../creative/types';
import type { DirectorAdvice, ShotPin, StoryboardReceipt, StoryboardShot } from '../creative/studioStoryboardContract';
import {
  STORYBOARD_WORKSPACE_BOUNDS, STORYBOARD_WORKSPACE_ERROR_CODES,
  type BoundShotTargetDraft, type DirectorFieldResolution, type DirectorGoal, type DirectorOverrideField,
  type DirectorVsShotResolution, type SendTarget, type ShotAction, type ShotImageBindingRef,
  type ShotOrderDraft, type ShotStalenessNote, type ShotSummary, type ShotTargetDraft,
  type ShotVideoBindingRef,
} from './storyboardWorkspaceTypes';

const { orderLocalInvalid, reorderDraftInvalid, sendLocalInvalid, targetNotDeclared } = STORYBOARD_WORKSPACE_ERROR_CODES;

const identifier = STORYBOARD_WORKSPACE_BOUNDS.identifier;

/** 每条可由 owner 声明的自由文本的实际上界（`app/creative/models.py`）。 */
const SHOT_TEXT_BOUNDS = {
  frame_prompt: 8000, action: 16000, shot_size: 80, camera_angle: 80, camera_motion: 80,
  lens: 1000, composition: 4000, lighting: 4000, environment: 4000, color: 2000, sound: 4000,
  sound_effect: 4000, emotion: 4000, video_generation_hint: 8000, character: 240, dialogue: 16000,
  delivery: 2000, continuity: 4000,
} as const;

const trimmed = (value: string | null | undefined): string | null => {
  if (typeof value !== 'string') return null;
  const result = value.trim();
  return result ? result : null;
};

const brief = (value: string, maximum = 80): string =>
  value.length > maximum ? `${value.slice(0, maximum)}…` : value;

/** 明确的本地拒绝；调用方（视图/控制器）能稳定断言这个码。 */
function refuse(code: string, message: string): never {
  throw new ApiError({ status: 200, code, message });
}

/** 一个显示顺序调整：把 `shot_id` 移到 `before_shot_id` 之前（`null` = 末尾）。 */
export type ShotMoveInput = { shot_id: string; before_shot_id: string | null };

export type ShotOrderState = {
  order: string[];
  saved: boolean;
  renumbered: string[];
  invalidated_bindings: string[];
};

/**
 * 应用一串显示顺序调整。
 *
 * 身份与顺序是两件事：`shot_id` 一直跟着同一个镜头，`shot.number` 只是显示序号。
 * 因此重排后每个位置的 `number` 变成 `位置 + 1`，其余字段**逐字节**保持不变
 * （owner 的 `shot_versions`/`shot_digest` 是内容摘要，所以任何内容改动都会让
 * 版本前进、批准失效、不一致绑定被丢弃 —— 这一点如实报在返回值里）。
 */
export function orderShots(shots: readonly StoryboardShot[], moves: readonly ShotMoveInput[]): ShotOrderState {
  if (!Array.isArray(shots) || shots.length > STORYBOARD_WORKSPACE_BOUNDS.shots) {
    refuse(orderLocalInvalid, '镜头清单不可用，请重新读取原分镜。');
  }
  const ids = shots.map(shot => shot.shot_id);
  if (new Set(ids).size !== ids.length) refuse(orderLocalInvalid, '镜头身份重复，无法确定显示顺序。');
  const known = new Set(ids);
  if (!Array.isArray(moves) || moves.length > STORYBOARD_WORKSPACE_BOUNDS.shots) {
    refuse(orderLocalInvalid, '顺序调整过多，请重新选择要移动的镜头。');
  }
  const moved = new Set<string>();
  const order = [...ids];
  for (const move of moves) {
    if (!move || typeof move.shot_id !== 'string' || !known.has(move.shot_id)
      || (move.before_shot_id !== null && !known.has(move.before_shot_id))
      || move.before_shot_id === move.shot_id || moved.has(move.shot_id)) {
      refuse(orderLocalInvalid, '顺序调整指向了不存在的镜头，请重新读取后再拖动。');
    }
    moved.add(move.shot_id);
    order.splice(order.indexOf(move.shot_id), 1);
    if (move.before_shot_id === null) order.push(move.shot_id);
    else order.splice(order.indexOf(move.before_shot_id), 0, move.shot_id);
  }
  const byId = new Map(shots.map(shot => [shot.shot_id, shot]));
  const renumbered = order.filter((id, index) => byId.get(id)!.shot.number !== index + 1);
  return {
    order, saved: renumbered.length === 0, renumbered,
    invalidated_bindings: renumbered.filter(id => {
      const shot = byId.get(id)!;
      return shot.image_asset !== null || shot.video_result !== undefined;
    }),
  };
}

/** 把重排结果变成带序号的镜头清单；身份不变，只有 `number` 变。 */
export function renumberShots(shots: readonly StoryboardShot[], state: ShotOrderState): StoryboardShot[] {
  const byId = new Map(shots.map(shot => [shot.shot_id, shot]));
  if (state.order.length !== shots.length || state.order.some(id => !byId.has(id))) {
    refuse(reorderDraftInvalid, '顺序草稿与当前分镜不一致，请重新读取。');
  }
  return state.order.map((id, index) => {
    const shot = byId.get(id)!;
    return shot.shot.number === index + 1 ? shot : { ...shot, shot: { ...shot.shot, number: index + 1 } };
  });
}

/**
 * 当前**可见**的镜头序列（按 1-based 显示位置）。返回原 owner 的镜头对象，
 * 不做任何改写：序号是在渲染时由位置推出的，而不是写进数据里。
 *
 * 断言：同一时刻只会有"原始顺序 + 一串草稿 move"这一种状态。
 */
export function visibleOrderShots(shots: readonly StoryboardShot[], moves: readonly ShotMoveInput[]): StoryboardShot[] {
  const state = orderShots(shots, moves);
  const byId = new Map(shots.map(shot => [shot.shot_id, shot]));
  return state.order.map(id => byId.get(id)!);
}

/**
 * 把"目标显示顺序"折算成一串 canonical move，用来替换整份草稿。
 *
 * 视图上的每个按钮（上移/下移/移到最前/移到最后）都先在本地算出目标顺序，
 * 再交给这里。这样控制器里永远只有**一份**结构化的顺序状态。
 */
export function movesToOrder(shots: readonly StoryboardShot[], target: readonly string[]): ShotMoveInput[] {
  const ids = shots.map(shot => shot.shot_id);
  if (target.length !== ids.length || new Set(target).size !== target.length
    || target.some(id => !ids.includes(id))) {
    refuse(reorderDraftInvalid, '目标顺序与当前分镜不一致，请重新读取。');
  }
  const moves: ShotMoveInput[] = [];
  const working = [...ids];
  for (let index = 0; index < target.length; index += 1) {
    const id = target[index];
    if (working[index] === id) continue;
    moves.push({ shot_id: id, before_shot_id: working[index] });
    working.splice(working.indexOf(id), 1);
    working.splice(index, 0, id);
  }
  return moves;
}

/** 重排草稿的呈现形状；`saved` 为假时界面必须说"尚未保存到原文档"。 */
export function orderDraft(shots: readonly StoryboardShot[], state: ShotOrderState): ShotOrderDraft {
  return {
    shot_ids: [...state.order], saved: state.saved, renumbered: [...state.renumbered],
    approval_effect: 'REVOKES_APPROVAL_AND_DROPS_MISMATCHED_BINDINGS',
    invalidated_bindings: [...state.invalidated_bindings],
  };
}

/**
 * 相邻镜头。顺序就是**当前显示的**顺序（重排草稿未保存时也用它），
 * 边界如实返回 `null`，绝不回绕。
 */
export function neighbourOf(
  shots: readonly StoryboardShot[], shotId: string, direction: 'PREVIOUS' | 'NEXT',
): StoryboardShot | null {
  if (direction !== 'PREVIOUS' && direction !== 'NEXT') {
    refuse(orderLocalInvalid, '未知的相邻方向，请重新读取分镜。');
  }
  const index = shots.findIndex(shot => shot.shot_id === shotId);
  if (index < 0) return null;
  const next = direction === 'PREVIOUS' ? index - 1 : index + 1;
  return next >= 0 && next < shots.length ? shots[next] : null;
}

/** 用 owner 声明的 `continuity` 解释相邻关系；没有声明就说没有。 */
export function continuityOf(shot: StoryboardShot, direction: 'PREVIOUS' | 'NEXT'): string | null {
  const continuity = shot.shot.continuity;
  if (!continuity) return null;
  return trimmed(direction === 'PREVIOUS' ? continuity.previous_shot_id : continuity.next_shot_id);
}

/** 一条绑定引用的可比较形状；只有 owner 明写的原版本会出现在这里。 */
export function imageBindingRef(shot: StoryboardShot): ShotImageBindingRef | null {
  const image = shot.image_asset;
  return image === null ? null : { asset_id: image.asset_id, version: image.version, digest: image.digest };
}

export function videoBindingRef(shot: StoryboardShot): ShotVideoBindingRef | null {
  const result = shot.video_result;
  if (!result) return null;
  return {
    asset_id: result.asset.asset_id, version: result.asset.version, digest: result.asset.digest,
    job: result.job,
    source_shot: {
      shot_id: result.source_shot.shot_id, shot_version: result.source_shot.shot_version,
      shot_digest: result.source_shot.shot_digest,
    },
  };
}

/** 镜头文本字段的越界检查：owner 的边界不会被本工作区放宽。 */
function assertShotText(shot: StoryboardShot): void {
  const content = shot.shot;
  const values: [keyof typeof SHOT_TEXT_BOUNDS, string | null | undefined][] = [
    ['frame_prompt', content.frame_prompt], ['action', content.action], ['shot_size', content.shot_size],
    ['camera_angle', content.camera_angle], ['camera_motion', content.camera_motion], ['lens', content.lens],
    ['composition', content.composition], ['lighting', content.lighting], ['environment', content.environment],
    ['color', content.color], ['sound', content.sound], ['sound_effect', content.sound_effect],
    ['emotion', content.emotion], ['video_generation_hint', content.video_generation_hint],
  ];
  for (const [name, value] of values) {
    if (typeof value === 'string' && value.length > SHOT_TEXT_BOUNDS[name]) {
      refuse(orderLocalInvalid, `镜头字段 ${name} 超出原文档允许的长度，请读取原文档核对。`);
    }
  }
  for (const character of content.characters ?? []) {
    if (character.length > SHOT_TEXT_BOUNDS.character) refuse(orderLocalInvalid, '镜头角色名超出原文档允许的长度。');
  }
  for (const line of content.dialogue) {
    if (line.speaker.length > SHOT_TEXT_BOUNDS.character || line.text.length > SHOT_TEXT_BOUNDS.dialogue
      || line.delivery.length > SHOT_TEXT_BOUNDS.delivery) {
      refuse(orderLocalInvalid, '镜头对白超出原文档允许的长度。');
    }
  }
}

/**
 * 镜头一览卡：**只**由 owner 事实组成。
 *
 * `evidence.fields` 列出真的读到的字段，`evidence.absent` 列出缺席的字段；
 * 视图据此显示"未提供"，而不是补一个默认值。
 */
export function shotSummary(shot: StoryboardShot): ShotSummary {
  if (!shot || typeof shot !== 'object' || typeof shot.shot_id !== 'string' || !shot.shot_id) {
    refuse(orderLocalInvalid, '镜头数据不完整，请重新读取原分镜。');
  }
  assertShotText(shot);
  const content = shot.shot;
  const framing = {
    shot_size: trimmed(content.shot_size), camera_angle: trimmed(content.camera_angle),
    camera_motion: trimmed(content.camera_motion), lens: trimmed(content.lens),
    composition: trimmed(content.composition),
  };
  const lighting = {
    lighting: trimmed(content.lighting), color: trimmed(content.color), environment: trimmed(content.environment),
  };
  const audio = trimmed(content.sound_effect) === null && trimmed(content.sound) === null
    ? null : { sound_effect: trimmed(content.sound_effect), sound: trimmed(content.sound) };
  const continuity = content.continuity ? {
    previous_shot_id: trimmed(content.continuity.previous_shot_id),
    next_shot_id: trimmed(content.continuity.next_shot_id),
    fidelity: (['characters', 'outfit', 'environment', 'camera'] as const)
      .map(key => trimmed(content.continuity![key])).filter((value): value is string => value !== null),
  } : null;
  const characters = content.characters ?? [];
  const noteIds = content.director_note_ids ?? [];
  const image = imageBindingRef(shot);
  const video = videoBindingRef(shot);

  const fields: string[] = [];
  const absent: string[] = [];
  const mark = (name: string, present: boolean) => { (present ? fields : absent).push(name); };
  mark('number', Number.isSafeInteger(content.number) && content.number > 0);
  mark('scene_id', !!trimmed(content.scene_id));
  mark('duration_seconds', Number.isSafeInteger(content.duration_seconds) && content.duration_seconds > 0);
  mark('framing', Object.values(framing).some(value => value !== null));
  mark('lighting', Object.values(lighting).some(value => value !== null));
  mark('characters', characters.length > 0);
  mark('director_note_ids', noteIds.length > 0);
  mark('continuity', continuity !== null);
  mark('image_binding', image !== null);
  mark('video_binding', video !== null);
  mark('audio', audio !== null);

  /**
   * 下一步可用动作只由 owner 事实推导，不构成任何授权。
   * 顺序固定、去重：视图的第一条必须唯一，否则按钮文案会重复。
   */
  const next_actions: ShotAction[] = [];
  const offer = (action: ShotAction) => { if (!next_actions.includes(action)) next_actions.push(action); };
  if (!image) offer('PREPARE_IMAGE_DRAFT');
  else offer('COMPARE_REFERENCE');
  offer('REVIEW_APPROVAL');
  if (!video) offer('PREPARE_VIDEO_DRAFT');
  if (image) offer('PREPARE_TIMELINE_DRAFT');
  if (noteIds.length > 0) offer('DIRECTOR_ADVICE');

  return {
    shot_id: shot.shot_id,
    number: content.number,
    scene_id: content.scene_id,
    subject: trimmed(content.frame_prompt) ?? trimmed(content.action),
    duration: Number.isSafeInteger(content.duration_seconds) && content.duration_seconds > 0
      ? { seconds: content.duration_seconds, source: 'SHOT' } : null,
    framing, lighting_color: lighting,
    references: {
      characters: [...characters], director_note_ids: [...noteIds], continuity,
    },
    candidate: video ? { kind: 'VIDEO', ref: video } : image ? { kind: 'IMAGE', ref: image } : null,
    audio,
    staleness: [],
    next_actions,
    evidence: { fields, absent },
  };
}

/** `sendToDraft` 的只读输入：owner 投影 + 导演文档（可选）。 */
export type StoryboardOwnerFacts = {
  receipt: StoryboardReceipt;
  /** 导演建议投影；没有读到就是 `null`，不会凭空编一份。 */
  directorAdvice: DirectorAdvice | null;
  /** 导演文档里的备注；用来判断"镜头级覆写"确实有继承来源。 */
  directorNotes: readonly DirectorNote[];
};

/**
 * 镜头级覆写 vs 导演目标：只读对比。
 *
 * 继承依据是 owner 自己记下的 `shot.director_note_ids`。**只有**备注 id 真的指向
 * 一份已读取的导演备注时，才谈"继承"；否则一律说"没有继承依据"。这个函数不写入
 * 任何东西：修改导演目标不会改写已经批准的下游结果（原 owner 的
 * `invalidate_storyboard` 只在内容真的变化时撤销批准，而这段代码根本不改内容）。
 */
export function directorVsShotOverride(goal: DirectorGoal, shot: StoryboardShot): DirectorVsShotResolution {
  const noteIds = shot.shot.director_note_ids ?? [];
  if (!noteIds.includes(goal.note_id)) {
    return {
      shot_id: shot.shot_id, scene_id: shot.shot.scene_id, inherited_from_note_ids: [],
      director_document: goal.source_document,
      fields: DIRECTOR_FIELD_TABLE.map(field => {
        const directorOnly = DIRECTOR_ONLY_FIELDS.includes(field);
        const current = shotValue(shot.shot, field);
        return {
          field, shot_value: current, inherited_value: directorOnly ? goalValue(goal, field) : null,
          effective: directorOnly ? (goalValue(goal, field) === null ? 'ABSENT' : 'DIRECTOR_INHERITED')
            : current === null ? 'ABSENT' : 'SHOT_OVERRIDE',
          overridden: false,
        };
      }),
      downstream: 'DIRECTOR_GOAL_EDIT_DOES_NOT_OVERWRITE_APPROVED_RESULTS',
    };
  }
  const fields = DIRECTOR_FIELD_TABLE.map<DirectorFieldResolution>(field => {
    const current = shotValue(shot.shot, field);
    const inherited = goalValue(goal, field);
    // 导演文档独有的字段没有镜头侧对应项，因此谈不上"镜头级覆写"。
    if (DIRECTOR_ONLY_FIELDS.includes(field)) {
      return {
        field, shot_value: null, inherited_value: inherited,
        effective: inherited === null ? 'ABSENT' : 'DIRECTOR_INHERITED', overridden: false,
      };
    }
    if (current === null && inherited === null) return { field, shot_value: null, inherited_value: null, effective: 'ABSENT', overridden: false };
    if (current === null) return { field, shot_value: null, inherited_value: inherited, effective: 'DIRECTOR_INHERITED', overridden: false };
    if (inherited === null) return { field, shot_value: current, inherited_value: null, effective: 'SHOT_OVERRIDE', overridden: false };
    const overridden = current !== inherited;
    return {
      field, shot_value: current, inherited_value: inherited,
      effective: overridden ? 'SHOT_OVERRIDE' : 'DIRECTOR_INHERITED', overridden,
    };
  });
  return {
    shot_id: shot.shot_id, scene_id: shot.shot.scene_id,
    inherited_from_note_ids: [...noteIds], director_document: goal.source_document, fields,
    downstream: 'DIRECTOR_GOAL_EDIT_DOES_NOT_OVERWRITE_APPROVED_RESULTS',
  };
}

/** 对比用的字段表；与 `service.py::derive` 实际复制的字段一一对应。 */
export const DIRECTOR_FIELD_TABLE: readonly DirectorOverrideField[] = [
  'shot_size', 'camera_angle', 'camera_motion', 'lens', 'composition', 'frame_prompt',
  'lighting', 'color', 'duration_seconds', 'emotion', 'pacing', 'performance',
];

/**
 * `pacing` / `performance` 只存在于导演备注里，镜头文档没有对应字段：它们**永远**
 * 来自导演文档，所以既不算"镜头级覆写"，也不允许被本工作区写回快照。
 */
const DIRECTOR_ONLY_FIELDS: readonly DirectorOverrideField[] = ['pacing', 'performance'];

function shotValue(shot: CreativeShot, field: DirectorOverrideField): string | number | null {
  switch (field) {
    case 'shot_size': return trimmed(shot.shot_size);
    case 'camera_angle': return trimmed(shot.camera_angle);
    case 'camera_motion': return trimmed(shot.camera_motion);
    case 'lens': return trimmed(shot.lens);
    case 'composition': return trimmed(shot.composition);
    case 'frame_prompt': return trimmed(shot.frame_prompt);
    case 'lighting': return trimmed(shot.lighting);
    case 'color': return trimmed(shot.color);
    case 'duration_seconds': return Number.isSafeInteger(shot.duration_seconds) ? shot.duration_seconds : null;
    case 'emotion': return trimmed(shot.emotion);
    default: return null;
  }
}

function goalValue(goal: DirectorGoal, field: DirectorOverrideField): string | number | null {
  switch (field) {
    case 'shot_size': return trimmed(goal.adopted.shot_size);
    case 'camera_angle': return trimmed(goal.adopted.camera_angle);
    case 'camera_motion': return trimmed(goal.adopted.camera_motion);
    case 'duration_seconds': return Number.isSafeInteger(goal.adopted.duration_seconds) ? goal.adopted.duration_seconds : null;
    case 'emotion': return trimmed(goal.adopted.emotion);
    case 'pacing': return trimmed(goal.adopted.pacing);
    case 'performance': return trimmed(goal.adopted.performance);
    default: return null;
  }
}

/**
 * 送往目标草稿。
 *
 * 返回的就是契约要求的六个字段（`target/document_version/shot_id/shot_version/
 * source_digest` + `bindings`），单独成一张卡：**没有** `request_id`、没有队列、
 * 没有 `dispatch`。目标模块是否执行，完全由拿到这张卡的调用方决定。
 */
export function sendToDraft(target: SendTarget, shot: StoryboardShot): ShotTargetDraft {
  if (!isSendTarget(target)) {
    refuse(targetNotDeclared, '这个目标模块没有被声明为可接收草稿，请在原模块内操作。');
  }
  if (!shot || typeof shot !== 'object' || typeof shot.shot_id !== 'string' || !shot.shot_id) {
    refuse(sendLocalInvalid, '镜头数据不完整，无法形成草稿。');
  }
  const image = imageBindingRef(shot);
  const video = videoBindingRef(shot);
  if (target === 'VIDEO' && image === null) {
    refuse(sendLocalInvalid, '这个镜头还没有绑定正式图片，文字生成视频需要原 owner 明确指定来源。');
  }
  if (target === 'TIMELINE' && image === null) {
    refuse(sendLocalInvalid, '这个镜头还没有绑定正式图片，原时间线底稿需要精确的图片版本。');
  }
  return {
    target,
    // 纯函数不知道、也绝不猜文档版本：必须由调用方用已核对的原回执补上。
    document_version: null,
    shot_id: shot.shot_id,
    shot_version: shot.shot_version,
    source_digest: shot.shot_digest,
    bindings: { IMAGE: image, VIDEO: video },
    order_shot_ids: [shot.shot_id],
  };
}

/** 用已核对的原回执补齐文档版本与时间线顺序；不匹配就在本地拒绝。 */
export function bindDraftToReceipt(
  draft: ShotTargetDraft, receipt: StoryboardReceipt, orderShotIds?: readonly string[],
): BoundShotTargetDraft {
  const shot = receipt.shots.find(row => row.shot_id === draft.shot_id);
  if (!shot || shot.shot_version !== draft.shot_version || shot.shot_digest !== draft.source_digest) {
    refuse(sendLocalInvalid, '草稿引用的镜头版本已变化，请重新读取原分镜后再形成草稿。');
  }
  if (orderShotIds) {
    const order = [...orderShotIds];
    if (new Set(order).size !== order.length || !order.includes(draft.shot_id)
      || order.some(id => !receipt.shots.some(row => row.shot_id === id))
      || order.length > STORYBOARD_WORKSPACE_BOUNDS.timeline_shots) {
      refuse(sendLocalInvalid, '时间线顺序与当前分镜不一致，请重新读取后再形成草稿。');
    }
    return { ...draft, document_version: receipt.document_snapshot.version, order_shot_ids: order };
  }
  return { ...draft, document_version: receipt.document_snapshot.version };
}

function isSendTarget(value: unknown): value is SendTarget {
  return value === 'IMAGE' || value === 'VIDEO' || value === 'TIMELINE';
}

/** 冻结挂载契约要求的回调载荷：精确到原版本，不携带执行意图。 */
export function toSendToDraft(draft: BoundShotTargetDraft): {
  shot_id: string; shot_version: number; document_version: number; source_digest: string;
} {
  return {
    shot_id: draft.shot_id, shot_version: draft.shot_version,
    document_version: draft.document_version, source_digest: draft.source_digest,
  };
}

/** `sourceStaleness` 的只读输入：owner 记下的上游版本针 + 我们真正读到的版本。 */
export type ShotStalenessFacts = {
  sources?: Readonly<Record<string, { version: number; digest: string }>>;
  knownDocuments?: Readonly<Record<string, { version: number; digest: string }>>;
};

/**
 * 来源陈旧性：**只**报告有证据的不一致。
 *
 * 三件事只根据 owner 事实判断：
 *  1. 原 owner 记下的上游文档针 vs 我们实际读到的上游版本（`source_documents`）。
 *  2. 已绑定视频的 `source_shot` 是否仍等于当前镜头版本。
 *  3. `source_documents` 里指向一个我们不知道、也读不到的文档。
 *
 * 这里**没有**「连续性没问题」这种结论：证据不足就是空数组。
 */
export function sourceStaleness(shot: StoryboardShot, facts?: ShotStalenessFacts): ShotStalenessNote[] {
  const notes: ShotStalenessNote[] = [];
  for (const [id, expected] of Object.entries(facts?.sources ?? {})) {
    const actual = facts?.knownDocuments?.[id];
    if (!actual) {
      notes.push({
        kind: 'DIRECTOR_SOURCE_UNAVAILABLE',
        detail: `原分镜记下的上游文档 ${brief(id)} 目前读不到，无法确认它是否仍然是同一版本。`,
        expected: { id, version: expected.version, digest: expected.digest }, actual: null,
      });
      continue;
    }
    if (actual.version !== expected.version || actual.digest !== expected.digest) {
      notes.push({
        kind: 'DIRECTOR_SOURCE_CHANGED',
        detail: `上游文档 ${brief(id)} 已经不是原分镜记下的那一版。`,
        expected: { id, version: expected.version, digest: expected.digest },
        actual: { id, version: actual.version, digest: actual.digest },
      });
    }
  }
  const result = shot.video_result;
  if (result && (result.source_shot.shot_id !== shot.shot_id || result.source_shot.shot_version !== shot.shot_version
    || result.source_shot.shot_digest !== shot.shot_digest)) {
    notes.push({
      kind: 'CANDIDATE_SOURCE_SHOT_CHANGED',
      detail: '已绑定视频来自另一个镜头版本；它仍然存在，但不再代表当前镜头内容。',
      expected: { id: shot.shot_id, version: shot.shot_version, digest: shot.shot_digest },
      actual: {
        id: result.source_shot.shot_id, version: result.source_shot.shot_version,
        digest: result.source_shot.shot_digest,
      },
    });
  }
  return notes;
}

/** 镜头在回执里的版本针；送给原 owner 时使用。 */
export function shotPin(receipt: StoryboardReceipt, shot: StoryboardShot): ShotPin {
  return {
    document_snapshot: receipt.document_snapshot, shot_id: shot.shot_id,
    shot_version: shot.shot_version, shot_digest: shot.shot_digest,
  };
}

/** 明确说明"这张卡不能执行"的文案，视图与测试共用同一份字面量。 */
export const STORYBOARD_DRAFT_NOTICE = '这是一张草稿卡片：不会入队、不会调用模型、不会改写原文档或时间线。';
