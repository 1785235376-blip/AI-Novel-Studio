import { useEffect, useRef, useState } from "react";
import type { ReactNode, CSSProperties } from "react";
import {
  BookOpenText,
  PanelRightClose,
  PanelRightOpen,
  Search,
} from "lucide-react";
import { IconButton } from "./primitives";
import { STUDIO_MODULES } from "./moduleRegistry";
import type { StudioModule } from "./moduleRegistry";
import {
  mergeTaskSummaries,
  TASK_SUMMARY_EVENT,
  requestFailedTaskFocus,
  type TaskSummary,
} from "./taskSummary";

export type { StudioModule };
export interface ScopeLabels {
  workspace: string;
  project: string;
  storyline: string;
  branch: string;
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
    const next =
      STUDIO_MODULES[
        (index + delta + STUDIO_MODULES.length) % STUDIO_MODULES.length
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

export function ContextBar({ scope }: { scope: ScopeLabels }) {
  const fallback = "未选择";
  return (
    <nav className="context-bar" aria-label="当前创作范围">
      <span>创作空间：{scope.workspace || fallback}</span>
      <i>/</i>
      <span>小说：{scope.project || fallback}</span>
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
  actor,
  sidebar,
  sidebarClassName,
  main,
  inspector,
  status,
}: {
  module: StudioModule;
  onModuleChange: (value: StudioModule) => void;
  scope: ScopeLabels;
  actor: string;
  sidebar: ReactNode;
  sidebarClassName?: string;
  main: ReactNode;
  inspector: ReactNode;
  status: ReactNode;
}) {
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
  const [inspectorOpen, setInspectorOpen] = useState(
    () =>
      typeof window === "undefined" ||
      !window.matchMedia?.("(max-width: 1100px)").matches,
  );
  const [inspectorWidth, setInspectorWidth] = useState(() => {
    if (typeof window === "undefined") return 340;
    const value = Number(localStorage.getItem("studio-inspector-width"));
    return Number.isFinite(value) && value >= 280 && value <= 480 ? value : 340;
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
      localStorage.setItem("studio-inspector-width", String(width));
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  };
  useEffect(() => {
    if (!inspectorOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setInspectorOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [inspectorOpen]);
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
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
  const commands = STUDIO_MODULES.filter(
    (item) =>
      item.label.toLowerCase().includes(commandText) ||
      item.id.toLowerCase().includes(commandText),
  );
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
      id: "providers",
      label: "打开 Provider 控制中心",
      hint: "控制中心",
      action: () => onModuleChange("CONTROL"),
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
      if (utility.id === "inspector" || utility.id === "providers") {
        setCommandOpen(false);
        setCommandQuery("");
      }
    }
  };
  const toggleLabel = inspectorOpen ? "收起侧栏" : "展开侧栏";
  const shellStyle = {
    "--layout-inspector-width": `${inspectorWidth}px`,
  } as CSSProperties;
  const actorInitial = (actor.trim()[0] || "作").toUpperCase();
  return (
    <div
      className={`app-shell${inspectorOpen ? "" : " is-inspector-collapsed"}`}
      style={shellStyle}
      data-module={module}
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
        <button
          ref={commandTrigger}
          className="global-search"
          aria-label="打开全局命令"
          onClick={() => setCommandOpen(true)}
        >
          <Search aria-hidden="true" />
          <span>搜索作品、章节与素材</span>
          <kbd>Ctrl K</kbd>
        </button>
        <span className="current-actor">
          <span className="current-actor__avatar" aria-hidden="true">
            {actorInitial}
          </span>
          <span>{actor}</span>
        </span>
      </header>
      <ContextBar scope={scope} />
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
          aria-expanded={inspectorOpen}
          aria-controls="workspace-inspector"
          onClick={() => setInspectorOpen((value) => !value)}
        >
          {inspectorOpen ? (
            <PanelRightClose aria-hidden="true" />
          ) : (
            <PanelRightOpen aria-hidden="true" />
          )}
        </IconButton>
        <aside
          id="workspace-inspector"
          className="workspace-inspector"
          aria-hidden={!inspectorOpen}
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
            {taskTotal.queued} 排队
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
                        const target =
                          source === "image"
                            ? "IMAGE"
                            : source === "audio" || source === "speech" || source === "audiobook"
                              ? "AUDIO"
                              : source === "workflow" || source === "agent"
                                ? "WORKFLOW"
                                : "VIDEO";
                        onModuleChange(target as StudioModule);
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
