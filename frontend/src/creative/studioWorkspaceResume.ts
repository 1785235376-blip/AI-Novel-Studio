/** Local-author navigation hint. Original owners must re-read every restored ID.
 * No drafts, prompts, outputs, tokens, credentials or execution receipts are stored.
 * Authenticated/collaboration sessions must not consult this local-author key.
 */
import type { LocalStudioModule } from '../workspaceSelection';

const key = 'studio.workspace-resume.v1:local-author:file';
export type StudioWorkspaceView = 'START' | 'ASSETS' | 'GRAPH' | 'PRODUCTION' | 'TASKS';
export type StudioWorkspaceStage = 'M4' | 'M5' | 'M6' | 'M7' | 'M8' | 'M9';
/** Presentation-only density. Both modes share the same project, assets, tasks,
 * graph and drafts; switching never converts, copies or deletes production data. */
export type StudioInterfaceMode = 'NOVICE' | 'PROFESSIONAL';
/** Today's full workspace is the default: adding a presentation mode must never
 * change an existing user's interface or hide a feature they already use.
 * Novice mode is an explicit opt-in from the entry panel or the mode switch. */
export const DEFAULT_STUDIO_INTERFACE_MODE: StudioInterfaceMode = 'PROFESSIONAL';
export type StudioWorkspaceLocation = {
  module: LocalStudioModule;
  view: StudioWorkspaceView;
  stage: StudioWorkspaceStage;
  graphId?: string;
  runId?: string;
  interfaceMode?: StudioInterfaceMode;
};
export type StudioWorkspaceResume = { state: 'EMPTY' | 'INVALID' | 'UNAVAILABLE' }
  | { state: 'SAVED'; location: StudioWorkspaceLocation };
const validId = (value: unknown): value is string => typeof value === 'string' && !!value.trim()
  && value.length <= 240 && !/[\u0000-\u001f\u007f]/.test(value);
const modules = ['IMAGE', 'VIDEO', 'AUDIO', 'ASSETS'];
const views = ['START', 'ASSETS', 'GRAPH', 'PRODUCTION', 'TASKS'];
const stages = ['M4', 'M5', 'M6', 'M7', 'M8', 'M9'];
const modes = ['NOVICE', 'PROFESSIONAL'];
const fields = ['schema', 'mode', 'actor', 'project_id', 'module', 'view', 'stage', 'graph_id', 'run_id', 'interface_mode'];

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
      || ('interface_mode' in record && !modes.includes(record.interface_mode as string))
      || ('run_id' in record && !('graph_id' in record))) return { state: 'INVALID' };
    if (record.project_id !== projectId) return { state: 'EMPTY' };
    return { state: 'SAVED', location: {
      module: record.module as LocalStudioModule, view: record.view as StudioWorkspaceView,
      stage: record.stage as StudioWorkspaceStage,
      ...(typeof record.graph_id === 'string' ? { graphId: record.graph_id } : {}),
      ...(typeof record.run_id === 'string' ? { runId: record.run_id } : {}),
      ...(modes.includes(record.interface_mode as string) ? { interfaceMode: record.interface_mode as StudioInterfaceMode } : {}),
    } };
  } catch { return { state: 'UNAVAILABLE' }; }
}

/** Read only the saved presentation mode.
 *
 * An unusable, absent or older record yields the default, which is today's full
 * interface, so no existing workspace changes under its user.
 */
export function readLocalStudioInterfaceMode(projectId: string,
  storage?: Pick<Storage, 'getItem'>): StudioInterfaceMode {
  const resume = readLocalStudioResume(projectId, storage);
  if (resume.state !== 'SAVED') return DEFAULT_STUDIO_INTERFACE_MODE;
  return resume.location.interfaceMode ?? DEFAULT_STUDIO_INTERFACE_MODE;
}

/** Persist a mode change immediately by merging into the existing record.
 *
 * Returns false when no valid record exists yet: this never fabricates a
 * location, so the caller must also carry the mode into the next
 * `rememberLocalStudioResume` call instead of inventing module/view/stage.
 */
export function rememberLocalStudioInterfaceMode(projectId: string, mode: StudioInterfaceMode,
  storage?: Pick<Storage, 'getItem' | 'setItem'>): boolean {
  if (!validId(projectId) || !modes.includes(mode)) return false;
  const resume = readLocalStudioResume(projectId, storage);
  if (resume.state !== 'SAVED') return false;
  return rememberLocalStudioResume(projectId, { ...resume.location, interfaceMode: mode }, storage);
}

export function rememberLocalStudioResume(projectId: string, location: StudioWorkspaceLocation,
  storage?: Pick<Storage, 'setItem'>): boolean {
  if (!validId(projectId) || !modules.includes(location.module) || !views.includes(location.view)
    || !stages.includes(location.stage) || (location.graphId !== undefined && !validId(location.graphId))
    || (location.interfaceMode !== undefined && !modes.includes(location.interfaceMode))
    || (location.runId !== undefined && (!validId(location.runId) || !location.graphId))) return false;
  try {
    (storage ?? globalThis.localStorage).setItem(key, JSON.stringify({
      schema: 1, mode: 'local', actor: 'local-author', project_id: projectId,
      module: location.module, view: location.view, stage: location.stage,
      ...(location.graphId === undefined ? {} : { graph_id: location.graphId }),
      ...(location.runId === undefined ? {} : { run_id: location.runId }),
      ...(location.interfaceMode === undefined ? {} : { interface_mode: location.interfaceMode }),
    }));
    return true;
  } catch { return false; }
}
