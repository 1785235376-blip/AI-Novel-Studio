// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { FOCUS_FAILED_TASKS_EVENT, TASK_SUMMARY_EVENT } from "../ui/taskSummary";
import { AgentQueuePanel } from "./AgentQueuePanel";

afterEach(() => vi.restoreAllMocks());

it("publishes agent queue failures and focuses the matching task", async () => {
  vi.spyOn(api, "agentQueue").mockResolvedValue({
    items: [{ run_id: "run-2", node_id: "draft", agent_role: "writer", status: "FAILED", error: "执行失败" }],
  });
  const summaries: any[] = [];
  const listener = (event: Event) => summaries.push((event as CustomEvent).detail);
  window.addEventListener(TASK_SUMMARY_EVENT, listener);
  const inspect = vi.fn();
  render(<AgentQueuePanel novelId="novel-1" onInspect={inspect} />);
  expect(await screen.findByText(/运行 run-2/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "检查" }));
  expect(inspect).toHaveBeenCalledWith(expect.objectContaining({ kind: "agent", id: "run-2:draft", nodeId: "draft", error: "执行失败" }));
  await waitFor(() =>
    expect(summaries.at(-1)).toMatchObject({
      source: "agent",
      summary: { failed: 1, failures: [{ id: "run-2:draft", error: "执行失败" }] },
    }),
  );
  window.dispatchEvent(
    new CustomEvent(FOCUS_FAILED_TASKS_EVENT, {
      detail: { source: "agent", taskId: "run-2:draft" },
    }),
  );
  await waitFor(() =>
    expect(document.activeElement).toBe(
      document.querySelector('[data-task-id="run-2:draft"]'),
    ),
  );
  window.removeEventListener(TASK_SUMMARY_EVENT, listener);
});
