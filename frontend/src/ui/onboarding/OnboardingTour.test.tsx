// @vitest-environment jsdom
// [HERMIA-UX-20261030 ONBOARD] 首次引导：只弹一次、跳过/Esc、按身份持久化、设置里可重看、专业模式专属一步、焦点管理
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {AppShell} from '../AppShell';
import {OnboardingTour, TOUR_STEPS, useOnboarding} from './OnboardingTour';
import {__resetOnboarding, markOnboardingSeen, onboardingStorageKey, readOnboardingSeen} from './onboarding';
import {resolveWorkspaceIdentity} from '../../workspace/state/scopeLease';
import {zhCN} from '../../i18n/zh-CN';
import {en} from '../../i18n/en';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement, root: Root;
beforeEach(() => { vi.useFakeTimers(); localStorage.clear(); __resetOnboarding(); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
afterEach(() => { act(() => root.unmount()); host.remove(); document.querySelectorAll('.module-start-gate').forEach(n => n.remove()); vi.useRealTimers(); });

function Harness({mode = 'basic' as 'basic' | 'pro'}) {
  const c = useOnboarding({shellMode: mode, auto: true});
  return <><button data-settings-trigger>设置</button><OnboardingTour c={c} /></>;
}
const flush = () => act(() => { vi.advanceTimersByTime(500); });
const card = () => document.querySelector('.onboarding__card');
const key = (k: string) => act(() => { document.dispatchEvent(new KeyboardEvent('keydown', {key: k, bubbles: true})); });

describe('onboarding tour', () => {
  it('auto-opens once, Skip closes and it stays closed', () => {
    act(() => root.render(<Harness />)); flush();
    expect(card()?.getAttribute('role')).toBe('dialog');
    expect(card()?.textContent).toContain('第 1 / 5 步');
    act(() => (document.querySelector('[data-onboarding-skip]') as HTMLButtonElement).click());
    expect(card()).toBeNull();
    act(() => root.unmount()); root = createRoot(host);
    act(() => root.render(<Harness />)); flush();
    expect(card()).toBeNull();
  });
  it('Esc closes and marks seen', () => {
    act(() => root.render(<Harness />)); flush();
    key('Escape');
    expect(card()).toBeNull();
    expect(readOnboardingSeen(resolveWorkspaceIdentity({actorId: null, collabScope: null, projectId: null}))).toBe(true);
  });
  it('waits for the start gate and opens after it closes', () => {
    const gate = document.createElement('div'); gate.className = 'module-start-gate'; document.body.append(gate);
    act(() => root.render(<Harness />)); flush();
    expect(card()).toBeNull();
    gate.remove(); act(() => { window.dispatchEvent(new Event('studio:start-gate-closed')); }); flush();
    expect(card()).not.toBeNull();
  });
  it('next/prev/done walk the steps; basic has no pro step, pro has 6', () => {
    act(() => root.render(<Harness />)); flush();
    const next = () => act(() => (document.querySelector('[data-onboarding-next]') as HTMLButtonElement).click());
    for (let i = 0; i < 4; i++) next();
    expect(card()?.textContent).toContain('完成');
    expect(document.body.textContent).not.toMatch(/专业模式|双画布/);
    next(); expect(card()).toBeNull();
    __resetOnboarding(); act(() => root.unmount()); root = createRoot(host);
    act(() => root.render(<Harness mode="pro" />)); flush();
    expect(card()?.textContent).toContain('第 1 / 6 步');
    for (let i = 0; i < 5; i++) next();
    expect(card()?.textContent).toMatch(/双画布/);
  });
  it('session-only identity is labelled honestly on the last step', () => {
    act(() => root.render(<Harness />)); flush();
    for (let i = 0; i < 4; i++) act(() => (document.querySelector('[data-onboarding-next]') as HTMLButtonElement).click());
    expect(card()?.textContent).toContain('仅本次会话');
  });
  it('real identity persists per user in localStorage; session identity writes nothing', () => {
    const scope = {workspaceId: 'w', projectId: 'p1', storylineId: 's', branchId: 'b'};
    const id = resolveWorkspaceIdentity({actorId: 'u1', collabScope: scope, projectId: 'p1'});
    if (id.kind !== 'real') throw new Error('expected real identity');
    expect(markOnboardingSeen(id)).toBe('saved');
    expect(localStorage.getItem(onboardingStorageKey(id))).toBe('{"v":1,"seen":true}');
    __resetOnboarding();
    expect(readOnboardingSeen(id)).toBe(true);
    expect(readOnboardingSeen(resolveWorkspaceIdentity({actorId: 'u2', collabScope: scope, projectId: 'p1'}))).toBe(false);
    localStorage.clear();
    expect(markOnboardingSeen(resolveWorkspaceIdentity({actorId: null, collabScope: null, projectId: null}))).toBe('session');
    expect(localStorage.length).toBe(0);
  });
  it('focus is trapped in the card and Settings →「重新查看引导」reopens, focus returns to settings', () => {
    act(() => root.render(<AppShell scope={{workspace: "w", project: "p", storyline: "s", branch: "b"}} onModuleChange={vi.fn()} actor="作者" module="NOVEL" sidebar="n" main="m" inspector="i" status="s" />));
    flush();
    expect(card()).toBeNull(); // test mode never auto-opens
    const trig = host.querySelector('[data-settings-trigger]') as HTMLButtonElement;
    act(() => trig.click());
    const item = host.querySelector('[data-replay-tour]') as HTMLButtonElement;
    expect(item.textContent).toBe('重新查看引导');
    act(() => item.click());
    expect(card()).not.toBeNull();
    expect(card()?.contains(document.activeElement)).toBe(true);
    key('Escape'); act(() => { vi.runAllTimers(); });
    expect(card()).toBeNull();
    expect(document.activeElement).toBe(trig);
  });
  it('every tour string exists in zh and en', () => {
    for (const s of TOUR_STEPS) for (const k of [s.title, s.body]) { expect(zhCN[k]).toBeTruthy(); expect((en as Record<string, string>)[k]).toBeTruthy(); }
  });
});
