import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import {
  DELIVERY_CODES, DELIVERY_NOTICES,
  type DeliveryAttempt, type DeliveryClient, type DeliveryProblem, type DeliveryReceipt,
  type DeliveryReceiptPage, type DeliveryRecovery, type DeliveryRequest, type DeliverySurfaceState,
} from './deliveryTypes';
import { receiptRecovery, receiptShowsSuccess } from './deliveryOps';

const READ_FAILURE = '导出交付读取失败，请稍后重新核对。';
const RECOVERY_FAILURE = '恢复读取未完成：原回执状态仍未确认，不会再次派发。';

export type DeliveryControllerProps = {
  /** 稳定的工作区/分支身份；变化会丢弃此前读到的一切。 */
  identity: string;
  /** 视图在屏幕上。关闭的视图永远不发起读取，也没有任何定时器。 */
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  /** 本目录只提供只读客户端：没有派发、取消或重试方法。 */
  client: DeliveryClient;
  onUnavailable?: () => void;
};

function problemOf(reason: unknown, fallback: string, fallbackCode: string): DeliveryProblem {
  // 只渲染传输层自己的有界文案；本地异常绝不原样回显。
  return reason instanceof ApiError
    ? { code: reason.problem.code, message: apiErrorView(reason, fallback).message }
    : { code: fallbackCode, message: fallback };
}

/** `EMPTY` 只表示"读成功且真的没有内容"；`DENIED` 永远优先于 `EMPTY`。 */
function surface(page: DeliveryReceiptPage | undefined, denied: boolean): DeliverySurfaceState {
  if (denied) return 'DENIED';
  if (!page) return 'IDLE';
  return page.items.length ? 'READY' : 'EMPTY';
}

/**
 * 导出交付控制器：**一次读取**，没有轮询、没有定时器、没有自动重试。
 *
 * 三条不可违反的性质：
 * 1. 视图关闭（`active === false`）或身份被撤销（`denied`）时不发起任何读取；
 * 2. 丢失/未知的回执永远不渲染成成功 —— `successful` 只可能是原 owner 的真实
 *    `succeeded` 回执；`trackAttempt()` 只登记"请求已经离开本机"，不发起任何网络调用；
 * 3. 恢复（`recover`）只能重新读取同一条原任务，绝不再次派发。
 */
