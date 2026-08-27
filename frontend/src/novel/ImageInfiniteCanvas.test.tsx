// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ImageInfiniteCanvas,
  safeImagePreviewUri,
} from "./ImageInfiniteCanvas";
import type {
  CanvasViewport,
  RefNode,
} from "./useMultimodalWorkspacePersistence";

const initial: RefNode[] = [
  { id: "one", uri: "ref://one", role: "角色", x: 10, y: 10, z: 0 },
  { id: "two", uri: "ref://two", role: "场景", x: 320, y: 80, z: 1 },
];
function Harness({
  onNodes = vi.fn(),
}: {
  onNodes?: (nodes: RefNode[]) => void;
}) {
  const [nodes, setNodes] = useState(initial);
  const [viewport, setViewport] = useState<CanvasViewport>({
    x: 0,
    y: 0,
    zoom: 1,
  });
  const change = (value: React.SetStateAction<RefNode[]>) =>
    setNodes((current) => {
      const next = typeof value === "function" ? value(current) : value;
      onNodes(next);
      return next;
    });
  return (
    <ImageInfiniteCanvas
      nodes={nodes}
      onChange={change}
      viewport={viewport}
      onViewportChange={setViewport}
      undo={vi.fn()}
      redo={vi.fn()}
      canUndo
      canRedo
    />
  );
}
describe("ImageInfiniteCanvas", () => {
  afterEach(cleanup);
  it("selects a layer and deletes the selected unlocked node with the keyboard", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("角色 · ref://one"));
    fireEvent.keyDown(screen.getByLabelText("图片无限画布"), { key: "Delete" });
    expect(screen.queryByText("角色 · ref://one")).toBeNull();
    expect(screen.getByText("场景 · ref://two")).toBeTruthy();
  });
  it("keeps locked nodes when delete is pressed", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("角色 · ref://one"));
    fireEvent.click(screen.getByLabelText("锁定或解锁节点"));
    fireEvent.keyDown(screen.getByLabelText("图片无限画布"), { key: "Delete" });
    expect(screen.getByText("角色 · ref://one")).toBeTruthy();
  });
  it("deletes selected unlocked nodes from the visible toolbar control", () => {
    render(<Harness />);
    const remove = screen.getByLabelText("删除所选节点");
    expect((remove as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByText("角色 · ref://one"));
    expect((remove as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(remove);
    expect(screen.queryByText("角色 · ref://one")).toBeNull();
  });
  it("hides and restores a node from the layer list", () => {
    render(<Harness />);
    expect(document.querySelector('[data-node-id="one"]')).toBeTruthy();
    fireEvent.click(screen.getByLabelText("隐藏 ref://one"));
    expect(document.querySelector('[data-node-id="one"]')).toBeNull();
    fireEvent.click(screen.getByLabelText("显示 ref://one"));
    expect(document.querySelector('[data-node-id="one"]')).toBeTruthy();
  });
  it("changes zoom without resizing the canvas shell", () => {
    render(<Harness />);
    fireEvent.click(screen.getByLabelText("放大画布"));
    expect(screen.getByLabelText("画布缩放").textContent).toBe("115%");
  });
  it("renders only safe image preview schemes and reports failed loads", () => {
    const nodes: RefNode[] = [
      { ...initial[0], previewUri: "javascript:alert(1)" },
      { ...initial[1], previewUri: "https://example.test/safe.png" },
    ];
    function PreviewHarness() {
      const [value, setValue] = useState(nodes);
      return (
        <ImageInfiniteCanvas
          nodes={value}
          onChange={setValue}
          viewport={{ x: 0, y: 0, zoom: 1 }}
          onViewportChange={vi.fn()}
          undo={vi.fn()}
          redo={vi.fn()}
          canUndo={false}
          canRedo={false}
        />
      );
    }
    render(<PreviewHarness />);
    expect(safeImagePreviewUri("javascript:alert(1)")).toBeUndefined();
    expect(document.querySelector('img[src^="javascript:"]')).toBeNull();
    const image = document.querySelector(
      'img[src="https://example.test/safe.png"]',
    )!;
    fireEvent.error(image);
    expect(screen.getByText("预览失败")).toBeTruthy();
  });
});
