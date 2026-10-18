/**
 * UX-06 纯函数层：标尺、缩放、吸附、入出点、轨道状态、编辑指令映射、字幕轨、导出状态与上限提示。
 *
 * 规则：
 *  - 时间一律使用原 owner 的整数毫秒基（`studioTimelineTypes`）；标尺刻度由
 *    `起点 + 序号 × 步长` 直接计算，绝不做浮点累加；速度用原 owner 的整数比 `speed_num / speed_den`。
 *  - 每个入参都按不可信数据处理；非法输入返回带稳定机器码与中文原因的**明确拒绝**，
 *    绝不静默改成别的动作，也绝不发明 owner 没有的编辑语义。
 *  - 本模块不发网络请求、不建定时器、不读写存储、不生成随机标识。
 */
import { checkedTimeline, timelineClipDuration } from '../creative/studioTimelineTypes';
import type {
  StudioTimeline, StudioTimelineClip, StudioTimelineSource, StudioTimelineTrack,
} from '../creative/studioTimelineTypes';
import { checkedTimelineExportProfile } from '../creative/studioTimelineExportTypes';
import {
  NLE_CODES, NLE_OWNER_LIMITS,
  type NleClipFacts, type NleCaptionKind, type NleEditKind, type NleEditPlan, type NleExportStage, type NleExportStatus,
  type NleLimitsNotice, type NleLimitRow, type NleMarks, type NleMarksCheck, type NleMediaPreviewRequest, type NleOk,
  type NleOwnerOperation, type NleOwnerOperationId, type NleRangeCheck, type NleRefusal,
  type NleRuler, type NleRulerTick, type NleSnapCandidate, type NleSnapKind, type NleSnapResult,
  type NleSnapSet, type NleSourceRange, type NleSubtitleCueState, type NleSubtitleFormat,
  type NleSubtitleModel, type NleTimebase, type NleTimelineCheck, type NleTrackHeaderCheck,
  type NleTrackHeaderState, type NleTrimPlan, type NleUsage, type NleViewWindow, type NleWindowCheck,
  type NleWindowRange,
} from './timelineOpsTypes';

export const NLE_DEFAULT_SNAP_TOLERANCE_MS = 120;
export const NLE_MAX_SNAP_TOLERANCE_MS = 2000;
export const NLE_MAX_SNAP_CANDIDATES = 120;
export const NLE_RULER_MAX_TICKS = 240;
export const NLE_RULER_MAX_MAJOR_TICKS = 12;
export const NLE_VIEW_SCALE_MIN = 0.001;
export const NLE_VIEW_SCALE_MAX = 8;
export const NLE_DEFAULT_VIEW_WIDTH_PX = 960;
export const NLE_MAX_VIEW_WIDTH_PX = 8192;
/** 上限提示的"接近"阈值：4/5（80%）。 */
export const NLE_NEAR_NUMERATOR = 4;
export const NLE_NEAR_DENOMINATOR = 5;

export const NLE_LIMIT_SOURCES = {
  timeline: 'frontend/src/creative/studioTimelineTypes.ts: TIMELINE_LIMITS / app/services/studio_timeline_schema.py',
  render: 'app/services/studio_timeline_render.py: MAX_* 与 render_studio_timeline(max_bytes)',
  subtitles: 'app/services/studio_timeline_subtitles.py: MAX_SIDECAR_BYTES',
  edit: 'app/services/studio_timeline_edit.py: apply_timeline_edits',
} as const;

export const NLE_SPLIT_ADVICE =
  '接近轨道、片段、总长或素材体积上限时，请把内容拆成多段时间线分别编辑与交付。本界面只如实说明原上限，不会提高任何上限。';

/** 原 owner 的标识文法（`studio_timeline_render.py: _identity`）。 */
const IDENTITY = /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/;
const DIGEST = /^[a-f0-9]{64}$/;
const ALL_OWNER_OPERATIONS: readonly NleOwnerOperationId[] = [
  'canvas.update', 'track.insert', 'track.remove', 'track.update', 'track.reorder',
  'clip.insert', 'clip.update', 'clip.remove', 'clip.move', 'clip.duplicate',
  'clip.split', 'clip.trim', 'clip.slip', 'caption.insert', 'caption.update', 'caption.remove',
];

export function nleRefusal(code: string, message: string): NleRefusal {
  return { ok: false, code, message };
}

function plainObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}
function closedObject(value: unknown, allowed: readonly string[]): Record<string, unknown> | null {
  const row = plainObject(value);
  if (!row) return null;
  return Object.keys(row).some(key => !allowed.includes(key)) ? null : row;
}
const isInteger = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value);
const isFiniteNumber = (value: unknown, min: number, max: number): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
const clampInteger = (value: number, min: number, max: number): number => value < min ? min : value > max ? max : value;
const pad = (value: number, size = 2): string => String(value).padStart(size, '0');
/** UTF-8 字节数（按码点计算，不依赖 TextEncoder / Buffer）。 */
function utf8Length(value: string): number {
  let bytes = 0;
  for (const character of value) {
    const code = character.codePointAt(0) ?? 0;
    bytes += code <= 0x7f ? 1 : code <= 0x7ff ? 2 : code <= 0xffff ? 3 : 4;
  }
  return bytes;
}

/** 整数毫秒 → `mm:ss.mmm`（超过一小时为 `h:mm:ss.mmm`）。纯整数运算。 */
export function rulerLabel(ms: number): string {
  const hours = Math.floor(ms / 3_600_000), minutes = Math.floor(ms / 60_000) % 60;
  const seconds = Math.floor(ms / 1000) % 60, millis = ms % 1000;
  return `${hours ? `${hours}:${pad(minutes)}` : pad(minutes)}:${pad(seconds)}.${pad(millis, 3)}`;
}
/** 由整数毫秒基派生的帧序号（向下取整），不是权威帧边界。 */
export function frameIndex(ms: number, fps: number): number {
  return Math.floor(ms * fps / 1000);
}

/** 用原 owner 的封闭校验器读取时间线；失败时保留它自己的中文说明。 */
export function safeTimeline(value: unknown): NleTimelineCheck {
  try {
    return { ok: true, timeline: checkedTimeline(value) };
  } catch (reason) {
    return nleRefusal(NLE_CODES.timelineInvalid,
      reason instanceof Error && reason.message ? reason.message : '时间线输入无效，请读取原服务保存的版本后重试。');
  }
}

export function timebaseOf(timeline: StudioTimeline): NleTimebase {
  return timeline.schema_version === 3 ? { durationMs: timeline.duration_ms, mediaKind: 'AUDIO' } : { durationMs: timeline.duration_ms, fps: timeline.fps };
}

export function validateTimebase(value: unknown): NleOk<NleTimebase> | NleRefusal {
  const row = plainObject(value);
  if (row?.mediaKind === 'AUDIO' && Object.keys(row).every(key => ['durationMs', 'mediaKind'].includes(key))
    && isInteger(row.durationMs) && row.durationMs >= 1 && row.durationMs <= NLE_OWNER_LIMITS.durationMs) return { ok: true, value: { durationMs: row.durationMs, mediaKind: 'AUDIO' } };
  if (!row || Object.keys(row).some(key => key !== 'durationMs' && key !== 'fps')
    || !isInteger(row.durationMs) || row.durationMs < 1 || row.durationMs > NLE_OWNER_LIMITS.durationMs
    || !isInteger(row.fps) || row.fps < NLE_OWNER_LIMITS.fpsMin || row.fps > NLE_OWNER_LIMITS.fpsMax) {
    return nleRefusal(NLE_CODES.timebaseInvalid,
      `时间基数需要 1 至 ${NLE_OWNER_LIMITS.durationMs} 的整数毫秒总长与 ${NLE_OWNER_LIMITS.fpsMin} 至 ${NLE_OWNER_LIMITS.fpsMax} 的整数帧率。`);
  }
  return { ok: true, value: { durationMs: row.durationMs, fps: row.fps } };
}

export function validateWindow(value: unknown, timebase: NleTimebase): NleWindowCheck {
  const row = plainObject(value);
  if (!row || Object.keys(row).some(key => key !== 'startMs' && key !== 'scale')
    || !isInteger(row.startMs) || row.startMs < 0 || row.startMs > Math.max(0, timebase.durationMs - 1)
    || typeof row.scale !== 'number' || !Number.isFinite(row.scale)
    || row.scale < NLE_VIEW_SCALE_MIN || row.scale > NLE_VIEW_SCALE_MAX) {
    return nleRefusal(NLE_CODES.viewInvalid,
      `视窗需要 0 至 ${Math.max(0, timebase.durationMs - 1)} 的整数起点与 ${NLE_VIEW_SCALE_MIN} 至 ${NLE_VIEW_SCALE_MAX} 的缩放（每毫秒像素数）。`);
  }
  return { ok: true, window: { startMs: row.startMs, scale: row.scale } };
}

