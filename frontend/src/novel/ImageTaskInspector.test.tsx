// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ImageTaskInspector } from "./ImageTaskInspector";

afterEach(cleanup);

it("renders only a real provider result URI", () => {
  render(<ImageTaskInspector novelId="novel-1" inspection={{ id: "image-task", status: "SUCCEEDED", providerId: "ddshub", modelId: "gpt-image-2", assetUri: "https://example.test/result.png" }}/>);
  expect(screen.getByAltText("当前图片生成结果").getAttribute("src")).toBe("https://example.test/result.png");
  expect(screen.getByText("ddshub")).toBeTruthy();
  expect(screen.getByText("尚未导入")).toBeTruthy();
});

it("announces failure without fabricating a preview", () => {
  render(<ImageTaskInspector novelId="novel-1" inspection={{ id: "image-task", status: "FAILED", providerId: "ddshub", modelId: "gpt-image-2", error: "Provider 不可达" }}/>);
  expect(screen.queryByAltText("当前图片生成结果")).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain("Provider 不可达");
  expect(screen.getByText("未生成可用图片")).toBeTruthy();
});
