import type { CollaborationContext } from '../api';
import type { HostRoute } from './client';

export type EditorSelection = { from: number; to: number; text: string; text_start?: number; text_end?: number };
export type LocalTutorProps = {
  context: CollaborationContext; projectId: string; module: string; surface: string;
  chapterId?: string; chapterVersion?: number; taskId?: string;
  selection?: EditorSelection; sourceReady: boolean;
  onNavigate: (route: HostRoute, signal: AbortSignal) => void | Promise<void>;
};
export function localTutorIdentity(props: LocalTutorProps) {
  const scope = props.context.scope;
  return JSON.stringify([props.context.sessionToken, props.context.actor?.id, props.context.actor?.workspaceId, scope?.workspaceId, scope?.projectId,
    scope?.storylineId, scope?.branchId, props.projectId, props.chapterId, props.module, props.surface, props.taskId]);
}
