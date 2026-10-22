// @vitest-environment jsdom
/** [HERMIA-FE-20261022] H-UX-START-01 ModuleStartGate */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MODULE_START_CARDS,
  MODULE_START_GATE_KEY,
  ModuleStartGate,
  isModuleStartGateDismissed,
  markModuleStartGateDismissed,
  resetModuleStartGateDismissed,
  shouldOpenModuleStartGate,
} from "./ModuleStartGate";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;

beforeEach(() => {
  sessionStorage.clear();
  resetModuleStartGateDismissed();
  host = document.createElement("div");
  document.body.append(host);
});

afterEach(() => {
  host?.remove();
  sessionStorage.clear();
  // restore hash without navigation
  history.replaceState(null, "", location.pathname + location.search);
});

describe("MODULE_START_CARDS", () => {
  it("exposes six T67U modules in chrome order", () => {
    expect(MODULE_START_CARDS.map((c) => c.id)).toEqual([
      "NOVEL",
      "IMAGE",
      "VIDEO",
      "AUDIO",
      "EDIT",
      "ASSETS",
    ]);
    expect(MODULE_START_CARDS).toHaveLength(6);
  });
});

describe("start-gate dismissal", () => {
  it("defaults open and persists dismiss in sessionStorage", () => {
    expect(isModuleStartGateDismissed()).toBe(false);
    markModuleStartGateDismissed();
    expect(sessionStorage.getItem(MODULE_START_GATE_KEY)).toBe("1");
    expect(isModuleStartGateDismissed()).toBe(true);
    resetModuleStartGateDismissed();
    expect(isModuleStartGateDismissed()).toBe(false);
  });

  it("shouldOpenModuleStartGate stays false under vitest (MODE=test)", () => {
    resetModuleStartGateDismissed();
    expect(isModuleStartGateDismissed()).toBe(false);
    expect(shouldOpenModuleStartGate()).toBe(false);
  });

  it("treats #skip / #skip-start hash as dismissed (proto parity)", () => {
    history.replaceState(null, "", "#skip");
    expect(isModuleStartGateDismissed()).toBe(true);
    history.replaceState(null, "", "#skip-start");
    expect(isModuleStartGateDismissed()).toBe(true);
  });
});

describe("ModuleStartGate", () => {
  it("renders six cards and routes pick / skip", () => {
    const onPick = vi.fn();
    const onSkip = vi.fn();
    const root = createRoot(host);
    act(() => root.render(<ModuleStartGate onPick={onPick} onSkip={onSkip} />));

    const cards = [...host.querySelectorAll("[data-testid^='module-start-card-']")];
    expect(cards).toHaveLength(6);
    expect(host.querySelector('[data-testid="module-start-card-NOVEL"]')?.textContent).toContain(
      "我想写作",
    );
    expect(host.querySelector('[data-testid="module-start-card-EDIT"]')?.textContent).toContain(
      "我想剪辑",
    );

    act(() => {
      (host.querySelector('[data-testid="module-start-card-VIDEO"]') as HTMLButtonElement).click();
    });
    expect(onPick).toHaveBeenCalledWith("VIDEO");

    act(() => {
      (host.querySelector('[data-testid="module-start-skip"]') as HTMLButtonElement).click();
    });
    expect(onSkip).toHaveBeenCalledTimes(1);

    act(() => root.unmount());
  });

  it("uses theme tokens (no hard-coded success green class)", () => {
    const root = createRoot(host);
    act(() => root.render(<ModuleStartGate onPick={() => {}} onSkip={() => {}} />));
    const gate = host.querySelector(".module-start-gate");
    expect(gate).toBeTruthy();
    expect(gate?.className).not.toMatch(/success|is-ready|is-connected/);
    act(() => root.unmount());
  });
});
