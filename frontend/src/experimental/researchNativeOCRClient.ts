import type { ExperimentalClient } from './api';
import type { Source } from './researchLibraryClient';
export type OCRRoute = { provider_id: string; model_id: string; display_name: string; languages: string[] };
export type OCRPreview = { receipt_version: number; source_binding: { source_id: string; source_version: number; source_digest: string }; provider_id: string; model_id: string; language: string; expires_at: string; reviewed_preview_digest: string; external_provider_fee_microusd: number; host_compute_cost_included: false };
export type OCRRow = { id: string; version: number; status: string; request: { source_id: string; source_version: number; operation: string }; native_ocr_preview?: OCRPreview | null; result?: { blocks: { text: string; page: number; citation: { source_id: string; source_version: number; quote_sha256: string } }[] } | null };
export function currentOCR(row: OCRRow, source: Source) {
  return !!row && typeof row.id === 'string' && Number.isInteger(row.version) && row.version > 0 && row.request?.operation === 'OCR' && row.request.source_id === source.id && row.request.source_version === source.version;
}
export function researchNativeOCRClient(client: ExperimentalClient) {
  const base = '/research-library/analysis', path = (id: string) => `${base}/jobs/${encodeURIComponent(id)}`;
  return {
    status: (signal?: AbortSignal) => client.get<{ native_ocr?: { status: string; routes: OCRRoute[] } }>(base + '/status', signal),
    list: (signal?: AbortSignal) => client.get<{ items: OCRRow[] }>(base + '/jobs', signal),
    get: (id: string) => client.get<OCRRow>(path(id)),
    create: (source: Source) => client.post<OCRRow>(base + '/jobs', { source_id: source.id, source_version: source.version, operation: 'OCR', pages: [1] }),
    preview: (row: OCRRow, route: OCRRoute, language: string) => client.post<OCRRow>(path(row.id) + '/native-preview', { expected_version: row.version, provider_id: route.provider_id, model_id: route.model_id, language }),
    dispatch: (row: OCRRow, key: string) => client.post<OCRRow>(path(row.id) + '/native-dispatch', { expected_version: row.version, reviewed_preview_digest: row.native_ocr_preview?.reviewed_preview_digest, idempotency_key: key }),
    action: (row: OCRRow, action: 'review' | 'cancel') => client.post<OCRRow>(path(row.id) + '/' + action, { expected_version: row.version }),
  };
}
