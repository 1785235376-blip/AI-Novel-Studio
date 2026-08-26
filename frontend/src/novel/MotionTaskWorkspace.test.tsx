// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { MotionTaskWorkspace, sortVideoProviders } from "./MotionTaskWorkspace";

vi.mock("../api", () => ({ api: {
  screenplays: vi.fn(), videoProviders: vi.fn(), updateMotionProvider: vi.fn(), updateMotionFrames: vi.fn(),
  executeMotionTask: vi.fn(), cancelMotionTask: vi.fn(), retryMotionTask: vi.fn(), syncMotionTask: vi.fn(),
  importMotionAsset: vi.fn(), downloadMotionAsset: vi.fn(),
} }));

const local = { id: "local", display_name: "Comfy Video", endpoint: "http://127.0.0.1:8189", model: "local-model", local: true, requires_credential: false, credential_configured: true, available: true, registered: true, health: "READY" };
const cloud = { id: "cloud", display_name: "Cloud Video", endpoint: "https://video.example", model: "cloud-model", local: false, requires_credential: true, credential_configured: false, available: false, registered: false, health: "NOT_CONFIGURED" };

describe("MotionTaskWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(api.videoProviders).mockResolvedValue({ items: [cloud, local] });
    vi.mocked(api.updateMotionProvider).mockResolvedValue({});
    vi.mocked(api.executeMotionTask).mockResolvedValue({});
  });
  afterEach(cleanup);

  it("sorts reachable local providers before cloud fallbacks", () => {
    expect(sortVideoProviders([cloud, local]).map((item) => item.id)).toEqual(["local", "cloud"]);
  });

  it("shows real unavailability and does not enable execution", async () => {
    vi.mocked(api.screenplays).mockResolvedValue([{ id: "sp", motion_tasks: [{ id: "task", status: "PENDING", provider_id: "cloud", model_id: "cloud-model", start_frame: "https://a/start.png", end_frame: "https://a/end.png" }] }]);
    render(<MotionTaskWorkspace novelId="novel" screenplayId="sp" />);
    await screen.findByText(/当前 Provider 未配置或不可达/);
    expect((screen.getByRole("button", { name: "执行生成" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("option", { name: /云端 · Cloud Video（不可用）/ }) as HTMLOptionElement).disabled).toBe(true);
  });

  it("submits through the configured provider and refreshes without reloading", async () => {
    vi.mocked(api.screenplays).mockResolvedValue([{ id: "sp", motion_tasks: [{ id: "task", status: "PENDING", provider_id: "local", model_id: "local-model", start_frame: "https://a/start.png", end_frame: "https://a/end.png" }] }]);
    render(<MotionTaskWorkspace novelId="novel" screenplayId="sp" />);
    fireEvent.click(await screen.findByRole("button", { name: "执行生成" }));
    await waitFor(() => expect(api.executeMotionTask).toHaveBeenCalledWith("novel", "sp", "task"));
    expect(api.screenplays).toHaveBeenCalledTimes(2);
  });

  it("selects a real task before a target director shot confirms binding", async () => {
    vi.mocked(api.screenplays).mockResolvedValue([{ id: "sp", motion_tasks: [{ id: "task", status: "PENDING", provider_id: "local", model_id: "local-model" }] }]);
    const listener = vi.fn(); window.addEventListener("multimodal-motion-binding", listener);
    render(<MotionTaskWorkspace novelId="novel" screenplayId="sp" />);
    fireEvent.click(await screen.findByRole("button", { name: "选择用于镜头绑定" }));
    expect(JSON.parse(localStorage.getItem("multimodal-selected-motion:novel") || "{}")).toMatchObject({ screenplay_id: "sp", motion_task_id: "task" });
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener("multimodal-motion-binding", listener);
  });
});