export function useDelivery(props: DeliveryControllerProps) {
  const [page, setPage] = useState<DeliveryReceiptPage>();
  const [state, setState] = useState<DeliverySurfaceState>('IDLE');
  const [problem, setProblem] = useState<DeliveryProblem>();
  const [notice, setNotice] = useState('');
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);

  const alive = useRef(true), epoch = useRef(0), running = useRef(false), revoked = useRef(false);
  const abort = useRef<AbortController>();
  const latest = useRef(props);
  const attemptsRef = useRef(attempts);
  latest.current = props; attemptsRef.current = attempts;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; abort.current?.abort(); }; }, []);

  const admit = useCallback(() => alive.current && !revoked.current && latest.current.active
    && !latest.current.denied && latest.current.isCurrent(), []);

  const reload = useCallback(async () => {
    const captured = latest.current;
    if (!admit() || running.current || captured.busy) return;
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    const request = ++epoch.current;
    running.current = true;
    setProblem(undefined); setState('LOADING');
    try {
      const value = await captured.read(() => captured.client.readReceipts(controller.signal));
      if (request !== epoch.current || !admit()) return;
      setPage(value);
      // 读成功且确实没有内容才是 EMPTY；被拒绝的读取在 catch 里走 DENIED。
      setState(surface(value, false));
      setNotice('');
    } catch (reason) {
      if (request !== epoch.current || controller.signal.aborted || !alive.current) return;
      setProblem(problemOf(reason, READ_FAILURE, DELIVERY_CODES.readFailed));
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
        revoked.current = true;
        setPage(undefined); setAttempts([]);
        setState('DENIED');
        latest.current.onUnavailable?.();
      } else setState('FAILED');
    } finally { if (request === epoch.current) running.current = false; }
  }, [admit]);

  useEffect(() => {
    epoch.current++; abort.current?.abort(); running.current = false;
    revoked.current = props.denied;
    setPage(undefined); setProblem(undefined); setNotice(''); setAttempts([]);
    setState(props.denied ? 'DENIED' : 'IDLE');
  }, [props.identity, props.denied]);
  useEffect(() => { if (props.active && !props.denied) void reload(); }, [props.active, props.identity, props.denied, reload]);

  /**
   * 登记一次**已经发生**的派发（由原导出 owner 执行，本目录只记录参数）。
   * 这是一个纯粹的本地登记：不发起网络调用、不排队、不重试。
   */
  const trackAttempt = useCallback((request: DeliveryRequest, projectId: string) => {
    if (!alive.current || !latest.current.isCurrent()) return;
    setAttempts(previous => previous.some(entry => entry.request.idempotency_key === request.idempotency_key)
      ? previous.map(entry => entry.request.idempotency_key === request.idempotency_key ? { ...entry, request } : entry)
      : [...previous, { project_id: projectId, request, receipt: null }]);
  }, []);

  const recoveryFor = useCallback((attempt: DeliveryAttempt): DeliveryRecovery => receiptRecovery(attempt), []);
  const recoveryOfKey = useCallback((idempotencyKey: string): DeliveryRecovery => {
    const entry = attemptsRef.current.find(candidate => candidate.request.idempotency_key === idempotencyKey);
    return receiptRecovery(entry ?? { project_id: '', request: null, receipt: null });
  }, []);

  /**
   * 恢复：只重新读取原回执。优先按回执 id 读同一条任务；没有 id 时读取历史页，
   * 用**同一个幂等键**把原任务找回来。任何失败都不会触发第二次派发。
   */
  const recover = useCallback(async (idempotencyKey: string, jobId?: string) => {
    const captured = latest.current;
    if (!admit() || captured.busy) return;
    const entry = attemptsRef.current.find(candidate => candidate.request.idempotency_key === idempotencyKey);
    if (!entry) { setNotice(DELIVERY_NOTICES.readOnlyRecovery); return; }
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    const request = ++epoch.current;
    setProblem(undefined); setNotice('');
    try {
      const receipt: DeliveryReceipt = jobId
        ? await captured.read(() => captured.client.readReceipt(jobId, controller.signal))
        : await captured.read(async () => {
          const history = await captured.client.readReceipts(controller.signal);
          setPage(history);
          // 原 owner 用 (novel_id, idempotency_key, permission_context) 去重，因此"同格式且
          // 本次登记的请求"是历史里唯一可核对的匹配依据；找不到就是**没有回执**，
          // 绝不拿另一条任务冒充这一次的结果。
          const match = history.items.find(item => item.format === entry.request.format);
          if (!match) throw new ApiError({ status: 404, code: DELIVERY_CODES.receiptUnknown, message: '历史里还没有这次请求的回执。' });
          return match;
        });
      if (request !== epoch.current || !admit()) return;
      setAttempts(previous => previous.map(candidate => candidate.request.idempotency_key === idempotencyKey
        ? { ...candidate, receipt } : candidate));
      setNotice(receiptShowsSuccess(receipt)
        ? '已重新读取到原导出服务的回执：原 owner 判定为已完成。'
        : '已重新读取到原导出服务的回执：原 owner 未判定为完成，这里不会显示成功。');
    } catch (reason) {
      if (request !== epoch.current || controller.signal.aborted || !alive.current) return;
      const problem = problemOf(reason, RECOVERY_FAILURE, DELIVERY_CODES.receiptUnknown);
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
        revoked.current = true; setPage(undefined); setAttempts([]); setState('DENIED');
        latest.current.onUnavailable?.();
        return;
      }
      setProblem(problem);
      setNotice(`${problem.message}（原请求参数仍保留，本目录不会再次派发。）`);
    }
  }, [admit]);

  const receipts = page?.items ?? [];
  /**
   * "已确认成功"的唯一来源：原 owner 自己的 `succeeded` 回执 —— 来自历史页，或来自
   * 恢复时按 id 重新读到的同一条任务。未知/丢失/失败一例都不在其中。
   */
  const confirmed = [
    ...receipts,
    ...attempts.map(attempt => attempt.receipt).filter((entry): entry is DeliveryReceipt => entry !== null),
  ].filter(receiptShowsSuccess);
  return {
    state, problem, notice, page, receipts, attempts,
    /** 只有原 owner 的真实 succeeded 回执才会出现在这里。 */
    confirmedSuccessIds: [...new Set(confirmed.map(receipt => receipt.id))],
    canRead: !props.denied && !revoked.current && props.active && !props.busy && state !== 'LOADING',
    reload, trackAttempt, recover, recoveryFor, recoveryOfKey,
  };
}
export type DeliveryController = ReturnType<typeof useDelivery>;
