// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useMultimodalWorkspacePersistence } from "./useMultimodalWorkspacePersistence";

describe("useMultimodalWorkspacePersistence", () => {
  it("keeps at most five snapshots and restores the latest", () => {
    localStorage.clear();
    const { result } = renderHook(() =>
      useMultimodalWorkspacePersistence("test-workspace", [
        {
          shot_id: "shot-01",
          name: "默认镜头",
          duration: "3s",
          camera: "",
          action: "",
        },
      ]),
    );
    act(() => {
      result.current.setRefs([
        { id: "ref-1", uri: "ref://1", x: 0, y: 0, role: "角色", z: 0 },
      ]);
      result.current.snapshot();
    });
    act(() => result.current.clear());
    expect(result.current.snapshots.length).toBeGreaterThan(0);
    act(() => result.current.restore());
    expect(result.current.refs[0].uri).toBe("ref://1");
  });
  it("caps snapshot history at five entries", () => {
    localStorage.clear();
    const { result } = renderHook(() =>
      useMultimodalWorkspacePersistence("snapshot-cap", []),
    );
    for (let i = 0; i < 7; i += 1) act(() => result.current.snapshot());
    expect(result.current.snapshots).toHaveLength(5);
  });
  it("stores a note on a single clear snapshot", () => {
    localStorage.clear();
    const { result } = renderHook(() =>
      useMultimodalWorkspacePersistence("note-workspace", []),
    );
    act(() => result.current.clear("切换到新分镜"));
    expect(result.current.snapshots).toHaveLength(1);
    expect(result.current.snapshots[0].note).toBe("切换到新分镜");
  });
  it("imports references and shots from a constraint package", () => {
    const { result } = renderHook(() =>
      useMultimodalWorkspacePersistence("import-workspace", []),
    );
    act(() =>
      expect(
        result.current.importWorkspace({
          references: [{ uri: "ref://import", x: 1, y: 2, role: "场景" }],
          shots: [{ name: "导入镜头", duration: "3s", camera: "", action: "" }],
        }),
      ).toBe(true),
    );
    expect(result.current.refs[0].uri).toBe("ref://import");
    expect(result.current.shots[0].name).toBe("导入镜头");
  });
  it("rejects invalid constraint package shapes", () => {
    const { result } = renderHook(() =>
      useMultimodalWorkspacePersistence("invalid-import", []),
    );
    act(() =>
      expect(result.current.importWorkspace({ invalid: true })).toBe(false),
    );
    expect(result.current.refs).toEqual([]);
    expect(result.current.shots).toEqual([]);
  });
  it("migrates legacy references and persists the viewport", () => {
    localStorage.setItem(
      "legacy-canvas",
      JSON.stringify({
        refs: [{ uri: "ref://old", role: "角色", x: 4, y: 8 }],
        viewport: { x: 20, y: -10, zoom: 1.25 },
      }),
    );
    const { result } = renderHook(() =>
      useMultimodalWorkspacePersistence("legacy-canvas", []),
    );
    expect(result.current.refs[0].id).toMatch(/^ref-/);
    expect(result.current.refs[0].z).toBe(0);
    expect(result.current.viewport).toEqual({ x: 20, y: -10, zoom: 1.25 });
  });
  it("undoes and redoes reference edits", () => {
    const { result } = renderHook(() =>
      useMultimodalWorkspacePersistence("undo-canvas", []),
    );
    act(() =>
      result.current.setRefs([
        { id: "one", uri: "ref://one", role: "角色", x: 0, y: 0, z: 0 },
      ]),
    );
    act(() =>
      result.current.setRefs((items) =>
        items.map((item) => ({ ...item, x: 120 })),
      ),
    );
    act(() => result.current.undo());
    expect(result.current.refs[0].x).toBe(0);
    act(() => result.current.redo());
    expect(result.current.refs[0].x).toBe(120);
  });
});
