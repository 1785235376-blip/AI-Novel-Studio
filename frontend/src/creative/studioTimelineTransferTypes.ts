import { ApiError } from '../api';
import { checkedTimeline, timelineSources, type StudioTimeline, type StudioTimelineRow, type StudioTimelineSource } from './studioTimelineTypes';

export type TimelineTransferDirection = 'IMPORT' | 'EXPORT';
export type TimelineTransferFormat = 'OTIO' | 'SRT' | 'VTT';
export type TimelineMediaBinding = { reference: string; source_snapshot: StudioTimelineSource };
export type TimelineTransferInput = { expected_version: number; reviewed_timeline_digest: string; direction: TimelineTransferDirection;
  format: TimelineTransferFormat; content: string; media_bindings: TimelineMediaBinding[] };
export type TimelineTransferLoss = { path: string; code: string; severity: 'LOSS' | 'WARNING' };
export type TimelineTransferPreview = { contract: 'studio-timeline-transfer-preview/1'; direction: TimelineTransferDirection; format: TimelineTransferFormat;
  timeline_snapshot: { id: string; version: number; digest: string }; input_digest: string; timeline: StudioTimeline; timeline_digest: string;
  sources: StudioTimelineSource[]; media_bindings: TimelineMediaBinding[]; loss_report: TimelineTransferLoss[]; requires_loss_acknowledgment: boolean;
  output_sha256: string | null; output_bytes: number | null; external_media_access: false; model_called: false; automatic_replay: false;
  product_acceptance: 'LOCAL_REQUIRED'; target_applications: { Resolve: 'NOT_RUN'; Premiere: 'NOT_RUN' }; preview_digest: string };

const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const hex = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '交换预览与原版本、素材或确认内容不一致，请重新读取核对。' }); }
function source(v: unknown): StudioTimelineSource {
  if (!record(v) || Object.keys(v).some(k => !['id', 'kind', 'version', 'digest', 'asset_kind'].includes(k))
    || v.kind !== 'ASSET' || typeof v.id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(v.id)
    || typeof v.version !== 'number' || !Number.isSafeInteger(v.version) || v.version < 1 || !hex(v.digest)
    || !['image', 'video', 'audio'].includes(String(v.asset_kind))) invalid();
  return { id: v.id, kind: 'ASSET', version: v.version, digest: v.digest, asset_kind: v.asset_kind as StudioTimelineSource['asset_kind'] };
}
export function checkedTimelineMediaBindings(value: unknown): TimelineMediaBinding[] {
  if (!Array.isArray(value) || value.length > 30) invalid();
  const references = new Set<string>(), assets = new Map<string, string>();
  return value.map(raw => {
    if (!record(raw) || Object.keys(raw).some(k => !['reference', 'source_snapshot'].includes(k))
      || typeof raw.reference !== 'string' || !raw.reference || raw.reference.length > 4096 || /[\x00-\x1f\x7f]/.test(raw.reference)
      || Array.from(raw.reference).some(c => c.codePointAt(0)! >= 0xd800 && c.codePointAt(0)! <= 0xdfff) || references.has(raw.reference)) invalid();
    references.add(raw.reference);
    const item = source(raw.source_snapshot), key = JSON.stringify(item), prior = assets.get(item.id);
    if (prior && prior !== key) invalid(); assets.set(item.id, key);
    return { reference: raw.reference, source_snapshot: item };
  });
}
export function checkedTimelineTransferInput(value: TimelineTransferInput): TimelineTransferInput {
  if (!Number.isSafeInteger(value.expected_version) || value.expected_version < 1 || !hex(value.reviewed_timeline_digest)
    || !['IMPORT', 'EXPORT'].includes(value.direction) || !['OTIO', 'SRT', 'VTT'].includes(value.format)
    || typeof value.content !== 'string' || Array.from(value.content).some(c => c.codePointAt(0)! >= 0xd800 && c.codePointAt(0)! <= 0xdfff)
    || new TextEncoder().encode(value.content).byteLength > (value.format === 'OTIO' ? 2 * 1024 * 1024 : 192000)) throw new Error('交换格式、内容或来源绑定超出允许范围。');
  const bindings = checkedTimelineMediaBindings(value.media_bindings);
  if (value.direction === 'EXPORT' && (value.content || bindings.length) || value.direction === 'IMPORT' && !value.content.trim()
    || value.format !== 'OTIO' && bindings.length) throw new Error('导入须提供文件内容；导出使用当前保存版本，字幕格式不接收媒体映射。');
  return { expected_version: value.expected_version, reviewed_timeline_digest: value.reviewed_timeline_digest,
    direction: value.direction, format: value.format, content: value.content, media_bindings: bindings };
}
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (record(value)) return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
  return JSON.stringify(value) ?? 'null';
}
export async function timelineTransferInputDigest(input: TimelineTransferInput): Promise<string> {
  const bytes = new TextEncoder().encode(canonical(checkedTimelineTransferInput(input)));
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), value => value.toString(16).padStart(2, '0')).join('');
}
export function checkedTimelineTransferPreview(value: unknown, original: StudioTimelineRow, input: TimelineTransferInput, inputDigest: string): TimelineTransferPreview {
  if (!record(value) || Object.keys(value).some(k => !['contract', 'direction', 'format', 'timeline_snapshot', 'input_digest', 'timeline', 'timeline_digest', 'sources',
    'media_bindings', 'loss_report', 'requires_loss_acknowledgment', 'output_sha256', 'output_bytes', 'external_media_access', 'model_called', 'automatic_replay',
    'product_acceptance', 'target_applications', 'preview_digest'].includes(k))) invalid();
  const snapshot = value.timeline_snapshot, apps = value.target_applications;
  if (value.contract !== 'studio-timeline-transfer-preview/1' || value.direction !== input.direction || value.format !== input.format
    || !hex(value.preview_digest) || !hex(value.timeline_digest) || value.input_digest !== inputDigest || !record(snapshot)
    || Object.keys(snapshot).some(k => !['id', 'version', 'digest'].includes(k)) || snapshot.id !== original.id
    || snapshot.version !== original.version || snapshot.digest !== original.timeline_digest || value.external_media_access !== false
    || value.model_called !== false || value.automatic_replay !== false || value.product_acceptance !== 'LOCAL_REQUIRED' || !record(apps)
    || Object.keys(apps).some(k => !['Resolve', 'Premiere'].includes(k)) || apps.Resolve !== 'NOT_RUN' || apps.Premiere !== 'NOT_RUN') invalid();
  let timeline: StudioTimeline;
  try { timeline = checkedTimeline(value.timeline); } catch { return invalid(); }
  if (timeline.schema_version === 3 || original.timeline.schema_version === 3) invalid();
  const expected = timelineSources(timeline);
  if (!Array.isArray(value.sources) || value.sources.length !== expected.length || value.sources.some((raw, index) => {
    const actual = source(raw); return Object.keys(actual).some(k => actual[k as keyof StudioTimelineSource] !== expected[index][k as keyof StudioTimelineSource]);
  })) invalid();
  const bindings = checkedTimelineMediaBindings(value.media_bindings);
  if (input.direction === 'IMPORT' && JSON.stringify(bindings) !== JSON.stringify(checkedTimelineMediaBindings(input.media_bindings))
    || input.format !== 'OTIO' && bindings.length) invalid();
  if (input.direction === 'EXPORT') {
    if (value.timeline_digest !== original.timeline_digest || JSON.stringify(timeline) !== JSON.stringify(checkedTimeline(original.timeline))
      || !hex(value.output_sha256) || typeof value.output_bytes !== 'number' || !Number.isSafeInteger(value.output_bytes)
      || value.output_bytes < 0 || value.output_bytes > (input.format === 'OTIO' ? 2 * 1024 * 1024 : 192000)) invalid();
    if (input.format === 'OTIO' && (bindings.length !== expected.length
      || new Set(bindings.map(binding => binding.source_snapshot.id)).size !== expected.length || bindings.some(binding => {
      const item = expected.find(s => s.id === binding.source_snapshot.id);
      return !item || binding.reference !== `media/${item.id}-${item.digest}`
        || Object.keys(item).some(k => item[k as keyof StudioTimelineSource] !== binding.source_snapshot[k as keyof StudioTimelineSource]);
    }))) invalid();
  } else if (value.output_sha256 !== null || value.output_bytes !== null) invalid();
  if (!Array.isArray(value.loss_report) || value.loss_report.length > 10000 || value.loss_report.some(loss => !record(loss)
    || Object.keys(loss).some(k => !['path', 'code', 'severity'].includes(k)) || typeof loss.path !== 'string' || loss.path.length > 1024
    || typeof loss.code !== 'string' || !/^[A-Z][A-Z0-9_]{0,119}$/.test(loss.code) || !['LOSS', 'WARNING'].includes(String(loss.severity)))
    || value.requires_loss_acknowledgment !== (value.loss_report.length > 0)) invalid();
  return { ...value, timeline, sources: expected, media_bindings: bindings } as unknown as TimelineTransferPreview;
}

