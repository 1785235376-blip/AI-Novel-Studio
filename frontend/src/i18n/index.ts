/**
 * [HERMIA-FE-20261025 I18N P0] 轻量 i18n：zh-CN 源词典 + 编译期 en 完整性 + 运行时回退 zh（永不显示裸 key）。
 * 持久化 localStorage `studio.locale`，默认 zh-CN（不跟随浏览器）；切换即时生效并同步 <html lang>。
 */
import { useSyncExternalStore } from 'react';
import { zhCN, type MessageKey } from './zh-CN';
import { en } from './en';

export type Locale = 'zh-CN' | 'en';
export type { MessageKey };
export const LOCALE_STORAGE_KEY = 'studio.locale';
export const LOCALES: Locale[] = ['zh-CN', 'en'];
const DICTS: Record<Locale, Partial<Record<MessageKey, string>>> = { 'zh-CN': zhCN, en };

let current: Locale = readStoredLocale();
const listeners = new Set<() => void>();
const warned = new Set<string>();

export function readStoredLocale(): Locale {
  try {
    const v = globalThis.localStorage?.getItem(LOCALE_STORAGE_KEY);
    if (v === 'en' || v === 'zh-CN') return v;
  } catch { /* private mode */ }
  return 'zh-CN';
}
export function getLocale(): Locale { return current; }
function applyHtmlLang(locale: Locale) {
  if (typeof document !== 'undefined') document.documentElement.lang = locale;
}
export function setLocale(locale: Locale): void {
  if (!LOCALES.includes(locale)) return;
  try { globalThis.localStorage?.setItem(LOCALE_STORAGE_KEY, locale); } catch { /* session-only */ }
  applyHtmlLang(locale);
  if (locale === current) return;
  current = locale;
  listeners.forEach((l) => l());
}
/** Call once before first render (main.tsx). */
export function bootstrapLocale(): Locale {
  current = readStoredLocale();
  applyHtmlLang(current);
  return current;
}
export function subscribeLocale(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

type Vars = Record<string, string | number>;
function interpolate(locale: Locale, template: string, vars?: Vars): string {
  if (!vars) return template;
  // ICU-lite plural: {name, plural, one {...} other {...}} — # → number
  const withPlural = template.replace(
    /\{(\w+), plural, ((?:\w+ \{[^}]*\}\s*)+)\}/g,
    (_m, name: string, body: string) => {
      const n = Number(vars[name]);
      const forms: Record<string, string> = {};
      body.replace(/(\w+) \{([^}]*)\}/g, (_x, k: string, v: string) => { forms[k] = v; return ''; });
      const cat = new Intl.PluralRules(locale).select(n);
      return (forms[cat] ?? forms.other ?? '').replace(/#/g, formatNumber(n, locale));
    },
  );
  return withPlural.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

export function translate(locale: Locale, key: MessageKey, vars?: Vars): string {
  const own = DICTS[locale]?.[key];
  if (own !== undefined) return interpolate(locale, own, vars);
  const zh = zhCN[key];
  if (locale !== 'zh-CN' && !warned.has(key) && import.meta.env?.DEV) {
    warned.add(key);
    console.warn(`[i18n] missing ${locale} key: ${key}`);
  }
  // Never render the raw key: unknown keys (e.g. dynamic) render empty string.
  return zh !== undefined ? interpolate('zh-CN', zh, vars) : '';
}
export function t(key: MessageKey, vars?: Vars): string { return translate(current, key, vars); }

export function useLocale(): Locale {
  return useSyncExternalStore(subscribeLocale, getLocale, getLocale);
}
export function useT(): (key: MessageKey, vars?: Vars) => string {
  const locale = useLocale();
  return (key, vars) => translate(locale, key, vars);
}

export function formatNumber(n: number, locale: Locale = current, opts?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(locale, opts).format(n);
}
export function formatDate(d: Date | string | number, locale: Locale = current, opts: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short', hour12: false }): string {
  const date = d instanceof Date ? d : new Date(d);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(locale, opts).format(date);
}
export function formatDuration(seconds: number, locale: Locale = current): string {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60), r = s % 60;
  return locale === 'en' ? (m ? `${m} min ${r} s` : `${r} s`) : (m ? `${m} 分 ${r} 秒` : `${r} 秒`);
}
