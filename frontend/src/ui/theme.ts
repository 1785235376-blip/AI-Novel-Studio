/** [HERMIA-FE-20261022] t71u light/dark theme preference */
export type StudioTheme = "light" | "dark";

export const STUDIO_THEME_KEY = "studio-theme";

export function readStudioTheme(): StudioTheme {
  try {
    const value = globalThis.localStorage?.getItem(STUDIO_THEME_KEY);
    if (value === "light" || value === "dark") return value;
  } catch {
    /* private mode / denied */
  }
  return "dark";
}

export function applyStudioTheme(theme: StudioTheme): void {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
  try {
    globalThis.localStorage?.setItem(STUDIO_THEME_KEY, theme);
  } catch {
    /* session-only ok */
  }
}

/** Call before first paint when possible (main.tsx). */
export function bootstrapStudioTheme(): StudioTheme {
  const theme = readStudioTheme();
  applyStudioTheme(theme);
  return theme;
}
