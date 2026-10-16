import { useCallback, useEffect, useRef, useState } from 'react';
import type { TaskCenterControllerProps } from './useTaskCenter';
import type { TaskCenterTask } from './taskCenterTypes';
import { unknownCostReceipt, type TaskCostReceipt } from './taskCostReceipt';

type Selection = { identity: string; task: TaskCenterTask; receipt?: TaskCostReceipt; loading: boolean };
/** One explicit selected read. No cache, polling, mutation, or automatic retry. */
export function useTaskCostReceipt(props: TaskCenterControllerProps, tasks: TaskCenterTask[], enabled: boolean) {
  const [selection, setSelection] = useState<Selection>();
  const latest = useRef({ props, tasks, enabled });
  latest.current = { props, tasks, enabled };
  const request = useRef(0), abort = useRef<AbortController>();
  const close = useCallback(() => {
    request.current++; abort.current?.abort(); setSelection(undefined);
  }, []);
  useEffect(() => { close(); return () => { request.current++; abort.current?.abort(); }; },
    [props.identity, props.active, props.denied, enabled, tasks, close]);
  const read = useCallback(async (task: TaskCenterTask) => {
    const current = latest.current;
    const p = current.props;
    if (!current.enabled || !p.active || p.denied || p.busy || !p.isCurrent() || !current.tasks.includes(task)) return;
    abort.current?.abort();
    const controller = new AbortController(); abort.current = controller;
    const serial = ++request.current;
    setSelection({ identity: p.identity, task, loading: true });
    let receipt: TaskCostReceipt;
    try {
      receipt = p.client.readCostReceipt
        ? await p.read(() => p.client.readCostReceipt!(task, controller.signal))
        : unknownCostReceipt('UNSUPPORTED');
    } catch { receipt = unknownCostReceipt('UNREADABLE'); }
    const next = latest.current;
    if (controller.signal.aborted || serial !== request.current || next.props.identity !== p.identity
      || !next.enabled || !next.props.active || next.props.denied || !next.props.isCurrent()
      || !next.tasks.includes(task)) return;
    setSelection({ identity: p.identity, task, loading: false, receipt });
  }, []);
  // Render-time check prevents even a single old-identity frame before effects run.
  const visible = selection && enabled && props.active && !props.denied && props.isCurrent()
    && selection.identity === props.identity && tasks.includes(selection.task) ? selection : undefined;
  return { selection: visible, read, close };
}