export function windowRange(window: NleViewWindow, widthPx: number, timebase: NleTimebase): NleWindowRange {
  const width = isInteger(widthPx) && widthPx > 0 ? Math.min(widthPx, NLE_MAX_VIEW_WIDTH_PX) : NLE_DEFAULT_VIEW_WIDTH_PX;
  const startMs = clampInteger(window.startMs, 0, Math.max(0, timebase.durationMs - 1));
  const wanted = Math.max(1, Math.round(width / window.scale));
  const endMs = Math.min(timebase.durationMs, startMs + wanted);
  return { startMs, endMs, windowMs: endMs - startMs };
}

function clampStart(startMs: number, scale: number, timebase: NleTimebase): number {
  const viewMs = Math.min(timebase.durationMs, Math.max(1, Math.round(NLE_DEFAULT_VIEW_WIDTH_PX / scale)));
  return clampInteger(startMs, 0, Math.max(0, timebase.durationMs - viewMs));
}

/** 以 `anchorMs` 为锚点缩放；结果是总函数，越界一律收敛到合法视窗。 */
export function zoomWindow(window: NleViewWindow, factor: number, anchorMs: number, timebase: NleTimebase): NleViewWindow {
  const next = isFiniteNumber(factor, NLE_VIEW_SCALE_MIN, 1 / NLE_VIEW_SCALE_MIN) ? factor : 1;
  const scale = Math.min(NLE_VIEW_SCALE_MAX, Math.max(NLE_VIEW_SCALE_MIN, window.scale * next));
  const anchor = clampInteger(isInteger(anchorMs) ? anchorMs : window.startMs, 0, timebase.durationMs);
  const offset = anchor - window.startMs;
  return { startMs: clampStart(anchor - Math.round(offset * window.scale / scale), scale, timebase), scale };
}

export function scrollWindow(window: NleViewWindow, deltaMs: number, timebase: NleTimebase): NleViewWindow {
  const delta = isInteger(deltaMs) ? deltaMs : 0;
  return { startMs: clampStart(window.startMs + delta, window.scale, timebase), scale: window.scale };
}

/** 标尺刻度：位置一律为 `序号 × 步长`，无浮点累加，且绝不超出 owner 的总长。 */
export function rulerTicks(window: NleViewWindow, timebase: NleTimebase, widthPx = NLE_DEFAULT_VIEW_WIDTH_PX): NleRuler {
  const range = windowRange(window, widthPx, timebase);
  const span = Math.max(1, range.windowMs);
  let stepMs: number = NLE_OWNER_LIMITS.durationMs;
  for (const candidate of [10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000,
    10_000, 15_000, 30_000, 60_000, 120_000, 300_000, 600_000]) {
    if (span <= candidate * NLE_RULER_MAX_MAJOR_TICKS) { stepMs = candidate; break; }
  }
  const minorStepMs = stepMs % 5 === 0 && stepMs / 5 >= 5 ? stepMs / 5 : stepMs;
  const ticks: NleRulerTick[] = [];
  let truncated = false;
  for (let index = Math.ceil(range.startMs / minorStepMs); ; index++) {
    const ms = index * minorStepMs;
    if (ms > range.endMs) break;
    if (ticks.length >= NLE_RULER_MAX_TICKS) { truncated = true; break; }
    ticks.push({ index: ticks.length, ms, major: ms % stepMs === 0, label: rulerLabel(ms), ...(timebase.mediaKind === 'AUDIO' ? {} : { frame: frameIndex(ms, timebase.fps) }) });
  }
  return { window: { startMs: range.startMs, scale: window.scale }, range, stepMs, minorStepMs, ticks, truncated };
}

const SNAP_PRIORITY: Record<NleSnapKind, number> = { MARK_IN: 0, MARK_OUT: 1, PLAYHEAD: 2, CLIP_START: 3, CLIP_END: 4 };
const SNAP_LABELS: Record<NleSnapKind, string> = { MARK_IN: '入点', MARK_OUT: '出点', PLAYHEAD: '播放头', CLIP_START: '片段开始', CLIP_END: '片段结束' };

export function validateMarks(value: unknown, timebase: NleTimebase): NleMarksCheck {
  const row = closedObject(value, ['inMs', 'outMs']);
  if (!row) return nleRefusal(NLE_CODES.marksInvalid, '入点与出点需要是空值或时间线范围内的整数毫秒。');
  const checked: NleMarks = { inMs: null, outMs: null };
  for (const key of ['inMs', 'outMs'] as const) {
    const point = row[key];
    if (point === null || point === undefined) continue;
    if (!isInteger(point) || point < 0 || point > timebase.durationMs) {
      return nleRefusal(NLE_CODES.integerRequired, `入点与出点需要是 0 至 ${timebase.durationMs} 的整数毫秒。`);
    }
    checked[key] = point;
  }
  return { ok: true, marks: checked };
}

/** 只返回真实候选：片段边界、播放头与明确设置的入/出点。 */
export function snapCandidates(input: {
  timeline: StudioTimeline;
  playheadMs: number;
  marks: NleMarks;
  selectedClipIds?: readonly string[];
  toleranceMs?: number;
}): NleSnapSet {
  const durationMs = input.timeline.duration_ms;
  const selected = new Set(input.selectedClipIds ?? []);
  const toleranceMs = isInteger(input.toleranceMs) && input.toleranceMs >= 0 && input.toleranceMs <= NLE_MAX_SNAP_TOLERANCE_MS
    ? input.toleranceMs : NLE_DEFAULT_SNAP_TOLERANCE_MS;
  const raw: Array<NleSnapCandidate & { selected: boolean }> = [];
  const push = (ms: number, kind: NleSnapKind, trackId: string | null, clipId: string | null) => {
    if (!isInteger(ms) || ms < 0 || ms > durationMs) return;
    raw.push({ ms, kind, trackId, clipId, label: SNAP_LABELS[kind], selected: clipId !== null && selected.has(clipId) });
  };
  push(input.marks.inMs ?? Number.NaN, 'MARK_IN', null, null);
  push(input.marks.outMs ?? Number.NaN, 'MARK_OUT', null, null);
  push(input.playheadMs, 'PLAYHEAD', null, null);
  for (const track of input.timeline.tracks) {
    for (const clip of track.clips) {
      const length = timelineClipDuration(clip);
      push(clip.start_ms, 'CLIP_START', track.id, clip.id);
      push(clip.start_ms + length, 'CLIP_END', track.id, clip.id);
    }
  }
  const best = new Map<number, NleSnapCandidate & { selected: boolean }>();
  for (const candidate of raw) {
    const current = best.get(candidate.ms);
    const better = !current || SNAP_PRIORITY[candidate.kind] < SNAP_PRIORITY[current.kind]
      || SNAP_PRIORITY[candidate.kind] === SNAP_PRIORITY[current.kind] && current.selected === false && candidate.selected;
    if (better) best.set(candidate.ms, candidate);
  }
  const sorted = [...best.values()].sort((left, right) => left.ms - right.ms
    || SNAP_PRIORITY[left.kind] - SNAP_PRIORITY[right.kind] || (left.selected === right.selected ? 0 : left.selected ? -1 : 1));
  const truncated = sorted.length > NLE_MAX_SNAP_CANDIDATES;
  return {
    candidates: sorted.slice(0, NLE_MAX_SNAP_CANDIDATES).map(({ ms, kind, trackId, clipId, label }) => ({ ms, kind, trackId, clipId, label })),
    toleranceMs, truncated,
  };
}

export function snapTime(set: NleSnapSet, ms: number, toleranceMs?: number): NleSnapResult {
  const tolerance = isInteger(toleranceMs) && toleranceMs >= 0 && toleranceMs <= NLE_MAX_SNAP_TOLERANCE_MS ? toleranceMs : set.toleranceMs;
  if (!isInteger(ms)) return { ms: 0, snapped: false, candidate: null };
  let winner: NleSnapCandidate | null = null, distance = Number.MAX_SAFE_INTEGER;
  for (const candidate of set.candidates) {
    const delta = Math.abs(candidate.ms - ms);
    if (delta < distance || delta === distance && winner && candidate.ms < winner.ms) { winner = candidate; distance = delta; }
  }
  return winner && distance <= tolerance ? { ms: winner.ms, snapped: true, candidate: winner } : { ms, snapped: false, candidate: null };
}

/** 吸附后的片段起点始终落在 `[0, 总长 − 片段时长]` 内，绝不因吸附越出时间线。 */
export function snapClipStart(timeline: StudioTimeline, clip: StudioTimelineClip, proposedStartMs: number, set: NleSnapSet): NleSnapResult {
  const length = timelineClipDuration(clip);
  const maxStart = Math.max(0, timeline.duration_ms - length);
  const snapped = snapTime(set, proposedStartMs);
  const candidate = snapped.candidate && snapped.candidate.ms <= maxStart ? snapped : { ms: proposedStartMs, snapped: false, candidate: null };
  return { ms: clampInteger(candidate.ms, 0, maxStart), snapped: candidate.snapped, candidate: candidate.candidate };
}

