import { ApiError } from '../api';
import type { StudioAsset } from './studioClient';

export type StudioTimelineSource = { id: string; kind: 'ASSET'; asset_kind: 'video' | 'audio'; version: number; digest: string };
export type StudioTimelineClip = { id: string; source_snapshot: StudioTimelineSource; start_ms: number; in_ms: number; out_ms: number;
  x?: number; y?: number; width?: number; height?: number };
export type StudioTimelineTrack = { id: string; kind: 'VIDEO' | 'AUDIO'; order: number; muted: boolean; gain_db: number; clips: StudioTimelineClip[] };
export type StudioTimelineCaption = { start_ms: number; end_ms: number; text: string };
export type StudioTimeline = { duration_ms: number; width: number; height: number; fps: number; tracks: StudioTimelineTrack[]; captions: StudioTimelineCaption[] };
export type StudioTimelineDraft = { title: string; timeline: StudioTimeline };
export type StudioTimelineRow = StudioTimelineDraft & { id: string; version: number; timeline_digest: string; created_at: string; updated_at: string };
export const TIMELINE_LIMITS = { duration: 600000, tracks: 8, kindTracks: 4, clips: 30, captions: 500, captionCharacters: 32000 } as const;
const identity = /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/, digest = /^[a-f0-9]{64}$/;

export const cloneTimeline = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
export const timelineInputKey = (value: StudioTimelineDraft) => JSON.stringify(value);
export const timelineBinding = (value: StudioTimelineRow) => `${value.id}:${value.version}:${value.timeline_digest}`;
export const newTimelineDraft = (): StudioTimelineDraft => ({ title: '未命名时间线', timeline: { duration_ms: 5000, width: 1280, height: 720, fps: 24, tracks: [], captions: [] } });

function object(value: unknown, allowed?: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value) || allowed && Object.keys(value).some(key => !allowed.includes(key))) throw new Error('时间线字段不符合原渲染接口。');
  return value as Record<string, unknown>;
}
function integer(value: unknown, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) throw new Error(`时间参数或尺寸需要是 ${min} 至 ${max} 的整数。`);
  return value;
}
function id(value: unknown): string {
  if (typeof value !== 'string' || !identity.test(value)) throw new Error('轨道、片段或素材标识无效。');
  return value;
}
function flag(value: unknown): boolean { if (typeof value !== 'boolean') throw new Error('轨道隐藏或静音状态无效。'); return value; }
function compareText(left: string, right: string): number {
  const a = Array.from(left), b = Array.from(right);
  for (let index = 0; index < Math.min(a.length, b.length); index++) {
    const delta = a[index].codePointAt(0)! - b[index].codePointAt(0)!; if (delta) return delta;
  }
  return a.length - b.length;
}

