import { ApiError } from '../api';
import type { ImpactNode, ImpactView } from './changeImpactClient';

const invalid = (): never => { throw new ApiError({ status: 200, code: 'CHANGE_IMPACT_STORYBOARD_RESPONSE_INVALID',
  message: 'Storyboard 影响回执不完整，请重新读取原范围。' }); };
const object = (v: unknown): Record<string, unknown> => v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : invalid();
const text = (v: unknown, max = 240): string => typeof v === 'string' && v.trim() && v.length <= max && !/[\u0000-\u001f\u007f]/.test(v) ? v : invalid();
const version = (v: unknown): number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 1 ? v : invalid();
const digest = (v: unknown): string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v) ? v : invalid();

/** Complete, authorized direct references only. Never turn this response into execution authority. */
export function checkedStoryboardImpact(value: unknown, documentId: string): ImpactView {
  const r = object(value), source = object(r.source), binding = object(source.binding);
  if (source.kind !== 'CREATIVE_STORYBOARD' || source.id !== documentId
    || r.coverage !== 'EXACT_AUTHORIZED_DIRECT_STORYBOARD_GRAPH_REFERENCES_ONLY'
    || r.other_owner_coverage !== 'NOT_EVALUATED' || r.unrecorded_dependencies !== 'UNKNOWN'
    || r.automatic_regeneration !== false || r.truncated !== false || r.target_limit !== 20
    || !Array.isArray(r.inferred) || r.inferred.length || !Array.isArray(r.items) || r.items.length > 20
    || Object.keys(binding).sort().join(',') !== 'digest,incarnation_digest,version') invalid();
  const pin = { version: version(binding.version), digest: digest(binding.digest), incarnation_digest: digest(binding.incarnation_digest) };
  const items: ImpactNode[] = (r.items as unknown[]).map(value => {
    const node = object(value);
    if (node.kind !== 'CREATIVE_GRAPH_NODE' || !/^CREATIVE_GRAPH_NODE:[a-f0-9]{64}$/.test(text(node.key, 500))
      || !['SAVED', 'DISABLED'].includes(String(node.status)) || typeof node.stale !== 'boolean'
      || node.feature !== 'narrative_production_v2' || node.locked !== false || node.lock_version !== 0
      || node.refresh_candidate !== false || node.refresh_reason !== 'ORIGINAL_DOMAIN_MANUAL_REVIEW_REQUIRED'
      || node.evidence_type !== 'EXACT_SAVED_DIRECT_STORYBOARD_REFERENCE'
      || !Array.isArray(node.evidence) || node.evidence.length !== 1) invalid();
    const edge = object((node.evidence as unknown[])[0]);
    if (edge.key !== `CREATIVE_STORYBOARD:${documentId}` || edge.state !== (node.stale ? 'STALE' : 'CURRENT')
      || edge.current_version !== pin.version) invalid();
    return { key: text(node.key, 500), kind: 'CREATIVE_GRAPH_NODE', id: text(node.id, 500), label: text(node.label, 2000),
      version: version(node.version), status: String(node.status), feature: 'narrative_production_v2', stale: node.stale as boolean,
      locked: false, lock_version: 0, refresh_candidate: false, refresh_reason: 'ORIGINAL_DOMAIN_MANUAL_REVIEW_REQUIRED',
      evidence: [{ key: String(edge.key), label: text(edge.label, 2000), state: String(edge.state),
        recorded_version: version(edge.recorded_version), current_version: pin.version }] };
  });
  if (new Set(items.map(row => row.key)).size !== items.length || new Set(items.map(row => row.id)).size !== items.length) invalid();
  return { source: { kind: 'CREATIVE_STORYBOARD', id: documentId, label: text(source.label, 2000), binding: pin }, items,
    coverage: String(r.coverage), inferred: [], unrecorded_dependencies: 'UNKNOWN', automatic_regeneration: false };
}
