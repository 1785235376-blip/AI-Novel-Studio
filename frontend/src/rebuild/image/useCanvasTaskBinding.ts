import {useEffect, useState, useSyncExternalStore} from 'react';
import {getCollaborationEpoch, subscribeCollaborationContext} from '../../api';
import {useLocalHostSession} from '../../localHostSession';
import {useStudio} from '../../store';
import {useScopedRequestConsent} from '../../useScopedRequestConsent';
import {canvasTaskBindingKey, captureCanvasTaskOwner, readCanvasTaskBinding, subscribeCanvasTaskBindings} from './canvasTaskBinding';

const identity = (state: ReturnType<typeof useStudio.getState>) => JSON.stringify([
  state.sessionToken, state.actor?.id, state.actor?.workspaceId, state.scope?.workspaceId,
  state.scope?.projectId, state.scope?.storylineId, state.scope?.branchId, state.novelId,
]);

/** Persisted IDs are navigation hints; request/session fences and server reads remain authoritative. */
export function useCanvasTaskBinding(novelId: string, nodeId: string) {
  const {scopeKey} = useScopedRequestConsent([]);
  const hostEpoch = useLocalHostSession(state => state.epoch);
  const clientEpoch = useSyncExternalStore(subscribeCollaborationContext, getCollaborationEpoch, getCollaborationEpoch);
  const [scopeEpoch, setScopeEpoch] = useState(0);
  const [storageRevision, setStorageRevision] = useState(0);
  useEffect(() => {
    let observed = identity(useStudio.getState());
    return useStudio.subscribe(state => {
      const next = identity(state);
      if (next !== observed) { observed = next; setScopeEpoch(value => value + 1); }
    });
  }, []);
  useEffect(() => subscribeCanvasTaskBindings(() => setStorageRevision(value => value + 1)), []);
  const owner = captureCanvasTaskOwner(novelId);
  const binding = owner ? readCanvasTaskBinding(owner, nodeId) : undefined;
  const sessionKey = JSON.stringify([owner ? canvasTaskBindingKey(owner, nodeId) : null, scopeKey,
    scopeEpoch, hostEpoch, clientEpoch, binding?.taskId, storageRevision]);
  return {owner, binding, sessionKey};
}
