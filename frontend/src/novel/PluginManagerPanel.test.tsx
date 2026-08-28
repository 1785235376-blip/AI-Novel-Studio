// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { PluginManagerPanel } from "./PluginManagerPanel";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function mockStatus(registered: any[] = [], discovered: any[] | undefined = undefined, catalog: any = undefined) {
  vi.spyOn(api, "discoverPlugins").mockResolvedValue({
    items: discovered ?? [{
      path: "D:/plugins/story-tools",
      plugin_dir: "story-tools",
      manifest: {
        id: "story-tools",
        name: "故事工具",
        version: "1.0.0",
        capabilities: ["writing_tool"],
        requested_permissions: ["project.read"],
        manifest_version: "1.0",
        host_api_version: "1",
        execution_mode: "declarative",
        publisher: "Acme Studio",
        resources: [{ kind: "writing_presets" }, { kind: "workflow_templates" }],
      },
      resource_count: 2,
      resource_kinds: ["writing_presets", "workflow_templates"],
    }],
    execution_supported: false,
  });
  vi.spyOn(api, "plugins").mockResolvedValue({ items: registered });
  vi.spyOn(api, "multimodalHealth").mockResolvedValue({ image_providers: ["ddshub"], video_provider_configs: 0 } as any);
  vi.spyOn(api, "pluginRuntimeStatus").mockResolvedValue({ execution_supported: false, sandbox: "NOT_CONFIGURED", isolation: "DENY_ALL" });
  vi.spyOn(api, "pluginResources").mockResolvedValue(catalog ?? {
    plugin_id: "story-tools",
    items: [],
    total: 0,
    visible: true,
    validated: false,
    validation_status: "MISSING",
    execution_supported: false,
    isolation: "DENY_ALL",
  });
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

it("selects a registered plugin for inspection without exposing secrets", async () => {
  const plugin = { id: "story-tools", name: "故事工具", version: "1.0.0", status: "REGISTERED", capabilities: ["writing_tool"], requested_permissions: ["project.read"], granted_permissions: [] };
  mockStatus([plugin]);
  const inspect = vi.fn();
  render(<PluginManagerPanel onInspect={inspect}/>);
  fireEvent.click(await screen.findByRole("button", { name: "检查插件 故事工具" }));
  expect(inspect).toHaveBeenCalledWith(expect.objectContaining({ id: "story-tools", name: "故事工具", requestedPermissions: ["project.read"], executionSupported: false }));
  expect(inspect.mock.calls.at(-1)?.[0]).not.toHaveProperty("key");
});

it("reviews requested permissions before manifest activation", async () => {
  const plugin = { id: "story-tools", name: "故事工具", version: "1.0.0", status: "REGISTERED", requested_permissions: ["project.read"], granted_permissions: [] };
  mockStatus([plugin]);
  const review = vi.spyOn(api, "setPluginPermissions").mockResolvedValue({} as any);
  render(<PluginManagerPanel />);
  const approve = await screen.findByRole("button", { name: "审核并授权" });
  expect(screen.queryByRole("button", { name: "激活清单" })).toBeNull();
  fireEvent.click(approve);
  await waitFor(() => expect(review).toHaveBeenCalledWith("story-tools", expect.objectContaining({ granted_permissions: ["project.read"] })));
});

it("labels publisher as unverified and shows declarative execution mode", async () => {
  mockStatus();
  render(<PluginManagerPanel />);
  expect(await screen.findByText("故事工具")).toBeTruthy();
  expect(screen.getAllByText(/Acme Studio（未验证发布者）/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/execution_mode=declarative/).length).toBeGreaterThan(0);
  expect(screen.getByText(/2 个声明式资源（写作预设、工作流模板）/)).toBeTruthy();
  expect(screen.getByText(/清单 1\.0 · Host API 1/)).toBeTruthy();
  expect(screen.getByText("禁止")).toBeTruthy();
  expect(screen.queryByText(/已签名/)).toBeNull();
});

