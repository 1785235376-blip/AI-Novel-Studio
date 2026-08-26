// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorldBuildingDashboard } from "./WorldBuildingDashboard";

afterEach(cleanup);
const data = {
  characters: [{ id: "lin", name: "林海" }, { id: "su", name: "苏夜" }],
  locations: [{ id: "port", name: "雾港" }],
  relationships: [{ id: "r1", source_character_id: "lin", target_character_id: "su", relationship_type: "盟友", valid_from_event_id: "e1", status: "ACTIVE" }],
  timeline: [{ id: "e1", sequence: 2, title: "港口封锁", time: "冬至夜", location: "port", characters: ["lin"], chapter_id: "chapter-2", status: "DISPUTED" }],
  foreshadowing: [{ id: "f1", title: "破损罗盘", planted_chapter: 1, target_chapter: 8, characters: ["lin"], events: ["e1"], status: "OPEN" }],
};

describe("WorldBuildingDashboard", () => {
  it("renders real relationship names and opens the existing editor", () => {
    const onOpen = vi.fn(); render(<WorldBuildingDashboard {...data} onOpen={onOpen} />);
    expect(screen.getAllByText("林海").length).toBeGreaterThan(0); expect(screen.getAllByText("苏夜").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("list", { name: "角色关系图" }).querySelector("button")!); expect(onOpen).toHaveBeenCalledWith("relationships", "r1");
  });
  it("orders real events and shows conflict state", () => {
    render(<WorldBuildingDashboard {...data} timeline={[data.timeline[0], { id: "e0", sequence: 1, title: "抵达" }]} onOpen={vi.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: /故事时间线/ }));
    expect(screen.getByText("抵达")).toBeTruthy(); expect(screen.getAllByText("DISPUTED").length).toBeGreaterThan(0);
  });
  it("shows planted chapter, linked events and resolved status without inventing appearances", () => {
    render(<WorldBuildingDashboard {...data} foreshadowing={[{ ...data.foreshadowing[0], status: "PAID_OFF" }]} onOpen={vi.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: /伏笔追踪/ }));
    expect(screen.getByText("第 1 章")).toBeTruthy(); expect(screen.getByText("港口封锁")).toBeTruthy(); expect(screen.getByText("已解决")).toBeTruthy(); expect(screen.queryByText("第 8 章再次出现")).toBeNull();
  });
  it("covers loading, empty and failed source states", () => {
    const { rerender } = render(<WorldBuildingDashboard loading onOpen={vi.fn()} />); expect(screen.getByRole("status").textContent).toContain("正在读取");
    rerender(<WorldBuildingDashboard onOpen={vi.fn()} />); expect(screen.getByText("还没有角色关系数据")).toBeTruthy();
    rerender(<WorldBuildingDashboard errors={{ relationships: "人物关系读取失败" }} onOpen={vi.fn()} />); expect(screen.getByRole("alert").textContent).toContain("人物关系读取失败");
  });
});
