/**
 * [HERMIA-FE-20261022] H-UX-START-01 · 六模块起步卡（对齐原型 T67U STARTS）
 * 冷启动发现面：点卡进对应 wt；跳过 → 小说 write。不改 N-UX-04；不新 FL id。
 */
import type { StudioModule } from "./moduleRegistry";
import { STUDIO_MODULES } from "./moduleRegistry";
import "./ModuleStartGate.css";

export const MODULE_START_GATE_KEY = "studio-start-gate-dismissed";

/** Cards mirror PoemSeed_V2 STARTS (comic stays under IMAGE). */
export const MODULE_START_CARDS: ReadonlyArray<{
  id: Extract<StudioModule, "NOVEL" | "IMAGE" | "VIDEO" | "AUDIO" | "EDIT" | "ASSETS">;
  title: string;
  detail: string;
}> = [
  { id: "NOVEL", title: "我想写作", detail: "小说、章节、角色与世界观" },
  { id: "IMAGE", title: "我想做图", detail: "图像、参考素材与比较" },
  { id: "VIDEO", title: "我想做视频", detail: "镜头、图生视频与时间线" },
  { id: "AUDIO", title: "我想处理音频", detail: "配音、音效与字幕" },
  { id: "EDIT", title: "我想剪辑", detail: "多轨时间线 · 送剪辑闭环" },
  { id: "ASSETS", title: "我想管资产", detail: "库浏览 · 诚实空态" },
];

export function isModuleStartGateDismissed(): boolean {
  try {
    if (typeof location !== "undefined" && /skip(-start)?/i.test(location.hash || "")) {
      return true;
    }
  } catch {
    /* SSR / odd hosts */
  }
  try {
    return globalThis.sessionStorage?.getItem(MODULE_START_GATE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Cold-start open predicate. Vitest MODE=test stays closed so App shells stay clickable. */
export function shouldOpenModuleStartGate(): boolean {
  try {
    if (import.meta.env?.MODE === "test") return false;
  } catch {
    /* bundlers without import.meta.env */
  }
  return !isModuleStartGateDismissed();
}

export function markModuleStartGateDismissed(): void {
  try {
    globalThis.sessionStorage?.setItem(MODULE_START_GATE_KEY, "1");
  } catch {
    /* session-only ok */
  }
  // [HERMIA-UX-20261030 ONBOARD] 通知首次引导：起步卡已关，可以出现了
  try { globalThis.dispatchEvent?.(new Event("studio:start-gate-closed")); } catch { /* ignore */ }
}

export function resetModuleStartGateDismissed(): void {
  try {
    globalThis.sessionStorage?.removeItem(MODULE_START_GATE_KEY);
  } catch {
    /* ignore */
  }
}

type StartModule = (typeof MODULE_START_CARDS)[number]["id"];

export function ModuleStartGate({
  onPick,
  onSkip,
}: {
  onPick: (module: StartModule) => void;
  onSkip: () => void;
}) {
  const icons = Object.fromEntries(STUDIO_MODULES.map((row) => [row.id, row.icon])) as Record<
    StartModule,
    (typeof STUDIO_MODULES)[number]["icon"]
  >;

  return (
    <div
      className="module-start-gate"
      role="dialog"
      aria-modal="true"
      aria-labelledby="module-start-gate-title"
      data-testid="module-start-gate"
    >
      <div className="module-start-gate__panel">
        <p className="module-start-gate__eyebrow">PoemSeed · 创作工作室</p>
        <h2 id="module-start-gate-title">你想从哪里开始？</h2>
        <p className="module-start-gate__lead">
          六张入口卡对应顶栏六个工作区。跳过则进入小说写作主面（不改右栏默认策略）。
        </p>
        <div className="module-start-gate__cards" role="list">
          {MODULE_START_CARDS.map((card) => (
            <button
              key={card.id}
              type="button"
              className="module-start-gate__card"
              role="listitem"
              data-module={card.id}
              data-testid={`module-start-card-${card.id}`}
              onClick={() => onPick(card.id)}
            >
              <span className="module-start-gate__icon" aria-hidden="true">
                {icons[card.id]}
              </span>
              <b>{card.title}</b>
              <p>{card.detail}</p>
            </button>
          ))}
        </div>
        <button
          type="button"
          className="module-start-gate__skip"
          data-testid="module-start-skip"
          onClick={onSkip}
        >
          跳过，直接进入小说写作
        </button>
      </div>
    </div>
  );
}
