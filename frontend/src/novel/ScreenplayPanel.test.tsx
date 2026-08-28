// @vitest-environment jsdom
import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {act, cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {api} from "../api";
import {ScreenplayPanel} from "./ScreenplayPanel";

vi.mock("./MotionTaskWorkspace", () => ({MotionTaskWorkspace: () => null}));
vi.mock("./ScreenplayPipelinePanel", () => ({ScreenplayPipelinePanel: () => null}));
vi.mock("./PipelineStatusPanel", () => ({PipelineStatusPanel: () => null}));
vi.mock("./AssetTaskExecutionPanel", () => ({AssetTaskExecutionPanel: () => null}));

const novelId = "novel-1";
const screenplayId = "screenplay-1";
const savedPrompt = "saved camera orbit";

function transition(id = "transition-1", motionPrompt = savedPrompt) {
  return {
    id,
    type: "CUT",
    duration_seconds: 1,
    note: "",
    from_shot_id: "shot-1",
    to_shot_id: "shot-2",
    prompt: "existing transition prompt",
    prompt_status: "DRAFT",
    prompt_history: [],
    motion_prompt: motionPrompt,
  };
}

function screenplay(row = transition(), approved = false) {
  return {
    id: screenplayId,
    novel_id: novelId,
    title: "Contract screenplay",
    status: "APPROVED",
    scenes: [],
    shots: [],
    shot_status: "APPROVED",
    storyboard: [],
    transitions: [row],
    transition_status: approved ? "APPROVED" : "DRAFT",
    motion_tasks: [],
  };
}

function panel(client: QueryClient) {
  return <QueryClientProvider client={client}><ScreenplayPanel novelId={novelId}/></QueryClientProvider>;
}

function renderPanel(row = transition(), approved = false) {
  const data = screenplay(row, approved);
  vi.spyOn(api, "screenplays").mockResolvedValue([data]);
  const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
  const view = render(panel(client));
  return {client, data, ...view};
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("REAL_NETWORK_REQUEST_BLOCKED"); }));
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ScreenplayPanel Motion Prompt contract", () => {
  it("initializes from a saved prompt and syncs a genuinely persisted update", async () => {
    const {client} = renderPanel();
    expect(await screen.findByDisplayValue(savedPrompt)).toBeTruthy();
    act(() => client.setQueryData(["screenplays", novelId], [screenplay(transition("transition-1", "persisted update"))]));
    expect(await screen.findByDisplayValue("persisted update")).toBeTruthy();
  });

  it("does not overwrite an unsaved edit during an ordinary parent rerender", async () => {
    const {client, rerender} = renderPanel();
    const editor = await screen.findByLabelText("Motion Prompt");
    fireEvent.change(editor, {target: {value: "local unsaved edit"}});
    rerender(panel(client));
    expect(screen.getByDisplayValue("local unsaved edit")).toBeTruthy();
  });

  it("generates without saving and sends exact generation identifiers", async () => {
    const generate = vi.spyOn(api, "motionPrompt").mockResolvedValue({motion_prompt: "generated tracking shot", status: "DRAFT"});
    const save = vi.spyOn(api, "saveMotionPrompt").mockResolvedValue({});
    renderPanel();
    fireEvent.click(await screen.findByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByDisplayValue("generated tracking shot")).toBeTruthy();
    expect(generate).toHaveBeenCalledWith(novelId, screenplayId, "transition-1");
    expect(save).not.toHaveBeenCalled();
  });

  it("saves the current edit once and invalidates the screenplay query", async () => {
    const save = vi.spyOn(api, "saveMotionPrompt").mockResolvedValue({});
    const {client} = renderPanel();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue(undefined);
    fireEvent.change(await screen.findByLabelText("Motion Prompt"), {target: {value: "manual dolly"}});
    fireEvent.click(screen.getByRole("button", {name: "保存 Motion Prompt"}));
    await waitFor(() => expect(save).toHaveBeenCalledWith(novelId, screenplayId, "transition-1", "manual dolly"));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({queryKey: ["screenplays", novelId]}));
  });

  it.each([undefined, "", "   "])("fails closed for an empty generated value %j without replacing the saved prompt", async (value) => {
    vi.spyOn(api, "motionPrompt").mockResolvedValue({motion_prompt: value, status: "DRAFT"} as any);
    renderPanel();
    fireEvent.click(await screen.findByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByText("Motion Prompt 生成失败：返回内容为空。")).toBeTruthy();
    expect(screen.getByDisplayValue(savedPrompt)).toBeTruthy();
  });

  it("reports generation rejection safely, preserves the edit, and clears only its own error on retry", async () => {
    const generate = vi.spyOn(api, "motionPrompt").mockRejectedValueOnce(new Error("secret backend URL"));
    renderPanel();
    const editor = await screen.findByLabelText("Motion Prompt");
    fireEvent.change(editor, {target: {value: "keep this edit"}});
    fireEvent.click(screen.getByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByText("Motion Prompt 生成失败。")).toBeTruthy();
    expect(screen.getByDisplayValue("keep this edit")).toBeTruthy();
    generate.mockResolvedValueOnce({motion_prompt: "recovered motion", status: "DRAFT"});
    fireEvent.click(screen.getByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByDisplayValue("recovered motion")).toBeTruthy();
    expect(screen.queryByText("Motion Prompt 生成失败。")).toBeNull();
  });

  it("reports save rejection without false success and clears the error after a successful retry", async () => {
    const save = vi.spyOn(api, "saveMotionPrompt").mockRejectedValueOnce(new Error("credential detail"));
    renderPanel();
    fireEvent.click(await screen.findByRole("button", {name: "保存 Motion Prompt"}));
    expect(await screen.findByText("Motion Prompt 保存失败。")).toBeTruthy();
    save.mockResolvedValueOnce({});
    fireEvent.click(screen.getByRole("button", {name: "保存 Motion Prompt"}));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText("Motion Prompt 保存失败。")).toBeNull());
  });

  it("keeps Transition Prompt and Motion Prompt failures independent", async () => {
    vi.spyOn(api, "transitionPrompt").mockRejectedValue(new Error("transition failure"));
    const motion = vi.spyOn(api, "motionPrompt").mockRejectedValueOnce(new Error("motion failure"));
    renderPanel();
    fireEvent.click(await screen.findByRole("button", {name: "生成 Transition Prompt"}));
    expect(await screen.findByText("Prompt 生成失败，请确认剧本已保存。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByText("Motion Prompt 生成失败。")).toBeTruthy();
    motion.mockResolvedValueOnce({motion_prompt: "motion recovered", status: "DRAFT"});
    fireEvent.click(screen.getByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByDisplayValue("motion recovered")).toBeTruthy();
    expect(screen.getByText("Prompt 生成失败，请确认剧本已保存。")).toBeTruthy();
    expect(screen.queryByText("Motion Prompt 生成失败。")).toBeNull();
  });

  it("does not let a Transition Prompt success clear a Motion Prompt error", async () => {
    vi.spyOn(api, "motionPrompt").mockRejectedValue(new Error("motion failure"));
    vi.spyOn(api, "transitionPrompt").mockResolvedValue({prompt: "new transition", template_version: "v1", generated_at: new Date(0).toISOString()} as any);
    renderPanel();
    fireEvent.click(await screen.findByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByText("Motion Prompt 生成失败。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", {name: "生成 Transition Prompt"}));
    expect(await screen.findByDisplayValue("new transition")).toBeTruthy();
    expect(screen.getByText("Motion Prompt 生成失败。")).toBeTruthy();
  });

  it("keeps transition suggestion failures independent from Motion success", async () => {
    vi.spyOn(api, "transitionSuggestion").mockRejectedValue(new Error("suggestion failure"));
    vi.spyOn(api, "motionPrompt").mockResolvedValue({motion_prompt: "motion succeeds", status: "DRAFT"});
    renderPanel();
    fireEvent.click(await screen.findByRole("button", {name: "获取类型建议"}));
    expect(await screen.findByText("转场建议生成失败。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByDisplayValue("motion succeeds")).toBeTruthy();
    expect(screen.getByText("转场建议生成失败。")).toBeTruthy();
  });

  it("does not misreport a post-save refresh failure as a save failure", async () => {
    const save = vi.spyOn(api, "saveMotionPrompt").mockResolvedValue({});
    const {client} = renderPanel();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockRejectedValue(new Error("refresh failure"));
    fireEvent.click(await screen.findByRole("button", {name: "保存 Motion Prompt"}));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("Motion Prompt 保存失败。")).toBeNull();
  });

  it("shows a saved prompt read-only when approved and blocks generation and save", async () => {
    const generate = vi.spyOn(api, "motionPrompt").mockResolvedValue({motion_prompt: "must not appear", status: "DRAFT"});
    const save = vi.spyOn(api, "saveMotionPrompt").mockResolvedValue({});
    renderPanel(transition(), true);
    const editor = await screen.findByLabelText("Motion Prompt") as HTMLTextAreaElement;
    expect(editor.value).toBe(savedPrompt);
    expect(editor.readOnly).toBe(true);
    const button = screen.getByRole("button", {name: "生成 Motion Prompt"}) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(generate).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", {name: "保存 Motion Prompt"})).toBeNull();
    expect(save).not.toHaveBeenCalled();
  });

  it("guards duplicate generation and save while either operation is pending", async () => {
    const generation = deferred<{motion_prompt: string; status: string}>();
    const generate = vi.spyOn(api, "motionPrompt").mockReturnValue(generation.promise);
    const saveRequest = deferred<unknown>();
    const save = vi.spyOn(api, "saveMotionPrompt").mockReturnValue(saveRequest.promise as any);
    renderPanel();
    const generateButton = await screen.findByRole("button", {name: "生成 Motion Prompt"}) as HTMLButtonElement;
    fireEvent.click(generateButton); fireEvent.click(generateButton);
    expect(generate).toHaveBeenCalledTimes(1);
    expect(generateButton.disabled).toBe(true);
    expect((screen.getByRole("button", {name: "保存 Motion Prompt"}) as HTMLButtonElement).disabled).toBe(true);
    generation.resolve({motion_prompt: "generated once", status: "DRAFT"});
    await screen.findByDisplayValue("generated once");
    const saveButton = screen.getByRole("button", {name: "保存 Motion Prompt"}) as HTMLButtonElement;
    fireEvent.click(saveButton); fireEvent.click(saveButton);
    expect(save).toHaveBeenCalledTimes(1);
    expect(saveButton.disabled).toBe(true);
    expect((screen.getByRole("button", {name: "生成 Motion Prompt"}) as HTMLButtonElement).disabled).toBe(true);
    saveRequest.resolve({});
    await waitFor(() => expect(saveButton.disabled).toBe(false));
  });

  it("resets prompt and Motion error when switching transitions", async () => {
    vi.spyOn(api, "motionPrompt").mockRejectedValue(new Error("old transition failure"));
    const {client} = renderPanel();
    fireEvent.click(await screen.findByRole("button", {name: "生成 Motion Prompt"}));
    expect(await screen.findByText("Motion Prompt 生成失败。")).toBeTruthy();
    act(() => client.setQueryData(["screenplays", novelId], [screenplay(transition("transition-2", "second saved prompt"))]));
    expect(await screen.findByDisplayValue("second saved prompt")).toBeTruthy();
    expect(screen.queryByText("Motion Prompt 生成失败。")).toBeNull();
  });

  it("never performs a real fetch", async () => {
    renderPanel();
    await screen.findByLabelText("Motion Prompt");
    expect(fetch).not.toHaveBeenCalled();
  });
});
