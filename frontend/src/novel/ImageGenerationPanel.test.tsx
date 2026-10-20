// @vitest-environment jsdom
import {
  act,
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { ImageGenerationPanel } from "./ImageGenerationPanel";
import { api } from "../api";
import { vi, it, expect, beforeEach, afterEach } from "vitest";
import { IMAGE_CANVAS_ADD_EVENT,IMAGE_CANVAS_SELECTION_EVENT } from "./imageCanvasEvents";

beforeEach(() => {
  vi.spyOn(api, "imageJobs").mockResolvedValue({ items: [] });
  // All transport dependencies must be explicit: this panel also mounts the
  // durable queue. Reject and report an omitted fixture instead of using fetch.
  vi.spyOn(globalThis, "fetch").mockRejectedValue(
    new Error("Unexpected network request in ImageGenerationPanel test"),
  );
});

afterEach(() => {
  cleanup();
  try {
    expect(vi.mocked(globalThis.fetch).mock.calls).toEqual([]);
  } finally {
    vi.restoreAllMocks();
  }
});

async function renderSettled(panel: Parameters<typeof render>[0]) {
  // Settle immediately-resolved startup requests and their provider/model
  // effects before interactions; an enabled DOM node alone is not that barrier.
  await act(async () => {
    render(panel);
  });
}

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
  await renderSettled(<ImageGenerationPanel novelId="n1" onInspect={inspect} />);
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "生成图片" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false),
  );
  fireEvent.click(screen.getByRole("button", { name: "生成图片" }));
  expect(await screen.findByText("任务状态：执行中")).toBeTruthy();
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
  await renderSettled(<ImageGenerationPanel novelId="n1" />);
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
  await renderSettled(<ImageGenerationPanel novelId="n1" />);
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
  await renderSettled(<ImageGenerationPanel novelId="n1" />);
  await waitFor(() => expect((screen.getByRole("button", { name: "生成图片" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "生成图片" }));
  await screen.findByText("Provider 返回了不受支持的图片地址，已阻止预览。");
  expect(screen.queryByAltText("生成结果")).toBeNull();
  expect((screen.getByRole("button", { name: "加入画布" }) as HTMLButtonElement).disabled).toBe(true);
});

it("uses DDSHub image edits when reference images are supplied", async () => {
  vi.spyOn(api, "imageGenerations").mockResolvedValue({ items: [] });
  vi.spyOn(api, "assetProviders").mockResolvedValue({items:[{provider_id:"ddshub",default_model:"gpt-image-2",configured:true,registered:true}]});
  const generate=vi.spyOn(api,"imageGenerate");
  const edit=vi.spyOn(api,"imageEdit").mockResolvedValue({provider_id:"ddshub",model_id:"gpt-image-2",asset_uri:"https://example.test/fused.png",prompt:"融合",reference_count:2});
  await renderSettled(<ImageGenerationPanel novelId="n1"/>);
  fireEvent.click(await screen.findByText("多参考图融合"));
  fireEvent.change(screen.getByLabelText("多参考图地址"),{target:{value:"https://example.test/a.png\nhttps://example.test/b.png"}});
  fireEvent.click(screen.getByRole("button",{name:"融合参考图"}));
  await waitFor(()=>expect(edit).toHaveBeenCalledWith(expect.objectContaining({provider_id:"ddshub",images:["https://example.test/a.png","https://example.test/b.png"]})));
  expect(generate).not.toHaveBeenCalled();
  expect(await screen.findByAltText("生成结果")).toBeTruthy();
});

