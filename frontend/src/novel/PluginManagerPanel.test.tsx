// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { PluginManagerPanel } from "./PluginManagerPanel";

afterEach(() => vi.restoreAllMocks());

function mockStatus(registered: any[] = []) {
  vi.spyOn(api, "discoverPlugins").mockResolvedValue({
    items: [{ path: "D:/plugins/story-tools", manifest: { id: "story-tools", name: "故事工具", version: "1.0.0", capabilities: ["context"], requested_permissions: ["novel.read"] } }],
    execution_supported: false,
  });
  vi.spyOn(api, "plugins").mockResolvedValue({ items: registered });
  vi.spyOn(api, "multimodalHealth").mockResolvedValue({ image_providers: ["ddshub"], video_provider_configs: 0 } as any);
  vi.spyOn(api, "pluginRuntimeStatus").mockResolvedValue({ execution_supported: false, sandbox: "NOT_CONFIGURED", isolation: "DENY_ALL" });
}

it("shows the runtime boundary and registers without implying permission approval", async () => {
  mockStatus();
  const register = vi.spyOn(api, "registerPlugin").mockResolvedValue({} as any);
  render(<PluginManagerPanel />);
  expect(await screen.findByText("故事工具")).toBeTruthy();
  expect(screen.getByText("当前激活仅表示清单可用，不代表插件代码能够执行。", { exact: false })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "注册" }));
  await waitFor(() => expect(register).toHaveBeenCalledWith(expect.objectContaining({ id: "story-tools" })));
  expect(await screen.findByText(/权限仍保持默认拒绝/)).toBeTruthy();
});

it("selects a registered plugin for inspection without exposing secrets", async()=>{const plugin={id:"story-tools",name:"故事工具",version:"1.0.0",status:"REGISTERED",capabilities:["context"],requested_permissions:["novel.read"],granted_permissions:[]};mockStatus([plugin]);const inspect=vi.fn();render(<PluginManagerPanel onInspect={inspect}/>);fireEvent.click(await screen.findByRole("button",{name:"检查插件 故事工具"}));expect(inspect).toHaveBeenCalledWith(expect.objectContaining({id:"story-tools",name:"故事工具",requestedPermissions:["novel.read"]}));expect(inspect.mock.calls.at(-1)?.[0]).not.toHaveProperty("key");});

it("reviews requested permissions before manifest activation", async () => {
  const plugin = { id: "story-tools", name: "故事工具", version: "1.0.0", status: "REGISTERED", requested_permissions: ["novel.read"], granted_permissions: [] };
  mockStatus([plugin]);
  const review = vi.spyOn(api, "setPluginPermissions").mockResolvedValue({} as any);
  render(<PluginManagerPanel />);
  const approve = await screen.findByRole("button", { name: "审核并授权" });
  expect(screen.queryByRole("button", { name: "激活清单" })).toBeNull();
  fireEvent.click(approve);
  await waitFor(() => expect(review).toHaveBeenCalledWith("story-tools", expect.objectContaining({ granted_permissions: ["novel.read"] })));
});
