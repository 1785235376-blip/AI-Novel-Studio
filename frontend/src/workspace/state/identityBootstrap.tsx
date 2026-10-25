/**
 * [HERMIA-FE-20261025 U1fix] MUST-FIX 3: the ?uw=1 preview returned before LegacyApp's collaboration bootstrap ran,
 * so the actor was always empty and real identity / cold reopen were unreachable on the real page.
 * This runs the SAME existing bootstrap (api.bootstrap GET, same query key, same enable condition: session token or
 * packaged host + complete collaboration scope) and stores the SERVER-returned actor via store.setCollaboration,
 * exactly like LegacyApp (App.tsx bootstrap effect). No token/scope ⇒ nothing runs and the workspace stays
 * "仅本次会话". Never invents an actor.
 */
import {useEffect} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api} from '../../api';
import {useStudio} from '../../store';
import {recoveryKey} from '../../collaborationGuards';
import {isPackagedDesktopHost} from '../../packagedHost';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';

export function useCollaborationBootstrap() {
  const s = useStudio();
  const packagedHost = isPackagedDesktopHost();
  const namespace = recoveryKey(s.scope, s.sessionToken) || 'file';
  const complete = !!s.scope && !!s.scope.projectId && !!s.scope.storylineId && !!s.scope.branchId;
  const bootstrap = useQuery({queryKey: ['bootstrap', namespace], queryFn: () => api.bootstrap(s.scope!), enabled: (!!s.sessionToken || packagedHost) && complete, retry: false});
  useEffect(() => {
    const a = bootstrap.data?.actor;
    const cur = useStudio.getState();
    if (a && a.actor_id !== cur.actor?.id)
      cur.setCollaboration(cur.sessionToken, {id: a.actor_id, displayName: a.actor_id, workspaceId: bootstrap.data!.scope.workspace_id}, cur.scope);
  }, [bootstrap.data]);
  return bootstrap;
}

/** ?uw=1 host: existing bootstrap first, then the unified workspace. */
export function UnifiedWorkspacePreviewHost() {
  useCollaborationBootstrap();
  return <UnifiedWorkspacePreview />;
}
