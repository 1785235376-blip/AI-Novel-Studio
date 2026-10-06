import type { ExperimentalClient } from './api';
import type { WorkspaceNavigation } from './uxClient';
export type WritingFocusPreferences = { column_width: 'narrow' | 'comfortable' | 'wide'; font_size: 16 | 18 | 20 | 24; line_height: 1.5 | 1.75 | 2; paragraph_focus: boolean };
export const defaultWritingPreferences: WritingFocusPreferences = { column_width: 'comfortable', font_size: 18, line_height: 1.75, paragraph_focus: false };
export type ReferencePin = { kind: 'character' | 'location' | 'chapter'; id: string; revision: string };
export type ReferenceCard = ReferencePin & { title: string; version?: number; text: string; truncated: boolean; read_only: true; privacy_level: string };
export type PinnedReference = ReferencePin & { state: 'READY' | 'STALE' | 'UNAVAILABLE'; title: string; card: ReferenceCard | null };
export type WritingPreferenceResult = { version: number; preferences: WritingFocusPreferences; pins: ReferencePin[]; recovery_required: boolean };
export type InspirationNote = { id: string; version: number; capture_id: string; title: string; text: string; status: 'DRAFT' | 'ARCHIVED'; chapter_id: string | null; chapter_version: number | null; source_state: 'NONE' | 'READY' | 'STALE' | 'UNAVAILABLE'; included_in_ai_context: false; canon: false; copies: { proposal_id: string; status: 'REVIEW' }[] };
export type NoteInput = Pick<InspirationNote, 'capture_id' | 'title' | 'text' | 'chapter_id' | 'chapter_version'>;
export type ChapterOverview = { id: string; title: string; version: number; revision: string; number?: number; word_count: number; scene_count: number; scenes_truncated: boolean; scenes: { id: string; title: string; chapter_id: string; sequence?: number; status: string; purpose: string; conflict: string; outcome: string; details_truncated: boolean }[] };
export type PlanningTarget = { id: string; version: number; title: string; level: string };
export type CopyInput = { expected_version: number; node_id: string; expected_node_version: number; field: 'goal' | 'conflict' | 'turning_point' };
export type CopyPreview = { preview_digest: string; field: CopyInput['field']; before: string; after: string; target_title: string; note_version: number; target_version: number; status_after_copy: 'REVIEW' };
export function writingFocusClient(client: ExperimentalClient) {
  const base = '/writing-focus';
  return {
    preferences: (signal?: AbortSignal) => client.get<WritingPreferenceResult>(base + '/preferences', signal),
    savePreferences: (version: number, preferences: WritingFocusPreferences, pins: ReferencePin[]) => client.put<WritingPreferenceResult>(base + '/preferences', { expected_version: version, preferences, pins }),
    references: (query: string, kind: string, signal?: AbortSignal) => client.get<{ items: ReferenceCard[]; truncated: boolean; branch_sources_available: boolean }>(base + '/references?' + new URLSearchParams({ q: query, kind }), signal),
    pins: (signal?: AbortSignal) => client.get<{ items: PinnedReference[] }>(base + '/pins', signal),
    openBookmark: (id: string, revision: string, current = false) => client.post<WorkspaceNavigation>(base + '/bookmarks/open', { id, revision, open_current: current }),
    overview: (chapterId: string, signal?: AbortSignal) => client.get<{ items: ChapterOverview[]; truncated: boolean; chapter_sources_available: boolean; scene_sources_available: boolean }>(base + '/overview' + (chapterId ? '?' + new URLSearchParams({ chapter_id: chapterId }) : ''), signal),
    notes: (archived: boolean, signal?: AbortSignal) => client.get<{ items: InspirationNote[]; truncated: boolean }>(base + '/notes?archived=' + archived, signal),
    createNote: (body: NoteInput) => client.post<InspirationNote>(base + '/notes', body),
    editNote: (id: string, version: number, body: NoteInput) => client.put<InspirationNote>(base + '/notes/' + encodeURIComponent(id), { ...body, expected_version: version }),
    transition: (note: InspirationNote, action: 'archive' | 'restore') => client.post<InspirationNote>(base + '/notes/' + encodeURIComponent(note.id) + '/' + action, { expected_version: note.version }),
    targets: (signal?: AbortSignal) => client.get<{ items: PlanningTarget[] }>(base + '/planning-targets', signal),
    preview: (id: string, body: CopyInput) => client.post<CopyPreview>(base + '/notes/' + encodeURIComponent(id) + '/planning/preview', body),
    copy: (id: string, body: CopyInput, previewDigest: string) => client.post<{ proposal_id: string; status: 'REVIEW'; note: InspirationNote }>(base + '/notes/' + encodeURIComponent(id) + '/planning/copy', { ...body, preview_digest: previewDigest }),
  };
}
