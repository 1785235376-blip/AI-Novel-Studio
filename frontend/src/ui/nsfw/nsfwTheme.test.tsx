// @vitest-environment jsdom
// [HERMIA-FE-20261030 NSFW-THEME] NSFW 开启 ⇒ <html data-nsfw="on"> 覆盖主题 token（浅/深色都覆盖 --color-*/--cv-*/--stg-*），关闭即时恢复，对比度 AA。
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {AppShell} from '../AppShell';
import {useStudio} from '../../store';
import {__resetNsfwSession} from './nsfwMode';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;
const props = {onModuleChange: vi.fn(), scope: {workspace: 'w', project: 'p', storyline: 's', branch: 'b'}, actor: '作者', sidebar: 'n', main: 'm', inspector: 'i', status: 's', module: 'NOVEL' as const};
let host: HTMLDivElement, root: Root;
const q = <T extends Element = HTMLElement>(s: string) => document.querySelector<T>(s);
const click = (el: Element | null) => act(() => { (el as HTMLElement).click(); });
const attr = () => document.documentElement.getAttribute('data-nsfw');
function turnOn() {
  click(q('[data-settings-trigger]')); click(q('[data-nsfw-toggle]'));
  click(q('[data-nsfw-ack]')); click(q('[data-nsfw-confirm]'));
}
beforeEach(() => { localStorage.clear(); __resetNsfwSession(); document.documentElement.removeAttribute('data-nsfw'); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
afterEach(() => { act(() => root.unmount()); host.remove(); useStudio.setState({actor: undefined, scope: undefined, novelId: ''}); });

describe('NSFW theme root attribute', () => {
  for (const mode of ['basic', 'pro'] as const) it(`${mode}: off by default, on after confirm, off restores immediately`, () => {
    act(() => root.render(<AppShell {...props} shellMode={mode} />));
    expect(attr()).toBeNull();
    click(q('[data-settings-trigger]')); click(q('[data-nsfw-toggle]'));
    expect(attr()).toBeNull(); // dialog open is not "on"
    click(q('[data-cfd-cancel]'));
    expect(attr()).toBeNull();
    turnOn();
    expect(attr()).toBe('on');
    click(q('[data-nsfw-off]'));
    expect(attr()).toBeNull();
  });
  it('unmount clears the attribute (no leak into other shells)', () => {
    act(() => root.render(<AppShell {...props} shellMode="basic" />));
    turnOn(); expect(attr()).toBe('on');
    act(() => root.unmount()); root = createRoot(host);
    expect(attr()).toBeNull();
  });
});

const css = readFileSync(resolve(__dirname, 'nsfwTheme.css'), 'utf8');
const block = (sel: RegExp) => { const m = css.match(sel); if (!m) throw new Error(`missing block ${sel}`); return m[1]; };
const vars = (b: string) => Object.fromEntries([...b.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map(m => [m[1], m[2].trim()]));
const lum = (hex: string) => { const n = hex.replace('#', ''); const c = [0, 2, 4].map(i => parseInt(n.slice(i, i + 2), 16) / 255).map(v => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
const ratio = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, r) => r - p); return (x + 0.05) / (y + 0.05); };
const themes: Record<string, () => Record<string, string>> = {
  dark: () => vars(block(/\[data-nsfw="on"\]:not\(\[data-theme="light"\]\)\s*\{([^}]*)\}/)),
  light: () => vars(block(/\[data-theme="light"\]\[data-nsfw="on"\]\s*\{([^}]*)\}/)),
};
describe('NSFW theme tokens', () => {
  for (const [name, get] of Object.entries(themes)) {
    it(`${name}: overrides color, --cv-* and --stg-* families`, () => {
      const v = get();
      for (const k of ['--color-bg-app', '--color-bg-surface', '--color-accent-primary', '--color-border-default', '--color-text-muted', '--color-selection-bg', '--focus-ring', '--cv-bg', '--cv-node', '--cv-ink', '--stg-mon', '--stg-tl', '--stg-line', '--stg-clip']) expect(v[k], k).toBeTruthy();
    });
    it(`${name}: text and accent meet WCAG AA on every NSFW surface`, () => {
      const v = get();
      const surf = ['--color-bg-app', '--color-bg-surface', '--color-bg-elevated', '--color-bg-subtle', '--color-selection-bg'];
      for (const s of surf) {
        expect(ratio(v['--color-text-primary'], v[s]), `primary/${s}`).toBeGreaterThanOrEqual(7);
        expect(ratio(v['--color-text-muted'], v[s]), `muted/${s}`).toBeGreaterThanOrEqual(4.5);
        expect(ratio(v['--color-accent-primary'], v[s]), `accent/${s}`).toBeGreaterThanOrEqual(4.5);
      }
      expect(ratio(v['--cv-ink'], v['--cv-node']), 'cv ink/node').toBeGreaterThanOrEqual(7);
      expect(ratio(v['--stg-ink'], v['--stg-mon']), 'stg ink/mon').toBeGreaterThanOrEqual(7);
      expect(ratio(v['--color-text-inverse'], v['--color-accent-primary']), 'inverse on accent').toBeGreaterThanOrEqual(4.5);
    });
  }
});
