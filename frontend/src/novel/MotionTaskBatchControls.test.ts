import { describe, expect, it } from "vitest";
import { summarizeMotionTasks } from "./MotionTaskBatchControls";

describe("summarizeMotionTasks", () => {
  it("汇总标准和兼容状态", () => {
    expect(summarizeMotionTasks([
      { id: "1", status: "PENDING" }, { id: "2", status: "RUNNING" },
      { id: "3", status: "SUCCEEDED" }, { id: "4", status: "FAILED" },
      { id: "5", status: "CANCELLED" }, { id: "6", status: "PROCESSING" },
    ])).toMatchObject({ total: 6, pending: 1, running: 2, succeeded: 1, failed: 1, cancelled: 1 });
  });
});
