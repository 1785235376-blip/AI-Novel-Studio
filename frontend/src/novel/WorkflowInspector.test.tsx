// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { WorkflowInspector } from "./WorkflowInspector";

it("renders a safe workflow failure summary", () => {
  render(<WorkflowInspector novelId="novel-1" inspection={{ kind: "run", id: "run-1", status: "FAILED", workflowTitle: "质量检查", currentNodeId: "review", error: "节点超时" }}/>);
  expect(screen.getByText("质量检查")).toBeTruthy();
  expect(screen.getByText("review")).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("节点超时");
});

it("marks dock-only selection as pending refresh", () => {
  render(<WorkflowInspector novelId="novel-1" inspection={{ kind: "agent", id: "run-2:draft", status: "FAILED", pendingRefresh: true }}/>);
  expect(screen.getByText(/详细记录尚未加载/)).toBeTruthy();
  expect(screen.getByText("run-2:draft")).toBeTruthy();
});