it("does not display absolute paths, secrets, or plugin HTML", async () => {
  mockStatus([], [{
    path: "D:/小说/plugins/evil-pack",
    plugin_dir: "evil-pack",
    manifest: {
      id: "evil-pack",
      name: "<img src=x onerror=alert(1)>",
      version: "1.0.0",
      description: "<script>alert(1)</script> https://evil.example/hook",
      publisher: "https://evil.example",
      execution_mode: "declarative",
    },
  }]);
  const { container } = render(<PluginManagerPanel />);
  expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeTruthy();
  expect(screen.queryByText(/D:\\小说/)).toBeNull();
  expect(screen.queryByText(/D:\/小说/)).toBeNull();
  expect(screen.queryByRole("img")).toBeNull();
  expect(screen.queryByRole("link")).toBeNull();
  expect(container.querySelector("script")).toBeNull();
  expect(screen.queryByText(/sk-|api[_-]?key|secret/i)).toBeNull();
});

it("keeps legacy manifests compatible in the governance list", async () => {
  mockStatus([], [{
    plugin_dir: "legacy-pack",
    path: "legacy-pack",
    manifest: { id: "legacy-pack", name: "旧清单", version: "0.1.0" },
  }]);
  render(<PluginManagerPanel />);
  expect(await screen.findByText("旧清单")).toBeTruthy();
  expect(screen.getByText(/清单 1\.0 · Host API 1/)).toBeTruthy();
  expect(screen.getByText(/execution_mode=declarative/)).toBeTruthy();
  expect(screen.getByText(/未声明（未验证发布者）/)).toBeTruthy();
  expect(screen.getByText(/0 个声明式资源/)).toBeTruthy();
});

