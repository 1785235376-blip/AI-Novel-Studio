import type { StudioModule } from '../ui/AppShell';
import type { CollaborationContext } from '../api';
import { ApiError } from '../api';
import type { HostRoute } from './client';

export function currentInteropSurface(module: StudioModule, panel: string, experimentalTab?: string): string {
  if (module === 'CONTROL') return 'model-center';
  if (module === 'WORKFLOW') return 'workflow';
  if (module === 'VIDEO') return 'screenplay';
  if (module !== 'NOVEL') return 'media';
  const panels: Record<string, string> = { history: 'editor', editor: 'editor', story: 'world', creation: 'world', diagnostics: 'error-panel', agents: 'task-center', screenplay: 'screenplay', exports: 'export', workflow: 'workflow', assets: 'media', settings: 'settings' };
  if (panel === 'experimental') return experimentalTab === 'story_simulator_v2' ? 'story-simulator' : experimentalTab === 'model_broker_v2' ? 'model-center' : experimentalTab === 'local_ai_workflow_inspector_v2' ? 'local-ai' : 'editor';
  return panels[panel] ?? 'editor';
}

/** Defense in depth: an authorized host response is still not an arbitrary URI. */
export function assertCurrentHandoff(route: HostRoute, context: CollaborationContext, projectId: string) {
  const scope = context.scope;
  if (!context.sessionToken || !scope || !route.scope || route.project_id && route.project_id !== projectId)
    throw new ApiError({ status: 403, code: 'PERMISSION_DENIED', message: '' });
  if (route.scope && (route.scope.workspace_id !== scope.workspaceId || route.scope.project_id !== scope.projectId
    || route.scope.storyline_id !== scope.storylineId || route.scope.branch_id !== scope.branchId))
    throw new ApiError({ status: 403, code: 'PERMISSION_DENIED', message: '' });
  if (!['OPEN_FEATURE', 'OPEN_PROJECT', 'OPEN_CHAPTER', 'OPEN_TASK'].includes(route.action))
    throw new ApiError({ status: 422, code: 'HANDOFF_TARGET_NOT_FOUND', message: '' });
}

export const interopFeatureRoutes: Record<string, { module: StudioModule; panel?: string; controlTab?: 'models'; experimental?: string }> = {
  editor: { module: 'NOVEL', panel: 'history' },
  'model-center': { module: 'CONTROL', controlTab: 'models' },
  'task-center': { module: 'NOVEL', panel: 'agents' },
  'error-panel': { module: 'NOVEL', panel: 'diagnostics' },
  'story-simulator': { module: 'NOVEL', panel: 'experimental', experimental: 'story_simulator_v2' },
  world: { module: 'NOVEL', panel: 'story' },
  screenplay: { module: 'NOVEL', panel: 'screenplay' },
  media: { module: 'ASSETS' }, export: { module: 'NOVEL', panel: 'exports' },
  'local-ai': { module: 'CONTROL', controlTab: 'models' },
  workflow: { module: 'WORKFLOW' }, settings: { module: 'NOVEL', panel: 'settings' },
};
