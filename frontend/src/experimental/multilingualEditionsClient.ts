import type { ExperimentalClient } from './api';
export type TermIssue = { code: string; rule_id?: string; term?: string; expected?: string; found?: string };
export type EditionSegment = { id: string; chapter_id: string; source_version: number; path: number[]; from_pos: number; to_pos: number; source_text: string; target_text: string; note: string; status: 'DRAFT' | 'REVIEW' | 'ACCEPTED' | 'REJECTED'; issues: TermIssue[] };
export type TermRule = { id: string; version: number; source_term: string; source_aliases: string[]; preferred: string; target_aliases: string[]; forbidden: string[]; strategy: 'meaning' | 'transliteration' | 'preserve'; category: 'term' | 'character' | 'title'; match: 'substring' | 'word'; status: 'DRAFT' | 'APPROVED' | 'REVOKED'; note: string; reviewed_by?: string; reviewed_at?: string };
export type EditionChecks = { missing: string[]; pending: string[]; terminology: TermIssue[]; aligned: boolean; can_export: boolean };
export type LanguageEdition = { id: string; version: number; status: string; title?: string; source_language?: string; target_language: string; direction: 'ltr' | 'rtl'; font?: 'serif' | 'sans-serif' | 'monospace'; style_note?: string; stale: boolean; content_withheld: boolean; segments?: EditionSegment[]; archived_segments?: { chapter_id: string; source_version: number; path: number[]; target_text: string; note: string }[]; rules?: TermRule[]; term_revision?: number; checks?: EditionChecks; segment_count?: number };
export type EditionCatalog = { chapters: { id: string; title: string; version: number }[]; branch_sources_available: boolean; translation: { available: false; reason: string; model_called: false } };
export type EditionCreate = { title: string; source_language: string; target_language: string; direction: 'auto' | 'ltr' | 'rtl'; font: 'serif' | 'sans-serif' | 'monospace'; style_note: string; chapters: { chapter_id: string; chapter_version: number }[] };
export type TermInput = Pick<TermRule, 'source_term' | 'source_aliases' | 'preferred' | 'target_aliases' | 'forbidden' | 'strategy' | 'category' | 'match' | 'note'>;
export type SegmentPreview = { preview_digest: string; can_accept: boolean; issues: TermIssue[] };
export type AlignmentPreview = { preview_digest: string; retained_exact: number; new_or_changed: number; archived_old: number; requires_review: number };
export type EditionExportPreview = { preview_digest: string; can_export: boolean; checks: EditionChecks; format: string; encoding: string };
export type EditionExport = { filename: string; mime: string; encoding: string; content: string; sha256: string; published: false };
export function multilingualEditionsClient(client: ExperimentalClient) {
  const base = '/language-editions'; const item = (e: LanguageEdition) => `${base}/${encodeURIComponent(e.id)}`;
  return {
    catalog: (signal?: AbortSignal) => client.get<EditionCatalog>(base + '/catalog', signal),
    list: (signal?: AbortSignal) => client.get<{ items: LanguageEdition[]; truncated: boolean }>(base, signal),
    get: (e: LanguageEdition) => client.get<LanguageEdition>(item(e)),
    create: (input: EditionCreate) => client.post<LanguageEdition>(base, input),
    save: (e: LanguageEdition, s: EditionSegment, text: string, note: string) => client.put<LanguageEdition>(`${item(e)}/segments/${encodeURIComponent(s.id)}`, { expected_version: e.version, text, note }),
    preview: (e: LanguageEdition, s: EditionSegment) => client.post<SegmentPreview>(`${item(e)}/segments/${encodeURIComponent(s.id)}/preview`, { expected_version: e.version }),
    review: (e: LanguageEdition, s: EditionSegment, action: 'submit' | 'accept' | 'reject' | 'reopen', preview?: SegmentPreview) => client.post<LanguageEdition>(`${item(e)}/segments/${encodeURIComponent(s.id)}/review`, { expected_version: e.version, action, ...(preview ? { preview_digest: preview.preview_digest } : {}) }),
    addRule: (e: LanguageEdition, rule: TermInput) => client.post<LanguageEdition>(item(e) + '/rules', { expected_version: e.version, ...rule }),
    ruleReview: (e: LanguageEdition, rule: TermRule, action: 'approve' | 'revoke') => client.post<LanguageEdition>(`${item(e)}/rules/${encodeURIComponent(rule.id)}/review`, { expected_version: e.version, action }),
    refreshPreview: (e: LanguageEdition) => client.post<AlignmentPreview>(item(e) + '/refresh-preview', { expected_version: e.version }),
    refresh: (e: LanguageEdition, preview: AlignmentPreview) => client.post<LanguageEdition>(item(e) + '/refresh', { expected_version: e.version, preview_digest: preview.preview_digest }),
    exportPreview: (e: LanguageEdition, format: string) => client.post<EditionExportPreview>(item(e) + '/export-preview', { expected_version: e.version, format }),
    export: (e: LanguageEdition, preview: EditionExportPreview) => client.post<EditionExport>(item(e) + '/export', { expected_version: e.version, format: preview.format, preview_digest: preview.preview_digest }),
  };
}