it("shows lifecycle states and keeps plugin code non-executable", async () => {
  const plugin = {
    id: "story-tools",
    name: "故事工具",
    plugin_version: "1.0.0",
    version: 3,
    status: "MANIFEST_ACTIVE",
    requested_permissions: [],
    granted_permissions: [],
    permission_review: { reviewed_by: "local-user" },
    execution_mode: "declarative",
    publisher: "Acme Studio",
    resources: [{ kind: "writing_presets" }],
  };
  mockStatus([plugin], undefined, {
    plugin_id: "story-tools",
    items: [{ resource_id: "resources:preset.json", kind: "writing_presets", name: "冷静叙述" }],
    total: 1,
    validated: true,
    validation_status: "VALIDATED",
    resource_count: 1,
    resource_kinds: ["writing_presets"],
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginManagerPanel />);
  expect(await screen.findByText("插件代码可执行：否")).toBeTruthy();
  expect(screen.getAllByText("已发现").length).toBeGreaterThan(0);
  expect(screen.getAllByText("已注册").length).toBeGreaterThan(0);
  expect(screen.getAllByText("无需权限").length).toBeGreaterThan(0);
  expect(screen.getByText("Manifest 已激活")).toBeTruthy();
  expect(screen.getByText("声明式资源已验证")).toBeTruthy();
});

it("sanitizes discovery errors and recovers from a failed scan", async () => {
  const discover = vi.spyOn(api, "discoverPlugins");
  discover.mockRejectedValueOnce(new Error("Traceback (most recent call last):\nFile \"D:/小说/app.py\""));
  vi.spyOn(api, "plugins").mockResolvedValue({ items: [] });
  vi.spyOn(api, "multimodalHealth").mockResolvedValue({ image_providers: [], video_provider_configs: 0 } as any);
  vi.spyOn(api, "pluginRuntimeStatus").mockResolvedValue({ execution_supported: false, sandbox: "NOT_CONFIGURED", isolation: "DENY_ALL" });
  render(<PluginManagerPanel />);
  expect(await screen.findByText("插件状态读取失败，请检查本地服务后重新扫描。")).toBeTruthy();
  expect(screen.queryByText(/Traceback/)).toBeNull();
  expect(screen.queryByText(/D:\/小说/)).toBeNull();
  discover.mockResolvedValue({
    items: [{ plugin_dir: "story-tools", manifest: { id: "story-tools", name: "故事工具", version: "1.0.0" } }],
    execution_supported: false,
  });
  fireEvent.click(screen.getByRole("button", { name: "重新扫描" }));
  expect(await screen.findByText("故事工具")).toBeTruthy();
});

it("does not claim resources are validated when the live catalog fails", async () => {
  mockStatus([{
    id: "story-tools",
    name: "故事工具",
    plugin_version: "1.0.0",
    status: "MANIFEST_ACTIVE",
    requested_permissions: [],
    granted_permissions: [],
    resources: [{ kind: "writing_presets" }, { kind: "workflow_templates" }],
  }], [], {
    items: [],
    total: 0,
    validated: false,
    validation_status: "MISSING",
    resource_count: 0,
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginManagerPanel />);
  expect(await screen.findByText("故事工具")).toBeTruthy();
  expect(screen.getAllByText("未发现").length).toBeGreaterThan(0);
  expect(screen.queryByText("声明式资源已验证")).toBeNull();
});

it("shows duplicate id, drift, and partial validation states", async () => {
  mockStatus([{
    id: "story-tools",
    name: "故事工具",
    plugin_version: "1.0.0",
    status: "MANIFEST_ACTIVE",
    requested_permissions: ["project.read"],
    granted_permissions: ["project.read"],
    permission_review: { reviewed_by: "local-user" },
  }], undefined, {
    items: [],
    validated: false,
    validation_status: "DUPLICATE",
    error_code: "PLUGIN_ID_DUPLICATE",
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginManagerPanel />);
  expect(await screen.findByText("重复 ID")).toBeTruthy();
  expect(screen.queryByText("声明式资源已验证")).toBeNull();
  cleanup();
  mockStatus([{
    id: "story-tools",
    name: "故事工具",
    plugin_version: "1.0.0",
    status: "MANIFEST_ACTIVE",
    requested_permissions: [],
    granted_permissions: [],
  }], undefined, {
    items: [],
    validated: false,
    validation_status: "DRIFT",
    status: "MANIFEST_DRIFT",
    error_code: "PLUGIN_MANIFEST_DRIFT",
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginManagerPanel />);
  expect(await screen.findByText("Manifest 漂移")).toBeTruthy();
  cleanup();
  mockStatus([{
    id: "story-tools",
    name: "故事工具",
    plugin_version: "1.0.0",
    status: "MANIFEST_ACTIVE",
    requested_permissions: [],
    granted_permissions: [],
  }], undefined, {
    items: [{ resource_id: "resources:good.json", kind: "writing_presets", name: "仍有效" }],
    validated: false,
    validation_status: "PARTIAL",
    invalid_resource_count: 1,
    resource_count: 1,
    resource_kinds: ["writing_presets"],
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginManagerPanel />);
  expect(await screen.findByText("部分资源有效")).toBeTruthy();
  expect(screen.queryByText("声明式资源已验证")).toBeNull();
});

it("uses live catalog resource counts instead of stale sidecar data", async () => {
  mockStatus([{
    id: "story-tools",
    name: "故事工具",
    plugin_version: "1.0.0",
    status: "MANIFEST_ACTIVE",
    requested_permissions: [],
    granted_permissions: [],
    resources: [{ kind: "writing_presets" }, { kind: "workflow_templates" }, { kind: "export_profiles" }],
  }], undefined, {
    items: [{ resource_id: "resources:preset.json", kind: "writing_presets" }],
    validated: true,
    validation_status: "VALIDATED",
    resource_count: 1,
    resource_kinds: ["writing_presets"],
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginManagerPanel />);
  expect(await screen.findByText(/1 个资源（写作预设）/)).toBeTruthy();
  expect(screen.queryByText(/3 个资源/)).toBeNull();
});
