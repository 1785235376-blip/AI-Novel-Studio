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
