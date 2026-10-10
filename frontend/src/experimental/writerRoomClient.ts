import type { ExperimentalClient } from './api';
export type RoomMember = { id: string; name: string; can_write: boolean; can_review: boolean };
export type ChapterRef = { id: string; revision: string };
export type RoomChapter = ChapterRef & { title: string; version: number };
export type ReviewRef = { domain: string; id: string; version: number };
export type TaskFields = { title: string; description: string; assignee: string; reviewer: string };
export type RoomTask = TaskFields & { id: string; version: number; status: string; created_by: string; source_state: string; participants_current: boolean; chapter: ChapterRef | null; review_target: ReviewRef | null; events: { action: string; actor: string; at: string; note: string }[] };
export type RoomOverview = { presence_interface?: { state: string; realtime: false; occupants: never[]; required_adapter_contract: string[]; next_action: string }; items: RoomTask[]; actor: string; members: RoomMember[]; can_write: boolean; can_review: boolean; truncated: boolean; copy_warning: string };
export type RoomCatalog = { chapters: RoomChapter[]; chapter_state: string; assets: { id: string; filename: string; sha256: string; size: number }[]; asset_state: string; review_targets: (ReviewRef & { preview: string; status: string })[]; truncated: boolean };
export type RoomComment = { id: string; version: number; status: string; anchor_state: string; anchor: { chapter_id: string; chapter_version: number; quote: string }; messages: { id: string; actor_id: string; text: string }[] };
export type RoomConflict = { id: string; version: number; status: string; target: { kind: string; id: string }; current_candidate: TaskFields & { version: number; messages?: { text: string }[] }; submitted_candidate: TaskFields & { expected_version: number; text?: string; action?: string; note?: string } };
export type PackageSelection = { chapters: ChapterRef[]; asset_ids: string[] };
export type PackagePreview = { preview_digest: string; selected_bytes: number; manifest: { chapters: { title: string; version: number }[]; assets: { id: string; size: number }[]; copy_warning: string } };
export type TaskAction = 'start' | 'submit' | 'request_changes' | 'close' | 'reopen' | 'cancel';
const p = '/writer-room';
export function writerRoomClient(client: ExperimentalClient) {
  return {
    overview: (signal?: AbortSignal) => client.get<RoomOverview>(p, signal),
    catalog: (signal?: AbortSignal) => client.get<RoomCatalog>(p + '/catalog', signal),
    conflicts: (signal?: AbortSignal) => client.get<{ items: RoomConflict[] }>(p + '/conflicts', signal),
    notices: (signal?: AbortSignal) => client.get<{ items: { id: string; title: string; status: string }[] }>(p + '/notices', signal),
    search: (query: string, signal?: AbortSignal) => client.get<{ items: RoomTask[] }>(p + '/index?query=' + encodeURIComponent(query), signal),
    chapter: (row: ChapterRef, signal?: AbortSignal) => client.get<{ title: string; version: number; text: string; mode: 'READ_ONLY' }>(p + '/chapters/' + encodeURIComponent(row.id) + '?revision=' + encodeURIComponent(row.revision), signal),
    create: (body: TaskFields & { request_id: string; chapter: ChapterRef | null; review_target: ReviewRef | null }) => client.post<RoomTask>(p + '/tasks', body),
    save: (id: string, version: number, fields: TaskFields, conflictId?: string) => client.put<RoomTask>(p + '/tasks/' + encodeURIComponent(id), { ...fields, expected_version: version, resolve_conflict_id: conflictId ?? null }),
    transition: (task: RoomTask, action: TaskAction, note: string) => client.post<RoomTask>(p + '/tasks/' + encodeURIComponent(task.id) + '/transition', { expected_version: task.version, action, note }),
    comments: (signal?: AbortSignal) => client.get<{ items: RoomComment[]; source_state: string }>(p + '/comments', signal),
    comment: (chapter: RoomChapter, quote: string, text: string) => client.post<RoomComment>(p + '/comments', { chapter_id: chapter.id, chapter_version: chapter.version, quote, text }),
    commentAction: (row: RoomComment, action: 'reply' | 'resolve' | 'reopen', text: string) => client.post<RoomComment>(p + '/comments/' + encodeURIComponent(row.id), { expected_version: row.version, action, text }),
    packagePreview: (selection: PackageSelection) => client.post<PackagePreview>(p + '/packages/preview', selection),
    download: (selection: PackageSelection, preview: PackagePreview) => client.post<{ filename: string; mime: string; content_base64: string }>(p + '/packages/download', { ...selection, preview_digest: preview.preview_digest, acknowledge_copy_boundary: true }),
  };
}
export type RoomApi = ReturnType<typeof writerRoomClient>;
