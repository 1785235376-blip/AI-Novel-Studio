/**
 * [HERMIA-FE-20261024 VW-M4] Panel focus navigation (frontend-only, no layout mutation, no model calls).
 * Order = visual DOM order of rendered panel regions (`section[role=region][data-panel-id]`, tabIndex -1 from DockLayout).
 * Hidden/closed panels are not focus targets; we report why instead of silently re-docking.
 */
export interface PanelFocusTracker {
  current(): string | null;
  previous(): string | null;
  /** Ordered rendered panel ids inside the root. */
  order(): string[];
  focus(id: string): boolean;
  next(dir: 1 | -1): {ok: true; id: string} | {ok: false; reason: string};
  returnToLast(): {ok: true; id: string} | {ok: false; reason: string};
  dispose(): void;
}
const SEL = 'section[role="region"][data-panel-id]';

export function createPanelFocusTracker(root: () => ParentNode | null, title: (id: string) => string = id => id): PanelFocusTracker {
  let cur: string | null = null; let prev: string | null = null;
  const onFocusIn = (e: Event) => {
    const t = e.target as Element | null;
    const r = root(); const host = t?.closest?.(SEL) as HTMLElement | null;
    if (!host || !r || !(r as Node).contains?.(host)) return;
    const id = host.getAttribute('data-panel-id');
    if (id && id !== cur) { prev = cur; cur = id; }
  };
  document.addEventListener('focusin', onFocusIn);
  const els = () => [...(root()?.querySelectorAll<HTMLElement>(SEL) ?? [])];
  const api: PanelFocusTracker = {
    current: () => cur, previous: () => prev,
    order: () => els().map(e => e.getAttribute('data-panel-id')!).filter(Boolean),
    focus: id => {
      const el = els().find(e => e.getAttribute('data-panel-id') === id); if (!el) return false;
      el.focus({preventScroll: true}); return document.activeElement === el;
    },
    next: dir => {
      const ids = api.order(); if (!ids.length) return {ok: false, reason: '当前没有可切换的面板。'};
      const active = (document.activeElement?.closest?.(SEL) as HTMLElement | null)?.getAttribute('data-panel-id') ?? cur;
      const i = active ? ids.indexOf(active) : -1;
      const id = ids[i < 0 ? (dir === 1 ? 0 : ids.length - 1) : (i + dir + ids.length) % ids.length];
      return api.focus(id) ? {ok: true, id} : {ok: false, reason: `无法把焦点移到「${title(id)}」。`};
    },
    returnToLast: () => {
      if (!prev) return {ok: false, reason: '还没有上一个面板可以返回。'};
      if (!api.order().includes(prev)) return {ok: false, reason: `「${title(prev)}」现在没有显示，先打开它再返回。`};
      const id = prev;
      return api.focus(id) ? {ok: true, id} : {ok: false, reason: `无法把焦点移到「${title(id)}」。`};
    },
    dispose: () => document.removeEventListener('focusin', onFocusIn),
  };
  return api;
}
