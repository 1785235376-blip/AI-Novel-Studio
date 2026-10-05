import type { ExperimentalClient } from './api';
export type Citation = { source_id: string; source_version: number; paragraph: number; page?: number; quote_sha256: string };
export type ResearchMeta = { title: string; author: string; source: string; source_version: string; usage_notes: string; access: 'PRIVATE' | 'PROJECT' };
export type Source = ResearchMeta & { id: string; version: number; origin: string; format: string; filename: string; accessed_at: string; extraction_status: string; paragraph_count: number; page_citations?: Citation[]; warnings: string[]; paragraphs?: { paragraph: number; page: number | null; text: string; citation: Citation }[] };
export type Evidence = { citation: Citation; title: string; author: string; text: string; page: number | null; paragraph: number; source: string; not_understood?: boolean; warning?: string };
export type Note = { id: string; version: number; title: string; text: string; citations: Citation[]; evidence: Evidence[] };
export type SettingDraft = { id: string; version: number; title: string; status: 'REVIEW' | 'RESEARCH_REVIEWED'; data: { description: string }; evidence: Evidence[]; canon_promotion_available: false };
const seg = encodeURIComponent;
export function researchLibraryClient(client: ExperimentalClient) {
  const base = '/research-library';
  return {
    sources: (signal?: AbortSignal) => client.get<{ items: Source[]; total: number; adapters: Record<string, string> }>(base + '/sources', signal),
    source: (id: string, signal?: AbortSignal) => client.get<Source>(`${base}/sources/${seg(id)}`, signal),
    original: (id: string) => client.blob(`${base}/sources/${seg(id)}/original`),
    importFile: (metadata: ResearchMeta, filename: string, content_base64: string) => client.post<Source>(base + '/sources/import', { ...metadata, filename, content_base64 }),
    fetchWeb: (metadata: ResearchMeta, url: string) => client.post<Source>(base + '/sources/fetch-webpage', { ...metadata, url, confirm_fetch: true }),
    edit: (row: Source, metadata: ResearchMeta) => client.put<Source>(`${base}/sources/${seg(row.id)}`, { ...metadata, expected_version: row.version }),
    remove: (row: Source, action: 'revoke' | 'delete') => client.post(`${base}/sources/${seg(row.id)}/${action}`, { expected_version: row.version }),
    search: (query: string) => client.get<{ items: Evidence[]; truncated: boolean }>(`${base}/search?q=${seg(query)}`),
    citation: (citation: Citation) => client.post<Evidence>(base + '/citation', citation),
    preview: (citations: Citation[]) => client.post<{ items: Evidence[]; automatic_injection: false }>(base + '/context-preview', { citations }),
    notes: (signal?: AbortSignal) => client.get<{ items: Note[] }>(base + '/notes', signal),
    note: (title: string, text: string, citations: Citation[]) => client.post<Note>(base + '/notes', { title, text, citations }),
    drafts: (signal?: AbortSignal) => client.get<{ items: SettingDraft[] }>(base + '/setting-drafts', signal),
    adopt: (title: string, original_setting: string, citations: Citation[]) => client.post<SettingDraft>(base + '/setting-drafts', { title, original_setting, citations, confirm_original: true }),
    review: (row: SettingDraft, action: 'review' | 'reopen') => client.post<SettingDraft>(`${base}/setting-drafts/${seg(row.id)}/${action}`, { expected_version: row.version }),
    backrefs: (id: string) => client.get<{ items: { id: string; kind: string; title: string }[]; total: number }>(`${base}/sources/${seg(id)}/backrefs`),
  };
}
export function readResearchFile(file: File): Promise<string> {
  if (!file.size || file.size > 4 * 1024 * 1024) return Promise.reject(new Error('请选取不超过 4 MiB 的非空文件。'));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('无法读取文件，原表单已保留。'));
    reader.onload = () => {
      const result = String(reader.result);
      resolve(result.slice(result.indexOf(',') + 1));
    };
    reader.readAsDataURL(file);
  });
}
