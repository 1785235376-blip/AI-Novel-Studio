// @vitest-environment jsdom
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { ImageGenerationPanel } from "./ImageGenerationPanel";
import { api } from "../api";
import { vi, it, expect, afterEach } from "vitest";
import { IMAGE_CANVAS_ADD_EVENT } from "./imageCanvasEvents";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("exposes real task lifecycle and only renders URI after generation resolves", async () => {
  vi.spyOn(api, "imageGenerations").mockResolvedValue({ items: [] });
  vi.spyOn(api, "assetProviders").mockResolvedValue({
    items: [
      {
        provider_id: "ddshub",
        default_model: "gpt-image-2",
        configured: true,
        registered: true,
      },
    ],
  });
  let resolve!: (value: any) => void;
  vi.spyOn(api, "imageGenerate").mockImplementation(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const inspect = vi.fn();
  render(<ImageGenerationPanel novelId="n1" onInspect={inspect} />);
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "生成图片" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false),
  );
  fireEvent.click(screen.getByRole("button", { name: "生成图片" }));
  expect(screen.getByText("任务状态：执行中")).toBeTruthy();
  expect(screen.queryByAltText("生成结果")).toBeNull();
  resolve({ asset_uri: "https://example.test/image.png" });
  await waitFor(() => expect(screen.getByAltText("生成结果")).toBeTruthy());
  expect(screen.getByText("任务状态：已完成")).toBeTruthy();
  expect(inspect).toHaveBeenLastCalledWith(
    expect.objectContaining({
      id: "image-task",
      status: "SUCCEEDED",
      providerId: "ddshub",
      modelId: "gpt-image-2",
      assetUri: "https://example.test/image.png",
    }),
  );
  expect(inspect.mock.calls.at(-1)?.[0]).not.toHaveProperty("prompt");
  const added = vi.fn();
  window.addEventListener(IMAGE_CANVAS_ADD_EVENT, added, { once: true });
  fireEvent.click(screen.getByRole("button", { name: "加入画布" }));
  expect(added).toHaveBeenCalledWith(
    expect.objectContaining({
      detail: expect.objectContaining({
        novelId: "n1",
        uri: "https://example.test/image.png",
        source: "generation",
      }),
    }),
  );
});

it("adds a real history result to the canvas without generating a new URI", async () => {
  vi.spyOn(api, "imageGenerations").mockResolvedValue({
    items: [
      {
        id: "h1",
        asset_uri: "https://example.test/history.png",
        prompt: "旧结果",
        provider_id: "local-comfyui",
        model_id: "flux",
      },
    ],
  });
  vi.spyOn(api, "assetProviders").mockResolvedValue({ items: [] });
  const generate = vi.spyOn(api, "imageGenerate");
  const added = vi.fn();
  window.addEventListener(IMAGE_CANVAS_ADD_EVENT, added, { once: true });
  render(<ImageGenerationPanel novelId="n1" />);
  await screen.findByText("生成历史（1）");
  fireEvent.click(screen.getByRole("button", { name: "加入画布" }));
  expect(added).toHaveBeenCalledWith(
    expect.objectContaining({
      detail: expect.objectContaining({
        uri: "https://example.test/history.png",
        providerId: "local-comfyui",
        modelId: "flux",
      }),
    }),
  );
  expect(generate).not.toHaveBeenCalled();
});

it("marks failed requests without fabricating an image URI", async () => {
  vi.spyOn(api, "imageGenerations").mockResolvedValue({ items: [] });
  vi.spyOn(api, "assetProviders").mockResolvedValue({
    items: [
      {
        provider_id: "ddshub",
        default_model: "gpt-image-2",
        configured: true,
        registered: true,
      },
    ],
  });
  vi.spyOn(api, "imageGenerate").mockRejectedValue(new Error("offline"));
  render(<ImageGenerationPanel novelId="n1" />);
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "生成图片" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false),
  );
  fireEvent.click(screen.getByRole("button", { name: "生成图片" }));
  await waitFor(() =>
    expect(
      screen.getByText("任务状态：失败 · 图片生成失败，请检查 Provider 配置。"),
    ).toBeTruthy(),
  );
  expect(screen.queryByAltText("生成结果")).toBeNull();
});

it("blocks an unsafe provider result from preview and canvas insertion", async () => {
  vi.spyOn(api, "imageGenerations").mockResolvedValue({ items: [] });
  vi.spyOn(api, "assetProviders").mockResolvedValue({
    items: [{ provider_id: "custom", default_model: "image", configured: true, registered: true }],
  });
  vi.spyOn(api, "imageGenerate").mockResolvedValue({
    asset_uri: "javascript:alert(1)",
    provider_id: "custom",
    model_id: "image",
    prompt: "unsafe result",
  });
  render(<ImageGenerationPanel novelId="n1" />);
  await waitFor(() => expect((screen.getByRole("button", { name: "生成图片" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "生成图片" }));
  await screen.findByText("Provider 返回了不受支持的图片地址，已阻止预览。");
  expect(screen.queryByAltText("生成结果")).toBeNull();
  expect((screen.getByRole("button", { name: "加入画布" }) as HTMLButtonElement).disabled).toBe(true);
});
