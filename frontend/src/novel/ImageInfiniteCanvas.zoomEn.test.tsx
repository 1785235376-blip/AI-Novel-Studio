// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-P3 zoom] 图片无限画布缩放按钮/读数用固定键：en 为 Zoom out canvas / Canvas zoom / Zoom in canvas；zh 不变。 */
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { setLocale } from "../i18n";
import { ImageInfiniteCanvas } from "./ImageInfiniteCanvas";
afterEach(() => { act(() => setLocale("zh-CN")); cleanup(); });
it.each([["en", ["Zoom out canvas", "Canvas zoom", "Zoom in canvas"]], ["zh-CN", ["缩小画布", "画布缩放", "放大画布"]]] as const)("%s canvas zoom labels", (loc, want) => {
  act(() => setLocale(loc));
  const { container } = render(<ImageInfiniteCanvas nodes={[]} onChange={vi.fn()} viewport={{ x: 0, y: 0, zoom: 1 }} onViewportChange={vi.fn()} undo={vi.fn()} redo={vi.fn()} canUndo canRedo />);
  const got = [...container.querySelectorAll("[aria-label]")].map(e => e.getAttribute("aria-label")!).filter(v => /zoom|缩|放大/i.test(v));
  expect(got).toEqual(want);
});
