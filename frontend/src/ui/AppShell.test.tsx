// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell, ModuleSwitcher, moduleForTaskSource, SettingsPathGateway } from "./AppShell";
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement;
beforeEach(() => {
  // [HERMIA-FE-20261022 N-UX-09] Wide viewport = overnight expanded default for existing shells.
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1440 });
});
afterEach(() => host?.remove());
it('maps every published task family without sending unknown failures to video',()=>{
  expect(moduleForTaskSource('plugin')).toBe('PLUGIN');
  expect(moduleForTaskSource('assets')).toBe('ASSETS');
  expect(moduleForTaskSource('provider')).toBe('CONTROL');
  expect(moduleForTaskSource('unknown')).toBe('WORKFLOW');
});
// [HERMIA-FE-20261025 DUI P1-5] Spec change: in normal mode pro entries (Provider/插件/工作流/主控 module) are not listed
// until the user types a query; they remain reachable by search. Helper types into the palette input.
function typeCommand(host: HTMLElement, text: string) {
  const input = host.querySelector<HTMLInputElement>(".command-palette input")!;
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, text);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("ModuleSwitcher", () => {
  it("uses one accessible tab contract for every module", () => {
    host = document.createElement("div");
    document.body.append(host);
    const change = vi.fn(),
      root = createRoot(host);
    act(() => root.render(<ModuleSwitcher value="NOVEL" onChange={change} />));
    const tabs = [...host.querySelectorAll('[role="tab"]')];
    expect(tabs).toHaveLength(6);
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
  it("collapses an open Inspector when the desktop window becomes compact", () => {
    host = document.createElement("div");
    document.body.append(host);
    let viewportListener: ((event: MediaQueryListEvent) => void) | undefined;
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: (_event: string, listener: (event: MediaQueryListEvent) => void) => { viewportListener = listener; },
      removeEventListener: vi.fn(),
    });
    const root = createRoot(host);
    act(() => root.render(<AppShell module="NOVEL" onModuleChange={vi.fn()} scope={{workspace:"w",project:"p",storyline:"s",branch:"b"}} actor="author" sidebar={<></>} main={<article>编辑器</article>} inspector={<section>AI 工作区</section>} status="已保存"/>));
    expect(host.querySelector(".app-shell")?.classList.contains("is-inspector-collapsed")).toBe(false);
    act(() => viewportListener?.({ matches: true } as MediaQueryListEvent));
    expect(host.querySelector(".app-shell")?.classList.contains("is-inspector-collapsed")).toBe(true);
    act(() => root.unmount());
    window.matchMedia = originalMatchMedia;
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
    typeCommand(host, "provider");
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

describe('R4 optional global-search consumer', () => {
  it('uses the supplied current search action and ignores composing shortcuts', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host), open = vi.fn();
    const props = { module: 'NOVEL' as const, onModuleChange: vi.fn(), scope: { workspace: '', project: '', storyline: '', branch: '' }, actor: 'author', sidebar: null, main: 'Editor', inspector: null, status: 'Saved' };
    act(() => root.render(<AppShell {...props} onGlobalSearch={open} />));
    act(() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, isComposing: true })));
    expect(open).not.toHaveBeenCalled();
    act(() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })));
    expect(open).toHaveBeenCalledTimes(1);
    const updated = vi.fn();
    act(() => root.render(<AppShell {...props} onGlobalSearch={updated} />));
    // [HERMIA-FE-20261025 DUI P1-7] spec change: global-search accessible name now equals its visible text (axe label-content-name-mismatch); same button, same assertions.
    act(() => host.querySelector<HTMLButtonElement>('[aria-label="搜索功能、章节或命令 Ctrl K"]')!.click());
    expect(updated).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledTimes(1);
    act(() => root.unmount());
  });
  it('mounts safely when browser layout storage is unavailable', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host), blocked = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new DOMException('Denied', 'SecurityError'); });
    try {
      expect(() => act(() => root.render(<AppShell module="NOVEL" onModuleChange={vi.fn()} scope={{ workspace: '', project: '', storyline: '', branch: '' }} actor="author" sidebar={null} main="Editor" inspector={null} status="Saved" />))).not.toThrow();
      expect(host.textContent).toContain('Editor');
      act(() => root.unmount());
    } finally { blocked.mockRestore(); }
  });
});
it('U04 focus reuses inspector collapse while retaining editor and save errors', () => {
  host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host), exit = vi.fn();
  const props = { module: 'NOVEL' as const, onModuleChange: vi.fn(), scope: { workspace: '', project: '', storyline: '', branch: '' }, actor: 'author', sidebar: 'Chapters', main: 'Same editor', inspector: 'Same assistance', status: 'Save failed: draft retained', onExitFocus: exit };
  act(() => root.render(<AppShell {...props} focusMode />));
  expect(host.querySelector('#workspace-inspector')?.getAttribute('aria-hidden')).toBe('true');
  expect(host.textContent).toContain('Same editor'); expect(host.textContent).toContain('Save failed: draft retained');
  act(() => host.querySelector<HTMLButtonElement>('.inspector-edge-toggle')!.click());
  expect(exit).toHaveBeenCalledTimes(1);
  act(() => root.render(<AppShell {...props} focusMode={false} />));
  expect(host.querySelector('#workspace-inspector')?.getAttribute('aria-hidden')).toBe('false');
  expect(host.textContent).toContain('Same assistance');
  act(() => root.unmount());
});

