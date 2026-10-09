import {useEffect, useMemo, useState} from 'react';
import {getCollaborationContext, type CollaborationContext} from './api';
import {localAiDiscoveryClient} from './localAiDiscoveryApi';
import {useLocalHostSession} from './localHostSession';
import {isPackagedDesktopHost} from './packagedHost';
import {useStudio} from './store';

export type LocalAiOnboardingOwner = {context: CollaborationContext; projectId?: string};
const signature = (context: CollaborationContext) => JSON.stringify([context.sessionToken, context.localHostToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
let observer = 0;
/** Opaque React owner key; credentials are never placed in query keys or storage. */
export function useLocalAiOwnerKey(owner?: LocalAiOnboardingOwner) {
  const epoch = useLocalHostSession(value => value.epoch);
  const contextKey = owner ? signature(owner.context) : '';
  return useMemo(() => owner ? `local-ai-owner-${++observer}` : 'legacy', [contextKey, owner?.projectId, epoch]);
}
/** Existing in-memory session owner, frozen for one mounted consumer. The
 * surrounding key remounts on identity/epoch changes; the synchronous guards
 * also reject responses during React transitions and switch-away/back races. */
export function useLocalAiDiscoveryOwner(origin: LocalAiOnboardingOwner) {
  const [invalidated, setInvalidated] = useState(false);
  const owner = useMemo(() => {
    const context = origin.context, host = useLocalHostSession.getState();
    const watchHost = !context.sessionToken && !context.scope && !context.actor && !isPackagedDesktopHost();
    const contextKey = signature(context), watchGlobal = contextKey === signature(getCollaborationContext());
    const projectId = origin.projectId, watchProject = projectId !== undefined && projectId === useStudio.getState().novelId;
    const captured = {...context, actor: context.actor && {...context.actor}, scope: context.scope && {...context.scope}, localHostToken: context.localHostToken ?? (watchHost ? host.token : '')};
    let revoked = false;
    const current = () => !revoked && (!watchHost || (host.epoch === useLocalHostSession.getState().epoch && host.token === useLocalHostSession.getState().token))
      && (!watchGlobal || contextKey === signature(getCollaborationContext())) && (!watchProject || projectId === useStudio.getState().novelId);
    return {client: localAiDiscoveryClient(captured, current), current, revoke: () => {revoked = true;}};
  }, []);
  useEffect(() => {
    const stop = useStudio.subscribe(() => {if (!owner.current()) {owner.revoke(); setInvalidated(true);}});
    // Content owns unmount/AbortController cleanup. Do not revoke identity on
    // StrictMode's synthetic cleanup/re-setup cycle.
    return stop;
  }, [owner]);
  return {...owner, invalidated};
}
