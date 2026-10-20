// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api, type Asset, type VisualReference } from "../api";
import { VisualReferencePanel } from "./VisualReferencePanel";

const asset: Asset = { id: "asset-1", novel_id: "novel-1", filename: "hero.png", kind: "image", media_type: "image/png", size: 1024, sha256: "a".repeat(64), created_at: "", updated_at: "" };
const draft: VisualReference = { id: "memory-1", novel_id: "novel-1", asset_id: "asset-1", entity_type: "STYLE", entity_id: "noir", notes: "silver hair", version: 1, status: "ACTIVE", approval_status: "DRAFT" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function open() {
  const summary = screen.getByText("参考记忆与引用");
  const details = summary.closest("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
}

function mockRead(items: VisualReference[] = []) {
  vi.spyOn(api, "assetReferences").mockResolvedValue({ asset_id: asset.id, items: [], total: 0, coverage: ["visual_memory"], other_project_references_scanned: false, deletion_policy: "recoverable_tombstone" });
  return vi.spyOn(api, "visualReferences").mockResolvedValue({ items, total: items.length });
}

it("stores a draft and requires a separate version-bound approval", async () => {
  const read = mockRead();
  vi.spyOn(api, "createVisualReference").mockImplementation(async () => { read.mockResolvedValue({ items: [draft], total: 1 }); return draft; });
  vi.spyOn(api, "approveVisualReference").mockResolvedValue({ ...draft, approval_status: "APPROVED", version: 2 });
  render(<VisualReferencePanel asset={asset}/>);
  expect(api.visualReferences).not.toHaveBeenCalled();
  open();
  await screen.findByText("当前图片还没有参考记忆。");
  fireEvent.change(screen.getByLabelText("参考实体 ID"), { target: { value: "noir" } });
  fireEvent.change(screen.getByLabelText("参考说明"), { target: { value: "silver hair" } });
  fireEvent.click(screen.getByRole("button", { name: "保存待审核参考" }));
  await screen.findByRole("button", { name: "审核通过并索引" });
  expect(api.createVisualReference).toHaveBeenCalledWith("novel-1", { entity_type: "STYLE", entity_id: "noir", asset_id: "asset-1", notes: "silver hair", origin: "USER" });
  expect(api.approveVisualReference).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "审核通过并索引" }));
  await waitFor(() => expect(api.approveVisualReference).toHaveBeenCalledWith("novel-1", "memory-1", 1));
});

it("reports lexical provenance and damaged asset exclusion honestly", async () => {
  mockRead([draft]);
  vi.spyOn(api, "searchVisualReferences").mockResolvedValue({ items: [{ id: "memory-1", version: 2, entity_type: "STYLE", entity_id: "noir", asset_id: "asset-1", score: 1, matched_terms: ["silver"], searchable: {}, provenance: { asset_sha256: "a".repeat(64), asset_version: 1, memory_version: 2 } }], total: 1, indexed_count: 1, excluded: [{ id: "missing", reason: "ASSET_MISSING_OR_INVALID" }], retrieval_mode: "LEXICAL_METADATA", inference_performed: false, embeddings_available: false });
  render(<VisualReferencePanel asset={asset}/>);
  open();
  await screen.findByText("silver hair");
  fireEvent.change(screen.getByLabelText("检索已审核参考"), { target: { value: "silver" } });
  fireEvent.click(screen.getByRole("button", { name: "检索参考" }));
  await screen.findByText("已索引 1 条，匹配 1 条。");
  expect(screen.getByText(/参考 memory-1 · 资产 asset-1 · SHA-256 aaaaaaaaaaaa/)).toBeTruthy();
  expect(screen.getByText(/因资产缺失、损坏或审核版本过期被排除/)).toBeTruthy();
  expect(api.searchVisualReferences).toHaveBeenCalledWith("novel-1", "silver");
});

it("keeps reference draft inputs after an approval conflict", async () => {
  mockRead([draft]);
  vi.spyOn(api, "approveVisualReference").mockRejectedValue(new Error("版本冲突，请重新读取"));
  render(<VisualReferencePanel asset={asset}/>);
  open();
  await screen.findByRole("button", { name: "审核通过并索引" });
  fireEvent.change(screen.getByLabelText("参考说明"), { target: { value: "unsaved notes" } });
  fireEvent.click(screen.getByRole("button", { name: "审核通过并索引" }));
  await screen.findByText("版本冲突，请重新读取");
  expect((screen.getByLabelText("参考说明") as HTMLTextAreaElement).value).toBe("unsaved notes");
});
