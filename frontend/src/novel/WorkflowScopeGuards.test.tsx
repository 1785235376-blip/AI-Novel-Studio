// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, type CollaborationContext, type Scope } from "../api";
import { useStudio } from "../store";
import { WorkflowPanel } from "./WorkflowPanel";
import { AgentQueuePanel } from "./AgentQueuePanel";

function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const baseScope: Scope = { workspaceId: "workspace-a", projectId: "project-a", storylineId: "story-a", branchId: "branch-a" };
const baseActor = { id: "actor-a", workspaceId: "workspace-a", displayName: "Synthetic author" };
const context: CollaborationContext = { sessionToken: "synthetic-session-a", actor: baseActor, scope: baseScope };

beforeEach(() => {
  useStudio.getState().setCollaboration(context.sessionToken, { ...baseActor }, { ...baseScope });
  useStudio.setState({ textModel: { providerId: "synthetic", modelId: "fixture" } });
});
afterEach(() => {
  cleanup(); vi.restoreAllMocks();
  useStudio.getState().setCollaboration("");
  useStudio.setState({ textModel: null });
});

const changes = ["actor", "session", "workspaceId", "projectId", "storylineId", "branchId"] as const;
function switchIdentity(change: typeof changes[number]) {
  const token = change === "session" ? "synthetic-session-b" : context.sessionToken;
  const actor = change === "actor" ? { ...baseActor, id: "actor-b" } : { ...baseActor };
  const scope = { ...baseScope, ...(change !== "actor" && change !== "session" ? { [change]: "new-scope" } : {}) };
  act(() => useStudio.getState().setCollaboration(token, actor, scope));
}

it.each(changes)("workflow fences late list data after %s changes", async (change) => {
  const pending = deferred<{ items: any[] }>();
  const list = vi.spyOn(api, "workflows").mockReturnValueOnce(pending.promise).mockResolvedValue({ items: [] });
  render(<WorkflowPanel novelId="project-a" />);
  expect(list).toHaveBeenCalledWith("project-a", context);
  switchIdentity(change);
  await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  await act(async () => pending.resolve({ items: [{ id: "private-old", title: "PRIVATE OLD WORKFLOW" }] }));
  expect(screen.queryByText(/PRIVATE OLD WORKFLOW/)).toBeNull();
});

it.each(changes)("agent queue fences late list data after %s changes", async (change) => {
  const pending = deferred<{ items: any[] }>();
  const list = vi.spyOn(api, "agentQueue").mockReturnValueOnce(pending.promise).mockResolvedValue({ items: [] });
  render(<AgentQueuePanel novelId="project-a" />);
  expect(list).toHaveBeenCalledWith("project-a", context);
  switchIdentity(change);
  await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  await act(async () => pending.resolve({ items: [{ run_id: "PRIVATE_OLD_AGENT", node_id: "writer", status: "FAILED" }] }));
  expect(screen.queryByText(/PRIVATE_OLD_AGENT/)).toBeNull();
});

it("workflow rejects out-of-order refresh results in the same scope", async () => {
  const old = deferred<{ items: any[] }>();
  vi.spyOn(api, "workflows").mockReturnValueOnce(old.promise).mockResolvedValue({ items: [{ id: "new", title: "NEW WORKFLOW" }] });
  render(<WorkflowPanel novelId="project-a" />);
  fireEvent.click(screen.getByRole("button", { name: "加载中…" }));
  expect(await screen.findByText(/NEW WORKFLOW/)).toBeTruthy();
  await act(async () => old.resolve({ items: [{ id: "old", title: "OLD WORKFLOW" }] }));
  expect(screen.queryByText(/OLD WORKFLOW/)).toBeNull();
  expect(screen.getByText(/NEW WORKFLOW/)).toBeTruthy();
});

