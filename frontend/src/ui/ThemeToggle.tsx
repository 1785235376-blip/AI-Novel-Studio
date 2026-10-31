/** [HERMIA-FE-20261022] t71u ThemeToggle — header / settings 浅色|深色 */
import { useEffect, useState } from "react";
import {
  applyStudioTheme,
  readStudioTheme,
  type StudioTheme,
} from "./theme";
import { useT } from "../i18n"; // [HERMIA-FE-20261025 I18N P0]

export function ThemeToggle({
  className = "shell-mode-toggle",
}: {
  className?: string;
}) {
  const t = useT();
  const [theme, setTheme] = useState<StudioTheme>(() => readStudioTheme());

  useEffect(() => {
    applyStudioTheme(theme);
  }, [theme]);

  return (
    <div className={className} role="group" aria-label={t("theme.group")}>
      <button
        type="button"
        className={theme === "light" ? "is-active" : ""}
        aria-pressed={theme === "light"}
        title={t("theme.light.title")}
        onClick={() => setTheme("light")}
      >
        {t("theme.light")}
      </button>
      <button
        type="button"
        className={theme === "dark" ? "is-active" : ""}
        aria-pressed={theme === "dark"}
        title={t("theme.dark.title")}
        onClick={() => setTheme("dark")}
      >
        {t("theme.dark")}
      </button>
    </div>
  );
}
