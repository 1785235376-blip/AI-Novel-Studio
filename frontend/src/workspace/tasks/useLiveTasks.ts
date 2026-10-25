/**
 * [HERMIA-FE-20261025 U3-M3/M4] Builds TaskFeed/TaskNavigator from the REAL session (store token/actor/scope) through
 * the existing owners (createTaskCenterClient + studioProductionClient read methods only). No identity ⇒ readers=null
 * ⇒ "not connected". A new lease per (identity key, novel) so A→B→A drops late responses. hasNode reads the local canvas draft only.
 */
import {useEffect, useMemo} from 'react';
import {createTaskCenterClient} from '../../taskcenter/taskCenterClient';
import {studioTransport} from '../../creative/studioClient';
import {studioProductionClient} from '../../creative/studioProductionClient';
import type {CollaborationContext} from '../../api';
import {createScopeLease} from '../state/scopeLease';
import {TaskFeed, type TaskReaders} from './taskFeed';
import {TaskNavigator} from './taskNavigation';

export function canvasHasNode(storage: Pick<Storage, 'getItem'> | null, novelId: string, canvas: 'creative' | 'execution', nodeId: string): boolean {
  try {
    const raw = storage?.getItem(`poemseed.rebuild.canvas.${canvas === 'creative' ? 'image' : 'video'}.${novelId}`);
    const nodes = raw ? (JSON.parse(raw) as {nodes?: {id?: unknown}[]}).nodes : null;
    return Array.isArray(nodes) && nodes.some(n => n?.id === nodeId);
  } catch { return false; }
}

export function useLiveTasks(novelId: string | null, ctx: CollaborationContext | null, identityKey: string | null) {
  const built = useMemo(() => {
    if (!novelId || !ctx || !identityKey) return {feed: new TaskFeed(null, null), navigator: null as TaskNavigator | null, lease: null};
    const lease = createScopeLease(`${identityKey}|${novelId}`);
    const tc = createTaskCenterClient(novelId, studioTransport(ctx), ctx.scope);
    const pc = studioProductionClient(novelId, ctx);
    const readers: TaskReaders = {taskCenter: {readTasks: (f, s) => tc.readTasks(f, s)}, production: {list: s => pc.list(s), get: (o, id, s) => pc.get(o, id, s)}};
    return {feed: new TaskFeed(readers, lease), navigator: new TaskNavigator(lease), lease};
  }, [novelId, ctx, identityKey]);
  useEffect(() => () => built.lease?.retire(), [built]);
  return built;
}
