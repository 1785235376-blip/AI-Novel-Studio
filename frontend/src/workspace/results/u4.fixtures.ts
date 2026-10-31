// [HERMIA-FE-20261025 U4-T] Evidence kind: mock (in-memory test doubles of existing owner clients). Not real provider/API.
import type {ProductionJob} from '../../creative/studioProductionClient';
import type {CanvasViewHistory, CanvasViewRecord, CanvasDefinition} from '../../creative/studioCanvasViewClient';
import type {StudioAsset} from '../../creative/studioClient';
export const D = (c: string) => c.repeat(64).slice(0, 64);
export function job(p: Partial<ProductionJob> = {}): ProductionJob {
  return {contract: 'studio-production-job/1', owner: 'image', id: 'job-1', novel_id: 'p1', branch_id: null, version: 3, operation_id: 'm5.image', request_id: 'r',
    status: 'APPROVED', request_digest: D('a'), receipt_digest: null, output_candidate: {id: 'asset-9', version: 2, digest: D('b'), kind: 'image'},
    approved_asset_version: 2, product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null,
    sources: [], command: null, provider: null, ...p} as unknown as ProductionJob;
}
export function def(cards: CanvasDefinition['cards'], title = '作品'): CanvasDefinition { return {schema_version: 1, title, cards, viewport: {x: 0, y: 0, zoom: 1}}; }
export function canvas(p: Partial<CanvasViewRecord> = {}): CanvasViewRecord {
  return {project_id: 'p1', id: 'cv1', version: 5, definition: def([{id: 'card-1', position: {x: 0, y: 0}, asset: {asset_id: 'asset-old', version: 1, digest: D('c'), kind: 'image'}}]),
    definition_digest: D('d'), created_at: 't0', updated_at: 't1', reference_states: [], execution_authority: false, binary_content_verified: false,
    capacity: {history_used: 5, record_bytes: 1}, ...p} as unknown as CanvasViewRecord;
}
export function history(cv: CanvasViewRecord, p: Partial<CanvasViewHistory> = {}): CanvasViewHistory {
  return {project_id: cv.project_id, id: cv.id, incarnation: 'inc-1', current_version: cv.version, current_definition_digest: cv.definition_digest,
    items: [], restore_policy: 'CURRENT_METADATA_ONLY', execution_authority: false, binary_content_verified: false, ...p} as unknown as CanvasViewHistory;
}
export function asset(p: Partial<StudioAsset> = {}): StudioAsset { return {id: 'asset-9', version: 2, sha256: D('b'), kind: 'image', deleted_at: null, ...p} as unknown as StudioAsset; }
export function lease() { const l = {epoch: 1, cur: true, isCurrent() { return l.cur; }}; return l; }
