// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api, type Asset } from "../api";
import { AssetInspector } from "./AssetInspector";

afterEach(() => vi.restoreAllMocks());

it("renders authenticated image preview and exact asset metadata", async () => {
  const asset: Asset = { id: "asset-1", novel_id: "novel-1", filename: "角色参考.png", kind: "image", media_type: "image/png", size: 2048, sha256: "abcdef1234567890", created_at: "", updated_at: "2026-08-26T08:00:00Z" };
  vi.spyOn(api, "assetDownload").mockResolvedValue(new Blob(["image"]));
  Object.defineProperty(URL, "createObjectURL", { configurable: true, writable: true, value: vi.fn() });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, writable: true, value: vi.fn() });
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:asset-preview");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  render(<AssetInspector asset={asset} novelId="novel-1" />);
  expect((await screen.findByAltText("角色参考.png")).getAttribute("src")).toBe("blob:asset-preview");
  expect(screen.getByText("2.0 KiB")).toBeTruthy();
  expect(screen.getByText("asset-1")).toBeTruthy();
  await waitFor(() => expect(api.assetDownload).toHaveBeenCalledWith("asset-1","novel-1"));
});

it("keeps an honest empty state before selection", () => {
  render(<AssetInspector novelId="novel-1" />);
  expect(screen.getByText("未选择资产")).toBeTruthy();
});

// [HERMIA-FE-20261025 VERA-620963bf P2] 下载失败：普通模式固定友好文案、无原文；专业模式额外渲染技术详情
import { cleanup, fireEvent, within } from "@testing-library/react";
import { ApiError } from "../api";
import { setApiErrorShellMode } from "../apiErrorMode";
const docAsset: Asset = { id: "asset-2", novel_id: "novel-1", filename: "notes.txt", kind: "document", media_type: "text/plain", size: 10, sha256: "ab", created_at: "", updated_at: "" };
const failing = () => Promise.reject(new ApiError({ status: 400, code: "INVALID_ASSET_REQUEST", message: "请求内容有误，请检查后重试", message_source: "fallback", raw_text: "'SECRET-R'" }));
it.each(["basic", "pro"] as const)("download failure in %s mode", async mode => {
  setApiErrorShellMode(mode);
  try {
    const { container } = render(<AssetInspector asset={docAsset} novelId="novel-1" downloadAsset={failing} />);
    fireEvent.click(within(container).getByRole("button", { name: /下载/ }));
    await within(container).findByText("资产下载失败，请检查本地服务后重试。");
    const tech = container.querySelector(".api-error-technical");
    if (mode === "pro") expect(tech?.textContent).toContain("'SECRET-R'");
    else { expect(tech).toBeNull(); expect(container.textContent).not.toContain("SECRET"); }
  } finally { setApiErrorShellMode("basic"); cleanup(); }
});
it("download failure with whitelisted server copy shows that copy", async () => {
  const legit = () => Promise.reject(new ApiError({ status: 409, code: "PLANNING_VERSION_CONFLICT", message: "比例需在 1/2.5 之间", message_source: "server" }));
  try {
    const { container } = render(<AssetInspector asset={docAsset} novelId="novel-1" downloadAsset={legit} />);
    fireEvent.click(within(container).getByRole("button", { name: /下载/ }));
    await within(container).findByText("比例需在 1/2.5 之间");
  } finally { cleanup(); }
});