describe("AppShell shellMode + writing ContextBar (H-P1-01 / N-UX-03 / N-UX-08)", () => {
  it("exposes 普通|专业 toggle bound to shellMode and writing breadcrumb", () => {
    host = document.createElement("div");
    document.body.append(host);
    const onMode = vi.fn();
    const onOverview = vi.fn();
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar={<nav>侧</nav>}
          main={<article>主</article>}
          inspector={<section>检</section>}
          status="ok"
          shellMode="basic"
          onShellModeChange={onMode}
          writingContext={{ bookTitle: "夜航船", chapterLabel: "第 1 章 · 开篇", saveLabel: "已保存", onOpenOverview: onOverview }}
        />,
      ),
    );
    expect(host.querySelector(".app-shell")?.getAttribute("data-shell-mode")).toBe("basic");
    const pro = [...host.querySelectorAll(".shell-mode-toggle button")].find(b => b.textContent === "专业") as HTMLButtonElement;
    expect(pro).toBeTruthy();
    act(() => pro.click());
    expect(onMode).toHaveBeenCalledWith("pro");
    expect(host.textContent).toContain("《夜航船》");
    expect(host.textContent).toContain("第 1 章 · 开篇");
    // [HERMIA-FE-20261022 N-UX-08] author language — no pure 项目腔
    expect(host.querySelector('[data-author-context="true"]')).toBeTruthy();
    expect(host.textContent).not.toContain("故事线：");
    expect(host.textContent).not.toContain("创作分支：");
    expect(host.textContent).not.toContain("创作空间：");
    act(() => {
      host.querySelector<HTMLButtonElement>(".context-bar__book-btn")!.click();
    });
    expect(onOverview).toHaveBeenCalled();
    act(() => root.unmount());
  });
  it("N-UX-08 unnamed book uses 未命名小说 author hint", () => {
    host = document.createElement("div");
    document.body.append(host);
    const onOverview = vi.fn();
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
          writingContext={{ chapterLabel: "第 2 章 · 夜雨", onOpenOverview: onOverview }}
        />,
      ),
    );
    expect(host.textContent).toContain("《未命名小说》");
    expect(host.textContent).toContain("点此完善概览");
    expect(host.textContent).toContain("第 2 章 · 夜雨");
    expect(host.textContent).not.toContain("故事线：");
    act(() => root.unmount());
  });
  it("persists inspector fold preference to localStorage", () => {
    host = document.createElement("div");
    document.body.append(host);
    localStorage.removeItem("studio-inspector-open");
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
        />,
      ),
    );
    const collapse = host.querySelector<HTMLButtonElement>(
      '.workspace-inspector__controls [aria-label="收起侧栏"]',
    )!;
    act(() => collapse.click());
    expect(localStorage.getItem("studio-inspector-open")).toBe("0");
    act(() => root.unmount());
  });
});

