// [HERMIA-FE-20261024 M6] TaskCenter alerts show human text only. The raw problem code (e.g. STUDIO_REQUEST_FAILED)
// is never rendered as visible text; callers keep it in a data-error-code attribute for diagnostics.
import type { TaskCenterProblem } from './taskCenterTypes';

export const TASK_CENTER_PROBLEM_FALLBACK = '请求没有完成，请稍后点「重新读取」。';
const RAW_CODE = /^[A-Z][A-Z0-9_]*$/;

export function problemText(problem: TaskCenterProblem | undefined): string {
  const message = (problem?.message ?? '').trim();
  if (!message || RAW_CODE.test(message) || (problem?.code && message === problem.code)) return TASK_CENTER_PROBLEM_FALLBACK;
  return message;
}
