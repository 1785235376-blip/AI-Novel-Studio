import type { ExperimentalClient } from './api';
export type TermIssue = { code: string; rule_id?: string; term?: string; expected?: string; found?: string };
export type EditionSegment = { id: string; chapter_id: string; source_version: number; path: number[]; from_pos: number; to_pos: number; source_text: string; target_text: string; note: string; status: 'DRAFT' | 'REVIEW' | 'ACCEPTED' | 'REJECTED'; issues: TermIssue[] };
export type TermRule = { id: string; version: number; source_term: string; source_aliases: string[]; preferred: string; target_aliases: string[]; forbidden: string[]; strategy: 'meaning' | 'transliteration' | 'preserve'; category: 'term' | 'character' | 'title'; match: 'substring' | 'word'; status: 'DRAFT' | 'APPROVED' | 'REVOKED'; note: string; reviewed_by?: string; reviewed_at?: string };
export type EditionChecks = { missing: string[]; pending: string[]; terminology: TermIssue[]; aligned: boolean; can_export: boolean };
export type LanguageEdition = { id: string; version: number; status: string; title?: string; source_language?: string; target_language: string; direction: 'ltr' | 'rtl'; font?: 'serif' | 'sans-serif' | 'monospace'; style_note?: string; stale: boolean; content_withheld: boolean; segments?: EditionSegment[]; archived_segments?: { chapter_id: string; source_version: number; path: number[]; target_text: string; note: string }[]; rules?: TermRule[]; term_revision?: number; checks?: EditionChecks; segment_count?: number };
export type EditionCatalog = { chapters: { id: string; title: string; version: number }[]; branch_sources_available: boolean; translation: { available: boolean; reason: string; execution_authorized?: false; model_called: false } };
export type EditionCreate = { title: string; source_language: string; target_language: string; direction: 'auto' | 'ltr' | 'rtl'; font: 'serif' | 'sans-serif' | 'monospace'; style_note: string; chapters: { chapter_id: string; chapter_version: number }[] };
export type TermInput = Pick<TermRule, 'source_term' | 'source_aliases' | 'preferred' | 'target_aliases' | 'forbidden' | 'strategy' | 'category' | 'match' | 'note'>;
export type SegmentPreview = { preview_digest: string; can_accept: boolean; issues: TermIssue[] };
export type AlignmentPreview = { preview_digest: string; retained_exact: number; new_or_changed: number; archived_old: number; requires_review: number };
export type EditionExportPreview = { preview_digest: string; can_export: boolean; checks: EditionChecks; format: string; encoding: string };
export type EditionExport = { filename: string; mime: string; encoding: string; content: string; sha256: string; published: false };
export type TranslationRoute = { route_id: string; provider_id: string; model_id: string; display_name: string; available: boolean; reasons: string[]; synthetic: boolean; verification: string };
export type TranslationRun = { id: string; version: number; status: string; edition_id: string; edition_version: number; segment_id: string; stale: boolean; content_withheld: boolean; automatic_retry: false; quality_verification: string;
  preview: null | { preview_digest: string; execution_available: boolean; blocked_reason?: string; max_output_bytes: number; timeout_seconds: number; excluded: string[]; request: { prompt: string; context: Record<string, unknown> } | null;
    broker: { id: string; version: number; budget_version: number; chosen: null | (TranslationRoute & { price: Record<string, unknown> }); candidates: (TranslationRoute & { reasons: string[] })[] } };
  execution: null | { job_id: string; reservation_id: string | null; receipt_state: string; model_called: boolean; usage_state: string; failure_code?: string; accounting: null | { status: string; cost_state: string; actual_microusd: number | null } };
  candidate: null | { text: string; digest: string; job_id: string; request_digest: string; applied: false; quality_verification: string } };
export function multilingualEditionsClient(client: ExperimentalClient) {
  const base = '/language-editions'; const item = (e: LanguageEdition) => `${base}/${encodeURIComponent(e.id)}`;
  return {
    translationRoutes: (signal?: AbortSignal) => client.get<{ items: TranslationRoute[] }>(base + '/translation/routes', signal),
    translationRuns: (e: LanguageEdition, signal?: AbortSignal) => client.get<{ items: TranslationRun[]; truncated: boolean }>(item(e) + '/translations', signal),
    translationPreview: (e: LanguageEdition, s: EditionSegment, route_id: string, allow_synthetic: boolean) => client.post<TranslationRun>(`${item(e)}/segments/${encodeURIComponent(s.id)}/translation-preview`, { expected_version: e.version, route_id, allow_synthetic }),
    translationAction: (e: LanguageEdition, r: TranslationRun, action: 'dispatch' | 'refresh' | 'cancel') => client.post<TranslationRun>(`${item(e)}/translations/${encodeURIComponent(r.id)}/${action}`, { expected_version: r.version, ...(action === 'dispatch' ? { reviewed_preview_digest: r.preview!.preview_digest } : {}) }),
    translationAdopt: (e: LanguageEdition, r: TranslationRun) => client.post<LanguageEdition>(`${item(e)}/translations/${encodeURIComponent(r.id)}/adopt`, { expected_version: r.version, expected_edition_version: e.version, candidate_digest: r.candidate!.digest }),
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
