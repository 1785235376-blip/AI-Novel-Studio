// @vitest-environment jsdom
import { StrictMode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { dehydrate, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App, { RevisionHistory } from "./App";
import { api, type Chapter, type Scope } from "./api";
import { useStudio } from "./store";
import { conflicts, drafts } from "./drafts";
import { recoveryKey } from "./collaborationGuards";

// Exercise the real App queries, revision panel, draft persistence and hydration.
// Only unrelated shell chrome and the rich-text widget are replaced.
vi.mock("./Editor", async importOriginal => ({ ...(await importOriginal<typeof import("./Editor")>()), ChapterEditor: ({ content, onChange }: any) =>
  <textarea aria-label="Test chapter editor" value={content} onChange={event => onChange(event.target.value, documentOf(event.target.value))} /> }));
vi.mock("./ui/AppShell", () => ({ AppShell: ({ main, status }: any) => <><main>{main}</main><footer>{status}</footer></> }));
vi.mock("./novel/AiWritingPanel", () => ({ AiWritingPanel: () => null }));
vi.mock("./novel/SourcePrivacyControl", () => ({ SourcePrivacyControl: () => null }));
vi.mock("./novel/ChapterTree", () => ({ ChapterTree: () => null }));
vi.mock("./ui/FeatureLauncher", () => ({ FeatureLauncher: () => null }));

function documentOf(text: string) { return { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text }] }] }; }
function chapterOf(version = 2, id = "novel-a:1", content = "SAVED CURRENT"): Chapter {
  return { id, novel_id: id.split(":")[0], number: 1, title: "Synthetic", version, content,
    document: documentOf(content), word_count: content.length, status: "DRAFT" };
}
function revision(version = 1, text = "HISTORICAL ORIGINAL", operator = "Synthetic author") {
  return { version, document: documentOf(text), timestamp: "2026-10-05T00:00:00Z", source: "USER", operator };
}
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const clients: QueryClient[] = [];
const reload = vi.fn();
function client() {
  const value = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  clients.push(value); return value;
}
function wrap(query: QueryClient, children: React.ReactNode) { return <QueryClientProvider client={query}>{children}</QueryClientProvider>; }
beforeEach(() => {
  localStorage.clear();
  useStudio.getState().setCollaboration("");
  useStudio.setState({ novelId: "novel-a", chapterId: "novel-a:1", textModel: null });
  reload.mockClear();
  vi.stubGlobal("location", { reload });
});
afterEach(() => { cleanup(); clients.splice(0).forEach(value => value.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); });

it("refreshes mounted history when the server chapter advances from v2 to v3", async () => {
  const history = vi.spyOn(api, "legacyHistory").mockResolvedValueOnce([revision(1)]).mockResolvedValue([revision(2, "PRE AI SAVE"), revision(1)]);
  const query = client(), restored = vi.fn();
  const view = render(wrap(query, <RevisionHistory chapter={chapterOf(2)} sessionToken="" onRestored={restored} />));
  await screen.findByRole("button", { name: /版本 1/ });
  expect(screen.queryByRole("button", { name: /版本 2/ })).toBeNull();
  view.rerender(wrap(query, <RevisionHistory chapter={chapterOf(3)} sessionToken="" onRestored={restored} />));
  fireEvent.click(await screen.findByRole("button", { name: /版本 2/ }));
  expect(await screen.findByText("PRE AI SAVE")).toBeTruthy();
  expect(history).toHaveBeenCalledTimes(2);
});

const scopeA: Scope = { workspaceId: "workspace-a", projectId: "novel-a", storylineId: "story-a", branchId: "branch-a" };
const actorA = { id: "actor-a", workspaceId: "workspace-a", displayName: "Synthetic author" };
function setContext(scope = scopeA, token = "private-session-a", actor = actorA, chapter = chapterOf()) {
  useStudio.getState().setCollaboration(token, actor, scope);
  useStudio.setState({ novelId: chapter.novel_id, chapterId: chapter.id });
}

