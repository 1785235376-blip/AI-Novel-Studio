import type { StudioAsset } from './studioClient';
import type { ProductionJob, ProductionOwner } from './studioProductionClient';
export type TimelineAssetRange = { in_ms: number; out_ms: number };
export type TimelineReceiptReader = (owner: ProductionOwner, id: string) => Promise<ProductionJob>;
/** Provenance is only a lookup hint; it never establishes duration or approval. */
export function timelineDurationHint(asset: StudioAsset): { owner: ProductionOwner; id: string } | undefined {
  const id = asset.provenance?.source_task_id, operation = asset.provenance?.operation;
  if (typeof id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(id)) return;
  if (asset.kind === 'audio' && operation === 'm8.audio.trim') return { owner: 'audio', id };
  if (asset.kind === 'video' && operation === 'm9.timeline.multitrack') return { owner: 'timeline', id };
}
/** The caller supplies the original client's validated GET receipt, never metadata
 * or a requested duration. Imported and otherwise unproven media stay unknown. */
export function timelineMeasuredDuration(asset: StudioAsset, job: ProductionJob): number | undefined {
  const hint = timelineDurationHint(asset), output = job.output_candidate, measured = job.media_measurement;
  if (!hint || job.id !== hint.id || job.owner !== hint.owner || job.operation_id !== asset.provenance?.operation
    || job.contract !== 'studio-production-job/1' || job.status !== 'APPROVED' || job.needs_reconciliation === true
    || job.novel_id !== asset.novel_id || (job.branch_id ?? null) !== (asset.branch_id ?? null) || asset.deleted_at
    || !output || output.id !== asset.id || output.kind !== asset.kind || output.digest !== asset.sha256
    || job.approved_asset_version !== asset.version || !Number.isSafeInteger(asset.version) || asset.version < 1
    || !/^[a-f0-9]{64}$/.test(asset.sha256) || !measured || !Number.isSafeInteger(measured.duration_ms)
    || typeof measured.duration_ms !== 'number' || measured.duration_ms <= 0 || measured.duration_ms > 36_000_000) return;
  if (hint.owner === 'audio') {
    if (!['PCM_DECODED', 'FLAC_STREAMINFO_PCM_VERIFIED', 'MP3_GAPLESS_PCM_VERIFIED'].includes(measured.profile_validation || '')
      || !('output_sha256' in measured) || measured.output_sha256 !== asset.sha256) return;
  } else if (measured.profile_validation !== 'NATIVE_FFPROBE_EXACT') return;
  return measured.duration_ms;
}
export function validTimelineAssetRange(range: TimelineAssetRange | undefined, duration?: number): range is TimelineAssetRange {
  return !!range && Number.isSafeInteger(range.in_ms) && Number.isSafeInteger(range.out_ms) && range.in_ms >= 0
    && range.out_ms > range.in_ms && range.out_ms <= 36_000_000 && (duration === undefined || range.out_ms <= duration);
}
export function parseTimelineAssetRange(start: string, end: string): TimelineAssetRange | undefined {
  if (!/^\d+$/.test(start) || !/^\d+$/.test(end)) return;
  const range = { in_ms: Number(start), out_ms: Number(end) }; return validTimelineAssetRange(range) ? range : undefined;
}