describe("AppShell X-UX-02/03/04/05 wave4", () => {
  it("exposes 更多 overflow without adding to default 6 chrome tabs", () => {
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
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
          shellMode="pro"
        />,
      ),
    );
    const tabs = [...host.querySelectorAll('[role="tablist"][aria-label="创作模块"] [role="tab"]')];
    expect(tabs.map(t => t.getAttribute("data-module-tab"))).toEqual([
      "NOVEL", "IMAGE", "VIDEO", "AUDIO", "EDIT", "ASSETS",
    ]);
    expect(host.querySelector('[data-overflow-chrome="true"]')).toBeTruthy();
    act(() => host.querySelector<HTMLButtonElement>('[data-overflow-trigger="true"]')!.click());
    expect(host.querySelector('[role="menu"]')).toBeTruthy();
    act(() => host.querySelector<HTMLButtonElement>('[data-overflow-item="CONTROL"]')!.click());
    expect(change).toHaveBeenCalledWith("CONTROL");
    act(() => root.unmount());
  });

  it("keeps overflow module selected indicator without kicking to NOVEL", () => {
    host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="PLUGIN"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
        />,
      ),
    );
    expect(host.querySelector(".module-overflow")?.className).toContain("is-active");
    expect(host.querySelector('[data-overflow-trigger="true"]')?.textContent).toContain("插件");
    act(() => root.unmount());
  });

  it("global command lists mode toggles and CONTROL/PLUGIN (chrome hide ≠ disable)", () => {
    host = document.createElement("div");
    document.body.append(host);
    const change = vi.fn();
    const onMode = vi.fn();
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={change}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
          shellMode="basic"
          onShellModeChange={onMode}
        />,
      ),
    );
    act(() => host.querySelector<HTMLButtonElement>(".global-search")!.click());
    const labels = [...host.querySelectorAll<HTMLButtonElement>(".command-palette__list button")].map(
      (b) => b.textContent || "",
    );
    expect(labels.some((t) => t.includes("专业模式"))).toBe(true);
    expect(labels.some((t) => t.includes("普通模式"))).toBe(true);
    expect(labels.some((t) => t.includes("打开设置"))).toBe(true);
    // normal mode, empty query: no pro entries and no internal codes on screen
    expect(labels.some((t) => /插件|工作流|Provider|CONTROL|PLUGIN|WORKFLOW|layout\.|X-UX|Inspector/.test(t))).toBe(false);
    // …but still reachable by typing (chrome hide ≠ disable)
    typeCommand(host, "插件");
    expect([...host.querySelectorAll<HTMLButtonElement>(".command-palette__list button")].some((b) => b.textContent?.includes("插件"))).toBe(true);
    typeCommand(host, "control");
    expect([...host.querySelectorAll<HTMLButtonElement>(".command-palette__list button")].some((b) => b.textContent?.includes("主控"))).toBe(true);
    typeCommand(host, "");
    const pro = [...host.querySelectorAll<HTMLButtonElement>(".command-palette__list button")].find(
      (b) => b.textContent?.includes("专业模式"),
    )!;
    act(() => pro.click());
    expect(onMode).toHaveBeenCalledWith("pro");
    act(() => root.unmount());
  });

  it("Esc closes inspector and restores focus to edge toggle (X-UX-05)", () => {
    host = document.createElement("div");
    document.body.append(host);
    localStorage.setItem("studio-inspector-open", "1");
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
        />,
      ),
    );
    // Ensure open even if a prior test collapsed
    if (host.querySelector("#workspace-inspector")?.getAttribute("aria-hidden") === "true") {
      act(() => host.querySelector<HTMLButtonElement>(".inspector-edge-toggle")!.click());
    }
    expect(host.querySelector("#workspace-inspector")?.getAttribute("aria-hidden")).toBe("false");
    act(() =>
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })),
    );
    expect(host.querySelector("#workspace-inspector")?.getAttribute("aria-hidden")).toBe("true");
    act(() => root.unmount());
  });

  it("data-shell-mode persists attribute across module prop change (X-UX-04)", () => {
    host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    const base = {
      onModuleChange: vi.fn(),
      scope: { workspace: "w", project: "p", storyline: "s", branch: "b" },
      actor: "author",
      sidebar: "侧",
      main: "主",
      inspector: "检",
      status: "ok",
      shellMode: "pro" as const,
    };
    act(() => root.render(<AppShell module="NOVEL" {...base} />));
    expect(host.querySelector(".app-shell")?.getAttribute("data-shell-mode")).toBe("pro");
    act(() => root.render(<AppShell module="IMAGE" {...base} />));
    expect(host.querySelector(".app-shell")?.getAttribute("data-shell-mode")).toBe("pro");
    expect(host.querySelector(".app-shell")?.getAttribute("data-module")).toBe("IMAGE");
    act(() => root.unmount());
  });
});

