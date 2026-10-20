import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../../api';
import type { StudioClient } from '../../creative/studioClient';
import type { ProductionJob, StudioProductionClient } from '../../creative/studioProductionClient';
import type { CanvasImageTaskOrigin } from '../../creative/canvasImageTask';
import { assertExecutionJob, inspectApprovedAsset, projectExecution, type ExecutionSelection } from './executionProvenanceModel';

export type ExecutionProvenanceProps = {
  selection: ExecutionSelection;
  production: Pick<StudioProductionClient, 'get'>;
  assets?: Pick<StudioClient, 'asset'>;
  active: boolean;
  denied: boolean;
  busy?: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>;
  /** Original host capture only. Persistent origin is read from the original Job command, never inferred from an asset. */
  origin?: CanvasImageTaskOrigin;
  isOriginCurrent?: () => boolean;
  onUnavailable?: () => void;
};

type ExecutionView = ReturnType<typeof projectExecution>;
type ApprovedAsset = ReturnType<typeof inspectApprovedAsset>;
type View = { token: object; execution?: ExecutionView; approved?: ApprovedAsset; assetNote?: string; error?: string };
type Request = { token: object; controller: AbortController };

// Receipt comparison, not a second execution identity or persistence store.
function canonical(value: unknown): string {
  const order = (item: unknown): unknown => Array.isArray(item) ? item.map(order)
    : item && typeof item === 'object' ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b)).map(([key, entry]) => [key, order(entry)])) : item;
  return JSON.stringify(order(value));
}

/** GET-only observer. It cannot dispatch, retry, review, reconcile or adopt. */
export function useExecutionProvenance(props: ExecutionProvenanceProps) {
  const latest = useRef(props); latest.current = props;
  const current = props.isCurrent();
  const key = JSON.stringify([props.selection, props.active, props.denied, !!props.busy, current, props.origin]);
  const fence = useRef({ key, production: props.production, assets: props.assets, token: {} });
  if (fence.current.key !== key || fence.current.production !== props.production || fence.current.assets !== props.assets) {
    fence.current = { key, production: props.production, assets: props.assets, token: {} };
  }
  const token = fence.current.token;
  const authKey = JSON.stringify([props.selection.projectId, props.selection.branchId, props.selection.identity]);
  const auth = useRef({ key: authKey, production: props.production, assets: props.assets, token: {} });
  if (auth.current.key !== authKey || auth.current.production !== props.production || auth.current.assets !== props.assets) {
    auth.current = { key: authKey, production: props.production, assets: props.assets, token: {} };
  }
  const receiptKey = JSON.stringify(props.selection);
  const receiptFence = useRef({ key: receiptKey, auth: auth.current.token, token: {} });
  if (receiptFence.current.key !== receiptKey || receiptFence.current.auth !== auth.current.token) {
    receiptFence.current = { key: receiptKey, auth: auth.current.token, token: {} };
  }
  const receiptToken = receiptFence.current.token;
  const alive = useRef(false), revoked = useRef<object>(), running = useRef<Request>();
  const receipt = useRef<{ token: object; job: ProductionJob }>();
  const [view, setView] = useState<View>(), [pending, setPending] = useState<Request>();
  const permitted = () => alive.current && token === fence.current.token && revoked.current !== auth.current.token
    && latest.current.active && !latest.current.denied && !latest.current.busy && latest.current.isCurrent();
  const valid = (request: Request) => permitted() && running.current === request && !request.controller.signal.aborted;

  async function load() {
    if (!permitted() || running.current) return;
    const request: Request = { token, controller: new AbortController() }, origin = latest.current;
    running.current = request; setPending(request); setView(undefined);
    try {
      const job = await origin.read(() => {
        if (!valid(request)) throw new Error('READ_RETIRED');
        return origin.production.get(origin.selection.job.owner, origin.selection.job.id, request.controller.signal);
      }, request.controller.signal);
      if (!valid(request)) return;
      assertExecutionJob(job, origin.selection);
      const previous = receipt.current?.token === receiptToken ? receipt.current.job : undefined;
      if (previous && (job.version < previous.version || job.version === previous.version && canonical(job) !== canonical(previous))) {
        throw new Error('RECEIPT_CHANGED_WITHOUT_VERSION');
      }
      if (previous && (['operation_id', 'sources', 'command', 'provider', 'execution_recipe', 'timeline_snapshot'] as const)
        .some(field => canonical(previous[field]) !== canonical(job[field]))) throw new Error('IMMUTABLE_REQUEST_CHANGED');
      receipt.current = { token: receiptToken, job: structuredClone(job) };
      const execution = projectExecution(job);
      let approved: ApprovedAsset | undefined, assetNote: string | undefined;
      if (job.status === 'APPROVED' && job.output_candidate) {
        assetNote = '原 Job 记录已审核入库；尚未核验当前正式资产元数据。';
        if (origin.assets) {
          try {
            const asset = await origin.read(() => {
              if (!valid(request)) throw new Error('READ_RETIRED');
              return origin.assets!.asset(job.output_candidate!.id, request.controller.signal);
            }, request.controller.signal);
            if (!valid(request)) return;
            approved = inspectApprovedAsset(job, asset, origin.selection);
            assetNote = '当前正式资产与原审核版本、摘要一致；这不代表已采用到作品。';
          } catch (reason) {
            if (!valid(request)) return;
            // Withheld asset metadata never replaces the Job's recorded candidate pin.
            assetNote = reason instanceof ApiError && [401, 403, 404].includes(reason.status)
              ? '正式资产不可读、已移除或无权限；未补全资产详情。'
              : '正式资产版本或摘要已变化，或元数据核验失败；未将当前资产替代原审核版本。';
          }
        }
      }
      if (valid(request)) setView({ token, execution, approved, assetNote });
    } catch (reason) {
      if (!valid(request)) return;
      const denied = reason instanceof ApiError && [401, 403].includes(reason.status);
      if (denied) revoked.current = auth.current.token;
      setView({ token, error: denied ? '原任务读取被拒绝，请核对项目与身份。旧来源已隐藏。'
        : reason instanceof ApiError && reason.status === 404 ? '原任务不存在或当前不可读。未补造执行来源。'
          : '来源读取失败、范围不符或回执版本已变化。请在原任务核对；不会重新发送。' });
      if (denied) origin.onUnavailable?.();
    } finally {
      if (running.current === request) {
        running.current = undefined;
        if (alive.current) setPending(undefined);
      }
    }
  }

  useLayoutEffect(() => {
    alive.current = true;
    return () => { alive.current = false; running.current?.controller.abort(); running.current = undefined; };
  }, []);
  useLayoutEffect(() => {
    if (running.current?.token !== token) {
      running.current?.controller.abort(); running.current = undefined; setPending(undefined);
    }
  }, [token]);

  return { load, view: current && props.active && !props.denied && view?.token === token ? view : undefined,
    pending: pending?.token === token, blocked: !current || !props.active || props.denied || !!props.busy || revoked.current === auth.current.token };
}
