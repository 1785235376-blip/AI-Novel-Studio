// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { PluginInspector } from "./PluginInspector";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const activeInspection = {
  id: "story-tools",
  name: "故事工具",
  version: "1.0.0",
  status: "MANIFEST_ACTIVE",
  capabilities: ["writing_tool"],
  requestedPermissions: ["project.read"],
  grantedPermissions: ["project.read"],
  executionSupported: false,
  sandbox: "NOT_CONFIGURED",
  isolation: "DENY_ALL",
  manifestVersion: "1.0",
  hostApiVersion: "1",
  executionMode: "declarative",
  publisher: "Acme Studio",
  resourceCount: 1,
  resourceKinds: ["writing_presets"],
};

it("renders manifest capabilities and truthful execution boundary", () => {
  vi.spyOn(api, "pluginResources").mockResolvedValue({ plugin_id: "story-tools", items: [], total: 0, visible: true, validated: true, execution_supported: false, isolation: "DENY_ALL" });
  render(<PluginInspector inspection={{ id: "story-tools", name: "故事工具", version: "1.0.0", status: "MANIFEST_ACTIVE", capabilities: ["context"], requestedPermissions: ["novel.read"], grantedPermissions: ["novel.read"], executionSupported: false, sandbox: "NOT_CONFIGURED", isolation: "DENY_ALL" }}/>);
  expect(screen.getByText("故事工具")).toBeTruthy();
  expect(screen.getAllByText(/代码执行：当前禁止/).length).toBeGreaterThan(0);
  expect(screen.getAllByText("novel.read")).toHaveLength(2);
  expect(screen.getByText("context")).toBeTruthy();
});

