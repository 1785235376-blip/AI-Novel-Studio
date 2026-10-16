import type { ExperimentalClient } from './api';
export type SyncRow = { id: string; version: number; status: string; channel_id: string; sequence: number; operation: string; chapter_id?: string; target_chapter_id?: string; source_version: number; envelope_digest: string; attempts?: number; error_code?: string; selection_withdrawn?: boolean };
export type SyncChannel = { id: string; version: number; status: string; stream_id: string; endpoint_id: string; peer_id: string; chapter_ids: string[]; allow_new_chapters: boolean; send_cursor: number; receive_cursor: number; withdrawn_chapter_ids?: string[] };
export type SyncCatalog = { chapters: { id: string; title: string; version: number }[]; truncated: boolean; network_enabled: false };
export type SyncRecords = { channels: SyncChannel[]; outbox: SyncRow[]; inbox: SyncRow[]; network_enabled: false };
export type SyncEnvelope = { protocol: 'AI_NOVEL_SYNC_1'; stream_id: string; source_endpoint: string; destination_endpoint: string; message_id: string; sequence: number; source_chapter_id: string; source_version: number; operation: 'SNAPSHOT' | 'TOMBSTONE'; base: { title: string; document: unknown }; snapshot: { title: string; document: unknown } | null; privacy_level: 'LOCAL_ONLY' };
export type SyncExport = SyncRow & { envelope: SyncEnvelope };
export type SyncChoices = Record<string, 'LOCAL' | 'INCOMING'>;
export type SyncPlan = { message_id: string; version: number; preview_digest: string; current: unknown; base: unknown; incoming: unknown; desired: unknown; unresolved: number; can_apply: boolean; choices: SyncChoices; blocked: string[]; operation: string; segments: { id?: string; kind: string; reason?: string; base?: unknown; nodes?: unknown; local?: unknown; incoming?: unknown; choice?: string }[] };
export type SyncRecovery = { id: string; version: number; status: string; observations: { chapter_id: string; version: number; state: string; document: unknown }[]; can_adopt: boolean; retry_allowed: false; preview_digest: string };
export type SyncSelection = { add_chapter_ids: string[]; withdraw_chapter_ids: string[] };
export type SyncSelectionPlan = { channel_id: string; version: number; additions: { id: string; title: string; version: number; document: unknown }[]; withdraw_chapter_ids: string[]; preview_digest: string; copy_boundary: string };
const p = '/offline-sync';
export function offlineSyncClient(client: ExperimentalClient) {
  return {
    catalog: (signal?: AbortSignal) => client.get<SyncCatalog>(p + '/catalog', signal),
    records: (signal?: AbortSignal) => client.get<SyncRecords>(p + '/records', signal),
    open: (body: { stream_id: string; endpoint_id: string; peer_id: string; chapter_ids: string[]; allow_new_chapters: boolean }) => client.post<SyncChannel>(p + '/channels', body),
    revoke: (row: SyncChannel) => client.post<SyncChannel>(p + '/channels/' + encodeURIComponent(row.id) + '/revoke', { expected_version: row.version }),
    previewSelection: (row: SyncChannel, selection: SyncSelection) => client.post<SyncSelectionPlan>(p + '/channels/' + encodeURIComponent(row.id) + '/selection/preview', { expected_version: row.version, ...selection }),
    changeSelection: (row: SyncChannel, selection: SyncSelection, plan: SyncSelectionPlan) => client.post<SyncChannel>(p + '/channels/' + encodeURIComponent(row.id) + '/selection', { expected_version: row.version, ...selection, preview_digest: plan.preview_digest, confirmed: true }),
    queue: (row: SyncChannel, chapterId: string, requestId: string, tombstone: boolean) => client.post<SyncRow>(p + '/channels/' + encodeURIComponent(row.id) + '/queue', { expected_version: row.version, chapter_id: chapterId, request_id: requestId, tombstone }),
    inspect: (row: SyncRow) => client.get<SyncExport>(p + '/outbox/' + encodeURIComponent(row.id)),
    export: (row: SyncRow) => client.post<SyncExport>(p + '/outbox/' + encodeURIComponent(row.id) + '/export', { expected_version: row.version, envelope_digest: row.envelope_digest, acknowledge_copy_boundary: true }),
    delivery: (row: SyncRow, state: 'FAILED' | 'UNKNOWN' | 'ACKNOWLEDGED', receipt?: unknown) => client.post<SyncRow>(p + '/outbox/' + encodeURIComponent(row.id) + '/delivery', { expected_version: row.version, state, receipt: receipt ?? null }),
    receive: (row: SyncChannel, envelope: unknown, target: string, createNew: boolean) => client.post<SyncRow & { receipt: unknown; duplicate: boolean }>(p + '/channels/' + encodeURIComponent(row.id) + '/receive', { expected_version: row.version, envelope, target_chapter_id: target || null, create_new: createNew }),
    review: (row: SyncRow, choices: SyncChoices) => client.post<SyncPlan>(p + '/inbox/' + encodeURIComponent(row.id) + '/review', { expected_version: row.version, choices }),
    apply: (row: SyncRow, plan: SyncPlan) => client.post<SyncRow>(p + '/inbox/' + encodeURIComponent(row.id) + '/apply', { expected_version: row.version, choices: plan.choices, preview_digest: plan.preview_digest, confirmed: true }),
    recovery: (row: SyncRow, result?: SyncRecovery, closeWithoutReplay = false) => client.post<SyncRecovery>(p + '/inbox/' + encodeURIComponent(row.id) + '/recovery', { expected_version: row.version, adopt_matching_result: !!result && !closeWithoutReplay, close_without_replay: closeWithoutReplay, preview_digest: result?.preview_digest ?? null }),
  };
}
export type SyncApi = ReturnType<typeof offlineSyncClient>;
