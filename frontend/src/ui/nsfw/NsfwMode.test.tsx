// @vitest-environment jsdom
// [HERMIA-FE-20261030 NSFW] 成人内容（NSFW）模式：默认关 / 必须确认 / 取消保持关 / 持久化规则 / 顶栏状态标
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {AppShell} from '../AppShell';
import {useStudio} from '../../store';
import {resolveWorkspaceIdentity} from '../../workspace/state/scopeLease';
import {NSFW_KEY_PREFIX, __resetNsfwSession, enableNsfwMode, nsfwStorageKey, readNsfwMode} from './nsfwMode';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;
const scope = {workspaceId: 'ws1', projectId: 'p1', storylineId: 'sl1', branchId: 'br1'};
const real = () => resolveWorkspaceIdentity({actorId: 'u1', collabScope: scope, projectId: 'p1'});
const realKey = () => { const id = real(); if (id.kind !== 'real') throw new Error('expected real identity'); return nsfwStorageKey(id); };
const props = {onModuleChange: vi.fn(), scope: {workspace: 'w', project: 'p', storyline: 's', branch: 'b'}, actor: '作者', sidebar: 'n', main: 'm', inspector: 'i', status: 's', module: 'NOVEL' as const};
let host: HTMLDivElement, root: Root;
const q = <T extends Element = HTMLElement>(s: string) => document.querySelector<T>(s);
const click = (el: Element | null) => act(() => { (el as HTMLElement).click(); });
function mount(mode: 'basic' | 'pro' = 'basic') { act(() => root.render(<AppShell {...props} shellMode={mode} />)); }
const openMenu = () => click(q('[data-settings-trigger]'));
const nsfwKeys = () => Object.keys(localStorage).filter(k => k.startsWith(NSFW_KEY_PREFIX));

