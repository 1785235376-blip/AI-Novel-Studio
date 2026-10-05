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
