import {checkedSavedCanvasAudioDraft,compileCanvasAudioDraftTimeline,audioDraftIdentity,type SavedCanvasAudioDraft} from './studioCanvasAudioDraft';
import {checkedCanvasVideoTaskCommand,compileCanvasVideoTimeline,type CanvasVideoTaskCommand} from './canvasVideoTrimTask';
import { ApiError } from '../api';
import type { StudioAsset } from './studioClient';
import { checkedClipLinks } from './studioTimelineClipLinks';

export type StudioTimelineSource = { id: string; kind: 'ASSET'; asset_kind: 'image' | 'video' | 'audio'; version: number; digest: string };
export type StudioTimelineColorAdjustment = { brightness: number; contrast: number; saturation: number };
export type StudioTimelineTransition = { kind: 'CROSS_DISSOLVE'; to_clip_id: string; duration_ms: number };
export type StudioTimelineClip = { id: string; source_snapshot: StudioTimelineSource; start_ms: number; in_ms: number; out_ms: number;
  x?: number; y?: number; width?: number; height?: number; speed_num?: number; speed_den?: number; opacity?: number;
  muted?: boolean; gain_db?: number; fade_in_ms?: number; fade_out_ms?: number; include_audio?: boolean;
  crop?: { x: number; y: number; width: number; height: number }; transition_out?: StudioTimelineTransition; color_adjustment?: StudioTimelineColorAdjustment };
export type StudioTimelineTrack = { id: string; kind: 'VIDEO' | 'AUDIO'; order: number; muted: boolean; gain_db: number;
  role?: 'PRIMARY' | 'OVERLAY' | 'DIALOGUE' | 'MUSIC' | 'EFFECTS'; locked?: boolean; clips: StudioTimelineClip[] };
export type StudioTimelineCaption = { start_ms: number; end_ms: number; text: string };
export type StudioTimelineCaptionStyle = { font_size: number; primary_color: string; alignment: 'TOP_CENTER' | 'BOTTOM_CENTER'; outline_width: number };
export type StudioTimelineClipLink = { video_clip_id: string; audio_clip_id: string; offset_ms: number };
export type StudioVideoTimeline = { schema_version?: 2; media_kind?: never; duration_ms: number; width: number; height: number; fps: number; tracks: StudioTimelineTrack[]; captions: StudioTimelineCaption[]; caption_style?: StudioTimelineCaptionStyle; clip_links?: StudioTimelineClipLink[] };
export type StudioAudioTimeline = { schema_version: 3; media_kind: 'AUDIO'; duration_ms: number; tracks: StudioTimelineTrack[]; width?: never; height?: never; fps?: never; captions?: never; caption_style?: never; clip_links?: never };
export type StudioTimeline = StudioVideoTimeline | StudioAudioTimeline;
export const isAudioTimeline = (timeline: StudioTimeline): timeline is StudioAudioTimeline => timeline.schema_version === 3;
export type StudioTimelineDraft = { title: string; timeline: StudioTimeline };
export type TimelineTransferReceipt = { operation: 'TRANSFER_IMPORT'; request_id: string; input_version: number; input_digest: string;
  output_digest: string; preview_digest: string; format: 'OTIO' | 'SRT' | 'VTT'; transfer_input_digest: string; acknowledge_losses: boolean };
export type TimelineEditReceipt = { request_id: string; request_digest: string; input_version: number; input_digest: string; output_digest: string };
export type StudioTimelineRow = StudioTimelineDraft & { id: string; version: number; timeline_digest: string; created_at: string; updated_at: string;
  transfer_receipt?: TimelineTransferReceipt; edit_receipt?: TimelineEditReceipt; canvas_video_draft?:CanvasVideoTaskCommand; canvas_video_draft_digest?:string; canvas_audio_draft?:SavedCanvasAudioDraft; canvas_audio_draft_digest?:string };
export const TIMELINE_LIMITS = { duration: 600000, tracks: 8, kindTracks: 4, clips: 30, captions: 500, captionCharacters: 32000 } as const;
const identity = /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/, digest = /^[a-f0-9]{64}$/;

