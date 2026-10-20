import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { productionStageProjection } from './studioWorkspaceOperationContract';
import { STUDIO_PRODUCTION_STAGES, type StudioProductionStageId, type StudioOperationSurfaceState,
  type StudioOperationReadProblem, type StudioWorkspaceProductionContracts } from './studioWorkspaceOperationTypes';

export type StudioWorkspaceOperationControllerProps = {
  identity: string; denied: boolean; busy: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  loadContracts: (signal?: AbortSignal) => Promise<StudioWorkspaceProductionContracts>;
  requestedStage?: StudioProductionStageId;
  onStageChange?: (stage: StudioProductionStageId) => void; onUnavailable?: () => void;
};

/** GET and local selection only. The skin receives state/actions; no JSX owns authority. */
export function useStudioWorkspaceOperations(props: StudioWorkspaceOperationControllerProps) {
  const [contracts, setContracts] = useState<StudioWorkspaceProductionContracts>();
  const [state, setState] = useState<StudioOperationSurfaceState>('IDLE');
  const [problem, setProblem] = useState<StudioOperationReadProblem>();
  const [selectedStage, setSelectedStage] = useState<StudioProductionStageId>(props.requestedStage ?? 'M4');
  const alive = useRef(true), epoch = useRef(0), pending = useRef(false), revoked = useRef(false);
  const abort = useRef<AbortController>(), identity = useRef(props.identity), latest = useRef(props);
  latest.current = props; identity.current = props.identity;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; abort.current?.abort(); }; }, []);

  const reload = useCallback(async () => {
    const captured = latest.current, requestIdentity = captured.identity;
    if (!alive.current || pending.current || revoked.current || captured.denied || captured.busy || !captured.isCurrent()) return;
    const request = ++epoch.current, controller = new AbortController(); abort.current?.abort(); abort.current = controller;
    pending.current = true; setContracts(undefined); setProblem(undefined); setState('LOADING');
    const current = () => alive.current && request === epoch.current && identity.current === requestIdentity
      && !revoked.current && !latest.current.denied && captured.isCurrent();
    try {
      const value = await captured.read(() => captured.loadContracts(controller.signal));
      if (current()) { setContracts(value); setState(value.operations.length ? 'READY' : 'EMPTY'); }
    } catch (reason) {
      if (current() && !controller.signal.aborted) {
        const error = apiErrorView(reason, '制作操作契约读取失败，请稍后重新核对。');
        setContracts(undefined); setProblem({ code: reason instanceof ApiError ? reason.problem.code : 'STUDIO_CONTRACT_READ_FAILED', message: error.message });
        if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
          revoked.current = true; setState('DENIED'); captured.onUnavailable?.();
        } else setState(reason instanceof ApiError && [404, 409].includes(reason.status) ? 'UNAVAILABLE' : 'ERROR');
      }
    } finally { if (request === epoch.current) pending.current = false; }
  }, []);

  useEffect(() => {
    epoch.current++; abort.current?.abort(); pending.current = false; revoked.current = props.denied;
    setContracts(undefined); setProblem(undefined); setState(props.denied ? 'DENIED' : 'IDLE');
    setSelectedStage(props.requestedStage ?? 'M4');
    if (!props.denied) void reload();
  }, [props.identity, props.denied, reload]);
  useEffect(() => { if (props.requestedStage && STUDIO_PRODUCTION_STAGES.includes(props.requestedStage)) setSelectedStage(props.requestedStage); }, [props.requestedStage]);

  const selectStage = useCallback((stage: StudioProductionStageId) => {
    if (!STUDIO_PRODUCTION_STAGES.includes(stage) || !alive.current || latest.current.denied || revoked.current || !latest.current.isCurrent()) return;
    setSelectedStage(stage); latest.current.onStageChange?.(stage);
  }, []);
  return { state, problem, contracts, selectedStage, stage: productionStageProjection(contracts, selectedStage),
    canRead: !props.denied && !revoked.current && !props.busy && state !== 'LOADING', reload, selectStage };
}