it("shows unverified publisher, declarative mode, and resource kinds", async () => {
  vi.spyOn(api, "pluginResources").mockResolvedValue({
    plugin_id: "story-tools",
    items: [{
      plugin_id: "story-tools",
      resource_id: "resources:writing-preset.json",
      kind: "writing_presets",
      name: "冷静叙述",
      schema_version: "1.0",
      sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      validated: true,
      summary: { sha256_short: "aaaaaaaaaaaa", name: "冷静叙述", kind: "writing_presets" },
    }],
    total: 1,
    visible: true,
    validated: true,
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginInspector inspection={activeInspection}/>);
  expect(screen.getByText(/Acme Studio（未验证发布者）/)).toBeTruthy();
  expect(screen.getByText("declarative")).toBeTruthy();
  expect(await screen.findByText("冷静叙述")).toBeTruthy();
  expect(screen.getByText(/1 个 · 写作预设/)).toBeTruthy();
  expect(screen.getByText(/SHA-256 aaaaaaaaaaaa/)).toBeTruthy();
  expect(screen.queryByText(/已签名/)).toBeNull();
});

it("does not fetch or display resources for disabled plugins", async () => {
  const fetchResources = vi.spyOn(api, "pluginResources").mockResolvedValue({ plugin_id: "story-tools", items: [{ resource_id: "hidden", kind: "writing_presets", name: "不应出现" }], total: 1, visible: false, validated: false, execution_supported: false, isolation: "DENY_ALL" });
  render(<PluginInspector inspection={{ ...activeInspection, status: "DISABLED" }}/>);
  expect(screen.getByText("清单未激活，声明式资源不可展示。")).toBeTruthy();
  expect(screen.queryByText("不应出现")).toBeNull();
  expect(fetchResources).not.toHaveBeenCalled();
});

it("renders plugin HTML and URLs as plain text", async () => {
  vi.spyOn(api, "pluginResources").mockResolvedValue({ plugin_id: "evil", items: [], total: 0, visible: true, validated: true, execution_supported: false, isolation: "DENY_ALL" });
  const { container } = render(<PluginInspector inspection={{
    id: "evil",
    name: "<img src=x onerror=alert(1)>",
    description: "<a href='https://evil.example'>click</a>",
    status: "REGISTERED",
    publisher: "https://evil.example",
  }}/>);
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeTruthy();
  expect(screen.getByText("<a href='https://evil.example'>click</a>")).toBeTruthy();
  expect(screen.queryByRole("img")).toBeNull();
  expect(screen.queryByRole("link")).toBeNull();
  expect(container.querySelector("script")).toBeNull();
  expect(screen.queryByText(/D:\\|C:\\|\/home\/|sk-/)).toBeNull();
});

it("recovers from a failed resource summary request", async () => {
  const fetchResources = vi.spyOn(api, "pluginResources");
  fetchResources.mockRejectedValueOnce(new Error("ENOENT D:/小说/plugins/story-tools/resources/x.json"));
  fetchResources.mockResolvedValueOnce({
    plugin_id: "story-tools",
    items: [{ resource_id: "resources:writing-preset.json", kind: "writing_presets", name: "冷静叙述", sha256: "bb".repeat(32), validated: true, summary: { sha256_short: "bbbbbbbbbbbb", name: "冷静叙述" } }],
    total: 1,
    visible: true,
    validated: true,
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginInspector inspection={activeInspection}/>);
  expect(await screen.findByText("声明式资源摘要读取失败。未展示未验证内容。")).toBeTruthy();
  expect(screen.queryByText(/ENOENT/)).toBeNull();
  expect(screen.queryByText(/D:\/小说/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "重试读取" }));
  expect(await screen.findByText("冷静叙述")).toBeTruthy();
  await waitFor(() => expect(fetchResources).toHaveBeenCalledTimes(2));
});

it("keeps a legacy inspection payload compatible", () => {
  render(<PluginInspector inspection={{ id: "legacy-pack", name: "旧清单", status: "REGISTERED" }}/>);
  expect(screen.getByText("1.0")).toBeTruthy();
  expect(screen.getByText("declarative")).toBeTruthy();
  expect(screen.getByText(/未声明（未验证发布者）/)).toBeTruthy();
  expect(screen.getAllByText(/代码执行：当前禁止/).length).toBeGreaterThan(0);
  expect(screen.getAllByText("DENY_ALL").length).toBeGreaterThan(0);
  expect(screen.getByText("清单未激活，声明式资源不可展示。")).toBeTruthy();
});

it("clears previous plugin resources immediately when switching selection", async () => {
  const fetchResources = vi.spyOn(api, "pluginResources");
  fetchResources.mockImplementation(async (id: string) => {
    if (id === "alpha") {
      return {
        plugin_id: "alpha",
        items: [{ resource_id: "resources:a.json", kind: "writing_presets", name: "Alpha 资源", summary: { name: "Alpha 资源" } }],
        total: 1,
        visible: true,
        validated: true,
        validation_status: "VALIDATED",
        resource_count: 1,
        resource_kinds: ["writing_presets"],
        execution_supported: false,
        isolation: "DENY_ALL",
      };
    }
    return {
      plugin_id: "beta",
      items: [{ resource_id: "resources:b.json", kind: "export_profiles", name: "Beta 资源", summary: { name: "Beta 资源" } }],
      total: 1,
      visible: true,
      validated: true,
      validation_status: "VALIDATED",
      resource_count: 1,
      resource_kinds: ["export_profiles"],
      execution_supported: false,
      isolation: "DENY_ALL",
    };
  });
  const { rerender } = render(<PluginInspector inspection={{ ...activeInspection, id: "alpha", name: "Alpha", resourceCount: 9 }}/>);
  expect(await screen.findByText("Alpha 资源")).toBeTruthy();
  rerender(<PluginInspector inspection={{ ...activeInspection, id: "beta", name: "Beta", resourceCount: 9 }}/>);
  expect(screen.queryByText("Alpha 资源")).toBeNull();
  expect(await screen.findByText("Beta 资源")).toBeTruthy();
  expect(screen.queryByText(/9 个/)).toBeNull();
});

it("overrides stale sidecar resource counts with live catalog data", async () => {
  vi.spyOn(api, "pluginResources").mockResolvedValue({
    plugin_id: "story-tools",
    items: [{ resource_id: "resources:preset.json", kind: "writing_presets", name: "仅一项", summary: { name: "仅一项" } }],
    total: 1,
    visible: true,
    validated: true,
    validation_status: "VALIDATED",
    resource_count: 1,
    resource_kinds: ["writing_presets"],
    execution_supported: false,
    isolation: "DENY_ALL",
  });
  render(<PluginInspector inspection={{ ...activeInspection, resourceCount: 8, resourceKinds: ["writing_presets", "workflow_templates"] }}/>);
  expect(await screen.findByText("仅一项")).toBeTruthy();
  expect(screen.getByText(/1 个 · 写作预设/)).toBeTruthy();
  expect(screen.queryByText(/8 个/)).toBeNull();
});
