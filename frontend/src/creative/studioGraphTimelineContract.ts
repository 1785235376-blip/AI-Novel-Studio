import type { StudioTimelineCaption, StudioTimelineClip, StudioTimelineSource, StudioTimelineTrack } from './studioTimelineTypes';
import { checkedTimelineExportProfile, type TimelineExportProfile } from './studioTimelineExportTypes';

export type GraphTimelineSnapshot = { id: string; version: number; digest: string };
export type GraphTimelinePort = `source_${1 | 2 | 3 | 4 | 5 | 6 | 7 | 8}`;
export type GraphTimelineBinding = { port: GraphTimelinePort; clip_id: string };
export type TimelineClipChanges = Partial<Omit<StudioTimelineClip, 'id' | 'crop' | 'transition_out'>> & {
  crop?: StudioTimelineClip['crop'] | null; transition_out?: StudioTimelineClip['transition_out'] | null };
export type GraphTimelineEdit =
  | { op: 'canvas.update'; changes: Partial<{ schema_version: 2; duration_ms: number; width: number; height: number; fps: number }> }
  | { op: 'track.insert'; track: StudioTimelineTrack }
  | { op: 'track.remove'; track_id: string; remove_clips: boolean }
  | { op: 'track.update'; track_id: string; changes: Partial<Pick<StudioTimelineTrack, 'muted' | 'gain_db' | 'role' | 'locked'>> }
  | { op: 'track.reorder'; track_ids: string[] }
  | { op: 'clip.insert'; track_id: string; clip: StudioTimelineClip }
  | { op: 'clip.update'; clip_id: string; changes: TimelineClipChanges }
  | { op: 'clip.remove'; clip_id: string; ripple: boolean }
  | { op: 'clip.move'; clip_id: string; track_id: string; start_ms: number }
  | { op: 'clip.duplicate'; clip_id: string; new_clip_id: string; track_id: string; start_ms: number }
  | { op: 'clip.split'; clip_id: string; at_ms: number; new_clip_id: string }
  | { op: 'clip.trim'; clip_id: string; in_ms: number; out_ms: number; ripple: boolean }
  | { op: 'clip.slip'; clip_id: string; offset_ms: number }
  | { op: 'caption.insert'; caption: StudioTimelineCaption }
  | { op: 'caption.update'; index: number; caption: StudioTimelineCaption }
  | { op: 'caption.remove'; index: number };
export type GraphTimelineParameters = { timeline_snapshot: GraphTimelineSnapshot; edit_operations: GraphTimelineEdit[];
  source_bindings: GraphTimelineBinding[]; export_profile: TimelineExportProfile };
export type GraphTimelineCommand = Omit<GraphTimelineParameters, 'source_bindings'> & { operation_id: 'm9.timeline.multitrack'; request_id: string;
  source_bindings: (GraphTimelineBinding & { asset: { asset_id: string; version: number; digest: string; kind: 'image' | 'video' | 'audio' } })[] };
export const graphTimelinePorts: GraphTimelinePort[] = ['source_1', 'source_2', 'source_3', 'source_4', 'source_5', 'source_6', 'source_7', 'source_8'];

