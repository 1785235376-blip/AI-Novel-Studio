// @vitest-environment jsdom
/** [HERMIA-FE-20261025 I18N P0] key parity, fallback (no raw keys), persistence, html lang, shell en coverage. */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react';
import { zhCN, type MessageKey } from './zh-CN';
import { en } from './en';
import { translate, setLocale, bootstrapLocale, getLocale, LOCALE_STORAGE_KEY, formatNumber, formatDate } from './index';
import { AppShell } from '../ui/AppShell';
import { LanguageToggle } from '../ui/LanguageToggle';

const vars = (s: string) => [...s.matchAll(/\{(\w+)[},]/g)].map((m) => m[1]).sort();
const HAN = /[\u4e00-\u9fff]/;

beforeEach(() => { cleanup(); localStorage.clear(); act(() => setLocale('zh-CN')); });

describe('dictionaries', () => {
  it('zh and en have identical key sets and placeholder sets', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(zhCN).sort());
    for (const k of Object.keys(zhCN) as MessageKey[]) expect([k, vars(en[k])]).toEqual([k, vars(zhCN[k])]);
  });
  it('en values contain no Chinese except the 中 language label', () => {
    for (const [k, v] of Object.entries(en)) if (k !== 'lang.zh' && k !== 'lang.zh.title') expect([k, HAN.test(v)]).toEqual([k, false]);
  });
  it('falls back to zh for missing en key and never returns the raw key', () => {
    const saved = (en as Record<string, string>)['common.close'];
    delete (en as Record<string, string>)['common.close'];
    try { expect(translate('en', 'common.close')).toBe('关闭'); } finally { (en as Record<string, string>)['common.close'] = saved; }
    expect(translate('en', 'no.such.key' as MessageKey)).toBe('');
  });
  it('interpolates and pluralises per locale', () => {
    expect(translate('en', 'common.chars', { count: 1 })).toBe('1 character');
    expect(translate('en', 'common.chars', { count: 20 })).toBe('20 characters');
    expect(translate('zh-CN', 'common.chars', { count: 20 })).toBe('20 字');
    expect(formatNumber(12345, 'en')).toBe('12,345');
    expect(formatDate('2026-10-25T03:00:00Z', 'en', { year: 'numeric', month: 'short', timeZone: 'UTC' })).toBe('Oct 2026');
    expect(formatDate('bad', 'en')).toBe('');
  });
});

describe('locale state', () => {
  it('defaults to zh-CN, persists, sets html lang and survives re-bootstrap (reload)', () => {
    expect(bootstrapLocale()).toBe('zh-CN');
    expect(document.documentElement.lang).toBe('zh-CN');
    act(() => setLocale('en'));
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('en');
    expect(document.documentElement.lang).toBe('en');
    expect(bootstrapLocale()).toBe('en');
    localStorage.setItem(LOCALE_STORAGE_KEY, 'fr');
    expect(bootstrapLocale()).toBe('zh-CN');
    expect(getLocale()).toBe('zh-CN');
  });
});

function Shell() {
  return <AppShell module="NOVEL" onModuleChange={() => {}} scope={{ workspace: 'W', project: 'P', storyline: 'S', branch: 'B' }} actor="Ann" sidebar={<div />} main={<div />} inspector={<div />} status={<span />} />;
}

describe('shell under en', () => {
  it('toggle switches without reload; migrated header/status/inspector contain no Chinese and no raw keys', () => {
    render(<Shell />);
    expect(screen.getByRole('tab', { name: /小说/ })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'EN' }));
    expect(screen.getByRole('tab', { name: /Novel/ })).toBeTruthy();
    const header = document.querySelector('header.global-header')!;
    const checked = [header, document.querySelector('.context-bar')!, document.querySelector('.workspace-inspector__controls')!];
    for (const el of checked) {
      const text = (el.textContent || '').replace('中', '');
      expect(HAN.test(text), text).toBe(false);
      expect(/\b[a-z]+\.[a-z_.]+\b/.test(text), text).toBe(false);
      el.querySelectorAll('[aria-label],[title]').forEach((n) => {
        const a = `${n.getAttribute('aria-label') || ''}${n.getAttribute('title') || ''}`.replace('中文', '');
        expect(HAN.test(a), a).toBe(false);
      });
    }
    expect(document.documentElement.lang).toBe('en');
    fireEvent.click(screen.getByRole('button', { name: '中' }));
    expect(screen.getByRole('tab', { name: /小说/ })).toBeTruthy();
  });
  it('Ctrl-K palette is English under en', () => {
    act(() => setLocale('en'));
    render(<Shell />);
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    const dlg = screen.getByRole('dialog', { name: 'Global commands' });
    expect(HAN.test(dlg.textContent || ''), dlg.textContent || '').toBe(false);
    fireEvent.change(dlg.querySelector('input')!, { target: { value: 'zzzz' } });
    expect(dlg.textContent).toContain('No matching commands');
  });
  it('LanguageToggle reflects persisted locale', () => {
    localStorage.setItem(LOCALE_STORAGE_KEY, 'en'); bootstrapLocale();
    render(<LanguageToggle />);
    expect(screen.getByRole('button', { name: 'EN' }).getAttribute('aria-pressed')).toBe('true');
  });
});