export function setInOut(marks: unknown, point: string, ms: unknown, timebase: NleTimebase): NleMarksCheck {
  const checked = validateMarks(marks, timebase);
  if (!checked.ok) return checked;
  if (point !== 'IN' && point !== 'OUT') {
    return nleRefusal(NLE_CODES.integerRequired, '标记点只能是入点或出点。');
  }
  if (!isInteger(ms) || ms < 0 || ms > timebase.durationMs) {
    return nleRefusal(NLE_CODES.integerRequired, `标记位置需要是 0 至 ${timebase.durationMs} 的整数毫秒。`);
  }
  const next: NleMarks = { ...checked.marks };
  if (point === 'IN') {
    if (next.outMs !== null && ms >= next.outMs) return nleRefusal(NLE_CODES.rangeOutBeforeIn, '入点必须早于出点；请先移动出点，这里不会替你改动它。');
    next.inMs = ms;
  } else {
    if (next.inMs !== null && ms <= next.inMs) return nleRefusal(NLE_CODES.rangeOutBeforeIn, '出点必须晚于入点；请先移动入点，这里不会替你改动它。');
    next.outMs = ms;
  }
  return { ok: true, marks: next };
}

/** 拒绝超出素材可用范围的出点、超出时间线的出点，以及早于入点的出点。 */
export function validateRange(marks: unknown, timebase: NleTimebase, source?: NleSourceRange): NleRangeCheck {
  const row = closedObject(marks, ['inMs', 'outMs']);
  if (!row) return nleRefusal(NLE_CODES.marksInvalid, '入点与出点需要是空值或时间线范围内的整数毫秒。');
  const rawIn = row.inMs ?? null, rawOut = row.outMs ?? null;
  if (rawIn === null) return nleRefusal(NLE_CODES.rangeInRequired, '请先设置入点。');
  if (rawOut === null) return nleRefusal(NLE_CODES.rangeOutRequired, '请先设置出点。');
  if (!isInteger(rawIn) || !isInteger(rawOut) || rawIn < 0 || rawOut < 0) {
    return nleRefusal(NLE_CODES.integerRequired, `入点与出点需要是 0 至 ${timebase.durationMs} 的整数毫秒。`);
  }
  const inMs = rawIn, outMs = rawOut;
  if (outMs <= inMs) return nleRefusal(NLE_CODES.rangeOutBeforeIn, '出点必须晚于入点。');
  if (outMs > timebase.durationMs) {
    return nleRefusal(NLE_CODES.rangeOutsideTimeline, `出点 ${outMs} 毫秒超出时间线总长 ${timebase.durationMs} 毫秒。`);
  }
  if (inMs > timebase.durationMs) {
    return nleRefusal(NLE_CODES.rangeOutsideTimeline, `入点 ${inMs} 毫秒超出时间线总长 ${timebase.durationMs} 毫秒。`);
  }
  if (source) {
    if (!isInteger(source.inMs) || !isInteger(source.outMs) || source.outMs <= source.inMs) {
      return nleRefusal(NLE_CODES.integerRequired, '素材可用范围需要是整数毫秒且出点晚于入点。');
    }
    if (inMs < source.inMs) return nleRefusal(NLE_CODES.rangeBeforeSourceIn, `入点早于素材可用入点 ${source.inMs} 毫秒。`);
    if (outMs > source.outMs) return nleRefusal(NLE_CODES.rangeOutsideSource, `出点超出素材可用范围 ${source.outMs} 毫秒；原渲染服务会拒绝超出来源时长的裁剪。`);
  }
  return { ok: true, range: { startMs: inMs, endMs: outMs, durationMs: outMs - inMs }, sourceRangeChecked: !!source };
}

export function trackGainState(kind: StudioTimelineTrack['kind'], gainDb: unknown): NleOk<number> | NleRefusal {
  if (typeof gainDb !== 'number' || !Number.isFinite(gainDb)) {
    return nleRefusal(NLE_CODES.trackGainOutOfRange, `音量需要是 ${NLE_OWNER_LIMITS.gainMinDb} 至 ${NLE_OWNER_LIMITS.gainMaxDb} dB 的有限数值。`);
  }
  if (gainDb < NLE_OWNER_LIMITS.gainMinDb || gainDb > NLE_OWNER_LIMITS.gainMaxDb) {
    return nleRefusal(NLE_CODES.trackGainOutOfRange, `音量范围为 ${NLE_OWNER_LIMITS.gainMinDb} 至 ${NLE_OWNER_LIMITS.gainMaxDb} dB。`);
  }
  if (kind === 'VIDEO' && gainDb !== 0) {
    return nleRefusal(NLE_CODES.trackGainVideoFixed, '视频轨道音量固定为 0 dB，只有音频轨道可以调整。');
  }
  return { ok: true, value: gainDb };
}

/** 校验单条轨道（不可信输入）的锁、静音与增益呈现状态。 */
export function trackHeaderState(track: unknown): NleTrackHeaderCheck {
  const row = closedObject(track, ['id', 'kind', 'order', 'muted', 'gain_db', 'clips', 'role', 'locked']);
  if (!row) return nleRefusal(NLE_CODES.trackNotFound, '轨道字段不符合原时间线契约。');
  const trackId = row.id;
  if (typeof trackId !== 'string' || !IDENTITY.test(trackId)) {
    return nleRefusal(NLE_CODES.trackNotFound, '轨道标识无效。');
  }
  const kind = row.kind;
  if (kind !== 'VIDEO' && kind !== 'AUDIO') return nleRefusal(NLE_CODES.trackNotFound, '轨道类型只能是视频或音频。');
  if (!isInteger(row.order) || row.order < 0 || row.order > 7) {
    return nleRefusal(NLE_CODES.trackNotFound, `轨道叠放顺序需要是 0 至 ${NLE_OWNER_LIMITS.tracks - 1} 的整数。`);
  }
  if (typeof row.muted !== 'boolean') return nleRefusal(NLE_CODES.trackNotFound, '轨道静音状态无效。');
  if (row.locked !== undefined && typeof row.locked !== 'boolean') return nleRefusal(NLE_CODES.trackNotFound, '轨道锁状态无效。');
  const gain = trackGainState(kind, row.gain_db);
  if (!gain.ok) return gain;
  const clips = row.clips;
  if (!Array.isArray(clips) || clips.length > NLE_OWNER_LIMITS.clips) {
    return nleRefusal(NLE_CODES.trackNotFound, `每条轨道最多 ${NLE_OWNER_LIMITS.clips} 个片段。`);
  }
  const clipIds: string[] = [];
  for (const clip of clips) {
    const item = plainObject(clip);
    if (!item || typeof item.id !== 'string' || !IDENTITY.test(item.id)) return nleRefusal(NLE_CODES.trackNotFound, '片段标识无效。');
    clipIds.push(item.id);
  }
  const role = row.role === undefined ? (kind === 'VIDEO' ? 'PRIMARY' : 'DIALOGUE') : row.role;
  if (typeof role !== 'string') return nleRefusal(NLE_CODES.trackNotFound, '轨道用途无效。');
  const header: NleTrackHeaderState = {
    trackId, kind, order: row.order, role, locked: row.locked === true, muted: row.muted,
    gainDb: gain.value, gainMinDb: NLE_OWNER_LIMITS.gainMinDb, gainMaxDb: NLE_OWNER_LIMITS.gainMaxDb,
    gainAdjustable: kind === 'AUDIO', clipCount: clipIds.length, clipIds,
  };
  return { ok: true, header };
}

export function clipFacts(timeline: StudioTimeline, clipId: string): NleClipFacts | null {
  for (const track of timeline.tracks) {
    for (const clip of track.clips) {
      if (clip.id !== clipId) continue;
      const durationMs = timelineClipDuration(clip);
      return { trackId: track.id, trackKind: track.kind, clip, startMs: clip.start_ms, durationMs,
        endMs: clip.start_ms + durationMs, sourceKind: clip.source_snapshot.asset_kind,
        speedNum: clip.speed_num ?? 1, speedDen: clip.speed_den ?? 1 };
    }
  }
  return null;
}

export function selectedClipFacts(timeline: StudioTimeline, clipIds: readonly string[]): NleClipFacts[] {
  const facts: NleClipFacts[] = [];
  for (const track of timeline.tracks) {
    for (const clip of track.clips) {
      if (!clipIds.includes(clip.id)) continue;
      const durationMs = timelineClipDuration(clip);
      facts.push({ trackId: track.id, trackKind: track.kind, clip, startMs: clip.start_ms, durationMs,
        endMs: clip.start_ms + durationMs, sourceKind: clip.source_snapshot.asset_kind,
        speedNum: clip.speed_num ?? 1, speedDen: clip.speed_den ?? 1 });
    }
  }
  return facts;
}

/** 时间线时长增量的媒体映射：`mediaDelta = delta * speed_num / speed_den`，必须落在整数毫秒上。 */
function mediaDelta(deltaMs: number, num: number, den: number): number | null {
  if (!isInteger(deltaMs)) return null;
  const product = deltaMs * num;
  if (product % den !== 0) return null;
  return product / den;
}

