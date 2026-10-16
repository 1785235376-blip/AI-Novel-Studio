import type { ExperimentalClient } from './api';
export type RelinkReview = { missing_id: string; expected_sha256: string | null; candidate_sha256: string; affected_chapters: { id: string; title: string; version: number; current_version?: number }[]; conflicts: { code: string; blocking: boolean; chapter_id?: string }[]; can_confirm: boolean };
export type PortableRecord = { id: string; version: number; status: string; kind: 'IMPORT' | 'EXPORT' | 'RELINK'; snapshot_digest: string; title?: string; chapter_count?: number; target_id?: string; digest_matches?: boolean; relink_review?: RelinkReview; error_code?: string; id_map?: { chapters: Record<string, string>; media: Record<string, string> }; media?: { ref: string; state: string; sha256?: string }[] };
export type PortableCatalog = { chapters: { id: string; title: string; version: number }[]; missing: { id: string; expected_sha256: string | null; chapter_ids: string[] }[]; restore_available: boolean; limitations: string[] };
export type StoragePreview = { categories: { kind: string; bytes: number | null; measurement: string; unmeasured_records?: number; cleanable: boolean }[]; eligible: { id: string; version: number; bytes: number; sha256: string }[]; preview_digest: string };
const key = encodeURIComponent;
const confirmation = (row: PortableRecord) => ({ expected_version: row.version, snapshot_digest: row.snapshot_digest, confirmed: true });
export function portableProjectsClient(client: ExperimentalClient) {
  return {
    catalog: (signal?: AbortSignal) => client.get<PortableCatalog>('/portable-projects/catalog', signal),
    records: (signal?: AbortSignal) => client.get<{ items: PortableRecord[] }>('/portable-projects/records', signal),
    storage: (signal?: AbortSignal) => client.get<StoragePreview>('/portable-projects/storage', signal),
    export: (chapter_ids: string[]) => client.post<PortableRecord>('/portable-projects/export', { chapter_ids }),
    download: (row: PortableRecord) => client.blob(`/portable-projects/records/${key(row.id)}/file?expected_version=${row.version}`),
    preflight: (filename: string, content_base64: string) => client.post<PortableRecord>('/portable-projects/import-preflight', { filename, content_base64 }),
    restore: (row: PortableRecord) => client.post<PortableRecord>(`/portable-projects/records/${key(row.id)}/restore`, confirmation(row)),
    preflightRelink: (filename: string, content_base64: string, missing_id: string, chapter_ids: string[], kind: string) => client.post<PortableRecord>('/portable-projects/relink-preflight', { filename, content_base64, missing_id, chapter_ids, kind }),
    relink: (row: PortableRecord, accept_different_digest: boolean) => client.post<PortableRecord>(`/portable-projects/records/${key(row.id)}/relink`, { ...confirmation(row), accept_different_digest }),
    cleanup: (preview: StoragePreview, record_ids: string[]) => client.post('/portable-projects/cleanup', { record_ids, preview_digest: preview.preview_digest, confirmed: true }),
  };
}
export function readPortableFile(file: File, maxBytes = 40 * 1024 * 1024): Promise<string> {
  if (!file.size || file.size > maxBytes) return Promise.reject(new Error('文件为空或超过大小限制。'));
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error('无法读取所选文件。')); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.readAsDataURL(file); });
}
export function downloadPortableBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
