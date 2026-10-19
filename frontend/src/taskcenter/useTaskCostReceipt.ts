import { useCallback, useEffect, useRef, useState } from 'react';
import type { TaskCenterControllerProps } from './useTaskCenter';
import type { TaskCenterTask } from './taskCenterTypes';
import { unknownCostReceipt, type TaskCostReceipt } from './taskCostReceiptHelpers';

type Selection = { companionEpoch: number; identity: string; task: TaskCenterTask; receipt?: TaskCostReceipt; loading: boolean };
/** One explicit selected read. No cache, polling, mutation, or automatic retry. */
export function useTaskCostReceipt(props: TaskCenterControllerProps, tasks: TaskCenterTask[], enabled: boolean) {
  const [selection, setSelection] = useState<Selection>();
  const companion = useRef({ client: props.costReceiptClient, epoch: 0 });
  if (companion.current.client !== props.costReceiptClient) {
    companion.current = { client: props.costReceiptClient, epoch: companion.current.epoch + 1 };
  }
  const companionEpoch = companion.current.epoch;
  const latest = useRef({ props, tasks, enabled, companionEpoch });
  latest.current = { props, tasks, enabled, companionEpoch };
  const request = useRef(0), abort = useRef<AbortController>();
  const close = useCallback(() => {
    request.current++; abort.current?.abort(); setSelection(undefined);
  }, []);
  useEffect(() => { close(); return () => { request.current++; abort.current?.abort(); }; },
    [props.identity, props.active, props.denied, props.costReceiptClient, enabled, tasks, close]);
  const read = useCallback(async (task: TaskCenterTask) => {
    const current = latest.current;
    const p = current.props;
    if (!current.enabled || !p.active || p.denied || p.busy || !p.isCurrent() || !current.tasks.includes(task)) return;
    abort.current?.abort();
    const controller = new AbortController(); abort.current = controller;
    const serial = ++request.current;
    setSelection({ identity: p.identity, companionEpoch: current.companionEpoch, task, loading: true });
    let receipt: TaskCostReceipt;
    try {
      receipt = p.costReceiptClient?.readCostReceipt
        ? await p.read(() => p.costReceiptClient!.readCostReceipt(task, controller.signal))
        : unknownCostReceipt('UNSUPPORTED');
    } catch { receipt = unknownCostReceipt('UNREADABLE'); }
    const next = latest.current;
    if (controller.signal.aborted || serial !== request.current || next.companionEpoch !== current.companionEpoch || next.props.identity !== p.identity
      || !next.enabled || !next.props.active || next.props.denied || !next.props.isCurrent()
      || !next.tasks.includes(task)) return;
    setSelection({ identity: p.identity, companionEpoch: current.companionEpoch, task, loading: false, receipt });
  }, []);
  // Render-time check prevents even a single old-identity frame before effects run.
  const visible = selection && enabled && props.active && !props.denied && props.isCurrent()
    && selection.identity === props.identity && selection.companionEpoch === companionEpoch && tasks.includes(selection.task) ? selection : undefined;
  return { selection: visible, read, close };
}
