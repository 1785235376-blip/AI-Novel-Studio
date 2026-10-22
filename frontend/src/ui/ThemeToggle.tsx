/** [HERMIA-FE-20261022] t71u ThemeToggle — header / settings 浅色|深色 */
import { useEffect, useState } from "react";
import {
  applyStudioTheme,
  readStudioTheme,
  type StudioTheme,
} from "./theme";

export function ThemeToggle({
  className = "shell-mode-toggle",
}: {
  className?: string;
}) {
  const [theme, setTheme] = useState<StudioTheme>(() => readStudioTheme());

  useEffect(() => {
    applyStudioTheme(theme);
  }, [theme]);

  return (
    <div className={className} role="group" aria-label="背景明暗">
      <button
        type="button"
        className={theme === "light" ? "is-active" : ""}
        aria-pressed={theme === "light"}
        title="浅色背景"
        onClick={() => setTheme("light")}
      >
        浅色
      </button>
      <button
        type="button"
        className={theme === "dark" ? "is-active" : ""}
        aria-pressed={theme === "dark"}
        title="深色背景"
        onClick={() => setTheme("dark")}
      >
        深色
      </button>
    </div>
  );
}
