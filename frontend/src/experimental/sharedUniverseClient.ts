import type { ExperimentalClient } from './api';
export type UniverseSource = { key: string; kind: string; title: string; source_digest: string; version?: number; references: string[] };
export type UniverseSnapshot = { id: string; version: number; status: string; snapshot_revision: number; snapshot_digest: string; universe_key?: string; title?: string; license?: string; content_withheld: boolean; source_changes: string[]; records?: Record<string, Record<string, unknown>> };
export type UniverseSnapshotInput = { universe_key: string; title: string; records: { key: string; source_digest: string }[]; license: string; allow_local_copy: true };
export type UniverseSnapshotPreview = { preview_digest: string; record_count: number; source_records: { key: string; source_digest: string; version?: number }[] };
export type UniverseRole = 'MAIN_NOVEL' | 'SEQUEL' | 'PREQUEL' | 'SIDE_STORY';
export type UniversePin = { id: string; version: number; status: string; content_withheld: boolean; universe_key?: string; snapshot_id?: string; snapshot_digest?: string; snapshot_revision?: number; target_project_id?: string; target_title?: string; role?: UniverseRole; history_versions?: number[]; source_changes?: string[] };
export type UniversePinInput = { snapshot_id: string; target_project_id: string; role: UniverseRole; expected_version: number };
export type UniversePinPreview = UniversePinInput & { preview_digest: string; previous_snapshot_id: string | null; snapshot_revision: number; target_title: string; source_changes: string[] };
export type IncomingUniversePin = { source_project_id: string; source_project_title: string; pin_id: string; pin_version: number; universe_key: string; snapshot_id: string; snapshot_revision: number; snapshot_digest: string; role: UniverseRole; source_changes: string[] };
export function sharedUniverseClient(client: ExperimentalClient) {
  const base = '/project-forks/universe';
  return {
    incoming: (signal?: AbortSignal) => client.get<{ items: IncomingUniversePin[]; truncated: boolean }>(base + '/incoming', signal),
    readIncoming: (pin: IncomingUniversePin) => client.get<{ snapshot: UniverseSnapshot; pin_version: number }>(`${base}/incoming/${encodeURIComponent(pin.source_project_id)}/${encodeURIComponent(pin.pin_id)}`),
    catalog: (signal?: AbortSignal) => client.get<{ records: UniverseSource[]; projects: { id: string; title: string }[]; truncated: boolean }>(base + '/catalog', signal),
    snapshots: (signal?: AbortSignal) => client.get<{ items: UniverseSnapshot[] }>(base + '/snapshots', signal),
    pins: (signal?: AbortSignal) => client.get<{ items: UniversePin[] }>(base + '/pins', signal),
    previewSnapshot: (input: UniverseSnapshotInput) => client.post<UniverseSnapshotPreview>(base + '/snapshot-preview', input),
    createSnapshot: (input: UniverseSnapshotInput, preview: UniverseSnapshotPreview, requestId: string) => client.post<UniverseSnapshot>(base + '/snapshots', { ...input, preview_digest: preview.preview_digest, request_id: requestId }),
    previewPin: (input: UniversePinInput) => client.post<UniversePinPreview>(base + '/pin-preview', input),
    pin: (input: UniversePinInput, preview: UniversePinPreview) => client.post<UniversePin>(base + '/pins', { ...input, preview_digest: preview.preview_digest, confirmed: true }),
    release: (row: UniversePin) => client.post<{ id: string; version: number; status: string }>(`${base}/pins/${encodeURIComponent(row.id)}/release`, { expected_version: row.version }),
  };
}
