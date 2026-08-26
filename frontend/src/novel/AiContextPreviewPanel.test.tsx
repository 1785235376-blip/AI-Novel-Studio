// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../api";
import { AiContextPreviewPanel } from "./AiContextPreviewPanel";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const context = (overrides: Record<string, unknown> = {}) => ({
  context_contract_version: "1.0",
  agent_id: "writer",
  agent_name: "作家 Agent",
  novel_id: "novel-1",
  chapter_id: "chapter-3",
  chapter_version: 7,
  target: "local",
  context_hash: "hash-123",
  sections: {
    characters: [{ id: "c1", name: "林" }],
    locations: [{ id: "loc-1", name: "旧港" }],
    timeline: [{ id: "event-1", title: "潮汐" }],
    foreshadowing: [{ id: "f1", title: "钟声" }],
    canon: [{ id: "canon-1", fact: "门只在夜里打开" }],
    writing_context: {
      chapter: 3,
      volume: 1,
      current_story_state: { active_characters: ["c1"] },
      must_not_include: ["未经批准改变 Canon"],
      lore_memory: { short_memory: [{ id: "m1" }] },
      context_pack_v2: { chunks: [{ source_id: "c1" }] },
    },
  },
  ...overrides,
});

function renderPreview(props: Partial<React.ComponentProps<typeof AiContextPreviewPanel>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AiContextPreviewPanel
        novelId="novel-1"
        chapterNumber={3}
        operation="continue"
        instruction=""
        {...props}
      />
    </QueryClientProvider>,
  );
}

describe("AI Context Preview", () => {
  it("reads the operation context and shows source statuses without demo records", async () => {
    const contextCall = vi.spyOn(api, "agentContext").mockResolvedValue(context());
    vi.spyOn(api, "writingGoal").mockResolvedValue({
      target_words: 10000,
      target_chapters: 10,
      current_words: 1200,
      current_chapters: 2,
      words_progress: 12,
      chapters_progress: 20,
      deadline: "",
    });
    vi.spyOn(api, "resource").mockResolvedValue([{ id: "canon-1", fact: "门只在夜里打开" }]);
    vi.spyOn(api, "worldRules").mockResolvedValue({ items: [{ id: "rule-1", text: "不可逆时间" }], storage: "file" });
    renderPreview();
    fireEvent.click(screen.getByRole("button", { name: "刷新上下文" }));
    expect(await screen.findByText("已同步")).toBeTruthy();
    await waitFor(() => expect(contextCall).toHaveBeenCalledWith("writer", "novel-1", 3, "", "local"));
    expect(screen.getByText("当前章节")).toBeTruthy();
    expect(screen.getByText("当前写作目标")).toBeTruthy();
    expect(screen.getByText("已确认 Canon")).toBeTruthy();
    expect(screen.getByText("世界规则约束")).toBeTruthy();
    expect(screen.getByText("Context Pack")).toBeTruthy();
    expect(screen.getByText(/资料：林 1 项/)).toBeTruthy();
    expect(screen.queryByText("示例人物")).toBeNull();
  });

  it("keeps loading visible while the real context request is pending", async () => {
    let resolve: (value: ReturnType<typeof context>) => void = () => {};
    vi.spyOn(api, "agentContext").mockImplementation(
      () => new Promise((next) => { resolve = next; }),
    );
    renderPreview();
    fireEvent.click(screen.getByRole("button", { name: "刷新上下文" }));
    expect(await screen.findByText(/正在读取章节/)).toBeTruthy();
    resolve(context());
  });

  it("distinguishes empty and not-configured sources", async () => {
    vi.spyOn(api, "agentContext").mockResolvedValue({
      ...context(),
      sections: { writing_context: { chapter: 3, volume: 1 }, characters: [], locations: [], timeline: [], foreshadowing: [] },
    });
    vi.spyOn(api, "writingGoal").mockResolvedValue({ target_words: 0, target_chapters: 0, current_words: 0, current_chapters: 0, words_progress: 0, chapters_progress: 0, deadline: "" });
    vi.spyOn(api, "resource").mockResolvedValue([]);
    vi.spyOn(api, "worldRules").mockResolvedValue({ items: [], storage: "file" });
    renderPreview();
    fireEvent.click(screen.getByRole("button", { name: "刷新上下文" }));
    expect(await screen.findByText("已同步")).toBeTruthy();
    expect(screen.getAllByText("无相关数据").length).toBeGreaterThan(2);
    expect(screen.getAllByText("未配置").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("示例地点")).toBeNull();
  });

  it("surfaces permission failure and does not claim that context was read", async () => {
    vi.spyOn(api, "agentContext").mockRejectedValue(new ApiError({ status: 403, code: "FORBIDDEN", message: "forbidden" }));
    renderPreview();
    fireEvent.click(screen.getByRole("button", { name: "刷新上下文" }));
    expect(await screen.findByText("没有读取上下文的权限")).toBeTruthy();
    expect(screen.queryByText("已同步")).toBeNull();
    expect(screen.queryByText("当前人物状态")).toBeNull();
  });

  it("sends the selected operation, trimmed instruction, and cloud target", async () => {
    const contextCall = vi.spyOn(api, "agentContext").mockResolvedValue({ ...context(), agent_id: "editor", agent_name: "编辑 Agent", target: "cloud" });
    vi.spyOn(api, "writingGoal").mockResolvedValue({ target_words: 1, target_chapters: 1, current_words: 0, current_chapters: 0, words_progress: 0, chapters_progress: 0, deadline: "" });
    vi.spyOn(api, "resource").mockResolvedValue([]);
    vi.spyOn(api, "worldRules").mockResolvedValue({ items: [], storage: "file" });
    renderPreview({ operation: "polish", instruction: "  保持节奏  ", defaultTarget: "cloud" });
    fireEvent.click(screen.getByRole("button", { name: "刷新上下文" }));
    await waitFor(() => expect(contextCall).toHaveBeenCalledWith("editor", "novel-1", 3, "保持节奏", "cloud"));
  });
});
