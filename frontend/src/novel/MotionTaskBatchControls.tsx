import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button } from "../ui/primitives";
import { FOCUS_FAILED_TASKS_EVENT, publishTaskSummary } from "../ui/taskSummary";

export type MotionTaskLike = { id: string; status?: string; error?: string };

export function summarizeMotionTasks(tasks: MotionTaskLike[]) {
  return tasks.reduce((summary, task) => {
    const key = String(task.status || "UNKNOWN").toUpperCase();
    summary.total += 1;
    if (key === "PENDING") summary.pending += 1;
    else if (key === "RUNNING" || key === "PROCESSING") summary.running += 1;
    else if (key === "SUCCEEDED" || key === "COMPLETED") summary.succeeded += 1;
    else if (key === "FAILED" || key === "ERROR") summary.failed += 1;
    else if (key === "CANCELLED" || key === "CANCELED") summary.cancelled += 1;
    else summary.unknown += 1;
    return summary;
  }, { total: 0, pending: 0, running: 0, succeeded: 0, failed: 0, cancelled: 0, unknown: 0 });
}

export function MotionTaskBatchControls({ novelId, screenplayId, tasks, onComplete }: { novelId?: string; screenplayId?: string; tasks: MotionTaskLike[]; onComplete?: () => void }) {
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");
  const executeButton = useRef<HTMLButtonElement>(null);
  const summary = summarizeMotionTasks(tasks);
  useEffect(() => { publishTaskSummary("motion", tasks); }, [tasks]);
  useEffect(() => { const listener = (event: Event) => { const detail = (event as CustomEvent).detail; if (detail?.source === "motion") { const target = detail.taskId ? tasks.find((task) => String(task.id) === String(detail.taskId)) : undefined; setMessage(target ? `已定位任务 ${target.id}，请检查失败状态并刷新或重试。` : "已定位到视频任务，请检查失败状态并刷新或重试。"); requestAnimationFrame(() => executeButton.current?.focus()); } }; window.addEventListener(FOCUS_FAILED_TASKS_EVENT, listener); return () => window.removeEventListener(FOCUS_FAILED_TASKS_EVENT, listener); }, [tasks]);
  const executable = tasks.filter((task) => String(task.status || "").toUpperCase() === "PENDING");
  async function executeBatch() {
    if (!novelId || !screenplayId || executable.length === 0 || running) return;
    setRunning(true); setMessage("");
    const results = await Promise.allSettled(executable.map((task) => api.executeMotionTask(novelId, screenplayId, task.id)));
    const failed = results.filter((result) => result.status === "rejected").length;
    setMessage(failed ? `已提交 ${executable.length - failed} 个任务，${failed} 个任务提交失败。` : `已提交 ${executable.length} 个任务，正在刷新状态。`);
    setRunning(false);
    onComplete?.();
  }
  return <section className="novel-help" aria-label="批量视频任务">
    <strong>批量任务</strong>
    <p>共 {summary.total} 个 · 待执行 {summary.pending} · 执行中 {summary.running} · 成功 {summary.succeeded} · 失败 {summary.failed} · 已取消 {summary.cancelled}</p>
    <Button ref={executeButton} variant="ghost" disabled={!novelId || !screenplayId || executable.length === 0 || running} onClick={executeBatch}>{running ? "批量提交中..." : `批量执行待处理任务（${executable.length}）`}</Button>
    {message && <p role="status">{message}</p>}
  </section>;
}