it.each(["project", "branch", "session", "actor", "workspace", "storyline"])("discards old revision-list responses after %s changes", async change => {
  setContext();
  const old = deferred<any[]>();
  const history = vi.spyOn(api, "history").mockReturnValueOnce(old.promise).mockResolvedValue([revision(7, "NEW", "New scope author")]);
  const query = client(), onRestored = vi.fn();
  const view = render(wrap(query, <RevisionHistory chapter={chapterOf()} scope={scopeA} sessionToken="private-session-a" onRestored={onRestored} />));
  await waitFor(() => expect(history).toHaveBeenCalledTimes(1));
  const scope = { ...scopeA, ...(change === "project" ? { projectId: "novel-b" } : {}),
    ...(change === "branch" ? { branchId: "branch-b" } : {}), ...(change === "workspace" ? { workspaceId: "workspace-b" } : {}),
    ...(change === "storyline" ? { storylineId: "story-b" } : {}) };
  const token = change === "session" ? "private-session-b" : "private-session-a";
  const actor = change === "actor" ? { ...actorA, id: "actor-b" } : actorA;
  const chapter = change === "project" ? chapterOf(2, "novel-b:1") : chapterOf();
  act(() => { setContext(scope, token, actor, chapter); });
  view.rerender(wrap(query, <RevisionHistory chapter={chapter} scope={scope} sessionToken={token} onRestored={onRestored} />));
  await screen.findByRole("button", { name: /版本 7/ });
  await act(async () => old.resolve([revision(1, "OLD", "PRIVATE OLD ACTOR")]));
  expect(screen.queryByText(/PRIVATE OLD ACTOR/)).toBeNull();
  expect(history).toHaveBeenLastCalledWith(scope, chapter.id, { sessionToken: token, actor, scope });
  expect(JSON.stringify(query.getQueryCache().getAll().map(row => row.queryKey))).not.toContain("private-session");
  expect(JSON.stringify(dehydrate(query))).not.toContain("private-session");
});

it("discards old selected-revision details after switching projects", async () => {
  setContext();
  vi.spyOn(api, "history").mockResolvedValue([revision()]);
  const pending = deferred<any>();
  vi.spyOn(api, "revisionDetail").mockReturnValueOnce(pending.promise).mockResolvedValue(revision(1, "NEW DETAIL"));
  const query = client(), restored = vi.fn();
  const view = render(wrap(query, <RevisionHistory chapter={chapterOf()} scope={scopeA} sessionToken="private-session-a" onRestored={restored} />));
  fireEvent.click(await screen.findByRole("button", { name: /版本 1/ }));
  const scopeB = { ...scopeA, projectId: "novel-b" }, chapterB = chapterOf(2, "novel-b:1");
  act(() => setContext(scopeB, "private-session-b", actorA, chapterB));
  view.rerender(wrap(query, <RevisionHistory chapter={chapterB} scope={scopeB} sessionToken="private-session-b" onRestored={restored} />));
  fireEvent.click(await screen.findByRole("button", { name: /版本 1/ }));
  await screen.findByText("NEW DETAIL");
  await act(async () => pending.resolve(revision(1, "PRIVATE OLD DETAIL")));
  expect(screen.queryByText("PRIVATE OLD DETAIL")).toBeNull();
});

async function confirmRestore() {
  fireEvent.click(await screen.findByRole("button", { name: /版本 1/ }));
  fireEvent.click(await screen.findByRole("button", { name: "预览并恢复此版本" }));
  fireEvent.click(screen.getByRole("button", { name: "恢复此版本" }));
}