it("switches from a local-first default to DDSHub when references are entered", async () => {
  vi.spyOn(api, "imageGenerations").mockResolvedValue({ items: [] });
  vi.spyOn(api, "assetProviders").mockResolvedValue({items:[
    {provider_id:"local-comfyui",default_model:"flux",configured:true,registered:true,local:true},
    {provider_id:"ddshub",default_model:"gpt-image-2",configured:true,registered:true},
  ]});
  await renderSettled(<ImageGenerationPanel novelId="n1"/>);
  fireEvent.click(await screen.findByText("多参考图融合"));
  fireEvent.change(screen.getByLabelText("多参考图地址"),{target:{value:"https://example.test/reference.png"}});
  await waitFor(()=>expect((screen.getByLabelText("图片 Provider") as HTMLSelectElement).value).toBe("ddshub"));
  expect((screen.getByRole("button",{name:"融合参考图"}) as HTMLButtonElement).disabled).toBe(false);
});

it('can reuse selected infinite-canvas images as references',async()=>{
  vi.spyOn(api,'imageGenerations').mockResolvedValue({items:[]});vi.spyOn(api,'assetProviders').mockResolvedValue({items:[{provider_id:'ddshub',default_model:'gpt-image-2',configured:true,registered:true}]});
  await renderSettled(<ImageGenerationPanel novelId="n1"/>);fireEvent.click(await screen.findByText('多参考图融合'));
  window.dispatchEvent(new CustomEvent(IMAGE_CANVAS_SELECTION_EVENT,{detail:{images:['https://example.test/a.png','data:image/png;base64,YQ==']}}));
  fireEvent.click(await screen.findByRole('button',{name:'使用画布所选（2）'}));
  expect((screen.getByLabelText('多参考图地址') as HTMLTextAreaElement).value).toContain('https://example.test/a.png');
  expect(screen.getByRole('button',{name:'融合参考图'})).toBeTruthy();
});


it.each(["loaded", "failed"] as const)(
  "keeps the direct task lifecycle when a delayed persistent queue is %s",
  async (queueOutcome) => {
    vi.spyOn(api, "imageGenerations").mockResolvedValue({ items: [] });
    let resolveProviders!: (
      value: Awaited<ReturnType<typeof api.assetProviders>>,
    ) => void;
    vi.spyOn(api, "assetProviders").mockImplementation(
      () => new Promise((resolve) => { resolveProviders = resolve; }),
    );
    let resolveQueue!: (value: Awaited<ReturnType<typeof api.imageJobs>>) => void;
    let rejectQueue!: (reason: Error) => void;
    vi.mocked(api.imageJobs).mockImplementation(
      () => new Promise((resolve, reject) => {
        resolveQueue = resolve;
        rejectQueue = reject;
      }),
    );
    let resolveGeneration!: (
      value: Awaited<ReturnType<typeof api.imageGenerate>>,
    ) => void;
    const generate = vi.spyOn(api, "imageGenerate").mockImplementation(
      () => new Promise((resolve) => { resolveGeneration = resolve; }),
    );
    const inspect = vi.fn();
    await renderSettled(<ImageGenerationPanel novelId="n1" onInspect={inspect} />);
    expect((screen.getByRole("button", { name: "生成图片" }) as HTMLButtonElement).disabled).toBe(true);
    expect(generate).not.toHaveBeenCalled();
    expect(api.imageJobs).toHaveBeenCalledWith("n1");

    await act(async () => {
      resolveProviders({ items: [{
        provider_id: "ddshub", default_model: "gpt-image-2",
        configured: true, registered: true,
      }] });
    });
    expect((screen.getByLabelText("图片 Provider") as HTMLSelectElement).value).toBe("ddshub");
    expect((screen.getByLabelText("图片模型") as HTMLInputElement).value).toBe("gpt-image-2");
    fireEvent.click(screen.getByRole("button", { name: "生成图片" }));
    expect(generate).toHaveBeenCalledTimes(1);
    expect(generate).toHaveBeenCalledWith(expect.objectContaining({
      novel_id: "n1", provider_id: "ddshub", model_id: "gpt-image-2",
      allow_cloud_prompt: false,
    }));
    expect(screen.getByText("任务状态：执行中")).toBeTruthy();
    expect(screen.queryByAltText("生成结果")).toBeNull();
    expect(inspect).toHaveBeenLastCalledWith(expect.objectContaining({ status: "RUNNING" }));

    await act(async () => {
      if (queueOutcome === "failed") rejectQueue(new Error("Synthetic queue unavailable"));
      else resolveQueue({ items: [] });
    });
    if (queueOutcome === "failed") {
      expect(screen.getByRole("alert").textContent).toBe("Synthetic queue unavailable");
    } else {
      expect(screen.queryByRole("alert")).toBeNull();
      expect(screen.getByText("暂无持久任务。")).toBeTruthy();
    }
    expect(screen.getByText("任务状态：执行中")).toBeTruthy();
    expect(screen.queryByAltText("生成结果")).toBeNull();
    expect((screen.getByRole("button", { name: "生成中…" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "生成中…" }));
    expect(generate).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveGeneration({
        asset_uri: "https://example.test/delayed.png", provider_id: "ddshub",
        model_id: "gpt-image-2", prompt: "Synthetic generated image",
      });
    });
    expect(screen.getByText("任务状态：已完成")).toBeTruthy();
    expect(screen.getByAltText("生成结果").getAttribute("src")).toBe("https://example.test/delayed.png");
    expect(inspect).toHaveBeenLastCalledWith(expect.objectContaining({
      status: "SUCCEEDED", assetUri: "https://example.test/delayed.png",
    }));
  },
);

