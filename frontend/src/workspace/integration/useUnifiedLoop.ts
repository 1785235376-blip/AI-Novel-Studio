// [HERMIA-FE-20261025 INT] 总控 wiring: builds U3 param session + U4 adopt/restore deps from the REAL existing clients and the
// SAME ScopeLease that the task feed uses (one lease system; no second state store). Nothing here executes, enqueues or adopts:
// it only constructs dependencies; every write remains behind the units' explicit user confirmation.
import {useEffect, useMemo, useState} from 'react';
import type {CollaborationContext} from '../../api';
import {studioClient} from '../../creative/studioClient';
import {studioProductionClient, type ProductionJob, type ProductionProvider} from '../../creative/studioProductionClient';
import type {ScopeLease} from '../contracts';
import type {AdoptDeps, AdoptTarget} from '../results/adoptFlow';
import type {RestoreDeps} from '../history/restoreFlow';
import {ParamSession} from '../params/paramSession';

export interface UnifiedLoop {
  u4: {adopt?: AdoptDeps; target?: AdoptTarget; restore?: RestoreDeps; canvasId?: string} | null;
  param: {session: ParamSession; title: string} | {gap: string} | null;
}

/** canvas_return binding is the only server link from a production job to a canvas card (G-U3-2). */
export function targetOf(job: ProductionJob | null): AdoptTarget | undefined {
  const b = job?.command?.canvas_return;
  if (!job || !b) return undefined;
  return {projectId: b.project_id, canvasId: b.canvas_id, cardId: b.card_id, job: {owner: job.owner, id: job.id, version: job.version, request_digest: job.request_digest}};
}

export function useUnifiedLoop(novelId: string | null, ctx: CollaborationContext | null, lease: ScopeLease | null, job: ProductionJob | null): UnifiedLoop {
  const clients = useMemo(() => (novelId && ctx ? {pc: studioProductionClient(novelId, ctx), sc: studioClient(novelId, ctx)} : null), [novelId, ctx]);
  const [providers, setProviders] = useState<ProductionProvider[] | null>(null);
  // Read-only provider catalogue, only once a production job is selected (no model call; GET /providers).
  useEffect(() => {
    if (!clients || !job || !lease || providers) return;
    const epoch = lease.epoch; let live = true;
    clients.pc.providers().then(p => { if (live && lease.isCurrent() && lease.epoch === epoch) setProviders(p); }, () => { if (live) setProviders([]); });
    return () => { live = false; };
  }, [clients, job, lease, providers]);
  useEffect(() => { setProviders(null); }, [clients, lease]);

  return useMemo<UnifiedLoop>(() => {
    if (!clients || !lease) return {u4: null, param: null};
    const canMutate = () => lease.isCurrent();
    const canvasViews = clients.sc.graphs.canvasViews;
    const asset: AdoptDeps['asset'] = async id => {
      const r = await clients.sc.assets(false);
      const a = r.items.find(x => x.id === id); if (!a) throw new Error('asset-missing'); return a;
    };
    const target = targetOf(job);
    const restore: RestoreDeps = {canvasViews, lease, canMutate};
    const adopt: AdoptDeps = {production: clients.pc, asset, canvasViews, lease, canMutate};
    let param: UnifiedLoop['param'] = null;
    if (job?.command) {
      const prov = providers?.find(p => p.provider_id === job.command!.provider_id && p.operation_id === job.command!.operation_id);
      param = prov ? {session: new ParamSession(clients.pc, prov, job.command, lease), title: '所选生产任务'}
        : providers ? {gap: '服务端没有返回这个任务对应的模型参数说明，不能在这里修改参数。'} : null;
    }
    return {u4: {adopt, target, restore, canvasId: target?.canvasId}, param};
  }, [clients, lease, job, providers]);
}