it.each(["project", "branch", "session", "actor", "aba"])("ignores late restore completion after %s navigation", async change => {
  setContext();
  vi.spyOn(api, "history").mockResolvedValue([revision()]);
  vi.spyOn(api, "revisionDetail").mockResolvedValue(revision());
  const pending = deferred<Chapter>(), onRestored = vi.fn();
  const restore = vi.spyOn(api, "restore").mockReturnValue(pending.promise);
  const query = client();
  const view = render(wrap(query, <RevisionHistory chapter={chapterOf()} scope={scopeA} sessionToken="private-session-a" onRestored={onRestored} />));
  await confirmRestore();
  expect(restore).toHaveBeenCalledWith("novel-a:1", 1, 2, { sessionToken: "private-session-a", actor: actorA, scope: scopeA });
  const scope = { ...scopeA, ...(change === "project" ? { projectId: "novel-b" } : {}), ...(change === "branch" ? { branchId: "branch-b" } : {}) };
  const token = change === "session" ? "private-session-b" : "private-session-a";
  const actor = change === "actor" ? { ...actorA, id: "actor-b" } : actorA;
  const chapter = change === "project" ? chapterOf(2, "novel-b:1") : chapterOf();
  act(() => {
    if (change === "aba") { setContext({ ...scopeA, branchId: "temporary-branch" }); setContext(); }
    else setContext(scope, token, actor, chapter);
  });
  view.rerender(wrap(query, <RevisionHistory chapter={chapter} scope={scope} sessionToken={token} onRestored={onRestored} />));
  await act(async () => pending.resolve(chapterOf(3, "novel-a:1", "OLD RESTORE")));
  expect(onRestored).not.toHaveBeenCalled();
  expect(reload).not.toHaveBeenCalled();
  expect(screen.queryByText(/恢复完成/)).toBeNull();
});

function appClient(chapter = chapterOf()) {
  const query = client();
  query.setQueryData(["novels"], [{ id: "novel-a", title: "Synthetic novel" }]);
  query.setQueryData(["chapter", "file", chapter.id], chapter);
  query.setQueryData(["chapters", "file", chapter.novel_id], [chapter]);
  query.setQueryData(["archived-chapters", "file", chapter.novel_id], []);
  query.setQueryData(["text-models"], []);
  query.setQueryData(["media-tasks", chapter.novel_id], { audiobook: [], motion: [] });
  query.setQueryData(["writing-goal", chapter.novel_id], { current_words: 0, target_words: 0, current_chapters: 1, target_chapters: 0, words_progress: 0 });
  vi.spyOn(api, "chapters").mockResolvedValue([chapter]);
  vi.spyOn(api, "legacyHistory").mockResolvedValue([revision()]);
  return query;
}

it("routes restore through actual App hydration without overwriting a newer dirty buffer", async () => {
  const query = appClient(), pending = deferred<Chapter>();
  vi.spyOn(api, "restore").mockReturnValue(pending.promise);
  render(wrap(query, <App />));
  await waitFor(() => expect((screen.getByLabelText("Test chapter editor") as HTMLTextAreaElement).value).toBe("SAVED CURRENT"));
  await confirmRestore();
  fireEvent.change(screen.getByLabelText("Test chapter editor"), { target: { value: "NEW UNSAVED LOCAL DRAFT" } });
  await act(async () => pending.resolve(chapterOf(3, "novel-a:1", "RESTORED SERVER VERSION")));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText("NEW UNSAVED LOCAL DRAFT", { selector: "pre" })).toBeTruthy();
  expect(within(dialog).getByText("RESTORED SERVER VERSION", { selector: "pre" })).toBeTruthy();
  expect((screen.getByLabelText("Test chapter editor") as HTMLTextAreaElement).value).toBe("NEW UNSAVED LOCAL DRAFT");
  expect(drafts.load("novel-a:1", "file")?.content).toBe("NEW UNSAVED LOCAL DRAFT");
  expect(conflicts.load("novel-a:1", "file")?.server.version).toBe(3);
  expect(reload).not.toHaveBeenCalled();
});

it("hydrates a clean buffer from the returned chapter without reloading", async () => {
  const query = appClient();
  vi.spyOn(api, "restore").mockResolvedValue(chapterOf(3, "novel-a:1", "RESTORED CLEAN BUFFER"));
  render(wrap(query, <App />));
  await confirmRestore();
  await waitFor(() => expect((screen.getByLabelText("Test chapter editor") as HTMLTextAreaElement).value).toBe("RESTORED CLEAN BUFFER"));
  expect(query.getQueryData<Chapter>(["chapter", "file", "novel-a:1"])?.version).toBe(3);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(reload).not.toHaveBeenCalled();
});