function invalid(): never { throw new Error('时间线节点的绑定或剪辑操作无效，请核对封闭字段、版本与摘要。'); }
const row = (value: unknown): Record<string, unknown> => { if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(); return value as Record<string, unknown>; };
const fields = (value: unknown, required: readonly string[], optional: readonly string[] = []) => {
  const result = row(value); if (required.some(key => !Object.hasOwn(result, key)) || Object.keys(result).some(key => ![...required, ...optional].includes(key))) invalid(); return result;
};
const integer = (value: unknown, min = -Number.MAX_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER): number => {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) invalid(); return value;
};
const number = (value: unknown, min: number, max: number): number => { if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) invalid(); return value; };
const bool = (value: unknown): boolean => { if (typeof value !== 'boolean') invalid(); return value; };
export const graphTimelineId = (value: unknown): string => { if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value)) invalid(); return value; };
const digest = (value: unknown): string => { if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) invalid(); return value; };
export function checkedGraphTimelineSnapshot(value: unknown): GraphTimelineSnapshot {
  const result = fields(value, ['id', 'version', 'digest']); return { id: graphTimelineId(result.id), version: integer(result.version, 1), digest: digest(result.digest) };
}
function source(value: unknown): StudioTimelineSource {
  const result = fields(value, ['id', 'version', 'digest', 'kind', 'asset_kind']);
  if (result.kind !== 'ASSET' || !['image', 'video', 'audio'].includes(result.asset_kind as string)) invalid();
  return { id: graphTimelineId(result.id), version: integer(result.version, 1), digest: digest(result.digest), kind: 'ASSET', asset_kind: result.asset_kind as StudioTimelineSource['asset_kind'] };
}
const clipFields = ['source_snapshot', 'start_ms', 'in_ms', 'out_ms', 'x', 'y', 'width', 'height', 'speed_num', 'speed_den', 'opacity', 'gain_db', 'muted', 'include_audio', 'fade_in_ms', 'fade_out_ms', 'crop', 'transition_out'];
function clipChanges(value: unknown): TimelineClipChanges {
  const raw = fields(value, [], clipFields); if (!Object.keys(raw).length) invalid();
  for (const [key, value] of Object.entries(raw)) {
    if (key === 'source_snapshot') source(value);
    else if (key === 'crop') {
      if (value !== null) { const crop = fields(value, ['x', 'y', 'width', 'height']); integer(crop.x, 0, 32767); integer(crop.y, 0, 32767); integer(crop.width, 1, 32768); integer(crop.height, 1, 32768); }
    }
    else if (key === 'transition_out') {
      if (value !== null) {
        const transition = fields(value, ['kind', 'to_clip_id', 'duration_ms']);
        if (transition.kind !== 'CROSS_DISSOLVE') invalid(); graphTimelineId(transition.to_clip_id); integer(transition.duration_ms, 1, 10000);
      }
    }
    else if (['muted', 'include_audio'].includes(key)) bool(value);
    else if (key === 'opacity') number(value, 0, 1);
    else if (key === 'gain_db') number(value, -60, 12);
    else integer(value);
  }
  return structuredClone(raw) as TimelineClipChanges;
}
function clip(value: unknown): StudioTimelineClip {
  const raw = fields(value, ['id', 'source_snapshot', 'start_ms', 'in_ms', 'out_ms'], clipFields);
  if (raw.crop === null || raw.transition_out === null) invalid();
  graphTimelineId(raw.id); const { id: _id, ...changes } = raw; clipChanges(changes);
  return structuredClone(raw) as StudioTimelineClip;
}
function trackChanges(value: unknown): Partial<Pick<StudioTimelineTrack, 'muted' | 'gain_db' | 'role' | 'locked'>> {
  const raw = fields(value, [], ['muted', 'gain_db', 'role', 'locked']); if (!Object.keys(raw).length) invalid();
  if ('muted' in raw) bool(raw.muted); if ('gain_db' in raw) number(raw.gain_db, -60, 12);
  if ('locked' in raw) bool(raw.locked);
  if ('role' in raw && !['PRIMARY', 'OVERLAY', 'DIALOGUE', 'MUSIC', 'EFFECTS'].includes(raw.role as string)) invalid();
  return structuredClone(raw) as Partial<Pick<StudioTimelineTrack, 'muted' | 'gain_db' | 'role' | 'locked'>>;
}
function caption(value: unknown): StudioTimelineCaption {
  const raw = fields(value, ['start_ms', 'end_ms', 'text']); integer(raw.start_ms, 0, 600000); integer(raw.end_ms, 1, 600000);
  if (typeof raw.text !== 'string' || !raw.text.trim() || raw.text.length > 32000 || (raw.end_ms as number) <= (raw.start_ms as number)) invalid();
  return raw as StudioTimelineCaption;
}
/** Field admission only; the original backend validates the entire resulting timeline atomically. */
export function checkedGraphTimelineEdits(value: unknown): GraphTimelineEdit[] {
  if (!Array.isArray(value) || value.length > 40 || new TextEncoder().encode(JSON.stringify(value)).length > 128000) invalid();
  return value.map(item => {
    const raw = row(item), op = raw.op;
    const check = (required: string[]) => fields(raw, ['op', ...required]);
    if (op === 'canvas.update') {
      check(['changes']); const changes = fields(raw.changes, [], ['duration_ms', 'width', 'height', 'fps', 'schema_version']);
      if (!Object.keys(changes).length) invalid(); Object.entries(changes).forEach(([key, value]) => { if (key === 'schema_version' ? value !== 2 : !Number.isSafeInteger(value)) invalid(); });
    } else if (op === 'track.insert') {
      check(['track']); const track = fields(raw.track, ['id', 'kind', 'order', 'clips'], ['muted', 'gain_db', 'role', 'locked']);
      graphTimelineId(track.id); integer(track.order, 0, 7); if (!['VIDEO', 'AUDIO'].includes(track.kind as string) || !Array.isArray(track.clips) || track.clips.length) invalid();
      const extra = Object.fromEntries(Object.entries(track).filter(([key]) => ['muted', 'gain_db', 'role', 'locked'].includes(key))); if (Object.keys(extra).length) trackChanges(extra);
    } else if (op === 'track.remove') { check(['track_id', 'remove_clips']); graphTimelineId(raw.track_id); bool(raw.remove_clips);
    } else if (op === 'track.update') { check(['track_id', 'changes']); graphTimelineId(raw.track_id); trackChanges(raw.changes);
    } else if (op === 'track.reorder') {
      check(['track_ids']); if (!Array.isArray(raw.track_ids) || raw.track_ids.length > 8 || !raw.track_ids.length) invalid();
      raw.track_ids.forEach(graphTimelineId); if (new Set(raw.track_ids).size !== raw.track_ids.length) invalid();
    } else if (op === 'clip.insert') { check(['track_id', 'clip']); graphTimelineId(raw.track_id); clip(raw.clip);
    } else if (op === 'clip.update') { check(['clip_id', 'changes']); graphTimelineId(raw.clip_id); clipChanges(raw.changes);
    } else if (op === 'clip.remove') { check(['clip_id', 'ripple']); graphTimelineId(raw.clip_id); bool(raw.ripple);
    } else if (op === 'clip.move' || op === 'clip.duplicate') {
      check(['clip_id', 'track_id', 'start_ms', ...(op === 'clip.duplicate' ? ['new_clip_id'] : [])]);
      graphTimelineId(raw.clip_id); graphTimelineId(raw.track_id); integer(raw.start_ms); if (op === 'clip.duplicate') graphTimelineId(raw.new_clip_id);
    } else if (op === 'clip.split') { check(['clip_id', 'at_ms', 'new_clip_id']); graphTimelineId(raw.clip_id); graphTimelineId(raw.new_clip_id); integer(raw.at_ms);
    } else if (op === 'clip.trim') { check(['clip_id', 'in_ms', 'out_ms', 'ripple']); graphTimelineId(raw.clip_id); integer(raw.in_ms); integer(raw.out_ms); bool(raw.ripple);
    } else if (op === 'clip.slip') { check(['clip_id', 'offset_ms']); graphTimelineId(raw.clip_id); integer(raw.offset_ms);
    } else if (op === 'caption.insert' || op === 'caption.update' || op === 'caption.remove') {
      check(op === 'caption.insert' ? ['caption'] : op === 'caption.update' ? ['index', 'caption'] : ['index']);
      if (op !== 'caption.insert') integer(raw.index, 0, 499); if (op !== 'caption.remove') caption(raw.caption);
    } else invalid();
    return structuredClone(raw) as GraphTimelineEdit;
  });
}
export function checkedGraphTimelineParameters(value: unknown): GraphTimelineParameters {
  const raw = fields(value, ['timeline_snapshot', 'export_profile'], ['edit_operations', 'source_bindings']);
  const bindings = raw.source_bindings === undefined ? [] : raw.source_bindings;
  if (!Array.isArray(bindings) || bindings.length > 8) invalid();
  const source_bindings = bindings.map(value => { const binding = fields(value, ['port', 'clip_id']);
    if (!graphTimelinePorts.includes(binding.port as GraphTimelinePort)) invalid(); return { port: binding.port as GraphTimelinePort, clip_id: graphTimelineId(binding.clip_id) }; });
  if (new Set(source_bindings.map(row => row.port)).size !== source_bindings.length || new Set(source_bindings.map(row => row.clip_id)).size !== source_bindings.length) invalid();
  const edit_operations = checkedGraphTimelineEdits(raw.edit_operations === undefined ? [] : raw.edit_operations);
  if (edit_operations.length + source_bindings.length > 40) invalid();
  return { timeline_snapshot: checkedGraphTimelineSnapshot(raw.timeline_snapshot), edit_operations,
    source_bindings, export_profile: checkedTimelineExportProfile(raw.export_profile) };
}
