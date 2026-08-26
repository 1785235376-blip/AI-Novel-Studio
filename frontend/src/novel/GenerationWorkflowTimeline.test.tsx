// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GenerationWorkflowTimeline, timelineSteps } from "./GenerationWorkflowTimeline";

describe("GenerationWorkflowTimeline", () => {
  it("keeps every phase waiting before a real request starts", () => {
    expect(timelineSteps({}).map((step) => step.state)).toEqual(["waiting", "waiting", "waiting", "waiting"]);
  });

  it("maps a real running job to completed admission stages and active generation", () => {
    const steps = timelineSteps({ drafts: [{ id: "job-1", output: "", status: "working" }] });
    expect(steps.map((step) => step.state)).toEqual(["complete", "complete", "active", "waiting"]);
    expect(steps[2].detail).toBe("草稿生成中");
  });

  it("moves a completed job into author review", () => {
    const steps = timelineSteps({ drafts: [{ id: "job-1", output: "草稿", status: "ready" }] });
    expect(steps.map((step) => step.state)).toEqual(["complete", "complete", "complete", "active"]);
  });

  it("shows restored runtime state without claiming a new task", () => {
    render(<GenerationWorkflowTimeline recovering drafts={[{ id: "job-1", output: "", status: "working" }]} />);
    expect(screen.getByText("已恢复任务")).toBeTruthy();
    expect(screen.getByText("草稿生成中")).toBeTruthy();
  });

  it("keeps successful variants reviewable and retries the failed variant", async () => {
    const onRetry = vi.fn();
    const failed = { id: "job-2", variantIndex: 2, output: "", status: "failed" as const, error: "模型连接失败" };
    render(<GenerationWorkflowTimeline drafts={[{ id: "job-1", output: "可用", status: "ready" }, failed]} onRetry={onRetry} />);
    expect(screen.getByText("1 个可审核，1 个失败")).toBeTruthy();
    expect(screen.getByText("模型连接失败")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "重试方案 2" }));
    expect(onRetry).toHaveBeenCalledWith(failed);
  });

  it("reports cancellation from the real task state", () => {
    const steps = timelineSteps({ cancelled: true });
    expect(steps.slice(0, 2).map((step) => step.state)).toEqual(["complete", "complete"]);
    expect(steps[2].state).toBe("cancelled");
    expect(steps[2].detail).toBe("任务已由用户停止");
  });

  it("does not claim a backend task for a preflight failure", () => {
    const steps = timelineSteps({ drafts: [{ id: "selection-required", output: "", status: "failed", tracked: false }] });
    expect(steps.slice(0, 2).map((step) => step.state)).toEqual(["waiting", "waiting"]);
    expect(steps[2].state).toBe("failed");
  });
});