it.each(["project", "branch", "session"])("actual App preserves the new dirty buffer when old restore completes after %s change", async change => {
  setContext();
  const query = appClient(), pending = deferred<Chapter>();
  function seedScope(chapter: Chapter, scope: Scope, token: string) {
    const namespace = recoveryKey(scope, token) || "file";
    query.setQueryData(["chapter", namespace, chapter.id], chapter);
    query.setQueryData(["chapters", namespace, chapter.novel_id], [chapter]);
    query.setQueryData(["archived-chapters", namespace, chapter.novel_id], []);
    query.setQueryData(["media-tasks", chapter.novel_id], { audiobook: [], motion: [] });
    query.setQueryData(["writing-goal", chapter.novel_id], { current_words: 0, target_words: 0, current_chapters: 1, target_chapters: 0, words_progress: 0 });
    query.setQueryData(["bootstrap", namespace], {
      actor: { actor_id: actorA.id, session_id: "synthetic", client_id: "synthetic" },
      scope: { workspace_id: scope.workspaceId, project_id: scope.projectId, storyline_id: scope.storylineId, branch_id: scope.branchId }, capabilities: {},
    });
    return namespace;
  }
  const namespaceA = seedScope(chapterOf(), scopeA, "private-session-a");
  vi.spyOn(api, "history").mockResolvedValue([revision()]);
  vi.spyOn(api, "revisionDetail").mockResolvedValue(revision());
  vi.spyOn(api, "restore").mockReturnValue(pending.promise);
  render(wrap(query, <App />));
  await confirmRestore();
  const scopeB = { ...scopeA, ...(change === "project" ? { projectId: "novel-b" } : {}), ...(change === "branch" ? { branchId: "branch-b" } : {}) };
  const tokenB = change === "session" ? "private-session-b" : "private-session-a";
  const chapterB = chapterOf(8, change === "project" ? "novel-b:1" : "novel-a:1", "NEW CONTEXT SAVED");
  const namespaceB = seedScope(chapterB, scopeB, tokenB);
  act(() => setContext(scopeB, tokenB, actorA, chapterB));
  await waitFor(() => expect((screen.getByLabelText("Test chapter editor") as HTMLTextAreaElement).value).toBe("NEW CONTEXT SAVED"));
  fireEvent.change(screen.getByLabelText("Test chapter editor"), { target: { value: "NEW CONTEXT DIRTY DRAFT" } });
  await act(async () => pending.resolve(chapterOf(3, "novel-a:1", "LATE PRIVATE OLD RESTORE")));
  expect((screen.getByLabelText("Test chapter editor") as HTMLTextAreaElement).value).toBe("NEW CONTEXT DIRTY DRAFT");
  expect(drafts.load(chapterB.id, namespaceB)?.content).toBe("NEW CONTEXT DIRTY DRAFT");
  expect(conflicts.load(chapterB.id, namespaceB)).toBeUndefined();
  expect(query.getQueryData<Chapter>(["chapter", namespaceB, chapterB.id])?.version).toBe(8);
  expect(query.getQueryData<Chapter>(["chapter", namespaceA, "novel-a:1"])?.version).toBe(2);
  expect(screen.queryByText("LATE PRIVATE OLD RESTORE")).toBeNull();
  expect(reload).not.toHaveBeenCalled();
});

it("actual App refreshes mounted history after chapter cache advances on AI Accept", async () => {
  const query = appClient();
  vi.mocked(api.legacyHistory).mockResolvedValueOnce([revision(1)]).mockResolvedValue([revision(2, "PRE AI VERSION TWO"), revision(1)]);
  render(wrap(query, <App />));
  await screen.findByRole("button", { name: /版本 1/ });
  act(() => { query.setQueryData(["chapter", "file", "novel-a:1"], chapterOf(3, "novel-a:1", "ACCEPTED AI VERSION")); });
  fireEvent.click(await screen.findByRole("button", { name: /版本 2/ }));
  expect(await screen.findByText("PRE AI VERSION TWO")).toBeTruthy();
});