/** Pure closed DTO validation for the form; the original server remains authoritative. */
export function checkedTimeline(value: unknown): StudioTimeline {
  const row = object(value, ['duration_ms', 'width', 'height', 'fps', 'tracks', 'captions']);
  const duration = integer(row.duration_ms, 1, TIMELINE_LIMITS.duration), width = integer(row.width, 16, 1920), height = integer(row.height, 16, 1080), fps = integer(row.fps, 1, 60);
  if (width % 2 || height % 2) throw new Error('画面宽高需要为偶数。');
  if (!Array.isArray(row.tracks) || !row.tracks.length || row.tracks.length > TIMELINE_LIMITS.tracks) throw new Error('请至少添加一条视频轨道，最多八条轨道。');
  const trackIds = new Set<string>(), orders = new Set<number>(), clipIds = new Set<string>(), sources = new Map<string, string>();
  let videos = 0, audios = 0, clipsCount = 0;
  const tracks = row.tracks.map(raw => {
    const track = object(raw, ['id', 'kind', 'order', 'muted', 'gain_db', 'clips']), tid = id(track.id), order = integer(track.order, 0, 7);
    if (track.kind !== 'VIDEO' && track.kind !== 'AUDIO' || trackIds.has(tid) || orders.has(order)) throw new Error('轨道类型、标识或叠放顺序无效。');
    const kind = track.kind;
    trackIds.add(tid); orders.add(order); kind === 'VIDEO' ? videos++ : audios++;
    if (videos > 4 || audios > 4) throw new Error('视频和音频各最多四条轨道。');
    const muted = flag(track.muted), gain = track.gain_db;
    if (typeof gain !== 'number' || !Number.isFinite(gain) || gain < -60 || gain > 12 || kind === 'VIDEO' && gain !== 0) throw new Error('音量范围为 −60 至 12 dB，仅音频轨道可调整。');
    if (!Array.isArray(track.clips) || !track.clips.length || track.clips.length > TIMELINE_LIMITS.clips) throw new Error('每条轨道需要至少一个片段。');
    const clips = track.clips.map(rawClip => {
      const clip = object(rawClip, ['id', 'source_snapshot', 'start_ms', 'in_ms', 'out_ms', 'x', 'y', 'width', 'height']);
      const cid = id(clip.id), source = object(clip.source_snapshot, ['id', 'kind', 'asset_kind', 'version', 'digest']);
      if (clipIds.has(cid) || ++clipsCount > TIMELINE_LIMITS.clips) throw new Error('片段标识重复或超过三十个片段。');
      clipIds.add(cid);
      const assetKind = kind === 'VIDEO' ? 'video' : 'audio';
      if (source.kind !== 'ASSET' || source.asset_kind !== assetKind || typeof source.digest !== 'string' || !digest.test(source.digest)) throw new Error('素材类型或摘要无效。');
      const snapshot: StudioTimelineSource = { id: id(source.id), kind: 'ASSET', asset_kind: assetKind, version: integer(source.version, 1, Number.MAX_SAFE_INTEGER), digest: source.digest };
      const previous = sources.get(snapshot.id), key = JSON.stringify(snapshot);
      if (previous && previous !== key) throw new Error('同一素材不能绑定两个不同的版本。');
      sources.set(snapshot.id, key);
      const start = integer(clip.start_ms, 0, duration - 1), trimIn = integer(clip.in_ms, 0, 36000000), trimOut = integer(clip.out_ms, 1, 36000000);
      if (trimOut <= trimIn || start + trimOut - trimIn > duration) throw new Error('片段出点须晚于入点，摆放后的结束不能超过时间线。');
      const output: StudioTimelineClip = { id: cid, source_snapshot: snapshot, start_ms: start, in_ms: trimIn, out_ms: trimOut };
      if (kind === 'VIDEO') {
        const x = integer(clip.x, 0, width - 16), y = integer(clip.y, 0, height - 16), cw = integer(clip.width, 16, width - x), ch = integer(clip.height, 16, height - y);
        if (cw % 2 || ch % 2) throw new Error('视频片段尺寸需要为偶数，并位于画面之内。');
        Object.assign(output, { x, y, width: cw, height: ch });
      } else if (['x', 'y', 'width', 'height'].some(key => key in clip)) throw new Error('音频片段没有画面位置或尺寸。');
      return output;
    }).sort((left, right) => left.start_ms - right.start_ms || compareText(left.id, right.id));
    if (kind === 'VIDEO' && clips.some((clip, index) => index > 0 && clips[index - 1].start_ms + clips[index - 1].out_ms - clips[index - 1].in_ms > clip.start_ms)) throw new Error('同一视频轨道的片段不能重叠；跨轨道可以叠放。');
    return { id: tid, kind, order, muted, gain_db: gain, clips } as StudioTimelineTrack;
  }).sort((left, right) => left.order - right.order);
  if (!videos) throw new Error('时间线至少需要一条视频轨道。');
  if (!Array.isArray(row.captions) || row.captions.length > TIMELINE_LIMITS.captions) throw new Error('字幕最多五百条。');
  let characters = 0;
  const captions = row.captions.map(raw => {
    const cue = object(raw, ['start_ms', 'end_ms', 'text']), start = integer(cue.start_ms, 0, duration - 1), end = integer(cue.end_ms, 1, duration);
    if (typeof cue.text !== 'string') throw new Error('请填写字幕文字。');
    const text = cue.text.replace(/\r\n/g, '\n');
    if (end <= start || !text.trim() || text.length > 1000 || text.split('\n').length > 8 || text.split('\n').some(line => !line.trim()) || /[{}<>\\\x00-\x09\x0b-\x1f\x7f]/.test(text) || Array.from(text).some(character => character.codePointAt(0)! >= 0xd800 && character.codePointAt(0)! <= 0xdfff) || text.includes('-->')) throw new Error('字幕为一至八行纯文字，不接受样式标记、空行或控制字符。');
    characters += text.length;
    if (characters > TIMELINE_LIMITS.captionCharacters) throw new Error('字幕总文字超过三万二千字。');
    return { start_ms: start, end_ms: end, text };
  }).sort((left, right) => left.start_ms - right.start_ms || left.end_ms - right.end_ms || compareText(left.text, right.text));
  return { duration_ms: duration, width, height, fps, tracks, captions };
}

