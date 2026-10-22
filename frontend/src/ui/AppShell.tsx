import { useEffect, useRef, useState } from "react";
import type { ReactNode, CSSProperties } from "react";
import {
  BookOpenText,
  PanelRightClose,
  PanelRightOpen,
  Search,
  MoreHorizontal,
} from "lucide-react";
import { IconButton } from "./primitives";
import { ThemeToggle } from "./ThemeToggle";
import {
  VIEWPORT_FORCE_DRAWER,
  resolveInspectorOpenPreference,
  readInspectorOpenSaved,
} from "../workbench/layout";
import { STUDIO_MODULES, STUDIO_MODULE_OVERFLOW } from "./moduleRegistry";
import type { StudioModule } from "./moduleRegistry";
import {
  mergeTaskSummaries,
  TASK_SUMMARY_EVENT,
  requestFailedTaskFocus,
  type TaskSummary,
} from "./taskSummary";

export type { StudioModule };
export type ProjectNoun = "小说" | "项目";
export interface ScopeLabels {
  workspace: string;
  project: string;
  storyline: string;
  branch: string;
}
export function moduleForTaskSource(source:string):StudioModule{
  if(source==='image')return 'IMAGE';
  if(source==='audio'||source==='speech'||source==='audiobook')return 'AUDIO';
  if(source==='video'||source==='motion'||source==='screenplay')return 'VIDEO';
  if(source==='plugin')return 'PLUGIN';
  if(source==='asset'||source==='assets')return 'ASSETS';
  if(source==='control'||source==='provider'||source==='model')return 'CONTROL';
  return 'WORKFLOW';
}

