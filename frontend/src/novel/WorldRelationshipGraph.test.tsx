// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorldRelationshipGraph } from "./WorldRelationshipGraph";

afterEach(cleanup);

const records = {
  characters: [
    { id: "lin", name: "林海", role: "调查员", status: "ALIVE" },
    { character_id: "su", title: "苏夜", state: "MISSING" },
  ],
  timeline: [{ id: "e1", title: "港口封锁" }, { event_id: "e2", event: "解除封锁" }],
  relationships: [{ id: "r1", source_character_id: "lin", target_character_id: "su", relationship_type: "FRIEND", description: "共同调查", status: "ACTIVE", certainty: "CONFIRMED", valid_from_event_id: "e1", valid_to_event_id: "e2" }],
};

describe("WorldRelationshipGraph", () => {
  it("renders real character, relationship, event and state fields", () => {
    render(<WorldRelationshipGraph {...records} onOpen={vi.fn()} />);
    expect(screen.getByRole("list", { name: "人物关系邻接列表" }).textContent).toContain("林海");
    expect(screen.getByText("朋友")).toBeTruthy();
    expect(screen.getByText(/港口封锁 → 解除封锁/)).toBeTruthy();
    expect(screen.getAllByText("有效").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /苏夜.*失踪/ })).toBeTruthy();
  });

  it("opens existing records and supports arrow-key node navigation", () => {
    const onOpen = vi.fn();
    render(<WorldRelationshipGraph {...records} onOpen={onOpen} />);
    const lin = screen.getByRole("button", { name: /林海，调查员/ });
    const su = screen.getByRole("button", { name: /苏夜，状态/ });
    lin.focus(); fireEvent.keyDown(lin, { key: "ArrowRight" }); expect(document.activeElement).toBe(su);
    fireEvent.click(su); expect(onOpen).toHaveBeenCalledWith("characters", "su");
    fireEvent.click(screen.getByRole("list", { name: "人物关系邻接列表" }).querySelector("button")!);
    expect(onOpen).toHaveBeenCalledWith("relationships", "r1");
  });

  it("supports compatible aliases and does not fabricate missing details", () => {
    render(<WorldRelationshipGraph characters={[{ id: "a", name: "甲" }]} relationships={[{ id: "alias", source_id: "a", target_id: "b", type: "宿敌" }]} onOpen={vi.fn()} />);
    expect(screen.getByText("宿敌")).toBeTruthy(); expect(screen.getAllByText("b").length).toBeGreaterThan(0);
    expect(screen.queryByText(/关联事件：/)).toBeNull(); expect(screen.queryByText(/共同调查/)).toBeNull();
  });

  it("shows honest empty states for characters without relationships and no data", () => {
    const { rerender } = render(<WorldRelationshipGraph characters={[{ id: "a", name: "甲" }]} onOpen={vi.fn()} />);
    expect(screen.getByText("角色已建立，尚未保存人物关系。")).toBeTruthy();
    rerender(<WorldRelationshipGraph onOpen={vi.fn()} />);
    expect(screen.getByText("还没有角色关系")).toBeTruthy();
  });
});
