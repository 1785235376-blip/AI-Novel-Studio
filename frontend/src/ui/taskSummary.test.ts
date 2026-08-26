// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mergeTaskSummaries, normalizeTaskLifecycle, publishTaskSummary, requestFailedTaskFocus, summarizeTasks, FOCUS_FAILED_TASKS_EVENT, TASK_SUMMARY_EVENT } from "./taskSummary";

describe("task summary", () => {
  it("normalizes provider lifecycle values", () => {
    expect(normalizeTaskLifecycle("GENERATING")).toBe("running");
    expect(normalizeTaskLifecycle("COMPLETED")).toBe("succeeded");
    expect(normalizeTaskLifecycle("FAILED")).toBe("failed");
    expect(normalizeTaskLifecycle("CANCELLED")).toBe("cancelled");
    expect(normalizeTaskLifecycle("QUEUED")).toBe("queued");
  });
  it("summarizes and merges tasks", () => {
    expect(summarizeTasks([{ status: "queued" }, { status: "RUNNING" }, { id: "img-1", status: "FAILED", error: "超时" }])).toMatchObject({ total: 3, queued: 1, running: 1, succeeded: 0, failed: 1, failures: [{ id: "img-1", error: "超时" }] });
    expect(mergeTaskSummaries(summarizeTasks([{ status: "DONE" }]), summarizeTasks([{ status: "ERROR" }]))).toMatchObject({ total: 2, succeeded: 1, failed: 1 });
    expect(summarizeTasks([{status:"CANCELLED"}])).toMatchObject({cancelled:1,failed:0,failures:[]});
  });
  it("publishes a source summary", () => {
    const received: any[] = [];
    const listener = (event: Event) => received.push((event as CustomEvent).detail);
    window.addEventListener(TASK_SUMMARY_EVENT, listener);
    publishTaskSummary("image", [{ status: "RUNNING" }]);
    window.removeEventListener(TASK_SUMMARY_EVENT, listener);
    expect(received[0]).toMatchObject({ source: "image", summary: { total: 1, running: 1 } });
  });
  it("requests focus for a failed-task source", () => {
    let source = "";
    const listener = (event: Event) => { source = (event as CustomEvent).detail.source; };
    window.addEventListener(FOCUS_FAILED_TASKS_EVENT, listener);
    requestFailedTaskFocus("motion", "motion-1");
    window.removeEventListener(FOCUS_FAILED_TASKS_EVENT, listener);
    expect(source).toBe("motion");
  });
});
