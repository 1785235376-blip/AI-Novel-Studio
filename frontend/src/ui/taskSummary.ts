export type TaskLifecycle = "queued" | "running" | "succeeded" | "failed";
export type TaskFailure = { id: string; error?: string };
export type TaskSummary = { total: number; queued: number; running: number; succeeded: number; failed: number; failures?: TaskFailure[] };

export function normalizeTaskLifecycle(status: unknown): TaskLifecycle {
  const value = String(status || "").toUpperCase();
  if (["RUNNING", "GENERATING", "RETRYING", "PROCESSING"].includes(value)) return "running";
  if (["SUCCEEDED", "SUCCESS", "COMPLETED", "DONE"].includes(value)) return "succeeded";
  if (["FAILED", "ERROR", "CANCELLED"].includes(value)) return "failed";
  return "queued";
}

export function summarizeTasks(tasks: Array<{ id?: string; task_id?: string; status?: unknown; error?: unknown }>): TaskSummary {
  const summary: TaskSummary = { total: tasks.length, queued: 0, running: 0, succeeded: 0, failed: 0, failures: [] };
  tasks.forEach((task, index) => { const lifecycle = normalizeTaskLifecycle(task.status); summary[lifecycle] += 1; if (lifecycle === "failed") summary.failures!.push({ id: String((task as any).id || (task as any).task_id || `task-${index + 1}`), error: typeof (task as any).error === "string" ? (task as any).error : undefined }); });
  return summary;
}

export function mergeTaskSummaries(...summaries: TaskSummary[]): TaskSummary {
  return summaries.reduce((total, current) => ({
    total: total.total + current.total,
    queued: total.queued + current.queued,
    running: total.running + current.running,
    succeeded: total.succeeded + current.succeeded,
    failed: total.failed + current.failed,
    failures: [...(total.failures || []), ...(current.failures || [])],
  }), { total: 0, queued: 0, running: 0, succeeded: 0, failed: 0 });
}

export const TASK_SUMMARY_EVENT = "studio:task-summary";
export const FOCUS_FAILED_TASKS_EVENT = "studio:focus-failed-tasks";
export function requestFailedTaskFocus(source: string, taskId?: string) {
  window.dispatchEvent(new CustomEvent(FOCUS_FAILED_TASKS_EVENT, { detail: { source, taskId } }));
}
export function publishTaskSummary(source: string, tasks: Array<{ id?: string; task_id?: string; status?: unknown; error?: unknown }>) {
  window.dispatchEvent(new CustomEvent(TASK_SUMMARY_EVENT, { detail: { source, summary: summarizeTasks(tasks) } }));
}