/** 反复裁剪也不漂移：每一步都在整数素材入出点上做精确加法，越界即拒绝而不是收敛。 */
export function trimClip(clip: StudioTimelineClip, step: { inDeltaMs?: number; outDeltaMs?: number },
  context: { sourceRange?: NleSourceRange; timelineDurationMs?: number } = {}): NleTrimPlan {
  const num = clip.speed_num ?? 1, den = clip.speed_den ?? 1;
  const inDelta = step.inDeltaMs ?? 0, outDelta = step.outDeltaMs ?? 0;
  const mediaIn = mediaDelta(inDelta, num, den), mediaOut = mediaDelta(outDelta, num, den);
  if (mediaIn === null || mediaOut === null) {
    return nleRefusal(NLE_CODES.editFractionalMs, '此裁剪增量不能按当前速度映射至整数毫秒的素材入出点。');
  }
  const inMs = clip.in_ms + mediaIn, outMs = clip.out_ms + mediaOut;
  if (outMs <= inMs) return nleRefusal(NLE_CODES.editTrimEmpty, '裁剪后片段长度必须为正整数毫秒。');
  if (inMs < 0 || outMs > NLE_OWNER_LIMITS.sourceTrimMs) {
    return nleRefusal(NLE_CODES.editTrimOutsideSource,
      `素材入出点需要落在 0 至 ${NLE_OWNER_LIMITS.sourceTrimMs} 毫秒内；原渲染服务还会核对实际素材时长。`);
  }
  if (context.sourceRange) {
    if (inMs < context.sourceRange.inMs || outMs > context.sourceRange.outMs) {
      return nleRefusal(NLE_CODES.editTrimOutsideSource, `裁剪超出素材可用范围 ${context.sourceRange.inMs} 至 ${context.sourceRange.outMs} 毫秒。`);
    }
  }
  const length = (outMs - inMs) * den / num;
  if (!Number.isSafeInteger(length)) return nleRefusal(NLE_CODES.editFractionalMs, '裁剪后的渲染长度必须落在整数毫秒上。');
  if (isInteger(context.timelineDurationMs) && clip.start_ms + length > context.timelineDurationMs) {
    return nleRefusal(NLE_CODES.rangeOutsideTimeline, `裁剪后片段结束 ${clip.start_ms + length} 毫秒超出时间线总长 ${context.timelineDurationMs} 毫秒。`);
  }
  return { ok: true, inMs, outMs, mediaInDeltaMs: mediaIn, mediaOutDeltaMs: mediaOut, durationMs: length, timelineDeltaMs: length - timelineClipDuration(clip) };
}

type EditContext = {
  timeline?: StudioTimeline;
  clipId?: string;
  targetTrackId?: string;
  atMs?: number;
  startMs?: number;
  inMs?: number;
  outMs?: number;
  offsetMs?: number;
  newClipId?: string;
  ripple?: boolean;
  sourceSnapshot?: StudioTimelineSource;
  sourceRange?: NleSourceRange;
};

const EDIT_CONTEXT_KEYS = ['timeline', 'clipId', 'targetTrackId', 'atMs', 'startMs', 'inMs', 'outMs',
  'offsetMs', 'newClipId', 'ripple', 'sourceSnapshot', 'sourceRange'] as const;

const EDIT_KIND_UNSUPPORTED_BY_OWNER: Record<string, string> = {
  speed: '原编辑服务没有"变速"动作；速度只能在片段已有字段上整段设置，本面不生成该指令。',
  grade: '高级调色、LUT 与自定义滤镜不支持；基础亮度、对比度和饱和度请使用片段属性中的基础调色控件。',
  composite: '本工作包不做合成；原编辑服务也没有合成语义。',
  transition: '原编辑服务只接受片段上已存在的交叉溶解字段，没有独立的转场动作。',
  render: '渲染由原制作任务发起，不属于编辑指令。',
};

function refusalForKind(kind: string): NleRefusal {
  return nleRefusal(NLE_CODES.editKindUnsupported,
    EDIT_KIND_UNSUPPORTED_BY_OWNER[kind] ?? `原编辑服务不接受"${kind}"这个动作；本面只生成它已经实现的操作。`);
}

function operationBytes(operation: NleOwnerOperation): number {
  return utf8Length(JSON.stringify(operation));
}

function finishPlan(kind: NleEditKind | NleCaptionKind, op: NleOwnerOperationId, payload: NleOwnerOperation): NleEditPlan {
  const batchBytes = operationBytes(payload);
  if (batchBytes > NLE_OWNER_LIMITS.editBatchBytes) {
    return nleRefusal(NLE_CODES.editBatchLimit, `单批编辑不能超过 ${NLE_OWNER_LIMITS.editBatchBytes} 字节。`);
  }
  return { ok: true, kind, op, payload, batchBytes };
}

/**
 * 把界面请求映射到**已经存在**的原编辑操作描述符；owner 没有的语义一律明确拒绝。
 * 只返回 `apply_timeline_edits` 已接受的形状，并且只返回 `clip.*` 这一类动作。
 */
