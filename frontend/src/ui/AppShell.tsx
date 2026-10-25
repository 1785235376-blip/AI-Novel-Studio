import { useEffect, useRef, useState } from "react";
import type { ReactNode, CSSProperties } from "react";
import {
  BookOpenText,
  PanelRightClose,
  PanelRightOpen,
  Search,
  MoreHorizontal,
  Settings2,
} from "lucide-react";
import { IconButton } from "./primitives";
import { ThemeToggle } from "./ThemeToggle";
import { LanguageToggle } from "./LanguageToggle"; // [HERMIA-FE-20261025 I18N P0]
import { useT, useTz, type MessageKey } from "../i18n";
const moduleKey = (id: StudioModule) => `module.${id}` as MessageKey;
import { RebuildHeaderTools } from "../rebuild/HeaderTools"; // [HERMIA-FE-20261022 REBUILD]
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
  /** [HERMIA-FE-20261025 DUI P0-1] Opaque owner IDs — data-* attributes only, never visible text. */
  ids?: { workspace: string; project: string; storyline: string; branch: string };
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
  const t = useT();
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
    <div className="module-switcher" role="tablist" aria-label={t("module.tablist")}>
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
          <span>{t(moduleKey(id)) || label}</span>
        </button>
      ))}
    </div>
  );
}

