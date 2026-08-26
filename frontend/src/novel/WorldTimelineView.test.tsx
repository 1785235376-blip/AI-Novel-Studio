// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorldTimelineView } from "./WorldTimelineView";

afterEach(cleanup);

const references = {
  characters: [{ id: "lin-hai", name: "林海" }, { id: "su-yan", name: "苏妍" }],
  locations: [{ id: "mist-port", name: "雾港" }],
  chapters: [{ id: "chapter-1", title: "第一章" }],
};

describe("WorldTimelineView", () => {
  it("sorts events stably by sequence and opens the real event id", () => {
    const onOpen = vi.fn();
    render(<WorldTimelineView {...references} onOpen={onOpen} timeline={[
      { id: "late", sequence: 2, title: "封锁解除", time: "冬夜", description: "港口恢复通行", location: "mist-port", characters: ["su-yan"], chapter_id: "chapter-1", status: "CONFIRMED" },
      { id: "first", sequence: 1, title: "雾港封锁", time: "黄昏", description: "城门关闭", location: "mist-port", characters: ["lin-hai"], chapter_id: "chapter-1", status: "PLANNED" },
      { id: "tie", sequence: 1, title: "同序事件", time: "黄昏后", description: "记录保留原顺序", location: "mist-port", characters: [], chapter_id: "chapter-1", status: "CONFIRMED" },
    ]} />);

    const buttons = screen.getAllByRole("button");
    expect(buttons[0].textContent).toContain("雾港封锁");
    expect(buttons[1].textContent).toContain("同序事件");
    expect(buttons[2].textContent).toContain("封锁解除");
    expect(screen.getByText("故事时间：黄昏")).toBeTruthy();
    expect(screen.getAllByText("地点：雾港").length).toBe(3);
    expect(screen.getByText("角色：林海")).toBeTruthy();
    expect(screen.getAllByText(/chapter_id：第一章（chapter-1）/).length).toBe(3);
    fireEvent.click(buttons[0]);
    expect(onOpen).toHaveBeenCalledWith("timeline", "first");
  });

  it("makes disputed events explicit and supports returning to the full scan", () => {
    render(<WorldTimelineView {...references} onOpen={vi.fn()} timeline={[
      { id: "disputed", sequence: 1, title: "记载冲突", time: "未知", description: "两个来源给出不同年份", status: "DISPUTED" },
      { id: "confirmed", sequence: 2, title: "已确认事件", time: "次日", description: "来源一致", status: "CONFIRMED" },
    ]} />);
    expect(screen.getByText("冲突待核实")).toBeTruthy();
    expect(screen.getAllByText("DISPUTED").length).toBe(2);
    fireEvent.change(screen.getByLabelText("状态筛选"), { target: { value: "DISPUTED" } });
    expect(screen.getByText("记载冲突")).toBeTruthy();
    expect(screen.queryByText("已确认事件")).toBeNull();
    fireEvent.change(screen.getByLabelText("状态筛选"), { target: { value: "ALL" } });
    expect(screen.getByText("已确认事件")).toBeTruthy();
  });

  it("uses truthful empty states for no records and an empty filter result", () => {
    const view = render(<WorldTimelineView {...references} onOpen={vi.fn()} timeline={[]} />);
    expect(screen.getByText("还没有时间线事件")).toBeTruthy();
    view.unmount();
    render(<WorldTimelineView {...references} onOpen={vi.fn()} timeline={[{ id: "one", sequence: 1, title: "唯一事件", status: "PLANNED" }, { id: "two", sequence: 2, title: "已确认事件", status: "CONFIRMED" }]} />);
    fireEvent.change(screen.getByLabelText("状态筛选"), { target: { value: "DISPUTED" } });
    expect(screen.getByText("没有符合筛选的事件")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("状态筛选"), { target: { value: "ALL" } });
    expect(screen.getByText("唯一事件")).toBeTruthy();
  });
});
