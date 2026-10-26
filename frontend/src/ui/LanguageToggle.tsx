/** [HERMIA-FE-20261025 I18N P0] LanguageToggle — 「中 / EN」分段，样式同 ThemeToggle；localStorage studio.locale。 */
import { setLocale, useLocale, useT } from "../i18n";

export function LanguageToggle({ className = "shell-mode-toggle" }: { className?: string }) {
  const locale = useLocale();
  const t = useT();
  return (
    <div className={className} role="group" aria-label={t("lang.group")} data-i18n-toggle="true">
      <button type="button" lang="zh-CN" className={locale === "zh-CN" ? "is-active" : ""} aria-pressed={locale === "zh-CN"} title={t("lang.zh.title")} onClick={() => setLocale("zh-CN")}>
        {t("lang.zh")}
      </button>
      <button type="button" lang="en" className={locale === "en" ? "is-active" : ""} aria-pressed={locale === "en"} title={t("lang.en.title")} onClick={() => setLocale("en")}>
        {t("lang.en")}
      </button>
    </div>
  );
}