describe("AppShell N-UX-09 fold persistence + narrow", () => {
  it("defaults expanded at wide with no saved preference (≠ N-UX-04 flip)", () => {
    localStorage.removeItem("studio-inspector-open");
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
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
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
        />,
      ),
    );
    expect(host.querySelector(".app-shell")?.getAttribute("data-inspector-open")).toBe("true");
    expect(host.querySelector(".app-shell")?.classList.contains("is-inspector-collapsed")).toBe(false);
    act(() => root.unmount());
  });

  it("soft-defaults folded at <1280 when no saved preference", () => {
    localStorage.removeItem("studio-inspector-open");
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1200 });
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
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
        />,
      ),
    );
    expect(host.querySelector(".app-shell")?.classList.contains("is-inspector-collapsed")).toBe(true);
    expect(host.querySelector(".app-shell")?.getAttribute("data-inspector-open")).toBe("false");
    // Folded inspector must not leave an empty shell node taking layout width.
    expect(host.querySelector("#workspace-inspector")?.getAttribute("aria-hidden")).toBe("true");
    act(() => root.unmount());
  });

  it("force-defaults folded at <1100 even if saved open", () => {
    localStorage.setItem("studio-inspector-open", "1");
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1000 });
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
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
        />,
      ),
    );
    expect(host.querySelector(".app-shell")?.classList.contains("is-inspector-collapsed")).toBe(true);
    act(() => root.unmount());
  });

  it("honors saved open on soft-narrow <1280 and sinks CTA into ContextBar when folded", () => {
    localStorage.setItem("studio-inspector-open", "1");
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1200 });
    host = document.createElement("div");
    document.body.append(host);
    const onCta = vi.fn();
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="NOVEL"
          onModuleChange={vi.fn()}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
          writingContext={{
            bookTitle: "夜航船",
            chapterLabel: "第 1 章",
            collapsedCta: { label: "继续写", kind: "continue", onClick: onCta },
          }}
        />,
      ),
    );
    // Soft-narrow + saved open → inspector visible; no sunk CTA yet
    expect(host.querySelector(".app-shell")?.getAttribute("data-inspector-open")).toBe("true");
    expect(host.querySelector("[data-context-cta]")).toBeNull();
    act(() =>
      host.querySelector<HTMLButtonElement>('.workspace-inspector__controls [aria-label="收起侧栏"]')!.click(),
    );
    expect(localStorage.getItem("studio-inspector-open")).toBe("0");
    expect(host.querySelector(".app-shell")?.classList.contains("is-inspector-collapsed")).toBe(true);
    const sunk = host.querySelector<HTMLButtonElement>("[data-context-cta=\"true\"]");
    expect(sunk?.textContent).toBe("继续写");
    expect(sunk?.getAttribute("data-cta-kind")).toBe("continue");
    act(() => sunk!.click());
    expect(onCta).toHaveBeenCalled();
    act(() => root.unmount());
  });
});