export function checkedTimelineDraft(value: StudioTimelineDraft): StudioTimelineDraft {
  if (typeof value.title !== 'string' || !value.title.trim() || value.title.length > 240) throw new Error('请填写不超过二百四十字的时间线名称。');
  return { title: value.title, timeline: checkedTimeline(value.timeline) };
}
export function checkedTimelineRow(value: unknown, expectedId?: string): StudioTimelineRow {
  try {
    const row = object(value), rowId = id(row.id);
    if (expectedId && rowId !== expectedId || typeof row.timeline_digest !== 'string' || !digest.test(row.timeline_digest) || typeof row.created_at !== 'string' || typeof row.updated_at !== 'string') throw new Error();
    const version = integer(row.version, 1, Number.MAX_SAFE_INTEGER);
    const input = checkedTimelineDraft({ title: row.title as string, timeline: row.timeline as StudioTimeline });
    return { id: rowId, version, timeline_digest: row.timeline_digest, created_at: row.created_at, updated_at: row.updated_at, ...input };
  } catch {
    throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '时间线回执字段无效，请读取服务端核对。' });
  }
}
export function checkedTimelineList(value: unknown): StudioTimelineRow[] {
  const data = object(value);
  if (!Array.isArray(data.items) || data.items.length > 25) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '时间线列表无效。' });
  const rows = data.items.map(row => checkedTimelineRow(row));
  if (new Set(rows.map(row => row.id)).size !== rows.length) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '时间线列表标识重复。' });
  return rows;
}
export function timelineSourceState(source: StudioTimelineSource, assets: StudioAsset[]): 'CURRENT' | 'STALE' | 'UNAVAILABLE' {
  const asset = assets.find(row => row.id === source.id && !row.deleted_at);
  if (!asset) return 'UNAVAILABLE';
  return asset.kind === source.asset_kind && asset.version === source.version && asset.sha256 === source.digest ? 'CURRENT' : 'STALE';
}
export function timelineSourcesCurrent(timeline: StudioTimeline, assets: StudioAsset[]): boolean {
  return timeline.tracks.every(track => track.clips.every(clip => timelineSourceState(clip.source_snapshot, assets) === 'CURRENT'));
}
export function timelineSources(timeline: StudioTimeline): StudioTimelineSource[] {
  const sources = new Map<string, StudioTimelineSource>();
  timeline.tracks.forEach(track => track.clips.forEach(clip => sources.set(clip.source_snapshot.id, cloneTimeline(clip.source_snapshot))));
  return [...sources.keys()].sort().map(key => sources.get(key)!);
}
export function timelineFailure(reason: unknown): 'CONFLICT' | 'UNKNOWN' | undefined {
  if (reason instanceof ApiError) {
    if (reason.status === 409) return 'CONFLICT';
    if (reason.status >= 400 && reason.status < 500 && ![408, 425, 429].includes(reason.status)) return undefined;
  }
  return 'UNKNOWN';
}