it.each([false, true])("StrictMode retains the first deferred history response and usable restore controls, collaboration=%s", async collaboration => {
  if (collaboration) setContext();
  const query = client(), history = deferred<any[]>(), detail = deferred<any>(), restoreResult = deferred<Chapter>();
  const historySpy = collaboration ? vi.spyOn(api, "history").mockReturnValue(history.promise)
    : vi.spyOn(api, "legacyHistory").mockReturnValue(history.promise);
  const detailSpy = vi.spyOn(api, "revisionDetail").mockReturnValue(detail.promise);
  const restore = vi.spyOn(api, "restore").mockReturnValue(restoreResult.promise);
  const onRestored = vi.fn();
  render(<StrictMode>{wrap(query, <RevisionHistory chapter={chapterOf()} scope={collaboration ? scopeA : undefined}
    sessionToken={collaboration ? "private-session-a" : ""} onRestored={onRestored} />)}</StrictMode>);
  await waitFor(() => expect(historySpy).toHaveBeenCalledTimes(1));
  await act(async () => history.resolve([revision(1, "STRICT INITIAL HISTORY")]));
  fireEvent.click(await screen.findByRole("button", { name: /版本 1/ }));
  if (collaboration) {
    await waitFor(() => expect(detailSpy).toHaveBeenCalledTimes(1));
    await act(async () => detail.resolve(revision(1, "STRICT SCOPED DETAIL")));
    expect(await screen.findByText("STRICT SCOPED DETAIL")).toBeTruthy();
  } else expect(await screen.findByText("STRICT INITIAL HISTORY")).toBeTruthy();
  fireEvent.click(await screen.findByRole("button", { name: "预览并恢复此版本" }));
  fireEvent.click(screen.getByRole("button", { name: "恢复此版本" }));
  expect(restore).toHaveBeenCalledTimes(1);
  await act(async () => restoreResult.resolve(chapterOf(3, "novel-a:1", "STRICT RESTORED")));
  expect(onRestored).toHaveBeenCalledTimes(1);
  expect(onRestored).toHaveBeenCalledWith(chapterOf(3, "novel-a:1", "STRICT RESTORED"));
  expect(await screen.findByText(/恢复完成/)).toBeTruthy();
  expect(reload).not.toHaveBeenCalled();
});

it("StrictMode still ignores a late restore after a genuine unmount", async () => {
  const query = client(), pending = deferred<Chapter>(), onRestored = vi.fn();
  vi.spyOn(api, "legacyHistory").mockResolvedValue([revision()]);
  vi.spyOn(api, "restore").mockReturnValue(pending.promise);
  const view = render(<StrictMode>{wrap(query, <RevisionHistory chapter={chapterOf()} sessionToken="" onRestored={onRestored} />)}</StrictMode>);
  await confirmRestore();
  view.unmount();
  await act(async () => pending.resolve(chapterOf(3)));
  expect(onRestored).not.toHaveBeenCalled();
  expect(reload).not.toHaveBeenCalled();
});

it("StrictMode still fences a pending initial history request across a branch switch", async () => {
  setContext();
  const query = client(), pending = deferred<any[]>(), onRestored = vi.fn();
  vi.spyOn(api, "history").mockReturnValueOnce(pending.promise).mockResolvedValue([revision(9, "NEW BRANCH", "New branch author")]);
  const view = render(<StrictMode>{wrap(query, <RevisionHistory chapter={chapterOf()} scope={scopeA} sessionToken="private-session-a" onRestored={onRestored} />)}</StrictMode>);
  const scopeB = { ...scopeA, branchId: "strict-branch-b" };
  act(() => setContext(scopeB));
  view.rerender(<StrictMode>{wrap(query, <RevisionHistory chapter={chapterOf()} scope={scopeB} sessionToken="private-session-a" onRestored={onRestored} />)}</StrictMode>);
  await screen.findByRole("button", { name: /版本 9/ });
  await act(async () => pending.resolve([revision(1, "OLD BRANCH", "PRIVATE STRICT OLD BRANCH")]));
  expect(screen.queryByText(/PRIVATE STRICT OLD BRANCH/)).toBeNull();
  expect(screen.getByRole("button", { name: /版本 9/ })).toBeTruthy();
});