export function editCommand(kind: string, context: unknown): NleEditPlan {
  const row = closedObject(context, EDIT_CONTEXT_KEYS) as EditContext | null;
  if (!row) return nleRefusal(NLE_CODES.editKindUnsupported, '编辑上下文包含原编辑服务不认识的字段。');
  const parsed = safeTimeline(row.timeline);
  if (!parsed.ok) return nleRefusal(NLE_CODES.timelineInvalid, '编辑指令需要当前通过原契约校验的时间线。');
  const timeline = parsed.timeline;
  const found = typeof row.clipId === 'string' ? clipFacts(timeline, row.clipId) : null;
  if (!found) return nleRefusal(NLE_CODES.editClipNotFound, '找不到要编辑的片段，请重新选择。');
  const track: StudioTimelineTrack | undefined = timeline.tracks.find(item => item.id === found.trackId);
  if (!track) return nleRefusal(NLE_CODES.editTrackNotFound, '找不到片段所在的轨道。');
  if (track.locked === true) {
    return nleRefusal(NLE_CODES.trackLocked, '该轨道已在原服务锁定；请先通过原服务明确解锁，这里不会绕过锁定。');
  }
  const clip = found.clip;
  const needsId = (value: unknown): string | NleRefusal => {
    if (typeof value !== 'string' || !IDENTITY.test(value)) {
      return nleRefusal(NLE_CODES.editNewIdRequired, '拆分或复制需要由调用方提供稳定的新片段标识（标识由作者给出，本面不生成）。');
    }
    return value;
  };
  const sameKindTarget = (): StudioTimelineTrack | NleRefusal => {
    const target = timeline.tracks.find(item => item.id === (row.targetTrackId ?? found.trackId));
    if (!target) return nleRefusal(NLE_CODES.editTrackNotFound, '找不到目标轨道。');
    if (target.kind !== track.kind) return nleRefusal(NLE_CODES.editMoveKindInvalid, '片段只能移动到同类型的轨道。');
    if (target.locked === true) return nleRefusal(NLE_CODES.trackLocked, '目标轨道已在原服务锁定。');
    return target;
  };

  if (kind === 'split') {
    const atMs = row.atMs;
    if (!isInteger(atMs)) return nleRefusal(NLE_CODES.editRangeInvalid, '拆分位置需要是整数毫秒。');
    const offset = atMs - clip.start_ms;
    if (!(offset > 0 && offset < found.durationMs)) {
      return nleRefusal(NLE_CODES.editSplitOutsideClip, '拆分位置必须位于片段的时间线范围内，并保留两段有效长度。');
    }
    if (mediaDelta(offset, found.speedNum, found.speedDen) === null) {
      return nleRefusal(NLE_CODES.editFractionalMs, '此拆分位置不能按当前速度映射至整数毫秒的素材入点。');
    }
    const newClipId = needsId(row.newClipId);
    if (typeof newClipId !== 'string') return newClipId;
    return finishPlan('split', 'clip.split', { op: 'clip.split', clip_id: clip.id, at_ms: atMs, new_clip_id: newClipId });
  }
  if (kind === 'trim') {
    const inMs = row.inMs, outMs = row.outMs;
    if (!isInteger(inMs) || !isInteger(outMs)) return nleRefusal(NLE_CODES.editRangeInvalid, '裁剪入点与出点需要是整数毫秒。');
    if (outMs <= inMs) return nleRefusal(NLE_CODES.editTrimEmpty, '裁剪后片段长度必须为正整数毫秒。');
    if (inMs < 0 || outMs > NLE_OWNER_LIMITS.sourceTrimMs) {
      return nleRefusal(NLE_CODES.editTrimOutsideSource, `素材入出点需要落在 0 至 ${NLE_OWNER_LIMITS.sourceTrimMs} 毫秒内。`);
    }
    if (row.sourceRange) {
      if (inMs < row.sourceRange.inMs || outMs > row.sourceRange.outMs) {
        return nleRefusal(NLE_CODES.editTrimOutsideSource, `裁剪超出素材可用范围 ${row.sourceRange.inMs} 至 ${row.sourceRange.outMs} 毫秒。`);
      }
    }
    const length = (outMs - inMs) * found.speedDen / found.speedNum;
    if (!Number.isSafeInteger(length)) return nleRefusal(NLE_CODES.editFractionalMs, '裁剪后的渲染长度必须落在整数毫秒上。');
    if (clip.start_ms + length > timeline.duration_ms) {
      return nleRefusal(NLE_CODES.rangeOutsideTimeline, '裁剪后片段结束超出时间线总长。');
    }
    const ripple = row.ripple === true;
    return finishPlan('trim', 'clip.trim', { op: 'clip.trim', clip_id: clip.id, in_ms: inMs, out_ms: outMs, ripple });
  }
  if (kind === 'move') {
    const startMs = row.startMs;
    if (!isInteger(startMs) || startMs < 0 || startMs > timeline.duration_ms - 1) {
      return nleRefusal(NLE_CODES.editRangeInvalid, `摆放位置需要是 0 至 ${timeline.duration_ms - 1} 的整数毫秒。`);
    }
    const target = sameKindTarget();
    if ('ok' in target) return target;
    if (startMs + found.durationMs > timeline.duration_ms) {
      return nleRefusal(NLE_CODES.rangeOutsideTimeline, '移动后片段结束超出时间线总长。');
    }
    return finishPlan('move', 'clip.move', { op: 'clip.move', clip_id: clip.id, track_id: target.id, start_ms: startMs });
  }
  if (kind === 'copy') {
    const startMs = row.startMs;
    if (!isInteger(startMs) || startMs < 0 || startMs > timeline.duration_ms - 1) {
      return nleRefusal(NLE_CODES.editRangeInvalid, `复制位置需要是 0 至 ${timeline.duration_ms - 1} 的整数毫秒。`);
    }
    const newClipId = needsId(row.newClipId);
    if (typeof newClipId !== 'string') return newClipId;
    if (newClipId === clip.id || clipFacts(timeline, newClipId)) {
      return nleRefusal(NLE_CODES.editNewIdRequired, '新片段标识不能与原片段或既有片段重复。');
    }
    const target = sameKindTarget();
    if ('ok' in target) return target;
    if (startMs + found.durationMs > timeline.duration_ms) {
      return nleRefusal(NLE_CODES.rangeOutsideTimeline, '复制后片段结束超出时间线总长。');
    }
    return finishPlan('copy', 'clip.duplicate', { op: 'clip.duplicate', clip_id: clip.id, new_clip_id: newClipId, track_id: target.id, start_ms: startMs });
  }
  if (kind === 'slip') {
    const offsetMs = row.offsetMs;
    if (!isInteger(offsetMs)) return nleRefusal(NLE_CODES.editRangeInvalid, '滑移增量需要是整数毫秒（可为负）。');
    if (found.sourceKind === 'image') {
      return nleRefusal(NLE_CODES.editStillSlipInvalid, '静态画面没有可滑移的素材时间，原编辑服务拒绝此类滑移。');
    }
    const inMs = clip.in_ms + offsetMs, outMs = clip.out_ms + offsetMs;
    if (inMs < 0 || outMs > NLE_OWNER_LIMITS.sourceTrimMs) {
      return nleRefusal(NLE_CODES.editSlipOutsideSource,
        `滑移后素材入出点需要落在 0 至 ${NLE_OWNER_LIMITS.sourceTrimMs} 毫秒内；原渲染服务还会核对实际素材时长。`);
    }
    if (row.sourceRange && (inMs < row.sourceRange.inMs || outMs > row.sourceRange.outMs)) {
      return nleRefusal(NLE_CODES.editSlipOutsideSource, `滑移超出素材可用范围 ${row.sourceRange.inMs} 至 ${row.sourceRange.outMs} 毫秒。`);
    }
    return finishPlan('slip', 'clip.slip', { op: 'clip.slip', clip_id: clip.id, offset_ms: offsetMs });
  }
  if (kind === 'ripple') {
    if (row.ripple !== true) return nleRefusal(NLE_CODES.editKindUnsupported, '波纹动作必须在上下文中明确 ripple=true；本面不会默认闭合间隙。');
    if (track.clips.length <= 1) {
      return nleRefusal(NLE_CODES.editKindUnsupported, '移走最后一个片段会留下空轨道；请先加入其他片段。');
    }
    return finishPlan('ripple', 'clip.remove', { op: 'clip.remove', clip_id: clip.id, ripple: true });
  }
  if (kind === 'source-replace') {
    const snapshot = closedObject(row.sourceSnapshot, ['id', 'kind', 'asset_kind', 'version', 'digest']);
    if (!snapshot) return nleRefusal(NLE_CODES.editSourceSnapshotInvalid, '替换素材需要完整的素材快照字段。');
    const allowedKinds = track.kind === 'VIDEO' ? ['video', 'image'] : ['audio'];
    if (snapshot.kind !== 'ASSET' || typeof snapshot.asset_kind !== 'string' || !allowedKinds.includes(snapshot.asset_kind)
      || typeof snapshot.id !== 'string' || !IDENTITY.test(snapshot.id)
      || typeof snapshot.digest !== 'string' || !DIGEST.test(snapshot.digest)
      || !isInteger(snapshot.version) || snapshot.version < 1) {
      return nleRefusal(NLE_CODES.editSourceKindInvalid, '替换素材的类型或摘要与轨道类型不匹配，或字段无效。');
    }
    const source: StudioTimelineSource = { id: snapshot.id, kind: 'ASSET', asset_kind: snapshot.asset_kind as StudioTimelineSource['asset_kind'], version: snapshot.version, digest: snapshot.digest };
    return finishPlan('source-replace', 'clip.update', { op: 'clip.update', clip_id: clip.id, changes: { source_snapshot: source } });
  }
  return refusalForKind(kind);
}

export function ownerOperationSupported(op: string): op is NleOwnerOperationId {
  return ALL_OWNER_OPERATIONS.includes(op as NleOwnerOperationId);
}

/** 编辑批次上限（原服务：每批 1..40 个操作、128000 字节）。 */
export function editBatchState(count: number, bytes: number): NleOk<{ count: number; bytes: number }> | NleRefusal {
  if (!isInteger(count) || count < 1 || count > NLE_OWNER_LIMITS.editOperationsPerBatch) {
    return nleRefusal(NLE_CODES.editBatchLimit, `每批编辑需要 1 至 ${NLE_OWNER_LIMITS.editOperationsPerBatch} 个操作。`);
  }
  if (!isInteger(bytes) || bytes < 0 || bytes > NLE_OWNER_LIMITS.editBatchBytes) {
    return nleRefusal(NLE_CODES.editBatchLimit, `每批编辑不能超过 ${NLE_OWNER_LIMITS.editBatchBytes} 字节。`);
  }
  return { ok: true, value: { count, bytes } };
}

/* -------------------------------------------------- 按需缩略图 / 波形契约 */

const PREVIEW_REQUEST_KEYS = ['kind', 'atMs', 'source', 'timelineId', 'timelineVersion', 'timelineDigest'] as const;

/**
 * 生成一个**只描述**按需缩略图或波形的请求（无 I/O、无缓存、无解码）。
 * 键绑定原始素材版本摘要与时间线版本摘要；任一变化都会得到不同的键。
 */
export function mediaPreviewRequest(input: unknown): NleOk<NleMediaPreviewRequest> | NleRefusal {
  const row = closedObject(input, PREVIEW_REQUEST_KEYS);
  if (!row) return nleRefusal(NLE_CODES.previewRequestInvalid, '缩略图或波形请求包含原契约不认识的字段。');
  if (row.kind !== 'THUMBNAIL' && row.kind !== 'WAVEFORM') {
    return nleRefusal(NLE_CODES.previewRequestInvalid, '只支持缩略图或波形两种按需读取。');
  }
  if (!isInteger(row.atMs) || row.atMs < 0 || row.atMs > NLE_OWNER_LIMITS.sourceTrimMs) {
    return nleRefusal(NLE_CODES.previewPositionInvalid, `读取位置需要是 0 至 ${NLE_OWNER_LIMITS.sourceTrimMs} 的整数毫秒。`);
  }
  const source = closedObject(row.source, ['id', 'kind', 'asset_kind', 'version', 'digest']);
  if (!source || source.kind !== 'ASSET' || typeof source.id !== 'string' || !IDENTITY.test(source.id)
    || typeof source.asset_kind !== 'string' || !['image', 'video', 'audio'].includes(source.asset_kind)
    || !isInteger(source.version) || source.version < 1
    || typeof source.digest !== 'string' || !DIGEST.test(source.digest)) {
    return nleRefusal(NLE_CODES.previewSourceInvalid, '按需读取必须绑定有效的原始素材标识、类型、版本与摘要。');
  }
  if (typeof row.timelineId !== 'string' || !IDENTITY.test(row.timelineId)
    || !isInteger(row.timelineVersion) || row.timelineVersion < 1
    || typeof row.timelineDigest !== 'string' || !DIGEST.test(row.timelineDigest)) {
    return nleRefusal(NLE_CODES.previewTimelineInvalid, '按需读取必须绑定有效的时间线标识、版本与摘要。');
  }
  const request: NleMediaPreviewRequest = {
    kind: row.kind, atMs: row.atMs,
    assetId: source.id, assetKind: source.asset_kind as StudioTimelineSource['asset_kind'],
    assetVersion: source.version, assetDigest: source.digest,
    timelineId: row.timelineId, timelineVersion: row.timelineVersion, timelineDigest: row.timelineDigest,
    key: `${row.kind}:${source.id}:v${source.version}:${source.digest}:tl:${row.timelineId}:v${row.timelineVersion}:${row.timelineDigest}:${row.atMs}`,
  };
  return { ok: true, value: request };
}

