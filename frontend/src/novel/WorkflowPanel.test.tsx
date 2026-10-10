// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { FOCUS_FAILED_TASKS_EVENT, TASK_SUMMARY_EVENT } from "../ui/taskSummary";
import { WorkflowPanel } from "./WorkflowPanel";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("publishes loaded workflow runs and focuses their real workspace", async () => {
  vi.spyOn(api, "workflows").mockResolvedValue({
    items: [{ id: "flow-1", title: "质量检查", status: "ACTIVE" }],
  });
  vi.spyOn(api, "workflowRuns").mockResolvedValue({
    items: [{ id: "run-1", workflow_id: "flow-1", status: "FAILED", error: "节点超时" }],
  });
  const summaries: any[] = [];
  const listener = (event: Event) => summaries.push((event as CustomEvent).detail);
  window.addEventListener(TASK_SUMMARY_EVENT, listener);
  const inspect = vi.fn();
  render(<WorkflowPanel novelId="novel-1" onInspect={inspect} />);
  fireEvent.click(await screen.findByRole("button", { name: "查看运行" }));
  expect(await screen.findByText(/run-1/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "检查" }));
  expect(inspect).toHaveBeenCalledWith(expect.objectContaining({ kind: "run", id: "run-1", status: "FAILED", error: "节点超时" }));
  await waitFor(() =>
    expect(summaries.at(-1)).toMatchObject({
      source: "workflow",
      summary: { failed: 1, failures: [{ id: "run-1", error: "节点超时" }] },
    }),
  );
  window.dispatchEvent(
    new CustomEvent(FOCUS_FAILED_TASKS_EVENT, {
      detail: { source: "workflow", taskId: "run-1" },
    }),
  );
  await waitFor(() =>
    expect(document.activeElement).toBe(screen.getByLabelText("工作流运行记录")),
  );
  window.removeEventListener(TASK_SUMMARY_EVENT, listener);
});

it("creates a bounded recipe and exposes reject beside real approval", async () => {
  vi.spyOn(api, "workflows").mockResolvedValue({items:[{id:"recipe-flow",title:"资料审核",status:"ACTIVE"}]});
  vi.spyOn(api,"workflowRuns").mockResolvedValue({items:[{id:"recipe-run",status:"WAITING_APPROVAL",node_states:{review:{status:"WAITING_APPROVAL",output:null}}}]});
  const create=vi.spyOn(api,"createWorkflowRecipe").mockResolvedValue({});
  const reject=vi.spyOn(api,"rejectWorkflowNode").mockResolvedValue({});
  render(<WorkflowPanel novelId="novel-1" />);
  fireEvent.change(screen.getByLabelText("模板"),{target:{value:"recipe:import_knowledge"}});
  fireEvent.click(screen.getByRole("button",{name:"创建工作流"}));
  await waitFor(()=>expect(create).toHaveBeenCalledWith("import_knowledge","novel-1",undefined));
  fireEvent.click(await screen.findByRole("button",{name:"查看运行"}));
  fireEvent.click(await screen.findByRole("button",{name:"拒绝并停止"}));
  await waitFor(()=>expect(reject).toHaveBeenCalledWith("recipe-run","review"));
  expect(screen.getByLabelText("运行 recipe-run 结果")).toBeTruthy();
});
