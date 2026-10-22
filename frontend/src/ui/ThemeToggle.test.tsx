// @vitest-environment jsdom
/** [HERMIA-FE-20261022] t71u ThemeToggle + studio-theme persistence */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ThemeToggle } from "./ThemeToggle";
import {
  STUDIO_THEME_KEY,
  applyStudioTheme,
  bootstrapStudioTheme,
  readStudioTheme,
} from "./theme";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

afterEach(() => {
  host?.remove();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("studio theme helpers", () => {
  it("defaults to dark and persists light/dark under studio-theme", () => {
    expect(readStudioTheme()).toBe("dark");
    applyStudioTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem(STUDIO_THEME_KEY)).toBe("light");
    expect(bootstrapStudioTheme()).toBe("light");
    applyStudioTheme("dark");
    expect(localStorage.getItem(STUDIO_THEME_KEY)).toBe("dark");
  });
});

describe("ThemeToggle", () => {
  it("toggles aria-pressed and writes localStorage", () => {
    host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(<ThemeToggle />));
    const buttons = [...host.querySelectorAll("button")];
    expect(buttons).toHaveLength(2);
    expect(buttons[0].textContent).toBe("浅色");
    expect(buttons[1].textContent).toBe("深色");
    expect(buttons[1].getAttribute("aria-pressed")).toBe("true");
    act(() => (buttons[0] as HTMLButtonElement).click());
    expect(localStorage.getItem(STUDIO_THEME_KEY)).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(buttons[0].getAttribute("aria-pressed")).toBe("true");
    act(() => (buttons[1] as HTMLButtonElement).click());
    expect(localStorage.getItem(STUDIO_THEME_KEY)).toBe("dark");
    act(() => root.unmount());
  });
});