export const cloneTimeline = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
export const timelineInputKey = (value: StudioTimelineDraft) => JSON.stringify(value);
export const timelineBinding = (value: StudioTimelineRow) => `${value.id}:${value.version}:${value.timeline_digest}`;
export const timelineClipDuration = (clip: StudioTimelineClip) => (clip.out_ms - clip.in_ms) * (clip.speed_den ?? 1) / (clip.speed_num ?? 1);
export const newTimelineDraft = (mediaKind: 'VIDEO' | 'AUDIO' = 'VIDEO'): StudioTimelineDraft => mediaKind === 'AUDIO'
  ? { title: '未命名音频时间线', timeline: { schema_version: 3, media_kind: 'AUDIO', duration_ms: 5000, tracks: [] } }
  : { title: '未命名时间线', timeline: { duration_ms: 5000, width: 1280, height: 720, fps: 24, tracks: [], captions: [] } };

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
function scalar(value: unknown, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) throw new Error(`参数需要在 ${min} 至 ${max} 范围内。`);
  return value;
}
const defaulted = (row: Record<string, unknown>, key: string, fallback: unknown) => key in row ? row[key] : fallback;
function gcd(a: number, b: number): number { while (b) [a, b] = [b, a % b]; return a; }
function compareText(left: string, right: string): number {
  const a = Array.from(left), b = Array.from(right);
  for (let index = 0; index < Math.min(a.length, b.length); index++) {
    const delta = a[index].codePointAt(0)! - b[index].codePointAt(0)!; if (delta) return delta;
  }
  return a.length - b.length;
}