/* ------------------------------------------------------------ 字幕编辑指令 */

const CAPTION_CONTEXT_KEYS = ['timeline', 'index', 'caption'] as const;

/** 重建一个只替换字幕数组的时间线对象；`schema_version` 只在确为 2 时保留。 */
function withCaptions(timeline: StudioTimeline, captions: unknown[]): Record<string, unknown> {
  return {
    ...(timeline.schema_version === 2 ? { schema_version: 2 } : {}),
    duration_ms: timeline.duration_ms, width: timeline.width, height: timeline.height, fps: timeline.fps,
    tracks: timeline.tracks, captions,
    ...('caption_style' in timeline ? { caption_style: timeline.caption_style } : {}),
  };
}

/**
 * 生成字幕编辑指令（`caption.insert` / `caption.update` / `caption.remove`）。
 * 内容合法性完全交给原 owner 的前端校验器 `checkedTimeline`，本函数不另立规则。
 */
export function captionCommand(kind: string, context: unknown): NleEditPlan {
  const row = closedObject(context, CAPTION_CONTEXT_KEYS);
  if (!row) return nleRefusal(NLE_CODES.captionShapeInvalid, '字幕上下文包含原编辑服务不认识的字段。');
  const parsed = safeTimeline(row.timeline);
  if (!parsed.ok) return nleRefusal(NLE_CODES.timelineInvalid, '字幕指令需要当前通过原契约校验的时间线。');
  const current = parsed.timeline;
  if (current.schema_version === 3) return nleRefusal(NLE_CODES.captionShapeInvalid, '纯音频时间线没有字幕轨道。');
  const index = row.index;
  if (kind === 'caption-remove') {
    if (!isInteger(index) || index < 0 || index >= current.captions.length) {
      return nleRefusal(NLE_CODES.captionIndexInvalid, '找不到要移除的字幕序号。');
    }
    return finishPlan('caption-remove', 'caption.remove', { op: 'caption.remove', index });
  }
  if (kind !== 'caption-insert' && kind !== 'caption-update') {
    return refusalForKind(kind);
  }
  const raw = closedObject(row.caption, ['start_ms', 'end_ms', 'text']);
  if (!raw || !isInteger(raw.start_ms) || !isInteger(raw.end_ms) || typeof raw.text !== 'string') {
    return nleRefusal(NLE_CODES.captionShapeInvalid, '字幕需要整数毫秒的开始、结束时间与纯文字。');
  }
  const caption = { start_ms: raw.start_ms, end_ms: raw.end_ms, text: raw.text.replace(/\r\n/g, '\n') };
  if (kind === 'caption-update' && (!isInteger(index) || index < 0 || index >= current.captions.length)) {
    return nleRefusal(NLE_CODES.captionIndexInvalid, '找不到要更新的字幕序号。');
  }
  const next = kind === 'caption-insert'
    ? [...current.captions, caption]
    : current.captions.map((cue, position) => position === index ? caption : cue);
  let normalized: StudioTimeline;
  try {
    normalized = checkedTimeline(withCaptions(current, next));
  } catch (reason) {
    const message = reason instanceof Error && reason.message ? reason.message : '字幕内容不符合原时间线契约。';
    const code = message.includes('五千') || message.includes('五百') ? NLE_CODES.captionLimit
      : message.includes('三万二千') ? NLE_CODES.captionCharacterLimit : NLE_CODES.captionShapeInvalid;
    return nleRefusal(code, message);
  }
  if (normalized.schema_version === 3) return nleRefusal(NLE_CODES.captionShapeInvalid, '纯音频时间线没有字幕轨道。');
  const kept = normalized.captions.find(cue => cue.start_ms === caption.start_ms && cue.end_ms === caption.end_ms && cue.text === caption.text);
  if (!kept) return nleRefusal(NLE_CODES.captionShapeInvalid, '字幕内容未被原时间线契约接受。');
  if (kind === 'caption-insert') return finishPlan('caption-insert', 'caption.insert', { op: 'caption.insert', caption: kept });
  return finishPlan('caption-update', 'caption.update', { op: 'caption.update', index: index as number, caption: kept });
}

/* ---------------------------------------------------------------- 字幕轨 */

const SUBTITLE_MODEL_KEYS = ['cues', 'durationMs', 'importContent', 'importFormat', 'exportFormat'] as const;
const TIMING_SRT = /(\d{2,6}):([0-5]\d):([0-5]\d),(\d{3}) --> (\d{2,6}):([0-5]\d):([0-5]\d),(\d{3})/;
const TIMING_VTT = /(\d{2,6}):([0-5]\d):([0-5]\d)\.(\d{3}) --> (\d{2,6}):([0-5]\d):([0-5]\d)\.(\d{3})/;