beforeEach(() => {
  localStorage.clear(); __resetNsfwSession();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(() => { act(() => root.unmount()); host.remove(); useStudio.setState({actor: undefined, scope: undefined, novelId: ''}); });
const signIn = () => useStudio.setState({actor: {id: 'u1', name: '作者'} as never, scope: scope as never, novelId: 'p1'});

describe('NSFW mode', () => {
  for (const mode of ['basic', 'pro'] as const) it(`default off, entry visible in ${mode} mode, no badge`, () => {
    signIn(); mount(mode); openMenu();
    const t = q('[data-nsfw-toggle]');
    expect(t?.textContent).toContain('成人内容（NSFW）模式');
    expect(t?.getAttribute('aria-checked')).toBe('false');
    expect(q('[data-nsfw-honest]')?.textContent).toContain('仅界面偏好，后端未接入');
    expect(q('[data-nsfw-badge]')).toBeNull();
    expect(nsfwKeys()).toEqual([]);
  });

  it('turning on needs the 18+ dialog; confirm is disabled until acknowledged', () => {
    signIn(); mount(); openMenu(); click(q('[data-nsfw-toggle]'));
    const dlg = q('[data-testid="nsfw-dialog"]');
    expect(dlg?.getAttribute('role')).toBe('dialog');
    expect(dlg?.textContent).toContain('18');
    expect(document.activeElement).toBe(q('[data-cfd-cancel]'));
    expect(q('[data-nsfw-badge]')).toBeNull();
    const ok = q<HTMLButtonElement>('[data-nsfw-confirm]')!;
    expect(ok.disabled).toBe(true);
    click(ok); // disabled click is a no-op
    expect(q('[data-nsfw-badge]')).toBeNull();
    click(q('[data-nsfw-ack]'));
    expect(ok.disabled).toBe(false);
    click(ok);
    expect(q('[data-testid="nsfw-dialog"]')).toBeNull();
    expect(q('[data-nsfw-badge]')?.textContent).toContain('NSFW 模式');
  });

  it('cancel and Esc keep it off and write nothing', () => {
    signIn(); mount(); openMenu(); click(q('[data-nsfw-toggle]'));
    click(q('[data-nsfw-ack]')); click(q('[data-cfd-cancel]'));
    expect(q('[data-testid="nsfw-dialog"]')).toBeNull();
    expect(q('[data-nsfw-badge]')).toBeNull();
    openMenu(); click(q('[data-nsfw-toggle]'));
    act(() => { document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); });
    expect(q('[data-testid="nsfw-dialog"]')).toBeNull();
    expect(q('[data-nsfw-badge]')).toBeNull();
    expect(nsfwKeys()).toEqual([]);
    expect(readNsfwMode(real())).toBe(false);
  });

  it('real identity persists per user/project/instance; badge turns it off in one click', () => {
    signIn(); mount(); openMenu();
    expect(q('[data-nsfw-persist]')?.getAttribute('data-nsfw-persist')).toBe('saved');
    click(q('[data-nsfw-toggle]')); click(q('[data-nsfw-ack]')); click(q('[data-nsfw-confirm]'));
    expect(JSON.parse(localStorage.getItem(realKey())!)).toEqual({v: 1, on: true});
    __resetNsfwSession(); // simulate reload
    expect(readNsfwMode(real())).toBe(true);
    expect(readNsfwMode(resolveWorkspaceIdentity({actorId: 'u2', collabScope: scope, projectId: 'p1'}))).toBe(false);
    expect(readNsfwMode(resolveWorkspaceIdentity({actorId: 'u1', collabScope: {...scope, branchId: 'br2'}, projectId: 'p1'}))).toBe(false);
    mount();
    click(q('[data-nsfw-off]'));
    expect(q('[data-nsfw-badge]')).toBeNull();
    expect(nsfwKeys()).toEqual([]);
  });

  it('no identity ⇒ 仅本次会话: memory only, zero storage writes, gone after reload', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    mount(); openMenu();
    expect(q('[data-nsfw-persist]')?.textContent).toContain('仅本次会话');
    click(q('[data-nsfw-toggle]')); click(q('[data-nsfw-ack]')); click(q('[data-nsfw-confirm]'));
    expect(q('[data-nsfw-badge]')?.textContent).toContain('仅本次会话');
    expect(setItem.mock.calls.filter(([k]) => String(k).startsWith(NSFW_KEY_PREFIX))).toEqual([]);
    __resetNsfwSession();
    expect(readNsfwMode(resolveWorkspaceIdentity({actorId: null, collabScope: null, projectId: null}))).toBe(false);
    setItem.mockRestore();
  });

  it('never auto-enables: corrupt / foreign stored values read as off', () => {
    for (const raw of ['{bad', 'true', '{"v":2,"on":true}', '{"v":1,"on":"yes"}', '{"v":1}']) {
      localStorage.setItem(realKey(), raw);
      __resetNsfwSession();
      expect(readNsfwMode(real())).toBe(false);
    }
  });

  it('english UI shows english strings', async () => {
    const {setLocale} = await import('../../i18n');
    act(() => setLocale('en')); signIn(); enableNsfwMode(real()); mount(); openMenu();
    expect(q('[data-nsfw-toggle]')?.textContent).toContain('Adult content (NSFW) mode');
    expect(q('[data-nsfw-badge]')?.textContent).toContain('NSFW mode');
    expect(q('[data-nsfw-badge]')?.textContent).not.toMatch(/[\u4e00-\u9fff]/);
    act(() => setLocale('zh-CN'));
  });
  for (const how of ['esc', 'cancel', 'confirm'] as const) it(`P2: focus returns to settings trigger after ${how}`, () => {
    signIn(); mount(); openMenu(); click(q('[data-nsfw-toggle]'));
    if (how === 'esc') act(() => { document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); });
    else if (how === 'cancel') click(q('[data-cfd-cancel]'));
    else { click(q('[data-nsfw-ack]')); click(q('[data-nsfw-confirm]')); }
    expect(q('[data-nsfw-confirm]')).toBeNull();
    expect(document.activeElement).toBe(q('[data-settings-trigger]'));
  });
});