/** Hint only: the original official parser and exact formal binding set decide admission. */
export function timelineExchangeReferences(content: string): string[] {
  if (new TextEncoder().encode(content).byteLength > 2 * 1024 * 1024) throw new Error('OTIO 文件超过 2 MiB。');
  let root: unknown; try { root = JSON.parse(content); } catch { throw new Error('文件内容不是可读取的 OTIO JSON。'); }
  const result = new Set<string>(), pending: Array<{ value: unknown; depth: number }> = [{ value: root, depth: 0 }];
  let count = 0;
  while (pending.length) {
    const next = pending.pop()!; if (++count > 40000 || next.depth > 32) throw new Error('OTIO 文件结构超出允许范围。');
    const raw = next.value;
    if (Array.isArray(raw)) { raw.forEach(value => pending.push({ value, depth: next.depth + 1 })); continue; }
    if (!record(raw)) continue;
    if (typeof raw.OTIO_SCHEMA === 'string' && raw.OTIO_SCHEMA.startsWith('Clip.')) {
      const selected = record(raw.media_references) && typeof raw.active_media_reference_key === 'string'
        ? raw.media_references[raw.active_media_reference_key] : raw.media_reference;
      if (record(selected) && typeof selected.target_url === 'string' && selected.target_url) result.add(selected.target_url);
    }
    Object.entries(raw).filter(([key]) => !['metadata', 'media_references', 'media_reference'].includes(key))
      .forEach(([, value]) => pending.push({ value, depth: next.depth + 1 }));
  }
  if (!result.size || result.size > 30 || [...result].some(ref => ref.length > 4096 || /[\x00-\x1f\x7f]/.test(ref))) throw new Error('没有可明确映射的媒体引用，或引用数量超过三十个。');
  return [...result];
}
