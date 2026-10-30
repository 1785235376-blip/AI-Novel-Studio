/**
 * [HERMIA-UX-20261030 ONBOARD] 首次引导：3–6 步聚光灯 / 提示卡，指向真实界面元素。
 * - 起步卡「你想从哪里开始？」负责「选模块」；引导只讲「界面在哪」，在起步卡关掉之后才出现，不重复。
 * - 只弹一次；「跳过」/ Esc 随时退出；设置 →「重新查看引导」可再看。
 * - 专业模式才多一步（提到双画布）；普通模式不出现任何专业模式字样。
 * - 卡片 role=dialog + aria-modal，焦点进卡片、Tab 圈在卡片内，结束后焦点回到合理位置（从设置打开 → 设置按钮）。
 */
import {useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {useStudio} from '../../store';
import {resolveWorkspaceUser} from '../../workspace/state/scopeLease';
import {useT} from '../../i18n';
import type {MessageKey} from '../../i18n/zh-CN';
import {START_GATE_CLOSED_EVENT, markOnboardingSeen, useOnboardingStore} from './onboarding';
import './onboarding.css';

export type TourStep = {id: string; targets: string[]; title: MessageKey; body: MessageKey; pro?: boolean};
export const TOUR_STEPS: readonly TourStep[] = [
  {id: 'modules', targets: ['.module-switcher'], title: 'tour.modules.title', body: 'tour.modules.body'},
  {id: 'work', targets: ['.main-workspace'], title: 'tour.work.title', body: 'tour.work.body'},
  {id: 'assist', targets: ['#workspace-inspector[aria-hidden="false"]', '.inspector-edge-toggle'], title: 'tour.assist.title', body: 'tour.assist.body'},
  {id: 'settings', targets: ['.shell-settings'], title: 'tour.settings.title', body: 'tour.settings.body'},
  {id: 'save', targets: ['.status-bar'], title: 'tour.save.title', body: 'tour.save.body'},
  {id: 'pro', targets: ['.shell-mode-toggle'], title: 'tour.pro.title', body: 'tour.pro.body', pro: true},
];

const visible = (el: Element | null): el is HTMLElement => {
  if (!(el instanceof HTMLElement)) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
};
const findTarget = (s: TourStep) => { for (const q of s.targets) { const el = document.querySelector(q); if (visible(el)) return el; } return null; };

const autoAllowed = () => {
  try { if (import.meta.env?.MODE === 'test') return false; } catch { /* non-vite */ }
  try { if (/skip-tour/i.test(location.hash || '')) return false; } catch { /* ignore */ }
  return true;
};
const startGateOpen = () => !!document.querySelector('.module-start-gate');

export function useOnboarding({shellMode, auto = autoAllowed()}: {shellMode: 'basic' | 'pro'; auto?: boolean}) {
  const actorId = useStudio(s => s.actor?.id);
  const identity = resolveWorkspaceUser(actorId);
  const {seen, requests} = useOnboardingStore(identity);
  const [open, setOpen] = useState(false);
  const fromSettings = useRef(false);
  const lastReq = useRef(requests);
  useEffect(() => { // 设置菜单请求
    if (requests !== lastReq.current) { lastReq.current = requests; fromSettings.current = true; setOpen(true); }
  }, [requests]);
  useEffect(() => { // 首次自动出现：等起步卡关掉、界面稳定后
    if (!auto || seen || open) return;
    let t: ReturnType<typeof setTimeout> | undefined;
    // 关闭事件先于起步卡卸载触发，所以到点再检查一次起步卡是否还在
    const tryOpen = () => { if (t) clearTimeout(t); t = setTimeout(() => { if (!startGateOpen()) setOpen(true); }, 400); };
    tryOpen();
    window.addEventListener(START_GATE_CLOSED_EVENT, tryOpen);
    return () => { window.removeEventListener(START_GATE_CLOSED_EVENT, tryOpen); if (t) clearTimeout(t); };
  }, [auto, seen, open]);
  const close = useCallback(() => {
    markOnboardingSeen(identity); setOpen(false);
    // [HERMIA-FE-20261030 VERA-P3] 无模块切换器/设置按钮时兜底到主区（tabindex=-1），不让焦点掉到 BODY
    // [HERMIA-FE-20261031 VERA-P3-2] 只把焦点还给可见元素：display:none / visibility:hidden / hidden 祖先一律跳过
    const shown = (el: HTMLElement | null): el is HTMLElement => { for (let n: HTMLElement | null = el; n; n = n.parentElement) { if (n.hidden) return false; const cs = getComputedStyle(n); if (cs.display === 'none' || cs.visibility === 'hidden') return false; } return !!el?.isConnected; };
    const q = (s: string) => Array.from(document.querySelectorAll<HTMLElement>(s)).find(shown) || null;
    const main = q('main, [role="main"]'); if (main && !main.hasAttribute('tabindex')) main.setAttribute('tabindex', '-1');
    const back = (fromSettings.current ? q('[data-settings-trigger]') : q('[data-module-tab][aria-selected="true"]') || q('[data-settings-trigger]')) || main;
    fromSettings.current = false;
    setTimeout(() => back?.focus(), 0);
  }, [identity]);
  return {open, close, shellMode, session: !identity};
}

type Rect = {top: number; left: number; width: number; height: number};
const PAD = 6, GAP = 12, CARD_W = 340;

export function OnboardingTour({c}: {c: ReturnType<typeof useOnboarding>}) {
  const t = useT();
  const steps = useMemo(() => TOUR_STEPS.filter(s => !s.pro || c.shellMode === 'pro'), [c.shellMode]);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const [vw, setVw] = useState(() => (typeof innerWidth === 'number' ? innerWidth : 1366));
  const [vh, setVh] = useState(() => (typeof innerHeight === 'number' ? innerHeight : 800));
  const card = useRef<HTMLDivElement>(null);
  const next = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (c.open) setI(0); }, [c.open]);
  const step = steps[Math.min(i, steps.length - 1)];
  const measure = useCallback(() => {
    setVw(innerWidth); setVh(innerHeight);
    const el = step ? findTarget(step) : null;
    if (!el) { setRect(null); return; }
    const r = el.getBoundingClientRect();
    const top = Math.max(r.top, 0), left = Math.max(r.left, 0);
    setRect({top, left, width: Math.min(r.right, innerWidth) - left, height: Math.min(r.bottom, innerHeight) - top});
  }, [step]);
  useLayoutEffect(() => {
    if (!c.open) return;
    measure();
    addEventListener('resize', measure); addEventListener('scroll', measure, true);
    return () => { removeEventListener('resize', measure); removeEventListener('scroll', measure, true); };
  }, [c.open, measure]);
  useEffect(() => { if (c.open) next.current?.focus(); }, [c.open, i]);
  useEffect(() => {
    if (!c.open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); c.close(); return; }
      if (e.key !== 'Tab' || !card.current) return;
      const f = [...card.current.querySelectorAll<HTMLElement>('button:not([disabled])')];
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1], a = document.activeElement;
      if (e.shiftKey && (a === first || !card.current.contains(a))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (a === last || !card.current.contains(a))) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, [c.open, c.close]);
  if (!c.open || !step) return null;
  const last = i >= steps.length - 1;
  const w = Math.min(CARD_W, vw - 24);
  let pos: {top: number; left: number};
  if (!rect) pos = {top: Math.max(24, vh / 2 - 100), left: (vw - w) / 2};
  else {
    const below = rect.top + rect.height + PAD + GAP, cardH = 190;
    const big = rect.height > vh * 0.5; // 大区域（工作区 / 辅助栏）：卡片放进区域里，不挤到屏幕外
    const top = big ? rect.top + 24 : below + cardH < vh ? below : Math.max(12, rect.top - PAD - GAP - cardH);
    const leftWanted = big && rect.width < w + 24 ? rect.left - w - GAP : rect.left;
    pos = {top, left: Math.min(Math.max(12, leftWanted), vw - w - 12)};
  }
  const titleId = 'onboarding-title', bodyId = 'onboarding-body';
  // 挂到 body：不继承外壳里 nowrap / transform / 层叠上下文
  return createPortal(
    <div className="onboarding" data-onboarding="true" data-step={step.id}>
      {rect ? <div className="onboarding__spot" aria-hidden="true" style={{top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2}} /> : <div className="onboarding__dim" aria-hidden="true" />}
      <div ref={card} className="onboarding__card" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={bodyId} style={{top: pos.top, left: pos.left, width: w}}>
        <p className="onboarding__count">{t('tour.count', {n: String(i + 1), total: String(steps.length)})}</p>
        <h2 id={titleId} className="onboarding__title">{t(step.title)}</h2>
        <p id={bodyId} className="onboarding__body">{t(step.body)}</p>
        {c.session && last ? <p className="onboarding__note">{t('tour.sessionOnly')}</p> : null}
        <div className="onboarding__actions">
          <button type="button" className="onboarding__skip" data-onboarding-skip onClick={c.close}>{t('tour.skip')}</button>
          <span className="onboarding__spacer" />
          {i > 0 ? <button type="button" className="onboarding__prev" data-onboarding-prev onClick={() => setI(i - 1)}>{t('tour.prev')}</button> : null}
          <button ref={next} type="button" className="onboarding__next" data-onboarding-next onClick={() => (last ? c.close() : setI(i + 1))}>{last ? t('tour.done') : t('tour.next')}</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