function stamp(ms: number, format: NleSubtitleFormat): string {
  const hours = Math.floor(ms / 3_600_000), minutes = Math.floor(ms / 60_000) % 60;
  const seconds = Math.floor(ms / 1000) % 60, millis = ms % 1000;
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}${format === 'SRT' ? ',' : '.'}${pad(millis, 3)}`;
}

function importReadiness(content: unknown, format: unknown): { ok: boolean; code: string | null; message: string; cueCount: number } {
  if (format !== 'SRT' && format !== 'VTT') {
    return { ok: false, code: NLE_CODES.subtitleFormatInvalid, message: '只接受 SRT 或 VTT 纯文本字幕。', cueCount: 0 };
  }
  if (typeof content !== 'string' || !content) {
    return { ok: false, code: NLE_CODES.subtitleShapeInvalid, message: '请提供字幕文件内容。', cueCount: 0 };
  }
  if (content.length > NLE_OWNER_LIMITS.subtitleSidecarBytes || utf8Length(content) > NLE_OWNER_LIMITS.subtitleSidecarBytes) {
    return { ok: false, code: NLE_CODES.subtitleByteLimit, message: `字幕文件不能超过 ${NLE_OWNER_LIMITS.subtitleSidecarBytes} 字节。`, cueCount: 0 };
  }
  let text = content.startsWith('\ufeff') ? content.slice(1) : content;
  text = text.replace(/\r\n/g, '\n');
  if (text.includes('\r')) {
    return { ok: false, code: NLE_CODES.subtitleLineEndingsInvalid, message: '字幕只接受 LF 换行。', cueCount: 0 };
  }
  if (format === 'VTT') {
    if (!text.startsWith('WEBVTT\n\n')) {
      return { ok: false, code: NLE_CODES.subtitleHeaderInvalid, message: 'VTT 需要以纯文本 WEBVTT 头开始。', cueCount: 0 };
    }
    text = text.slice(8);
  }
  const trimmed = text.replace(/^\n+|\n+$/g, '');
  const blocks = trimmed ? trimmed.split('\n\n') : [];
  if (blocks.length < 1 || blocks.length > NLE_OWNER_LIMITS.captions) {
    return { ok: false, code: NLE_CODES.subtitleCueLimit, message: `字幕条数需要为 1 至 ${NLE_OWNER_LIMITS.captions} 条。`, cueCount: blocks.length };
  }
  const pattern = format === 'SRT' ? TIMING_SRT : TIMING_VTT;
  for (const [index, block] of blocks.entries()) {
    const lines = block.split('\n');
    const numbered = lines[0] === String(index + 1);
    const timingIndex = numbered ? 1 : 0;
    if (format === 'SRT' && !numbered) {
      return { ok: false, code: NLE_CODES.subtitleNumberedCuesRequired, message: 'SRT 需要按序号连续编号的字幕块。', cueCount: index };
    }
    const timing = lines[timingIndex] ?? '';
    if (!pattern.test(timing)) {
      return { ok: false, code: NLE_CODES.subtitleShapeInvalid, message: `第 ${index + 1} 条字幕缺少规范的时间行。`, cueCount: index };
    }
    if (lines.length <= timingIndex + 1 || lines.slice(timingIndex + 1).some(line => !line.trim())) {
      return { ok: false, code: NLE_CODES.subtitleShapeInvalid, message: `第 ${index + 1} 条字幕需要至少一行非空文字，且不接受空行。`, cueCount: index };
    }
  }
  return { ok: true, code: null, message: `可以导入 ${blocks.length} 条纯文本字幕。`, cueCount: blocks.length };
}

/**
 * 字幕轨模型：定位/编辑就绪度、导入导出就绪度，以及"没有转录模型时手动字幕仍然可用"。
 * 原字幕服务只做严格 sidecar 转换，没有转录或时间轴推断，所以转录永远不可用。
 */
export function subtitleTrackModel(cues: unknown, options: unknown = {}): NleSubtitleModel {
  const row = closedObject(options, SUBTITLE_MODEL_KEYS);
  const list = Array.isArray(cues) ? cues : null;
  const durationMs = row && isInteger(row.durationMs) ? row.durationMs : null;
  const checked: NleSubtitleCueState[] = [];
  let characters = 0;
  if (list && list.length <= NLE_OWNER_LIMITS.captions) {
    list.forEach((raw, index) => {
      const cue = plainObject(raw);
      const problems: string[] = [];
      const startMs = cue?.start_ms, endMs = cue?.end_ms, text = cue?.text;
      if (!isInteger(startMs) || !isInteger(endMs) || typeof text !== 'string') {
        problems.push('字幕字段无效。');
        checked.push({ index, startMs: 0, endMs: 0, durationMs: 0, text: '', lines: 0, characters: 0, locateReady: false, editReady: false, problems });
        return;
      }
      const lines = text.split('\n').length;
      if (endMs <= startMs) problems.push('结束时间必须晚于开始时间。');
      if (!text.trim()) problems.push('字幕文字不能为空。');
      if (text.length > 1000) problems.push('单条字幕不能超过 1000 字。');
      if (lines > 8) problems.push('单条字幕最多 8 行。');
      if (durationMs !== null && (startMs < 0 || endMs > durationMs)) problems.push(`字幕需要落在时间线 0 至 ${durationMs} 毫秒内。`);
      characters += text.length;
      checked.push({ index, startMs, endMs, durationMs: endMs - startMs,
        text, lines, characters: text.length, locateReady: problems.length === 0, editReady: problems.length === 0, problems });
    });
  }
  const overCharacters = characters > NLE_OWNER_LIMITS.captionCharacters;
  const importReady = importReadiness(row?.importContent, row?.importFormat);
  const exportFormat: NleSubtitleFormat | null = row?.exportFormat === 'SRT' || row?.exportFormat === 'VTT' ? row.exportFormat : null;
  let exportOk = false, exportCode: string | null = null, exportMessage = '请选择 SRT 或 VTT 导出格式。';
  if (exportFormat) {
    const blocks = checked.map((cue, index) => `${index + 1}\n${stamp(cue.startMs, exportFormat)} --> ${stamp(cue.endMs, exportFormat)}\n${cue.text}`);
    const content = (exportFormat === 'VTT' ? 'WEBVTT\n\n' : '') + blocks.join('\n\n') + (blocks.length ? '\n' : '');
    const bytes = utf8Length(content);
    if (overCharacters) { exportCode = NLE_CODES.subtitleCharacterLimit; exportMessage = `字幕总文字超过 ${NLE_OWNER_LIMITS.captionCharacters} 字。`; }
    else if (bytes > NLE_OWNER_LIMITS.subtitleSidecarBytes) { exportCode = NLE_CODES.subtitleByteLimit; exportMessage = `导出字幕约 ${bytes} 字节，超过 ${NLE_OWNER_LIMITS.subtitleSidecarBytes} 字节上限。`; }
    else { exportOk = !checked.some(cue => !cue.editReady); exportCode = exportOk ? null : NLE_CODES.subtitleShapeInvalid; exportMessage = exportOk ? `可以导出 ${checked.length} 条字幕（约 ${bytes} 字节）。` : '存在无效字幕，导出会被原服务拒绝。'; }
  }
  const locateReady = checked.every(cue => cue.locateReady) && !overCharacters;
  return {
    cues: checked, cueCount: checked.length, characters,
    locateReady, editReady: locateReady,
    importReady: importReady.ok, importCode: importReady.code, importMessage: importReady.message,
    exportReady: exportOk, exportCode, exportMessage, exportFormat,
    transcriptionAvailable: false, transcriptionCode: NLE_CODES.subtitleNoTranscriptionOwner,
    transcriptionMessage: '原字幕服务只做严格的 sidecar 转换，没有转录或时间轴推断；没有转录模型时，手动字幕仍然可用。',
    manualAvailable: checked.length < NLE_OWNER_LIMITS.captions && !overCharacters,
    limits: { captions: NLE_OWNER_LIMITS.captions, captionCharacters: NLE_OWNER_LIMITS.captionCharacters, sidecarBytes: NLE_OWNER_LIMITS.subtitleSidecarBytes },
  };
}

/* -------------------------------------------------------------- 导出状态 */

const RECEIPT_KEYS = ['state', 'contract', 'export_profile', 'preview_digest', 'request_id', 'request_digest',
  'limits', 'model_called', 'automatic_replay', 'product_acceptance', 'timeline_snapshot', 'sources', 'execution_recipe'];

function invalidExport(detail: string): NleExportStatus {
  return { stage: 'INVALID', requestedQuality: null, previewQuality: null, finalExportQuality: null, deliveryReady: false,
    head: '导出回执无法核对', detail, warnings: [], code: NLE_CODES.exportShapeInvalid, requestId: null, previewDigest: null, limits: null };
}

/**
 * 导出状态：审核预览画质与交付成片画质**始终分开陈述**，
 * 任何情况下都不会把代理/审核预览写成已完成成片（`product_acceptance: 'LOCAL_REQUIRED'`）。
 */
export function exportStatus(receipt: unknown): NleExportStatus {
  if (receipt === null || receipt === undefined) {
    return { stage: 'NONE', requestedQuality: null, previewQuality: null, finalExportQuality: null, deliveryReady: false,
      head: '尚未核对导出配置', detail: '导出预览只核对配置、保存版本与素材摘要；尚未排队、渲染或产生媒体。',
      warnings: [], code: null, requestId: null, previewDigest: null, limits: null };
  }
  const row = closedObject(receipt, RECEIPT_KEYS);
  if (!row) return invalidExport('导出回执包含原导出契约不认识的字段。');
  if (row.contract !== undefined && row.contract !== 'studio-timeline-export-preview/1') return invalidExport('导出预览契约标识无效。');
  if (row.model_called !== undefined && row.model_called !== false) return invalidExport('导出预览不得调用模型。');
  if (row.automatic_replay !== undefined && row.automatic_replay !== false) return invalidExport('导出不得自动重放。');
  if (row.product_acceptance !== undefined && row.product_acceptance !== 'LOCAL_REQUIRED') return invalidExport('导出产物必须标记为需要本机验收。');
  if (row.state !== undefined && row.state !== 'UNKNOWN' && row.state !== 'RETURNED') return invalidExport('导出请求状态无效。');
  if (row.preview_digest !== undefined && (typeof row.preview_digest !== 'string' || !DIGEST.test(row.preview_digest))) {
    return { ...invalidExport('导出预览摘要无效。'), code: NLE_CODES.exportPreviewDigestInvalid };
  }
  let preset: string;
  try {
    preset = checkedTimelineExportProfile(row.export_profile).preset;
  } catch {
    return { ...invalidExport('导出配置无效，请重新选择预设。'), code: NLE_CODES.exportPresetInvalid };
  }
  let limits: NleExportStatus['limits'] = null;
  if (row.limits !== undefined) {
    const raw = closedObject(row.limits, ['max_output_bytes', 'render_timeout_seconds']);
    if (!raw || !isInteger(raw.max_output_bytes) || raw.max_output_bytes < 1
      || raw.max_output_bytes > NLE_OWNER_LIMITS.singleAssetBytes
      || raw.render_timeout_seconds !== NLE_OWNER_LIMITS.renderTimeoutSeconds) {
      return invalidExport(`导出上限需要 1 至 ${NLE_OWNER_LIMITS.singleAssetBytes} 字节且渲染超时为 ${NLE_OWNER_LIMITS.renderTimeoutSeconds} 秒。`);
    }
    limits = { renderTimeoutSeconds: raw.render_timeout_seconds, maxOutputBytes: raw.max_output_bytes };
  }
  const preview = preset === 'REVIEW_MP4';
  const quality = preview ? 'PREVIEW' : 'FINAL';
  const presetFact = preview
    ? { quality: 'PREVIEW' as const, preset, label: '审核预览画质（mpeg4 / aac，原审核策略）', detail: `审核 MP4 是代理/审核画质，${NLE_OWNER_LIMITS.renderTimeoutSeconds} 秒渲染超时，不是交付成片。` }
    : { quality: 'FINAL' as const, preset, label: preset === 'AUDIO_WAV_PCM16' ? 'PCM16 WAV · 48 kHz · 立体声交付配置' : `${preset === 'DELIVERY_H264_MP4' ? 'H.264 MP4' : 'VP9 WebM'} 交付画质`, detail: '交付预设是编码目标；产物仍是私有候选，需要人工审核后才能成为正式素材。' };
  const stage: NleExportStage = row.state === 'UNKNOWN' ? 'DISPATCHED_UNKNOWN' : row.state === 'RETURNED' ? 'RECEIPT_RETURNED' : 'PREVIEW_CHECKED';
  const warnings = [
    ...(preview ? ['审核 MP4 只是预览画质；交付画质需要另行选择交付预设。'] : []),
    '本地 Windows、真实媒体与重型渲染验收仍待执行（product_acceptance: LOCAL_REQUIRED）。',
  ];
  const head = stage === 'PREVIEW_CHECKED' ? `已核对导出配置（${preset}，尚未渲染）`
    : stage === 'DISPATCHED_UNKNOWN' ? `导出请求结果不明（${preset}）`
      : `已取得导出回执（${preset}）`;
  const detail = stage === 'PREVIEW_CHECKED'
    ? '只核对了配置、保存版本与素材摘要；没有排队、渲染或产生媒体。'
    : stage === 'DISPATCHED_UNKNOWN'
      ? '保留原请求标识，不会创建替代请求；未核对的结果不会被当作成片。'
      : '产物仍是私有候选，需在制作任务中预览并人工审核；本界面不声明已交付。';
  return {
    stage, requestedQuality: quality,
    previewQuality: preview ? presetFact : null,
    finalExportQuality: preview ? null : presetFact,
    deliveryReady: false, head, detail, warnings, code: null,
    requestId: typeof row.request_id === 'string' ? row.request_id : null,
    previewDigest: typeof row.preview_digest === 'string' ? row.preview_digest : null,
    limits,
  };
}

/* -------------------------------------------------------------- 上限提示 */

const OFFERED_LIMIT_KEYS = ['duration_ms', 'tracks', 'tracks_per_kind', 'clips', 'captions', 'caption_characters',
  'single_asset_bytes', 'max_output_bytes', 'total_source_bytes', 'render_timeout_seconds', 'subtitle_sidecar_bytes',
  'edit_operations_per_batch', 'edit_batch_bytes', 'gain_min_db', 'gain_max_db'] as const;
const USAGE_KEYS = ['tracks', 'clips', 'durationMs', 'captions', 'captionCharacters', 'largestAssetBytes', 'totalAssetBytes'] as const;

type RowSpec = { key: string; label: string; ownerLimit: number; unit: string; source: string; used: number | null };

/** 在用户触界**之前**说明既有上限，并建议拆分；绝不提高任何上限。 */
export function limitsNotice(limits: unknown = null, usage: unknown = null, mediaKind: 'VIDEO' | 'AUDIO' = 'VIDEO'): NleLimitsNotice {
  const offered = limits === null || limits === undefined ? {} : closedObject(limits, OFFERED_LIMIT_KEYS);
  const used = usage === null || usage === undefined ? {} : closedObject(usage, USAGE_KEYS);
  if (offered === null || used === null) {
    return { rows: [], warnings: [], splitAdvice: NLE_SPLIT_ADVICE, nearAny: false, reachedAny: false,
      raiseRefused: false, refusedRaises: [], code: NLE_CODES.limitsShapeInvalid };
  }
  const ownerOf: Record<string, number> = {
    duration_ms: NLE_OWNER_LIMITS.durationMs, tracks: mediaKind === 'AUDIO' ? NLE_OWNER_LIMITS.tracksPerKind : NLE_OWNER_LIMITS.tracks, tracks_per_kind: NLE_OWNER_LIMITS.tracksPerKind,
    clips: NLE_OWNER_LIMITS.clips, captions: NLE_OWNER_LIMITS.captions, caption_characters: NLE_OWNER_LIMITS.captionCharacters,
    single_asset_bytes: NLE_OWNER_LIMITS.singleAssetBytes, max_output_bytes: NLE_OWNER_LIMITS.singleAssetBytes,
    total_source_bytes: NLE_OWNER_LIMITS.totalSourceBytes, render_timeout_seconds: NLE_OWNER_LIMITS.renderTimeoutSeconds,
    subtitle_sidecar_bytes: NLE_OWNER_LIMITS.subtitleSidecarBytes,
    edit_operations_per_batch: NLE_OWNER_LIMITS.editOperationsPerBatch, edit_batch_bytes: NLE_OWNER_LIMITS.editBatchBytes,
    gain_min_db: NLE_OWNER_LIMITS.gainMinDb, gain_max_db: NLE_OWNER_LIMITS.gainMaxDb,
  };
  const refusedRaises: Array<{ key: string; offered: number; ownerLimit: number }> = [];
  for (const [key, value] of Object.entries(offered)) {
    if (!isInteger(value)) continue;
    const ownerLimit = ownerOf[key];
    if (ownerLimit !== undefined && value > ownerLimit) refusedRaises.push({ key, offered: value, ownerLimit });
  }
  const usageValue = (key: string): number | null => {
    const value = used[key];
    return isInteger(value) && value >= 0 ? value : null;
  };
  const specs: RowSpec[] = [
    { key: 'tracks', label: '轨道总数', ownerLimit: mediaKind === 'AUDIO' ? NLE_OWNER_LIMITS.tracksPerKind : NLE_OWNER_LIMITS.tracks, unit: '条', source: NLE_LIMIT_SOURCES.timeline, used: usageValue('tracks') },
    { key: 'tracks_per_kind', label: '每类轨道', ownerLimit: NLE_OWNER_LIMITS.tracksPerKind, unit: '条', source: NLE_LIMIT_SOURCES.timeline, used: null },
    { key: 'clips', label: '片段总数', ownerLimit: NLE_OWNER_LIMITS.clips, unit: '个', source: NLE_LIMIT_SOURCES.timeline, used: usageValue('clips') },
    { key: 'duration_ms', label: '时间线总长', ownerLimit: NLE_OWNER_LIMITS.durationMs, unit: '毫秒', source: NLE_LIMIT_SOURCES.timeline, used: usageValue('durationMs') },
    { key: 'captions', label: '字幕条数', ownerLimit: NLE_OWNER_LIMITS.captions, unit: '条', source: NLE_LIMIT_SOURCES.subtitles, used: usageValue('captions') },
    { key: 'caption_characters', label: '字幕总文字', ownerLimit: NLE_OWNER_LIMITS.captionCharacters, unit: '字', source: NLE_LIMIT_SOURCES.subtitles, used: usageValue('captionCharacters') },
    { key: 'single_asset_bytes', label: '单个素材字节', ownerLimit: NLE_OWNER_LIMITS.singleAssetBytes, unit: '字节', source: NLE_LIMIT_SOURCES.render, used: usageValue('largestAssetBytes') },
    { key: 'total_source_bytes', label: '素材字节总和', ownerLimit: NLE_OWNER_LIMITS.totalSourceBytes, unit: '字节', source: NLE_LIMIT_SOURCES.render, used: usageValue('totalAssetBytes') },
    { key: 'render_timeout_seconds', label: '单次渲染超时', ownerLimit: NLE_OWNER_LIMITS.renderTimeoutSeconds, unit: '秒', source: NLE_LIMIT_SOURCES.render, used: null },
    { key: 'subtitle_sidecar_bytes', label: '字幕文件字节', ownerLimit: NLE_OWNER_LIMITS.subtitleSidecarBytes, unit: '字节', source: NLE_LIMIT_SOURCES.subtitles, used: null },
    { key: 'edit_operations_per_batch', label: '单批编辑操作', ownerLimit: NLE_OWNER_LIMITS.editOperationsPerBatch, unit: '个', source: NLE_LIMIT_SOURCES.edit, used: null },
    { key: 'edit_batch_bytes', label: '单批编辑字节', ownerLimit: NLE_OWNER_LIMITS.editBatchBytes, unit: '字节', source: NLE_LIMIT_SOURCES.edit, used: null },
  ];
  const rows: NleLimitRow[] = specs.filter(spec => mediaKind !== 'AUDIO' || !['captions', 'caption_characters', 'subtitle_sidecar_bytes'].includes(spec.key)).map(spec => {
    const usedValue = spec.used;
    const remaining = usedValue === null ? null : Math.max(0, spec.ownerLimit - usedValue);
    const ratio = usedValue === null ? null : usedValue / spec.ownerLimit;
    const reached = usedValue !== null && usedValue >= spec.ownerLimit;
    const near = usedValue !== null && !reached && usedValue * NLE_NEAR_DENOMINATOR >= spec.ownerLimit * NLE_NEAR_NUMERATOR;
    return { key: spec.key, label: spec.label, ownerLimit: spec.ownerLimit, used: usedValue, remaining,
      ratio, near, reached, unit: spec.unit, source: spec.source };
  });
  const warnings: string[] = [];
  for (const row of rows) {
    if (row.reached) warnings.push(`${row.label}已达上限（${row.used} / ${row.ownerLimit} ${row.unit}）；原服务会拒绝继续添加。`);
    else if (row.near) warnings.push(`${row.label}已用 ${row.used} / ${row.ownerLimit} ${row.unit}，接近上限；建议先拆分内容。`);
  }
  return {
    rows, warnings, splitAdvice: NLE_SPLIT_ADVICE,
    nearAny: rows.some(row => row.near || row.reached), reachedAny: rows.some(row => row.reached),
    raiseRefused: refusedRaises.length > 0, refusedRaises,
    code: refusedRaises.length ? NLE_CODES.limitsRaiseRefused : null,
  };
}

/** 时间线当前用量（用于上限提示）。 */
export function timelineUsage(timeline: StudioTimeline, assetBytes: { largestAssetBytes?: number; totalAssetBytes?: number } = {}): NleUsage {
  const clips = timeline.tracks.reduce((total, track) => total + track.clips.length, 0);
  return {
    tracks: timeline.tracks.length, clips, durationMs: timeline.duration_ms,
    captions: (timeline.captions?.length ?? 0),
    captionCharacters: (timeline.captions?.reduce((total, cue) => total + cue.text.length, 0) ?? 0),
    ...assetBytes,
  };
}
