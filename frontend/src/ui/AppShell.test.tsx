// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell, ModuleSwitcher, moduleForTaskSource } from "./AppShell";
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement;
afterEach(() => host?.remove());
it('maps every published task family without sending unknown failures to video',()=>{
  expect(moduleForTaskSource('plugin')).toBe('PLUGIN');
  expect(moduleForTaskSource('assets')).toBe('ASSETS');
  expect(moduleForTaskSource('provider')).toBe('CONTROL');
  expect(moduleForTaskSource('unknown')).toBe('WORKFLOW');
});
describe("ModuleSwitcher", () => {
  it("uses one accessible tab contract for every module", () => {
    host = document.createElement("div");
    document.body.append(host);
    const change = vi.fn(),
      root = createRoot(host);
    act(() => root.render(<ModuleSwitcher value="NOVEL" onChange={change} />));
    const tabs = [...host.querySelectorAll('[role="tab"]')];
    expect(tabs).toHaveLength(8);
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    expect(
      tabs.filter((tab) => tab.getAttribute("tabindex") === "0"),
    ).toHaveLength(1);
    act(() => {
      (tabs[1] as HTMLButtonElement).click();
    });
    expect(change).toHaveBeenCalledWith("IMAGE");
    act(() => {
      tabs[0].dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }),
      );
    });
    expect(change).toHaveBeenCalledWith("IMAGE");
    act(() => root.unmount());
  });
});
describe("AppShell inspector recovery", () => {
  it("keeps the editor and chapter navigation rendered while the Inspector collapses and restores", () => {
    host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar={<nav aria-label="章节目录">章节</nav>}
          main={<article>编辑器</article>}
          inspector={<section>AI 工作区</section>}
          status="已保存"
        />,
      ),
    );
    expect(
      host.querySelector(".workspace-inspector")?.getAttribute("aria-hidden"),
    ).toBe("false");
    expect(host.textContent).toContain("编辑器");
    expect(host.textContent).toContain("章节");
    const collapse = host.querySelector<HTMLButtonElement>(
      '.workspace-inspector__controls [aria-label="收起侧栏"]',
    )!;
    expect(collapse.title).toBe("收起侧栏");
    act(() => collapse.click());
    expect(
      host
        .querySelector(".app-shell")
        ?.classList.contains("is-inspector-collapsed"),
    ).toBe(true);
    expect(
      host.querySelector(".workspace-inspector")?.getAttribute("aria-hidden"),
    ).toBe("true");
    const restore = host.querySelector<HTMLButtonElement>(
      ".inspector-edge-toggle",
    )!;
    expect(restore.getAttribute("aria-label")).toBe("展开侧栏");
    expect(restore.getAttribute("aria-expanded")).toBe("false");
    expect(host.textContent).toContain("编辑器");
    expect(host.textContent).toContain("章节");
    act(() => restore.click());
    expect(
      host.querySelector(".workspace-inspector")?.getAttribute("aria-hidden"),
    ).toBe("false");
    expect(restore.getAttribute("aria-label")).toBe("收起侧栏");
    act(() => root.unmount());
  });
});
describe("AppShell inspector sizing", () => {
  it("persists a bounded width after pointer resize", () => {
    localStorage.clear();
    host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar={<></>}
          main={<></>}
          inspector={<></>}
          status="已保存"
        />,
      ),
    );
    const handle = host.querySelector<HTMLElement>(
      ".workspace-inspector__resize",
    )!;
    act(() => {
      handle.dispatchEvent(
        new MouseEvent("pointerdown", { clientX: 500, bubbles: true }),
      );
      window.dispatchEvent(
        new MouseEvent("pointermove", { clientX: 400, bubbles: true }),
      );
      window.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    });
    expect(localStorage.getItem("studio-inspector-width")).toBe("440");
    expect(
      (host.querySelector(".app-shell") as HTMLElement).style.getPropertyValue(
        "--layout-inspector-width",
      ),
    ).toBe("440px");
    act(() => root.unmount());
  });
});
describe("AppShell task dock", () => {
  it("opens failed-task summary and locates the source workspace", () => {
    host = document.createElement("div");
    document.body.append(host);
    const change = vi.fn(),
      root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={change}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar={<></>}
          main={<></>}
          inspector={<></>}
          status="已保存"
        />,
      ),
    );
    act(() =>
      window.dispatchEvent(
        new CustomEvent("studio:task-summary", {
          detail: {
            source: "motion",
            summary: {
              total: 1,
              queued: 0,
              running: 0,
              succeeded: 0,
              failed: 1,
            },
          },
        }),
      ),
    );
    const open = host.querySelector<HTMLButtonElement>(".status-bar__action")!;
    expect(open).toBeTruthy();
    act(() => open.click());
    expect(host.textContent).toContain("motion");
    const row = host.querySelector<HTMLButtonElement>(".task-inspector__row")!;
    act(() => row.click());
    expect(change).toHaveBeenCalledWith("VIDEO");
    act(() => root.unmount());
  });
});
describe("AppShell task source routing", () => {
  it.each([
    ["speech", "AUDIO"],
    ["audiobook", "AUDIO"],
    ["audio", "AUDIO"],
    ["image", "IMAGE"],
    ["motion", "VIDEO"],
    ["workflow", "WORKFLOW"],
    ["agent", "WORKFLOW"],
  ])("routes %s failures to %s", (source, expected) => {
    host = document.createElement("div");
    document.body.append(host);
    const change = vi.fn();
    const root = createRoot(host);
    act(() => root.render(<AppShell module="NOVEL" onModuleChange={change} scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }} actor="author" sidebar={<></>} main={<></>} inspector={<></>} status="已保存" />));
    act(() => window.dispatchEvent(new CustomEvent("studio:task-summary", { detail: { source, summary: { total: 1, queued: 0, running: 0, succeeded: 0, failed: 1, failures: [{ id: `${source}-1` }] } } })));
    act(() => host.querySelector<HTMLButtonElement>(".status-bar__action")?.click());
    const row = host.querySelector<HTMLButtonElement>(".task-inspector__row")!;
    act(() => row.click());
    expect(change).toHaveBeenCalledWith(expected);
    act(() => root.unmount());
  });
});
describe("AppShell failed task keyboard navigation", () => {
  it("moves between failure rows with arrow keys", () => {
    host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar={<></>}
          main={<></>}
          inspector={<></>}
          status="已保存"
        />,
      ),
    );
    act(() =>
      window.dispatchEvent(
        new CustomEvent("studio:task-summary", {
          detail: {
            source: "motion",
            summary: {
              total: 2,
              queued: 0,
              running: 0,
              succeeded: 0,
              failed: 2,
              failures: [{ id: "motion-1" }, { id: "motion-2" }],
            },
          },
        }),
      ),
    );
    act(() =>
      host.querySelector<HTMLButtonElement>(".status-bar__action")!.click(),
    );
    const rows = [
      ...host.querySelectorAll<HTMLButtonElement>(".task-inspector__row"),
    ];
    act(() => rows[0].focus());
    act(() =>
      rows[0].dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }),
      ),
    );
    expect(document.activeElement).toBe(rows[1]);
    act(() => root.unmount());
  });
});
describe("AppShell failed-task keyboard handling", () => {
  it("moves focus into the dialog and closes with Escape without collapsing Inspector", async () => {
    host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar={<></>}
          main={<></>}
          inspector={<></>}
          status="已保存"
        />,
      ),
    );
    act(() =>
      window.dispatchEvent(
        new CustomEvent("studio:task-summary", {
          detail: {
            source: "image",
            summary: {
              total: 1,
              queued: 0,
              running: 0,
              succeeded: 0,
              failed: 1,
            },
          },
        }),
      ),
    );
    act(() =>
      host.querySelector<HTMLButtonElement>(".status-bar__action")!.click(),
    );
    await act(async () => {
      await new Promise((resolve) => requestAnimationFrame(resolve));
    });
    const close = host.querySelector<HTMLButtonElement>(
      '[aria-label="关闭失败任务"]',
    )!;
    expect(document.activeElement).toBe(close);
    act(() =>
      close.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      ),
    );
    expect(
      host.querySelector('[role="dialog"][aria-label="失败任务"]'),
    ).toBeNull();
    expect(
      host.querySelector(".workspace-inspector")?.getAttribute("aria-hidden"),
    ).toBe("false");
    act(() => root.unmount());
  });
});
describe("AppShell command actions", () => {
  it("opens the real Provider control workspace", () => {
    host = document.createElement("div");
    document.body.append(host);
    const change = vi.fn();
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={change}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar={<></>}
          main={<></>}
          inspector={<></>}
          status="已保存"
        />,
      ),
    );
    act(() => host.querySelector<HTMLButtonElement>(".global-search")!.click());
    const provider = [
      ...host.querySelectorAll<HTMLButtonElement>(
        ".command-palette__list button",
      ),
    ].find((button) => button.textContent?.includes("Provider 控制中心"))!;
    expect(provider.textContent).toContain("控制中心");
    act(() => provider.click());
    expect(change).toHaveBeenCalledWith("CONTROL");
    expect(host.querySelector(".command-palette")).toBeNull();
    act(() => root.unmount());
  });
});