describe("AppShell X-UX-09 settings path", () => {
  it("Header 设置 opens CONTROL without growing chrome past 6", () => {
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
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
          shellMode="basic"
        />,
      ),
    );
    const tabs = [...host.querySelectorAll('[role="tablist"][aria-label="创作模块"] [role="tab"]')];
    expect(tabs.map((t) => t.getAttribute("data-module-tab"))).toEqual([
      "NOVEL", "IMAGE", "VIDEO", "AUDIO", "EDIT", "ASSETS",
    ]);
    expect(host.querySelector('[data-settings-chrome="true"]')).toBeTruthy();
    expect(host.querySelector('[data-x-ux-09="settings"]')).toBeTruthy();
    act(() => host.querySelector<HTMLButtonElement>('[data-settings-trigger="true"]')!.click());
    expect(host.querySelector('[aria-label="设置与溢出工作区"]')).toBeTruthy();
    act(() => host.querySelector<HTMLButtonElement>('[data-settings-open="CONTROL"]')!.click());
    expect(change).toHaveBeenCalledWith("CONTROL");
    act(() => root.unmount());
  });

  it("pro「更多」still reaches PLUGIN; chrome stays 6", () => {
    host = document.createElement("div");
    document.body.append(host);
    const change = vi.fn();
    const root = createRoot(host);
    act(() =>
      root.render(
        <AppShell
          module="IMAGE"
          onModuleChange={change}
          scope={{ workspace: "w", project: "p", storyline: "s", branch: "b" }}
          actor="author"
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
          shellMode="pro"
        />,
      ),
    );
    expect(host.querySelector('[data-overflow-trigger="true"]')?.textContent).toContain("专业更多");
    expect(host.querySelectorAll('[role="tablist"][aria-label="创作模块"] [role="tab"]')).toHaveLength(6);
    act(() => host.querySelector<HTMLButtonElement>('[data-overflow-trigger="true"]')!.click());
    act(() => host.querySelector<HTMLButtonElement>('[data-overflow-item="PLUGIN"]')!.click());
    expect(change).toHaveBeenCalledWith("PLUGIN");
    act(() => root.unmount());
  });

  it("command utility lists 打开设置（AI 主控）", () => {
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
          sidebar="侧"
          main="主"
          inspector="检"
          status="ok"
        />,
      ),
    );
    act(() => host.querySelector<HTMLButtonElement>(".global-search")!.click());
    const btn = [...host.querySelectorAll<HTMLButtonElement>(".command-palette__list button")].find(
      (b) => b.textContent?.includes("打开设置"),
    );
    expect(btn).toBeTruthy();
    act(() => btn!.click());
    expect(change).toHaveBeenCalledWith("CONTROL");
    act(() => root.unmount());
  });

  it("SettingsPathGateway exposes CONTROL/PLUGIN CTAs without fake green", () => {
    host = document.createElement("div");
    document.body.append(host);
    const open = vi.fn();
    const root = createRoot(host);
    act(() =>
      root.render(
        <SettingsPathGateway onOpenModule={open}>
          <p>inline settings body</p>
        </SettingsPathGateway>,
      ),
    );
    const gate = host.querySelector('[data-settings-path="novel-panel"]')!;
    expect(gate.getAttribute("data-capability-tone")).toBe("neutral");
    expect(gate.textContent).not.toMatch(/已就绪|已连通/);
    act(() => host.querySelector<HTMLButtonElement>('[data-settings-open="PLUGIN"]')!.click());
    expect(open).toHaveBeenCalledWith("PLUGIN");
    act(() => root.unmount());
  });
});
