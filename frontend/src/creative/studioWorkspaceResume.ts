/** Local-author navigation hint. Original owners must re-read every restored ID.
 * No drafts, prompts, outputs, tokens, credentials or execution receipts are stored.
 * Authenticated/collaboration sessions must not consult this local-author key.
 */
import type { LocalStudioModule } from '../workspaceSelection';

const key = 'studio.workspace-resume.v1:local-author:file';
export type StudioWorkspaceView = 'ASSETS' | 'GRAPH' | 'PRODUCTION';
export type StudioWorkspaceStage = 'M4' | 'M5' | 'M6' | 'M7' | 'M8' | 'M9';
export type StudioWorkspaceLocation = {
  module: LocalStudioModule;
  view: StudioWorkspaceView;
  stage: StudioWorkspaceStage;
  graphId?: string;
  runId?: string;
};
export type StudioWorkspaceResume = { state: 'EMPTY' | 'INVALID' | 'UNAVAILABLE' }
  | { state: 'SAVED'; location: StudioWorkspaceLocation };
const validId = (value: unknown): value is string => typeof value === 'string' && !!value.trim()
  && value.length <= 240 && !/[\u0000-\u001f\u007f]/.test(value);
const modules = ['IMAGE', 'VIDEO', 'AUDIO', 'ASSETS'];
const views = ['ASSETS', 'GRAPH', 'PRODUCTION'];
const stages = ['M4', 'M5', 'M6', 'M7', 'M8', 'M9'];
const fields = ['schema', 'mode', 'actor', 'project_id', 'module', 'view', 'stage', 'graph_id', 'run_id'];

export function readLocalStudioResume(projectId: string, storage?: Pick<Storage, 'getItem'>): StudioWorkspaceResume {
  if (!validId(projectId)) return { state: 'INVALID' };
  try {
    const value = (storage ?? globalThis.localStorage).getItem(key);
    if (!value) return { state: 'EMPTY' };
    if (value.length > 2048) return { state: 'INVALID' };
    const row: unknown = JSON.parse(value);
    if (!row || typeof row !== 'object' || Array.isArray(row)) return { state: 'INVALID' };
    const record = row as Record<string, unknown>;
    if (Object.keys(record).some(field => !fields.includes(field)) || record.schema !== 1
      || record.mode !== 'local' || record.actor !== 'local-author' || !validId(record.project_id)
      || !modules.includes(record.module as string) || !views.includes(record.view as string)
      || !stages.includes(record.stage as string)
      || ('graph_id' in record && !validId(record.graph_id)) || ('run_id' in record && !validId(record.run_id))
      || ('run_id' in record && !('graph_id' in record))) return { state: 'INVALID' };
    if (record.project_id !== projectId) return { state: 'EMPTY' };
    return { state: 'SAVED', location: {
      module: record.module as LocalStudioModule, view: record.view as StudioWorkspaceView,
      stage: record.stage as StudioWorkspaceStage,
      ...(typeof record.graph_id === 'string' ? { graphId: record.graph_id } : {}),
      ...(typeof record.run_id === 'string' ? { runId: record.run_id } : {}),
    } };
  } catch { return { state: 'UNAVAILABLE' }; }
}

export function rememberLocalStudioResume(projectId: string, location: StudioWorkspaceLocation,
  storage?: Pick<Storage, 'setItem'>): boolean {
  if (!validId(projectId) || !modules.includes(location.module) || !views.includes(location.view)
    || !stages.includes(location.stage) || (location.graphId !== undefined && !validId(location.graphId))
    || (location.runId !== undefined && (!validId(location.runId) || !location.graphId))) return false;
  try {
    (storage ?? globalThis.localStorage).setItem(key, JSON.stringify({
      schema: 1, mode: 'local', actor: 'local-author', project_id: projectId,
      module: location.module, view: location.view, stage: location.stage,
      ...(location.graphId === undefined ? {} : { graph_id: location.graphId }),
      ...(location.runId === undefined ? {} : { run_id: location.runId }),
    }));
    return true;
  } catch { return false; }
}