it("keeps a task started at the first enabled commit when the queue then fails", async () => {
  vi.spyOn(api, "imageGenerations").mockResolvedValue({ items: [] });
  let resolveProviders!: (value: Awaited<ReturnType<typeof api.assetProviders>>) => void;
  vi.spyOn(api, "assetProviders").mockImplementation(
    () => new Promise((resolve) => { resolveProviders = resolve; }),
  );
  let rejectQueue!: (reason: Error) => void;
  vi.mocked(api.imageJobs).mockImplementation(
    () => new Promise((_resolve, reject) => { rejectQueue = reject; }),
  );
  let resolveGeneration!: (value: Awaited<ReturnType<typeof api.imageGenerate>>) => void;
  const generate = vi.spyOn(api, "imageGenerate").mockImplementation(
    () => new Promise((resolve) => { resolveGeneration = resolve; }),
  );
  const inspect = vi.fn();
  await renderSettled(<ImageGenerationPanel novelId="n1" onInspect={inspect} />);
  const button = screen.getByRole("button", { name: "生成图片" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  let dispatched = false;
  const observer = new MutationObserver(() => {
    if (!button.disabled && !dispatched) {
      dispatched = true;
      observer.disconnect();
      // Intentionally dispatch at the enabled DOM commit, before an awaited
      // readiness barrier can flush the provider/model passive effects.
      button.click();
      rejectQueue(new Error("Synthetic queue failed at first click"));
    }
  });
  observer.observe(button, { attributes: true, attributeFilter: ["disabled"] });
  try {
    resolveProviders({ items: [{
      provider_id: "ddshub", default_model: "gpt-image-2",
      configured: true, registered: true,
    }] });
    await waitFor(() => expect(generate).toHaveBeenCalledTimes(1));
    expect(dispatched).toBe(true);
    await screen.findByText("Synthetic queue failed at first click");
    expect(screen.getByText("任务状态：执行中")).toBeTruthy();
    expect(screen.queryByAltText("生成结果")).toBeNull();
    expect(inspect).toHaveBeenLastCalledWith(expect.objectContaining({ status: "RUNNING" }));
    await act(async () => {
      resolveGeneration({
        asset_uri: "https://example.test/first-click.png", provider_id: "ddshub",
        model_id: "gpt-image-2", prompt: "Synthetic first-click result",
      });
    });
    expect(screen.getByText("任务状态：已完成")).toBeTruthy();
    expect(screen.getByAltText("生成结果").getAttribute("src")).toBe("https://example.test/first-click.png");
    expect(generate).toHaveBeenCalledTimes(1);
  } finally {
    observer.disconnect();
  }
});