/** [HERMIA-FE-20261022 X-UX-03/09] CONTROL/PLUGIN/WORKFLOW via 更多 — never default 6 chrome. */
export function ModuleOverflowMenu({
  value,
  onChange,
  shellMode = "basic",
}: {
  value: StudioModule;
  onChange: (value: StudioModule) => void;
  shellMode?: "basic" | "pro";
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const isOverflow = STUDIO_MODULE_OVERFLOW.some((item) => item.id === value);
  const activeOverflow = STUDIO_MODULE_OVERFLOW.find((item) => item.id === value);
  const triggerLabel = isOverflow
    ? (activeOverflow ? t(moduleKey(activeOverflow.id)) : undefined)
    : shellMode === "pro"
      ? t("overflow.proMore")
      : t("overflow.more");
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
      data-settings-path="overflow"
      data-x-ux-09="overflow"
    >
      <button
        ref={trigger}
        type="button"
        className={isOverflow ? "is-active" : ""}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={
          isOverflow
            ? t("overflow.aria.current", { prefix: shellMode === "pro" ? t("overflow.proPrefix") : "", label: activeOverflow ? t(moduleKey(activeOverflow.id)) : "" })
            : shellMode === "pro"
              ? t("overflow.aria.pro")
              : t("overflow.aria")
        }
        data-overflow-trigger="true"
        onClick={() => setOpen((v) => !v)}
      >
        <MoreHorizontal aria-hidden="true" size={16} />
        <span>{triggerLabel}</span>
      </button>
      {open && (
        <div className="module-overflow__menu" role="menu" aria-label={t("overflow.menu")}>
          <p className="module-overflow__hint">
            {t("overflow.hint")}
          </p>
          {STUDIO_MODULE_OVERFLOW.map(({ id, icon, label }) => (
            <button
              key={id}
              type="button"
              role="menuitem"
              data-overflow-item={id}
              data-settings-open={id}
              className={value === id ? "is-active" : ""}
              aria-current={value === id ? "page" : undefined}
              onClick={() => {
                onChange(id);
                setOpen(false);
              }}
            >
              {icon}
              <span>{t(moduleKey(id)) || label}</span>
              {shellMode === "pro" && <small>{id}</small>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** [HERMIA-FE-20261022 X-UX-09] Header 设置 → CONTROL/PLUGIN/WORKFLOW；不进默认 6 钮。 */
export function ShellSettingsMenu({
  value,
  onChange,
  shellMode = "basic",
}: {
  value: StudioModule;
  onChange: (value: StudioModule) => void;
  shellMode?: "basic" | "pro";
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const isOverflow = STUDIO_MODULE_OVERFLOW.some((item) => item.id === value);
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
      className={`shell-settings${isOverflow ? " is-active" : ""}${shellMode === "pro" ? " is-pro" : ""}`}
      ref={root}
      data-settings-chrome="true"
      data-settings-path="header"
      data-x-ux-09="settings"
      data-capability-tone="neutral"
    >
      <button
        ref={trigger}
        type="button"
        className={isOverflow ? "is-active" : ""}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={shellMode === "pro" ? t("settings.aria") : t("settings.ariaBasic")} /* [HERMIA-FE-20261025 DUI P1-6] 普通模式不提插件 */
        data-settings-trigger="true"
        onClick={() => setOpen((v) => !v)}
      >
        <Settings2 aria-hidden="true" size={16} />
        <span>{t("settings.label")}</span>
      </button>
      {open && (
        <div className="shell-settings__menu" role="menu" aria-label={t("settings.menu")}>
          {shellMode === "pro" && (
            <p className="shell-settings__hint">
              {t("settings.hint")}
            </p>
          )}
          {/* [HERMIA-FE-20261025 DUI P1-6] 普通模式只留 AI 主控（含简化媒体模型配置）；插件/工作流仅专业 */}
          {STUDIO_MODULE_OVERFLOW.filter(({ id }) => shellMode === "pro" || id === "CONTROL").map(({ id, icon, label }) => (
            <button
              key={id}
              type="button"
              role="menuitem"
              data-settings-open={id}
              className={value === id ? "is-active" : ""}
              aria-current={value === id ? "page" : undefined}
              onClick={() => {
                onChange(id);
                setOpen(false);
              }}
            >
              {icon}
              <span>{id === "CONTROL" ? t("settings.control") : id === "PLUGIN" ? t("settings.plugin") : t(moduleKey(id)) || label}</span>
              {shellMode === "pro" ? <small>{id}</small> : null /* [HERMIA-FE-20261025 DUI P0-a] 普通模式不显示内部代号 */}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** [HERMIA-FE-20261022 X-UX-09] Novel FL「设置」面板网关 → 显式打开 CONTROL/PLUGIN。 */
export function SettingsPathGateway({
  onOpenModule,
  children,
}: {
  onOpenModule?: (module: StudioModule) => void;
  children?: ReactNode;
}) {
  const t = useT(); // [HERMIA-FE-20261025 I18N P1] settings path panel
  return (
    <section
      className="settings-path-gateway"
      data-settings-path="novel-panel"
      data-x-ux-09="gateway"
      data-capability-tone="neutral"
      aria-label={t("spg.region")}
    >
      <header className="settings-path-gateway__head">
        <strong>{t("spg.title")}</strong>
        <p>
          {t("spg.desc")}
        </p>
        <div className="settings-path-gateway__actions" role="group" aria-label={t("spg.actions")}>
          <button
            type="button"
            data-settings-open="CONTROL"
            onClick={() => onOpenModule?.("CONTROL")}
          >
            {t("spg.control")}
          </button>
          <button
            type="button"
            data-settings-open="PLUGIN"
            onClick={() => onOpenModule?.("PLUGIN")}
          >
            {t("spg.plugin")}
          </button>
          <button
            type="button"
            data-settings-open="WORKFLOW"
            onClick={() => onOpenModule?.("WORKFLOW")}
          >
            {t("spg.workflow")}
          </button>
        </div>
        <small>{t("spg.note")}</small>
      </header>
      {children}
    </section>
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
  /** [HERMIA-FE-20261022 REBUILD-W3] 原型上下文条右侧「保存位置」徽标 */
  saveLocation?: string;
  /** [HERMIA-FE-20261022 REBUILD-W3] 原型上下文条右侧「任务 / 候选 / 审核」 */
  onOpenReview?: () => void;
  reviewCount?: number;
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
  const t = useT();
  const tz = useTz();
  const nounLabel = (n?: ProjectNoun) => (n === "项目" ? t("noun.project") : t("noun.novel"));
  const fallback = t("context.unselected");
  // [HERMIA-FE-20261022 N-UX-08] Author-first when writing: 《书名》·小说·章序 — ban pure 项目腔
  if (writing) {
    const book = writing.bookTitle?.trim() || t("context.untitledNovel");
    const chapter = tz(writing.chapterLabel?.trim() || "") || undefined; // [HERMIA-FE-20261025 I18N P2] tz: legacy zh labels from App
    const save = tz(writing.saveLabel?.trim() || "") || undefined;
    const unnamed = !writing.bookTitle?.trim();
    return (
      <nav
        className="context-bar context-bar--writing"
        aria-label={t("context.writingAria")}
        data-author-context="true"
      >
        <span className="context-bar__book">
          {writing.onOpenOverview ? (
            <button
              type="button"
              className="context-bar__book-btn"
              onClick={writing.onOpenOverview}
              aria-label={unnamed ? t("context.unnamedAria") : t("context.openOverview", { book })}
            >
              {`《${book}》`}
            </button>
          ) : (
            `《${book}》`
          )}
        </span>
        <i>·</i>
        <span>{nounLabel(projectNoun)}</span>
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
            <span className="context-bar__hint">{t("context.completeOverview")}</span>
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
            {tz(writing.collapsedCta.label)}
          </button>
        ) : null}
        {writing.saveLocation || writing.onOpenReview ? <span className="context-bar__spacer" style={{ flex: 1 }} /> : null}
        {writing.saveLocation ? <span className="context-bar__save-location" data-save-location="true">{tz(writing.saveLocation)}</span> : null}
        {writing.onOpenReview ? (
          <button type="button" className="context-bar__review" data-context-review="true" onClick={writing.onOpenReview}>
            {`${t("context.review")}${writing.reviewCount ? ` ${writing.reviewCount}` : ''}`}
          </button>
        ) : null}
      </nav>
    );
  }
  return (
    <nav className="context-bar" aria-label={t("context.scopeAria")}>
      <span data-scope-id={scope.ids?.workspace || undefined}>{t("context.workspace")}{scope.workspace || fallback}</span>
      <i>/</i>
      <span data-scope-id={scope.ids?.project || undefined}>{t("context.projectLabel", { noun: nounLabel(projectNoun) })}{scope.project || fallback}</span>
      <i>/</i>
      <span data-scope-id={scope.ids?.storyline || undefined}>{t("context.storyline")}{scope.storyline || fallback}</span>
      <i>/</i>
      <span data-scope-id={scope.ids?.branch || undefined}>{t("context.branch")}{scope.branch || fallback}</span>
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
  banner,
}: {
  /** [HERMIA-FE-20261022 R1] 三栏上方整宽指引行（小说 #orient） */
  banner?: ReactNode;
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
  const t = useT();
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
  // [HERMIA-FE-20261025 DUI P1-7] 每个模块有自己的页标题；html lang 由 i18n 分支负责，这里只在缺失时兜底，不覆盖。
  const moduleTitle = [...STUDIO_MODULES, ...STUDIO_MODULE_OVERFLOW].find((m) => m.id === module)?.label || "";
  const moduleTitleText = (module && t(moduleKey(module))) || moduleTitle; // [HERMIA-FE-20261025 DUI×I18N] 标题/h1 随语言
  useEffect(() => {
    if (!document.documentElement.lang) document.documentElement.lang = "zh-CN";
    document.title = moduleTitleText ? `${moduleTitleText} · PoemSeed Studio` : "PoemSeed Studio";
  }, [moduleTitleText]);
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
  // [HERMIA-FE-20261025 DUI P1-5] Normal mode: pro entries are not listed by default but stay reachable by typing
  // (chrome hide ≠ disable, Lumen §4). Internal ids/codes still match the query but are never shown as text.
  const proHidden = (proOnly: boolean) => proOnly && shellMode !== "pro" && !commandText.trim();
  const commands = [...STUDIO_MODULES, ...STUDIO_MODULE_OVERFLOW].filter(
    (item) =>
      !proHidden(STUDIO_MODULE_OVERFLOW.some((o) => o.id === item.id)) &&
      (item.label.toLowerCase().includes(commandText) ||
      t(moduleKey(item.id)).toLowerCase().includes(commandText) ||
      item.id.toLowerCase().includes(commandText)),
  );
  // [HERMIA-FE-20261022 X-UX-02] chrome-hidden + mode still searchable in global palette
  const utilityCommands = [
    {
      id: "inspector",
      label: t("cmd.inspector"),
      hint: t("cmd.hint.sidebar"),
      keys: "inspector",
      proOnly: true,
      action: () => setInspectorOpen(true),
    },
    {
      id: "tasks",
      label: t("tasks.viewFailed"),
      hint: taskTotal.failed ? t("tasks.failedCount", { count: taskTotal.failed }) : t("tasks.noneFailed"),
      keys: "tasks",
      proOnly: false,
      action: openFailedTasks,
    },
    {
      id: "mode-basic",
      label: t("cmd.modeBasic"),
      hint: t("cmd.hint.mode"),
      keys: "layout.basic",
      proOnly: false,
      action: () => onShellModeChange?.("basic"),
    },
    {
      id: "mode-pro",
      label: t("cmd.modePro"),
      hint: t("cmd.hint.mode"),
      keys: "layout.pro",
      proOnly: false,
      action: () => onShellModeChange?.("pro"),
    },
    {
      id: "settings-hub",
      label: shellMode === "pro" ? t("cmd.settingsHub") : t("cmd.settingsBasic"),
      hint: shellMode === "pro" ? t("cmd.hint.settings") : t("cmd.hint.settingsBasic"),
      keys: "CONTROL X-UX-09 主控 settings",
      proOnly: false,
      action: () => onModuleChange("CONTROL"),
    },
    {
      id: "providers",
      label: t("cmd.providers"),
      hint: t("cmd.hint.providers"),
      keys: "CONTROL provider 主控",
      proOnly: true,
      action: () => onModuleChange("CONTROL"),
    },
    {
      id: "plugins",
      label: t("cmd.plugins"),
      hint: t("cmd.hint.plugins"),
      keys: "PLUGIN",
      proOnly: true,
      action: () => onModuleChange("PLUGIN"),
    },
    {
      id: "workflow-module",
      label: t("cmd.workflow"),
      hint: t("cmd.hint.workflow"),
      keys: "WORKFLOW",
      proOnly: true,
      action: () => onModuleChange("WORKFLOW"),
    },
  ].filter(
    (item) =>
      !proHidden(item.proOnly) &&
      (item.label.toLowerCase().includes(commandText) ||
      item.hint.toLowerCase().includes(commandText) ||
      item.keys.toLowerCase().includes(commandText)),
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
      if (utility.id === "inspector" || utility.id === "providers" || utility.id === "plugins" || utility.id === "workflow-module" || utility.id === "settings-hub" || utility.id === "mode-basic" || utility.id === "mode-pro") {
        setCommandOpen(false);
        setCommandQuery("");
      }
    }
  };
  const visibleInspector = inspectorOpen && !focusMode;
  const toggleLabel = visibleInspector ? t("inspector.collapse") : t("inspector.expand");
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
        {/* [HERMIA-FE-20261022 REBUILD-W2] 原型外壳：logo · 模块分段 · spacer · 搜索 · 模式 · 工具 · 明暗 · 设置 */}
        <div className="product-mark" aria-label="PoemSeed Studio" data-proto-shell="logo">
          <span className="product-mark__icon" aria-hidden="true">
            <BookOpenText aria-hidden="true" />
          </span>
          <span className="product-mark__name">
            <strong>PoemSeed Studio</strong>
          </span>
        </div>
        <ModuleSwitcher value={module} onChange={onModuleChange} />
        {/* [HERMIA-FE-20261022 REBUILD-W2] 「更多」仅专业模式或当前处于溢出模块时显示（原型 pro-only）；主控/插件始终经设置与 Ctrl K */}
        {shellMode === "pro" || STUDIO_MODULE_OVERFLOW.some((item) => item.id === module) ? (
          <ModuleOverflowMenu value={module} onChange={onModuleChange} shellMode={shellMode} />
        ) : null}
        <span className="proto-spacer" aria-hidden="true" />
        <button
          ref={commandTrigger}
          className="global-search"
          /* [HERMIA-FE-20261025 DUI×I18N P1-7] 不设 aria-label：可访问名直接取可见文本（中英文都满足 label-content-name-mismatch） */
          onClick={openSearch}
        >
          <Search aria-hidden="true" />
          <span>{t("search.placeholder")}</span>
          <kbd>Ctrl K</kbd>
        </button>
        <div className="shell-mode-toggle" role="group" aria-label={t("mode.group")}>
          <button
            type="button"
            className={shellMode === "basic" ? "is-active" : ""}
            aria-pressed={shellMode === "basic"}
            onClick={() => onShellModeChange?.("basic")}
          >
            {t("mode.basic")}
          </button>
          <button
            type="button"
            className={shellMode === "pro" ? "is-active" : ""}
            aria-pressed={shellMode === "pro"}
            onClick={() => onShellModeChange?.("pro")}
          >
            {t("mode.pro")}
          </button>
        </div>
        {/* [HERMIA-FE-20261022 REBUILD] 导出/资料/任务 — prototype header tools */}
        <RebuildHeaderTools module={module} activeTaskCount={taskTotal.running + taskTotal.queued} pro={shellMode === "pro"} /* [HERMIA-FE-20261025 DUI P1-6] */ />
        {/* [HERMIA-FE-20261022] t71u ThemeToggle — 浅色/深色，localStorage studio-theme */}
        <ThemeToggle />
        {/* [HERMIA-FE-20261025 I18N P0] 「中 / EN」紧随浅色/深色右侧 */}
        <LanguageToggle />
        {/* [HERMIA-FE-20261022 X-UX-09] Header 设置 → CONTROL/PLUGIN；不进 6 钮 */}
        <ShellSettingsMenu value={module} onChange={onModuleChange} shellMode={shellMode} />
        <span className="current-actor">
          <span className="current-actor__avatar" aria-hidden="true">
            {actorInitial}
          </span>
          <span>{actor}</span>
        </span>
      </header>
      <ContextBar scope={scope} projectNoun={projectNoun} writing={writingContext} showCollapsedCta={!visibleInspector && module === "NOVEL"} />
      <main className="workspace-body">
        <h1 className="sr-only" data-module-h1="true">{moduleTitleText || "PoemSeed Studio"}</h1>{/* [HERMIA-FE-20261025 DUI P1-7] */}
        {banner ? <div className="workspace-banner">{banner}</div> : null}
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
            aria-label={t("inspector.resize")}
            onPointerDown={startResize}
          />
          <div className="workspace-inspector__controls">
            <span>{t("inspector.title")}</span>
            <IconButton
              label={t("inspector.collapse")}
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
          <span aria-label={t("status.taskSummaryAria")}>
            {" "}
            · {t("status.taskSummary", { running: taskTotal.running, failed: taskTotal.failed, cancelled: taskTotal.cancelled, queued: taskTotal.queued })}
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
            {t("tasks.viewFailed")}
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
            aria-label={t("tasks.failedTitle")}
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
              <strong>{t("tasks.failedTitle")}</strong>
              <button
                ref={failedTasksClose}
                aria-label={t("tasks.closeFailed")}
                onClick={closeFailedTasks}
              >
                {t("common.close")}
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
                      <small>{failure.error || t("tasks.locate")}</small>
                    </button>
                  ),
                ),
              )}
            <p className="novel-help">{t("tasks.publishedOnly")}</p>
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
            aria-label={t("cmd.dialog")}
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
              placeholder={t("cmd.placeholder")}
            />
            <div className="command-palette__list" role="listbox" aria-label={t("cmd.list")}>
              {commands.map((item, index) => (
                <button
                  className={commandIndex === index ? "is-selected" : ""}
                  role="option"
                  aria-selected={commandIndex === index}
                  key={item.id}
                  onClick={() => executeCommand(index)}
                >
                  {item.icon}
                  <span data-command-id={item.id}>{t(moduleKey(item.id)) || item.label}</span>
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
                <p>{t("cmd.empty")}</p>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