/** Closed global subtitle presentation; no font files, names or ASS overrides. */
export function checkedTimelineCaptionStyle(value: unknown): StudioTimelineCaptionStyle {
  const row = object(value, ['font_size', 'primary_color', 'alignment', 'outline_width']);
  if (typeof row.primary_color !== 'string' || row.primary_color.length !== 7 || !/^#[0-9a-fA-F]{6}$/.test(row.primary_color)) throw new Error('字幕颜色需要是 #RRGGBB 格式的六位十六进制颜色。');
  if (row.alignment !== 'TOP_CENTER' && row.alignment !== 'BOTTOM_CENTER') throw new Error('字幕位置只能是顶部居中或底部居中。');
  return { font_size: integer(row.font_size, 8, 72), primary_color: row.primary_color.toUpperCase(),
    alignment: row.alignment, outline_width: integer(row.outline_width, 0, 4) };
}

/** Pure closed DTO validation for the form; the original server remains authoritative. */
export function checkedTimeline(value: unknown): StudioTimeline {
  const raw = object(value), audioOnly = raw.schema_version === 3;
  const row = object(value, audioOnly ? ['schema_version', 'media_kind', 'duration_ms', 'tracks'] : ['schema_version', 'duration_ms', 'width', 'height', 'fps', 'tracks', 'captions', ...(raw.schema_version === 2 ? ['caption_style', 'clip_links'] : [])]);
  const extended = row.schema_version === 2 || audioOnly;
  if ('schema_version' in row && !extended || audioOnly && row.media_kind !== 'AUDIO') throw new Error('时间线版本或媒体类型无效；音频时间线必须明确使用版本 3 与 AUDIO。');
  const duration = integer(row.duration_ms, 1, TIMELINE_LIMITS.duration);
  // Audio has no canvas or frame rate. These locals are only used in guarded video branches.
  const width = audioOnly ? undefined : integer(row.width, 16, 1920), height = audioOnly ? undefined : integer(row.height, 16, 1080), fps = audioOnly ? undefined : integer(row.fps, 1, 60);
  if (!audioOnly && (width! % 2 || height! % 2)) throw new Error('画面宽高需要为偶数。');
  if (!Array.isArray(row.tracks) || !row.tracks.length || row.tracks.length > (audioOnly ? TIMELINE_LIMITS.kindTracks : TIMELINE_LIMITS.tracks)) throw new Error(audioOnly ? '请至少添加一条音频轨道，最多四条轨道。' : '请至少添加一条视频轨道，最多八条轨道。');
  const trackIds = new Set<string>(), orders = new Set<number>(), clipIds = new Set<string>(), sources = new Map<string, string>();
  let videos = 0, audios = 0, clipsCount = 0;
  const tracks = row.tracks.map(raw => {
    const track = object(raw, ['id', 'kind', 'order', 'muted', 'gain_db', 'clips', ...(extended ? ['role', 'locked'] : [])]), tid = id(track.id), order = integer(track.order, 0, 7);
    if (audioOnly && track.kind !== 'AUDIO' || track.kind !== 'VIDEO' && track.kind !== 'AUDIO' || trackIds.has(tid) || orders.has(order)) throw new Error('轨道类型、标识或叠放顺序无效。');
    const kind = track.kind;
    const role = defaulted(track, 'role', kind === 'VIDEO' ? 'PRIMARY' : 'DIALOGUE');
    if (extended && !(kind === 'VIDEO' ? ['PRIMARY', 'OVERLAY'] : ['DIALOGUE', 'MUSIC', 'EFFECTS']).includes(String(role))) throw new Error('轨道用途与类型不一致。');
    trackIds.add(tid); orders.add(order); kind === 'VIDEO' ? videos++ : audios++;
    if (videos > 4 || audios > 4) throw new Error('视频和音频各最多四条轨道。');
    const muted = flag(track.muted), gain = track.gain_db;
    if (typeof gain !== 'number' || !Number.isFinite(gain) || gain < -60 || gain > 12 || kind === 'VIDEO' && gain !== 0) throw new Error('音量范围为 −60 至 12 dB，仅音频轨道可调整。');
    if (!Array.isArray(track.clips) || !track.clips.length || track.clips.length > TIMELINE_LIMITS.clips) throw new Error('每条轨道需要至少一个片段。');
    const clips = track.clips.map(rawClip => {
      const clip = object(rawClip, ['id', 'source_snapshot', 'start_ms', 'in_ms', 'out_ms', 'x', 'y', 'width', 'height',
        ...(extended ? ['speed_num', 'speed_den', 'opacity', 'muted', 'gain_db', 'fade_in_ms', 'fade_out_ms', 'include_audio', 'crop', 'transition_out', 'color_adjustment'] : [])]);
      const cid = id(clip.id), source = object(clip.source_snapshot, ['id', 'kind', 'asset_kind', 'version', 'digest']);
      if (clipIds.has(cid) || ++clipsCount > TIMELINE_LIMITS.clips) throw new Error('片段标识重复或超过三十个片段。');
      clipIds.add(cid);
      const assetKind = source.asset_kind;
      if (source.kind !== 'ASSET' || !(kind === 'VIDEO' ? extended ? ['image', 'video'] : ['video'] : ['audio']).includes(String(assetKind)) || typeof source.digest !== 'string' || !digest.test(source.digest)) throw new Error('素材类型或摘要无效。');
      const snapshot: StudioTimelineSource = { id: id(source.id), kind: 'ASSET', asset_kind: assetKind as StudioTimelineSource['asset_kind'], version: integer(source.version, 1, Number.MAX_SAFE_INTEGER), digest: source.digest };
      const previous = sources.get(snapshot.id), key = JSON.stringify(snapshot);
      if (previous && previous !== key) throw new Error('同一素材不能绑定两个不同的版本。');
      sources.set(snapshot.id, key);
      const start = integer(clip.start_ms, 0, duration - 1), trimIn = integer(clip.in_ms, 0, 36000000), trimOut = integer(clip.out_ms, 1, 36000000);
      const rawNum = extended ? integer(defaulted(clip, 'speed_num', 1), 1, 4) : 1, rawDen = extended ? integer(defaulted(clip, 'speed_den', 1), 1, 4) : 1;
      const divisor = gcd(rawNum, rawDen), speedNum = rawNum / divisor, speedDen = rawDen / divisor;
      const length = (trimOut - trimIn) * speedDen / speedNum;
      if (trimOut <= trimIn || !Number.isSafeInteger(length) || start + length > duration) throw new Error('片段长度须为正整数毫秒，摆放后的结束不能超过时间线。');
      if (assetKind === 'image' && (trimIn !== 0 || speedNum !== 1 || speedDen !== 1)) throw new Error('静态画面入点为零，速度保持 1/1；出点表示展示时长。');
      const output: StudioTimelineClip = { id: cid, source_snapshot: snapshot, start_ms: start, in_ms: trimIn, out_ms: trimOut };
      if (extended) Object.assign(output, { speed_num: speedNum, speed_den: speedDen, muted: flag(defaulted(clip, 'muted', false)), gain_db: scalar(defaulted(clip, 'gain_db', 0), -60, 12),
        fade_in_ms: integer(defaulted(clip, 'fade_in_ms', 0), 0, length), fade_out_ms: integer(defaulted(clip, 'fade_out_ms', 0), 0, length) });
      if ((output.fade_in_ms ?? 0) + (output.fade_out_ms ?? 0) > length) throw new Error('淡入和淡出总长不能超过片段的渲染时长。');
      if (kind === 'VIDEO') {
        const x = integer(clip.x, 0, width! - 16), y = integer(clip.y, 0, height! - 16), cw = integer(clip.width, 16, width! - x), ch = integer(clip.height, 16, height! - y);
        if (cw % 2 || ch % 2) throw new Error('视频片段尺寸需要为偶数，并位于画面之内。');
        Object.assign(output, { x, y, width: cw, height: ch });
        if (extended) {
          const includeAudio = flag(defaulted(clip, 'include_audio', false));
          if (includeAudio && assetKind !== 'video') throw new Error('静态画面不能包含视频原声。');
          if (!includeAudio && output.gain_db !== 0) throw new Error('视频片段的音量只在明确加入原声时可调整。');
          Object.assign(output, { opacity: scalar(defaulted(clip, 'opacity', 1), 0, 1), include_audio: includeAudio });
          if ('color_adjustment' in clip) {
            const color = object(clip.color_adjustment, ['brightness', 'contrast', 'saturation']);
            output.color_adjustment = { brightness: scalar(color.brightness, -1, 1),
              contrast: scalar(color.contrast, 0, 2), saturation: scalar(color.saturation, 0, 3) };
          }
          if ('crop' in clip) {
            const crop = object(clip.crop, ['x', 'y', 'width', 'height']);
            output.crop = { x: integer(crop.x, 0, 32767), y: integer(crop.y, 0, 32767),
              width: integer(crop.width, 1, 32768), height: integer(crop.height, 1, 32768) };
          }
          if ('transition_out' in clip) {
            const transition = object(clip.transition_out, ['kind', 'to_clip_id', 'duration_ms']);
            if (transition.kind !== 'CROSS_DISSOLVE') throw new Error('当前仅支持明确的交叉溶解转场。');
            output.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: id(transition.to_clip_id),
              duration_ms: integer(transition.duration_ms, Math.ceil(2000 / fps!), 10000) };
          }
        }
      } else if (['x', 'y', 'width', 'height', 'opacity', 'include_audio', 'crop', 'transition_out', 'color_adjustment'].some(key => key in clip)) throw new Error('音频片段没有画面位置、尺寸、透明度、像素裁剪、转场、调色或视频原声设置。');
      return output;
    }).sort((left, right) => left.start_ms - right.start_ms || compareText(left.id, right.id));
    if (kind === 'VIDEO') {
      let incoming = 0;
      clips.forEach((left, index) => {
        const right = clips[index + 1], transition = left.transition_out, length = timelineClipDuration(left);
        const overlap = right ? left.start_ms + length - right.start_ms : 0;
        if (!transition) {
          if (overlap > 0) throw new Error('同轨重叠必须明确指定与紧邻后片段的交叉溶解。');
          incoming = 0; return;
        }
        const window = transition.duration_ms;
        if (!right || transition.to_clip_id !== right.id || overlap !== window || window >= length
          || window >= timelineClipDuration(right) || incoming + window > length) throw new Error('转场须精确覆盖相邻片段的重叠区，且各窗口不能相交或占满片段。');
        if (left.x !== right.x || left.y !== right.y || left.width !== right.width || left.height !== right.height || left.opacity !== right.opacity
          || left.muted || right.muted || left.fade_in_ms || left.fade_out_ms || right.fade_in_ms || right.fade_out_ms) throw new Error('转场片段须使用相同位置、尺寸和透明度，保持可见并清除独立淡入淡出。');
        incoming = window;
      });
    }
    return { id: tid, kind, order, muted, gain_db: gain, clips, ...(extended ? { role } : {}),
      ...('locked' in track ? { locked: flag(track.locked) } : {}) } as StudioTimelineTrack;
  }).sort((left, right) => left.order - right.order);
  if (audioOnly) return { schema_version: 3, media_kind: 'AUDIO', duration_ms: duration, tracks };
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
  return { ...(extended ? { schema_version: 2 as const } : {}), duration_ms: duration, width: width!, height: height!, fps: fps!, tracks, captions,
    ...('caption_style' in row ? { caption_style: checkedTimelineCaptionStyle(row.caption_style) } : {}),
    ...('clip_links' in row ? { clip_links: checkedClipLinks(row.clip_links, tracks) } : {}) };
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
    let receipt: TimelineTransferReceipt | undefined;
    if (row.transfer_receipt !== undefined) {
      const r = object(row.transfer_receipt, ['operation', 'request_id', 'input_version', 'input_digest', 'output_digest', 'preview_digest', 'format', 'transfer_input_digest', 'acknowledge_losses']);
      if (r.operation !== 'TRANSFER_IMPORT' || typeof r.request_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(r.request_id)
        || typeof r.input_digest !== 'string' || !digest.test(r.input_digest) || typeof r.output_digest !== 'string' || !digest.test(r.output_digest)
        || r.output_digest !== row.timeline_digest || typeof r.preview_digest !== 'string' || !digest.test(r.preview_digest)
        || typeof r.transfer_input_digest !== 'string' || !digest.test(r.transfer_input_digest) || !['OTIO', 'SRT', 'VTT'].includes(String(r.format))
        || typeof r.acknowledge_losses !== 'boolean' || integer(r.input_version, 1, Number.MAX_SAFE_INTEGER) + 1 !== version) throw new Error();
      receipt = r as unknown as TimelineTransferReceipt;
    }
    let edit: TimelineEditReceipt | undefined;
    if (row.edit_receipt !== undefined) {
      const r = object(row.edit_receipt, ['request_id', 'request_digest', 'input_version', 'input_digest', 'output_digest']);
      if (Object.keys(r).length !== 5 || typeof r.request_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(r.request_id)
        || ['request_digest', 'input_digest', 'output_digest'].some(key => typeof r[key] !== 'string' || !digest.test(r[key] as string))
        || r.output_digest !== row.timeline_digest || integer(r.input_version, 1, Number.MAX_SAFE_INTEGER) + 1 !== version || receipt) throw new Error();
      edit = r as unknown as TimelineEditReceipt;
    }
    let videoDraft:CanvasVideoTaskCommand|undefined;
    if(Object.hasOwn(row,'canvas_video_draft')||Object.hasOwn(row,'canvas_video_draft_digest')){
      videoDraft=checkedCanvasVideoTaskCommand(row.canvas_video_draft);
      if(!videoDraft.derived_from||typeof row.canvas_video_draft_digest!=='string'||!digest.test(row.canvas_video_draft_digest)
        ||videoDraft.timeline_snapshot.id!==rowId||videoDraft.timeline_snapshot.version>version)throw new Error();
      if(videoDraft.timeline_snapshot.version===version&&(videoDraft.timeline_snapshot.digest!==row.timeline_digest
        ||JSON.stringify(checkedTimeline(compileCanvasVideoTimeline(videoDraft.source_snapshots[0],videoDraft.parameters)))!==JSON.stringify(input.timeline)))throw new Error();
    }
    let audioDraft:SavedCanvasAudioDraft|undefined;
    if(Object.hasOwn(row,'canvas_audio_draft')||Object.hasOwn(row,'canvas_audio_draft_digest')){
      audioDraft=checkedSavedCanvasAudioDraft(row.canvas_audio_draft);
      if(videoDraft||typeof row.canvas_audio_draft_digest!=='string'||!digest.test(row.canvas_audio_draft_digest)
        ||audioDraft.timeline_snapshot.id!==rowId||audioDraft.timeline_snapshot.version>version)throw new Error();
      if(audioDraft.timeline_snapshot.version===version&&(audioDraft.timeline_snapshot.digest!==row.timeline_digest
        ||audioDraftIdentity(checkedTimeline(compileCanvasAudioDraftTimeline(audioDraft)))!==audioDraftIdentity(input.timeline)))throw new Error();
    }
    return { id: rowId, version, timeline_digest: row.timeline_digest, created_at: row.created_at, updated_at: row.updated_at, ...input,
      ...(receipt ? { transfer_receipt: receipt } : {}), ...(edit ? { edit_receipt: edit } : {}),
      ...(videoDraft?{canvas_video_draft:videoDraft,canvas_video_draft_digest:row.canvas_video_draft_digest as string}:{}),
      ...(audioDraft?{canvas_audio_draft:audioDraft,canvas_audio_draft_digest:row.canvas_audio_draft_digest as string}:{}) };
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
