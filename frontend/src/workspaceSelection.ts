/** U01 discovery hint only. The original project list remains authoritative.
 * This local-author key is never consulted by authenticated/scoped sessions.
 * No session token, chapter reference, title or manuscript enters this record.
 */
const key = 'studio.workspace-selection.v1:local-author:file';
type Selection = { schema: 1; mode: 'local'; actor: 'local-author'; project_id: string };
export type SelectionRead = { state: 'EMPTY' | 'INVALID' | 'UNAVAILABLE' } | { state: 'SAVED'; projectId: string };
const validId = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 160;
export function readLocalWorkspaceSelection(storage?: Pick<Storage, 'getItem'>): SelectionRead {
  try {
    const value = (storage ?? globalThis.localStorage).getItem(key);
    if (!value) return { state: 'EMPTY' };
    const parsed = JSON.parse(value) as Selection;
    if (!parsed || parsed.schema !== 1 || parsed.mode !== 'local' || parsed.actor !== 'local-author'
      || !validId(parsed.project_id) || Object.keys(parsed).some(field => !['schema', 'mode', 'actor', 'project_id'].includes(field))) return { state: 'INVALID' };
    return { state: 'SAVED', projectId: parsed.project_id };
  } catch { return { state: 'UNAVAILABLE' }; }
}
export function rememberLocalWorkspaceSelection(projectId: string, storage?: Pick<Storage, 'setItem'>): boolean {
  if (!validId(projectId)) return false;
  try {
    (storage ?? globalThis.localStorage).setItem(key, JSON.stringify({ schema: 1, mode: 'local', actor: 'local-author', project_id: projectId } satisfies Selection));
    return true;
  } catch { return false; }
}

/** Optional local-author studio discovery hint. Never use this record to select
 * credentials, confer permission, activate a project, or bypass a server read.
 * It is deliberately independent of the original workspace-selection schema.
 */
const studioKey = 'studio.studio-selection.v1:local-author:file';
export type LocalStudioModule = 'IMAGE' | 'ASSETS' | 'VIDEO' | 'AUDIO';
type StudioSelection = {
  schema: 1; mode: 'local'; actor: 'local-author'; project_id: string;
  module: LocalStudioModule; asset_id?: string;
};
export type StudioSelectionRead = { state: 'EMPTY' | 'INVALID' | 'UNAVAILABLE' }
  | { state: 'SAVED'; projectId: string; module: LocalStudioModule; assetId?: string };
const validStudioId = (value: unknown): value is string => validId(value) && !!value.trim() && !/[\u0000-\u001f\u007f]/.test(value);
const validStudioModule = (value: unknown): value is LocalStudioModule =>
  value === 'IMAGE' || value === 'ASSETS' || value === 'VIDEO' || value === 'AUDIO';
const studioFields = ['schema', 'mode', 'actor', 'project_id', 'module', 'asset_id'];

export function readLocalStudioSelection(projectId: string, storage?: Pick<Storage, 'getItem'>): StudioSelectionRead {
  if (!validStudioId(projectId)) return { state: 'INVALID' };
  try {
    const value = (storage ?? globalThis.localStorage).getItem(studioKey);
    if (!value) return { state: 'EMPTY' };
    // Bound parsing and reject extra fields rather than retaining private data.
    if (value.length > 1024) return { state: 'INVALID' };
    let parsed: unknown;
    try { parsed = JSON.parse(value); } catch { return { state: 'INVALID' }; }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return { state: 'INVALID' };
    const record = parsed as Record<string, unknown>;
    if (record.schema !== 1 || record.mode !== 'local' || record.actor !== 'local-author'
      || !validStudioId(record.project_id) || !validStudioModule(record.module)
      || ('asset_id' in record && !validStudioId(record.asset_id))
      || Object.keys(record).some(field => !studioFields.includes(field))) return { state: 'INVALID' };
    if (record.project_id !== projectId) return { state: 'EMPTY' };
    return { state: 'SAVED', projectId, module: record.module,
      ...(typeof record.asset_id === 'string' ? { assetId: record.asset_id } : {}) };
  } catch { return { state: 'UNAVAILABLE' }; }
}

export function rememberLocalStudioSelection(projectId: string, module: LocalStudioModule, assetId?: string, storage?: Pick<Storage, 'setItem'>): boolean {
  if (!validStudioId(projectId) || !validStudioModule(module) || (assetId !== undefined && !validStudioId(assetId))) return false;
  try {
    const record: StudioSelection = { schema: 1, mode: 'local', actor: 'local-author', project_id: projectId, module,
      ...(assetId === undefined ? {} : { asset_id: assetId }) };
    (storage ?? globalThis.localStorage).setItem(studioKey, JSON.stringify(record));
    return true;
  } catch { return false; }
}
