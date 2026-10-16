import type { ExperimentalClient } from './api';
import type { WorkspaceNavigation } from './uxClient';
export type ProofRules = { punctuation: boolean; repeated_words: boolean; literals: { kind: 'naming' | 'replacement'; find: string; suggest: string }[] };
export type ReaderSettings = { version: number; rules: ProofRules; license_declaration: string; font_declaration: string };
export type ReadAnchor = { chapter_id: string; revision: string; offset: number; quote: string };
export type DraftStatus = { chapter_id: string; chapter_version: number; state: 'SAVED' | 'UNSAVED' | 'LOCAL_DRAFT' | 'SAVE_FAILED' | 'UNKNOWN' };
export type ReaderResult = { chapters: { id: string; title: string; version: number; revision: string; paragraphs: { index: number; offset: number; text: string }[] }[]; annotations: (ReadAnchor & { id: string; note: string; stale: boolean })[]; source_digest: string; branch_sources_available: boolean };
export type ProofFinding = ReadAnchor & { id: string; paragraph: number; kind: string; explanation: string; suggestion: string | null; ignored_reason: string | null };
export type PreflightResult = { findings: { code: string; severity: 'BLOCKER' | 'WARNING' | 'INFO'; message: string; feature: string; chapter_id?: string }[]; coverage: { area: string; state: string }[]; source_digest: string; has_integrity_blockers: boolean; checked_format: string };
export function readerPreflightClient(client: ExperimentalClient) {
  const base = '/reader-preflight';
  return {
    settings: (signal?: AbortSignal) => client.get<ReaderSettings>(base + '/settings', signal),
    save: (value: ReaderSettings) => { const { version, ...rest } = value; return client.put<ReaderSettings>(base + '/settings', { ...rest, expected_version: version }); },
    read: (signal?: AbortSignal) => client.get<ReaderResult>(base + '/read', signal),
    proof: (signal?: AbortSignal) => client.get<{ items: ProofFinding[]; truncated: boolean }>(base + '/proof', signal),
    open: (anchor: ReadAnchor) => client.post<WorkspaceNavigation>(base + '/open', anchor),
    annotate: (version: number, anchor: ReadAnchor, note: string) => client.post<ReaderSettings>(base + '/annotations', { ...anchor, note, expected_version: version }),
    ignore: (version: number, id: string, reason: string) => client.post<ReaderSettings>(base + '/ignore', { expected_version: version, finding_id: id, reason }),
    check: (format: string, draft_status: DraftStatus[]) => client.post<PreflightResult>(base + '/check', { format, draft_status }),
  };
}