it("workflow rejects a prior selection's late runs in the same scope", async () => {
  const old = deferred<{ items: any[] }>();
  vi.spyOn(api, "workflows").mockResolvedValue({ items: [{ id: "a", title: "A" }, { id: "b", title: "B" }] });
  vi.spyOn(api, "workflowRuns").mockReturnValueOnce(old.promise).mockResolvedValue({ items: [{ id: "RUN_B", status: "SUCCEEDED" }] });
  render(<WorkflowPanel novelId="project-a" />);
  const buttons = await screen.findAllByRole("button", { name: "查看运行" });
  fireEvent.click(buttons[0]); fireEvent.click(buttons[1]);
  expect(await screen.findByText(/RUN_B/)).toBeTruthy();
  await act(async () => old.resolve({ items: [{ id: "PRIVATE_RUN_A", status: "FAILED" }] }));
  expect(screen.queryByText(/PRIVATE_RUN_A/)).toBeNull();
});

it.each(["resolve", "reject"] as const)("workflow create %s cannot refresh or modify a new scope", async (result) => {
  const pending = deferred<any>();
  const list = vi.spyOn(api, "workflows").mockResolvedValue({ items: [] });
  const create = vi.spyOn(api, "createWorkflow").mockReturnValue(pending.promise);
  render(<WorkflowPanel novelId="project-a" />);
  fireEvent.change(screen.getByLabelText("标题"), { target: { value: "PRIVATE INPUT" } });
  fireEvent.click(screen.getByRole("button", { name: "创建工作流" }));
  expect(create).toHaveBeenCalledWith(expect.objectContaining({ novel_id: "project-a", branch_id: "branch-a", title: "PRIVATE INPUT" }), context);
  switchIdentity("session");
  await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  await act(async () => result === "resolve" ? pending.resolve({}) : pending.reject(new Error("old operation")));
  expect(list).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole("alert")).toBeNull();
  expect((screen.getByLabelText("标题") as HTMLInputElement).value).toBe("小说质量检查");
  expect((screen.getByRole("button", { name: "创建工作流" }) as HTMLButtonElement).disabled).toBe(false);
});

it("a completed old-workflow mutation never reloads the new selection", async () => {
  const pending = deferred<any>();
  vi.spyOn(api, "workflows").mockResolvedValue({ items: [{ id: "a", title: "A" }, { id: "b", title: "B" }] });
  const runs = vi.spyOn(api, "workflowRuns").mockResolvedValue({ items: [] });
  const start = vi.spyOn(api, "createWorkflowRun").mockReturnValue(pending.promise);
  render(<WorkflowPanel novelId="project-a" />);
  const buttons = await screen.findAllByRole("button", { name: "查看运行" });
  fireEvent.click(buttons[0]);
  fireEvent.click(screen.getByRole("button", { name: "启动运行" }));
  expect(start).toHaveBeenCalledWith("a", expect.any(Object), context);
  fireEvent.click(buttons[1]);
  await act(async () => pending.resolve({}));
  expect(runs).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("heading", { name: "B 运行" })).toBeTruthy();
});

it.each(["resolve", "reject"] as const)("agent execute %s cannot refresh or leak errors after branch switch", async (result) => {
  const pending = deferred<any>();
  const list = vi.spyOn(api, "agentQueue").mockResolvedValue({ items: [{ run_id: "a", node_id: "writer", status: "QUEUED" }] });
  const execute = vi.spyOn(api, "executeWorkflowAgent").mockReturnValue(pending.promise);
  render(<AgentQueuePanel novelId="project-a" />);
  fireEvent.click(await screen.findByRole("button", { name: "执行所选模型" }));
  expect(execute).toHaveBeenCalledWith("a", "writer", { chapter: 1, provider_id: "synthetic", model_id: "fixture" }, context);
  switchIdentity("branchId");
  await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  await act(async () => result === "resolve" ? pending.resolve({}) : pending.reject(new Error("old operation")));
  expect(list).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole("alert")).toBeNull();
  expect((screen.getByRole("button", { name: "执行所选模型" }) as HTMLButtonElement).disabled).toBe(false);
});

it("agent queue ignores older refresh errors and remains ready", async () => {
  const pending = deferred<{ items: any[] }>();
  vi.spyOn(api, "agentQueue").mockReturnValueOnce(pending.promise).mockResolvedValue({ items: [] });
  render(<AgentQueuePanel novelId="project-a" />);
  fireEvent.click(screen.getByRole("button", { name: "加载中…" }));
  await screen.findByRole("button", { name: "刷新队列" });
  await act(async () => pending.reject(new Error("late old error")));
  expect(screen.queryByRole("alert")).toBeNull();
});