export function ModuleSwitcher({
  value,
  onChange,
}: {
  value: StudioModule;
  onChange: (value: StudioModule) => void;
}) {
  const moveFocus = (current: StudioModule, delta: number) => {
    const index = STUDIO_MODULES.findIndex((item) => item.id === current);
    const base = index < 0 ? 0 : index;
    const next =
      STUDIO_MODULES[
        (base + delta + STUDIO_MODULES.length) % STUDIO_MODULES.length
      ];
    onChange(next.id);
    requestAnimationFrame(() =>
      document
        .querySelector<HTMLButtonElement>(`[data-module-tab="${next.id}"]`)
        ?.focus(),
    );
  };
  return (
    <div className="module-switcher" role="tablist" aria-label="创作模块">
      {STUDIO_MODULES.map(({ id, icon, label }) => (
        <button
          key={id}
          id={`module-tab-${id.toLowerCase()}`}
          data-module-tab={id}
          role="tab"
          tabIndex={value === id ? 0 : -1}
          aria-selected={value === id}
          className={value === id ? "is-active" : ""}
          onClick={() => onChange(id)}
          onKeyDown={(event) => {
            if (event.key === "ArrowRight" || event.key === "ArrowDown") {
              event.preventDefault();
              moveFocus(id, 1);
            } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
              event.preventDefault();
              moveFocus(id, -1);
            } else if (event.key === "Home" || event.key === "End") {
              event.preventDefault();
              const target =
                event.key === "Home"
                  ? STUDIO_MODULES[0]
                  : STUDIO_MODULES[STUDIO_MODULES.length - 1];
              onChange(target.id);
              requestAnimationFrame(() =>
                document
                  .querySelector<HTMLButtonElement>(
                    `[data-module-tab="${target.id}"]`,
                  )
                  ?.focus(),
              );
            }
          }}
        >
          {icon}
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}

/** [HERMIA-FE-20261022 X-UX-03] CONTROL/PLUGIN/WORKFLOW via 更多 — never default 6 chrome. */
export function ModuleOverflowMenu({
  value,
  onChange,
  shellMode = "basic",
}: {
  value: StudioModule;
  onChange: (value: StudioModule) => void;
  shellMode?: "basic" | "pro";
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const isOverflow = STUDIO_MODULE_OVERFLOW.some((item) => item.id === value);
  const activeOverflow = STUDIO_MODULE_OVERFLOW.find((item) => item.id === value);
  useEffect(() => {
    if (!open) return;
    const onDoc = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpen(false);
        requestAnimationFrame(() => trigger.current?.focus());
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div
      className={`module-overflow${isOverflow ? " is-active" : ""}${shellMode === "pro" ? " is-pro" : ""}`}
      ref={root}
      data-overflow-chrome="true"
    >
      <button
        ref={trigger}
        type="button"
        className={isOverflow ? "is-active" : ""}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={isOverflow ? `更多工作区（当前：${activeOverflow?.label}）` : "更多工作区"}
        data-overflow-trigger="true"
        onClick={() => setOpen((v) => !v)}
      >
        <MoreHorizontal aria-hidden="true" size={16} />
        <span>{isOverflow ? activeOverflow?.label : "更多"}</span>
      </button>
      {open && (
        <div className="module-overflow__menu" role="menu" aria-label="溢出工作区">
          <p className="module-overflow__hint">不在默认 6 钮 · 命令仍可搜</p>
          {STUDIO_MODULE_OVERFLOW.map(({ id, icon, label }) => (
            <button
              key={id}
              type="button"
              role="menuitem"
              data-overflow-item={id}
              className={value === id ? "is-active" : ""}
              aria-current={value === id ? "page" : undefined}
              onClick={() => {
                onChange(id);
                setOpen(false);
              }}
            >
              {icon}
              <span>{label}</span>
              <small>{id}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export interface WritingContextLabels {
  /** Book / novel display title for author breadcrumb (N-UX-03 / N-UX-08). */
  bookTitle?: string;
  /** e.g. "第 3 章 · 夜雨" */
  chapterLabel?: string;
  saveLabel?: string;
  onOpenOverview?: () => void;
  /** [HERMIA-FE-20261022 N-UX-09] Primary CTA sunk into ContextBar when inspector folded. */
  collapsedCta?: { label: string; kind?: string; onClick: () => void; disabled?: boolean };
}

export function ContextBar({
  scope,
  projectNoun = "小说",
  writing,
  showCollapsedCta = false,
}: {
  scope: ScopeLabels;
  projectNoun?: ProjectNoun;
  /** Optional novel writing breadcrumb — omitted keeps legacy markup byte-stable. */
  writing?: WritingContextLabels;
  /** [HERMIA-FE-20261022 N-UX-09] When inspector width is 0, surface primary CTA here. */
  showCollapsedCta?: boolean;
}) {
  const fallback = "未选择";
  // [HERMIA-FE-20261022 N-UX-08] Author-first when writing: 《书名》·小说·章序 — ban pure 项目腔
  if (writing) {
    const book = writing.bookTitle?.trim() || "未命名小说";
    const chapter = writing.chapterLabel?.trim();
    const save = writing.saveLabel?.trim();
    const unnamed = !writing.bookTitle?.trim();
    return (
      <nav
        className="context-bar context-bar--writing"
        aria-label="当前写作范围"
        data-author-context="true"
      >
        <span className="context-bar__book">
          {writing.onOpenOverview ? (
            <button
              type="button"
              className="context-bar__book-btn"
              onClick={writing.onOpenOverview}
              aria-label={unnamed ? "未命名小说 · 点此完善概览" : `打开《${book}》概览`}
            >
              {`《${book}》`}
            </button>
          ) : (
            `《${book}》`
          )}
        </span>
        <i>·</i>
        <span>{projectNoun || "小说"}</span>
        {chapter ? (
          <>
            <i>·</i>
            <span className="context-bar__chapter">{chapter}</span>
          </>
        ) : null}
        {save ? (
          <>
            <i>·</i>
            <span className="context-bar__save">{save}</span>
          </>
        ) : null}
        {unnamed && writing.onOpenOverview ? (
          <>
            <i>·</i>
            <span className="context-bar__hint">点此完善概览</span>
          </>
        ) : null}
        {showCollapsedCta && writing.collapsedCta ? (
          <button
            type="button"
            className="context-bar__cta"
            data-context-cta="true"
            data-cta-kind={writing.collapsedCta.kind || undefined}
            disabled={writing.collapsedCta.disabled}
            onClick={writing.collapsedCta.onClick}
          >
            {writing.collapsedCta.label}
          </button>
        ) : null}
      </nav>
    );
  }
  return (
    <nav className="context-bar" aria-label="当前创作范围">
      <span>创作空间：{scope.workspace || fallback}</span>
      <i>/</i>
      <span>{`${projectNoun}：`}{scope.project || fallback}</span>
      <i>/</i>
      <span>故事线：{scope.storyline || fallback}</span>
      <i>/</i>
      <span>创作分支：{scope.branch || fallback}</span>
    </nav>
  );
}

export function AppShell({
  module,
  onModuleChange,
  scope,
  projectNoun,
  actor,
  sidebar,
  sidebarClassName,
  main,
  inspector,
  status,
  onGlobalSearch,
  focusMode = false,
  onExitFocus,
  shellMode = 'basic',
  onShellModeChange,
  writingContext,
}: {
  module: StudioModule;
  onModuleChange: (value: StudioModule) => void;
  scope: ScopeLabels;
  projectNoun?: ProjectNoun;
  actor: string;
  sidebar: ReactNode;
  sidebarClassName?: string;
  main: ReactNode;
  inspector: ReactNode;
  status: ReactNode;
  onGlobalSearch?: () => void;
  focusMode?: boolean;
  onExitFocus?: () => void;
  /** [HERMIA-FE-20261022 H-P1-01] Header 普通|专业 — unique source is layout.mode */
  shellMode?: 'basic' | 'pro';
  onShellModeChange?: (mode: 'basic' | 'pro') => void;
  writingContext?: WritingContextLabels;
}) {
  const searchAction = useRef(onGlobalSearch);
  searchAction.current = onGlobalSearch;
  const openSearch = () => searchAction.current ? searchAction.current() : setCommandOpen(true);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [commandIndex, setCommandIndex] = useState(0);
  const commandInput = useRef<HTMLInputElement>(null);
  const commandTrigger = useRef<HTMLButtonElement>(null);
  const failedTasksClose = useRef<HTMLButtonElement>(null);
  const failedTasksTrigger = useRef<HTMLButtonElement>(null);
  const [taskSummaries, setTaskSummaries] = useState<
    Record<string, TaskSummary>
  >({});
  const [failedTasksOpen, setFailedTasksOpen] = useState(false);
  // [HERMIA-FE-20261022 N-UX-09] Persist fold; ≥1280 overnight expanded; <1280 soft fold; <1100 force drawer.
  // Does NOT change N-UX-04 product default (still expanded on wide / no saved).
  const [inspectorOpen, setInspectorOpen] = useState(() => {
    if (typeof window === "undefined") return true;
    const saved = readInspectorOpenSaved(window.localStorage);
    const width = typeof window.innerWidth === "number" ? window.innerWidth : VIEWPORT_FORCE_DRAWER;
    return resolveInspectorOpenPreference({ viewportWidth: width, saved });
  });
  const [inspectorWidth, setInspectorWidth] = useState(() => {
    if (typeof window === "undefined") return 340;
    try {
      const value = Number(localStorage.getItem("studio-inspector-width"));
      return Number.isFinite(value) && value >= 280 && value <= 480 ? value : 340;
    } catch { return 340; }
  });
  const startResize = (event: React.PointerEvent) => {
    event.preventDefault();
    const startX = event.clientX,
      startWidth = inspectorWidth;
    const move = (next: PointerEvent) => {
      const width = Math.min(
        480,
        Math.max(280, startWidth - (next.clientX - startX)),
      );
      setInspectorWidth(width);
      try { localStorage.setItem("studio-inspector-width", String(width)); } catch { /* Layout may remain session-only; manuscript storage has separate status. */ }
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  };
  useEffect(() => {
    try { localStorage.setItem("studio-inspector-open", inspectorOpen ? "1" : "0"); } catch { /* ignore */ }
  }, [inspectorOpen]);
  useEffect(() => {
    if (!inspectorOpen || focusMode) return;
    const close = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      // Do not steal Esc from nested dialogs (command / failed tasks / overflow).
      const t = event.target as HTMLElement | null;
      if (t?.closest?.('[role="dialog"], [role="menu"], .wb-command__overlay, .command-overlay, .task-inspector-overlay, .module-overflow__menu')) return;
      setInspectorOpen(false);
      requestAnimationFrame(() =>
        document.querySelector<HTMLButtonElement>(".inspector-edge-toggle")?.focus(),
      );
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [inspectorOpen, focusMode]);
  useEffect(() => {
    // Force-drawer only at <1100 — soft <1280 is init/default, not a live force-close (keeps user open).
    const compact = window.matchMedia?.(`(max-width: ${VIEWPORT_FORCE_DRAWER}px)`);
    if (!compact) return;
    const followViewport = (event: MediaQueryListEvent) => {
      if (event.matches) setInspectorOpen(false);
    };
    compact.addEventListener?.("change", followViewport);
    return () => compact.removeEventListener?.("change", followViewport);
  }, []);
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (!event.isComposing && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openSearch();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  useEffect(() => {
    if (commandOpen) {
      setCommandIndex(0);
      requestAnimationFrame(() => commandInput.current?.focus());
    }
  }, [commandOpen]);
  useEffect(() => {
    if (failedTasksOpen)
      requestAnimationFrame(() => failedTasksClose.current?.focus());
  }, [failedTasksOpen]);
  useEffect(() => {
    const receive = (event: Event) => {
      const detail = (event as CustomEvent).detail as {
        source?: string;
        summary?: TaskSummary;
      };
      if (detail?.source && detail.summary)
        setTaskSummaries((current) => ({
          ...current,
          [detail.source!]: detail.summary!,
        }));
    };
    window.addEventListener(TASK_SUMMARY_EVENT, receive);
    return () => window.removeEventListener(TASK_SUMMARY_EVENT, receive);
  }, []);
  const taskTotal = mergeTaskSummaries(...Object.values(taskSummaries));
  const openFailedTasks = () => {
    setFailedTasksOpen(true);
    setCommandOpen(false);
    setCommandQuery("");
  };
  const closeFailedTasks = () => {
    setFailedTasksOpen(false);
    requestAnimationFrame(() => failedTasksTrigger.current?.focus());
  };
  const closeCommand = () => {
    setCommandOpen(false);
    requestAnimationFrame(() => commandTrigger.current?.focus());
  };
  const commandText = commandQuery.toLowerCase();
  // [HERMIA-FE-20261022] Chrome=6; CONTROL/PLUGIN/WORKFLOW still command-reachable (Lumen §4).
  const commands = [...STUDIO_MODULES, ...STUDIO_MODULE_OVERFLOW].filter(
    (item) =>
      item.label.toLowerCase().includes(commandText) ||
      item.id.toLowerCase().includes(commandText),
  );
  // [HERMIA-FE-20261022 X-UX-02] chrome-hidden + mode still searchable in global palette
  const utilityCommands = [
    {
      id: "inspector",
      label: "打开检查面板",
      hint: "Inspector",
      action: () => setInspectorOpen(true),
    },
    {
      id: "tasks",
      label: "查看失败任务",
      hint: taskTotal.failed ? `${taskTotal.failed} 个失败` : "无失败任务",
      action: openFailedTasks,
    },
    {
      id: "mode-basic",
      label: "切换到普通模式",
      hint: "layout.basic",
      action: () => onShellModeChange?.("basic"),
    },
    {
      id: "mode-pro",
      label: "切换到专业模式",
      hint: "layout.pro",
      action: () => onShellModeChange?.("pro"),
    },
    {
      id: "providers",
      label: "打开 Provider 控制中心",
      hint: "主控 · CONTROL",
      action: () => onModuleChange("CONTROL"),
    },
    {
      id: "plugins",
      label: "打开插件管理",
      hint: "插件 · PLUGIN",
      action: () => onModuleChange("PLUGIN"),
    },
    {
      id: "workflow-module",
      label: "打开工作流工作区",
      hint: "工作流 · WORKFLOW",
      action: () => onModuleChange("WORKFLOW"),
    },
  ].filter(
    (item) =>
      item.label.toLowerCase().includes(commandText) ||
      item.hint.toLowerCase().includes(commandText),
  );
  const commandCount = commands.length + utilityCommands.length;
  const executeCommand = (index: number) => {
    const item = commands[index];
    if (item) {
      onModuleChange(item.id);
      setCommandOpen(false);
      setCommandQuery("");
      return;
    }
    const utility = utilityCommands[index - commands.length];
    if (utility) {
      utility.action();
      if (utility.id === "inspector" || utility.id === "providers" || utility.id === "plugins" || utility.id === "workflow-module" || utility.id === "mode-basic" || utility.id === "mode-pro") {
        setCommandOpen(false);
        setCommandQuery("");
      }
    }
  };
  const visibleInspector = inspectorOpen && !focusMode;
  const toggleLabel = visibleInspector ? '收起侧栏' : '展开侧栏';
  const toggleInspector = () => { if (focusMode) { onExitFocus?.(); setInspectorOpen(true); } else setInspectorOpen(value => !value); };
  const shellStyle = {
    "--layout-inspector-width": `${inspectorWidth}px`,
  } as CSSProperties;
  const actorInitial = (actor.trim()[0] || "作").toUpperCase();
  return (
    <div
      className={`app-shell${visibleInspector ? "" : " is-inspector-collapsed"}`}
      style={shellStyle}
      data-module={module}
      data-shell-mode={shellMode}
      data-inspector-open={visibleInspector ? "true" : "false"}
      data-inspector-fold="n-ux-09"
    >
      <header className="global-header">
        <div className="product-mark" aria-label="AI Novel Studio">
          <span className="product-mark__icon">
            <BookOpenText aria-hidden="true" />
          </span>
          <span className="product-mark__name">
            <strong>AI Novel</strong>
            <small>Studio</small>
          </span>
        </div>
        <ModuleSwitcher value={module} onChange={onModuleChange} />
        <ModuleOverflowMenu value={module} onChange={onModuleChange} shellMode={shellMode} />
        <button
          ref={commandTrigger}
          className="global-search"
          aria-label="打开全局命令"
          onClick={openSearch}
        >
          <Search aria-hidden="true" />
          <span>搜索作品、章节与素材</span>
          <kbd>Ctrl K</kbd>
        </button>
        <div className="shell-mode-toggle" role="group" aria-label="界面模式">
          <button
            type="button"
            className={shellMode === "basic" ? "is-active" : ""}
            aria-pressed={shellMode === "basic"}
            onClick={() => onShellModeChange?.("basic")}
          >
            普通
          </button>
          <button
            type="button"
            className={shellMode === "pro" ? "is-active" : ""}
            aria-pressed={shellMode === "pro"}
            onClick={() => onShellModeChange?.("pro")}
          >
            专业
          </button>
        </div>
        {/* [HERMIA-FE-20261022] t71u ThemeToggle — 浅色/深色，localStorage studio-theme */}
        <ThemeToggle />
        <span className="current-actor">
          <span className="current-actor__avatar" aria-hidden="true">
            {actorInitial}
          </span>
          <span>{actor}</span>
        </span>
      </header>
      <ContextBar scope={scope} projectNoun={projectNoun} writing={writingContext} showCollapsedCta={!visibleInspector && module === "NOVEL"} />
      <main className="workspace-body">
        <aside
          className={`workspace-sidebar${sidebarClassName ? ` ${sidebarClassName}` : ""}`}
        >
          {sidebar}
        </aside>
        <section className="main-workspace">{main}</section>
        <IconButton
          className="inspector-edge-toggle"
          label={toggleLabel}
          aria-expanded={visibleInspector}
          aria-controls="workspace-inspector"
          onClick={toggleInspector}
        >
          {visibleInspector ? (
            <PanelRightClose aria-hidden="true" />
          ) : (
            <PanelRightOpen aria-hidden="true" />
          )}
        </IconButton>
        <aside
          id="workspace-inspector"
          className="workspace-inspector"
          aria-hidden={!visibleInspector}
        >
          <div
            className="workspace-inspector__resize"
            role="separator"
            aria-orientation="vertical"
            aria-label="调整检查面板宽度"
            onPointerDown={startResize}
          />
          <div className="workspace-inspector__controls">
            <span>创作辅助</span>
            <IconButton
              label="收起侧栏"
              onClick={() => setInspectorOpen(false)}
            >
              <PanelRightClose aria-hidden="true" />
            </IconButton>
          </div>
          {inspector}
        </aside>
      </main>
      <footer className="status-bar">
        <span className="status-bar__signal" aria-hidden="true" />
        {status}
        {taskTotal.total ? (
          <span aria-label="跨模块任务摘要">
            {" "}
            · 任务 {taskTotal.running} 运行 / {taskTotal.failed} 失败 /{" "}
            {taskTotal.cancelled} 取消 / {taskTotal.queued} 排队
          </span>
        ) : null}
        {taskTotal.failed > 0 ? (
          <button
            ref={failedTasksTrigger}
            className="status-bar__action"
            onClick={() => {
              openFailedTasks();
            }}
          >
            查看失败任务
          </button>
        ) : null}
      </footer>
      {failedTasksOpen && (
        <div
          className="task-inspector-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeFailedTasks();
          }}
        >
          <section
            className="task-inspector"
            role="dialog"
            aria-modal="true"
            aria-label="失败任务"
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                closeFailedTasks();
                return;
              }
              if (event.key === "Tab") {
                const focusable = [
                  ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
                    "button",
                  ),
                ];
                if (focusable.length) {
                  const current = focusable.indexOf(
                    document.activeElement as HTMLButtonElement,
                  );
                  const next = event.shiftKey
                    ? (current - 1 + focusable.length) % focusable.length
                    : (current + 1) % focusable.length;
                  event.preventDefault();
                  focusable[next]?.focus();
                }
                return;
              }
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                const rows = [
                  ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
                    ".task-inspector__row",
                  ),
                ];
                if (!rows.length) return;
                event.preventDefault();
                const current = rows.indexOf(
                  document.activeElement as HTMLButtonElement,
                );
                const delta = event.key === "ArrowDown" ? 1 : -1;
                rows[(current + delta + rows.length) % rows.length]?.focus();
              }
            }}
          >
            <header>
              <strong>失败任务</strong>
              <button
                ref={failedTasksClose}
                aria-label="关闭失败任务"
                onClick={closeFailedTasks}
              >
                关闭
              </button>
            </header>
            {Object.entries(taskSummaries)
              .filter(([, summary]) => summary.failed > 0)
              .flatMap(([source, summary]) =>
                (summary.failures || [{ id: `${source}-failed` }]).map(
                  (failure) => (
                    <button
                      className="task-inspector__row"
                      key={`${source}-${failure.id}`}
                      onClick={() => {
                        const target=moduleForTaskSource(source);
                        onModuleChange(target);
                        requestAnimationFrame(() =>
                          requestFailedTaskFocus(source, failure.id),
                        );
                        setFailedTasksOpen(false);
                      }}
                    >
                      <strong>{source}</strong>
                      <span>{failure.id}</span>
                      <small>{failure.error || "点击定位到对应工作区"}</small>
                    </button>
                  ),
                ),
              )}
            <p className="novel-help">当前仅显示已发布的真实任务摘要。</p>
          </section>
        </div>
      )}
      {commandOpen && (
        <div
          className="command-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeCommand();
          }}
        >
          <section
            className="command-palette"
            role="dialog"
            aria-modal="true"
            aria-label="全局命令"
            onKeyDown={(event) => {
              if (event.key !== "Tab") return;
              const focusable = [...event.currentTarget.querySelectorAll<HTMLElement>("input,button")];
              if (!focusable.length) return;
              const current = focusable.indexOf(document.activeElement as HTMLElement);
              event.preventDefault();
              focusable[event.shiftKey ? (current - 1 + focusable.length) % focusable.length : (current + 1) % focusable.length]?.focus();
            }}
          >
            <input
              ref={commandInput}
              value={commandQuery}
              onChange={(event) => {
                setCommandQuery(event.target.value);
                setCommandIndex(0);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  closeCommand();
                  return;
                }
                if (event.key === "ArrowDown" && commandCount) {
                  event.preventDefault();
                  setCommandIndex((index) => (index + 1) % commandCount);
                }
                if (event.key === "ArrowUp" && commandCount) {
                  event.preventDefault();
                  setCommandIndex(
                    (index) => (index - 1 + commandCount) % commandCount,
                  );
                }
                if (event.key === "Enter" && commandCount)
                  executeCommand(commandIndex);
              }}
              placeholder="搜索模块或命令"
            />
            <div className="command-palette__list" role="listbox" aria-label="可用命令">
              {commands.map((item, index) => (
                <button
                  className={commandIndex === index ? "is-selected" : ""}
                  role="option"
                  aria-selected={commandIndex === index}
                  key={item.id}
                  onClick={() => executeCommand(index)}
                >
                  {item.icon}
                  <span>{item.label}</span>
                  <small>{item.id}</small>
                </button>
              ))}
              {utilityCommands.map((item, index) => (
                <button
                  className={
                    commandIndex === commands.length + index
                      ? "is-selected"
                      : ""
                  }
                  role="option"
                  aria-selected={commandIndex === commands.length + index}
                  key={item.id}
                  onClick={() => executeCommand(commands.length + index)}
                >
                  <span>{item.label}</span>
                  <small>{item.hint}</small>
                </button>
              ))}
              {!commands.length && !utilityCommands.length && (
                <p>没有匹配的命令</p>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
