// @vitest-environment jsdom
// [HERMIA-UX-20261030] 普通用户可用性审计修复：红→绿
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {AppShell, ContextBar} from './AppShell';
import {orientWhat} from '../rebuild/novel/NovelOrient';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement, root: Root;
beforeEach(() => { localStorage.clear(); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
afterEach(() => { act(() => root.unmount()); host.remove(); });
const scope = {workspace: '已选创作空间（未命名）', project: '已选作品（未命名）', storyline: '已选故事线（未命名）', branch: '已选分支（未命名）'};
const props = {onModuleChange: vi.fn(), scope, sidebar: 'n', main: 'm', inspector: 'i', status: 's'};

describe('UX audit 2026-10-30', () => {
  it('H1 orient never says "no work open" while a work is open', () => {
    expect(orientWhat(undefined, 'n1')).toBe('《未命名小说》');
    expect(orientWhat('雾港', 'n1', '第 1 章 · 第一章')).toBe('《雾港》 · 第 1 章 · 第一章');
    expect(orientWhat(undefined, '')).toBe('还没有打开作品');
  });
  it('M1 basic-mode context bar hides workspace/storyline/branch jargon', () => {
    act(() => root.render(<ContextBar scope={scope} compact />));
    const txt = host.textContent || '';
    expect(txt).not.toMatch(/创作空间|故事线|创作分支|已选/);
    expect(txt).toContain('小说：未命名作品');
  });
  it('M1 pro mode keeps the full scope path', () => {
    act(() => root.render(<AppShell {...props} actor="作者" module="IMAGE" shellMode="pro" />));
    expect(host.querySelector('.context-bar')?.textContent).toContain('创作分支');
  });
  it('M1 basic mode non-novel module uses the compact bar', () => {
    act(() => root.render(<AppShell {...props} actor="作者" module="IMAGE" shellMode="basic" />));
    expect(host.querySelector('.context-bar')?.textContent).not.toContain('创作分支');
  });
  it('M4 raw actor id never reaches the accessibility tree', () => {
    act(() => root.render(<AppShell {...props} actor="u-a" module="NOVEL" shellMode="basic" />));
    expect(host.querySelector('.current-actor')?.textContent).not.toContain('u-a');
    act(() => root.render(<AppShell {...props} actor="林雾" module="NOVEL" shellMode="basic" />));
    expect(host.querySelector('.current-actor')?.textContent).toContain('林雾');
  });
  it('M5 both asides carry distinct accessible names', () => {
    act(() => root.render(<AppShell {...props} actor="作者" module="NOVEL" shellMode="basic" />));
    const names = [...host.querySelectorAll('aside')].map(a => a.getAttribute('aria-label'));
    expect(names.every(Boolean)).toBe(true);
    expect(new Set(names).size).toBe(names.length);
  });
});
