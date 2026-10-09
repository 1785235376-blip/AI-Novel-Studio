// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppShell, ContextBar, type ScopeLabels } from './AppShell';
import { STUDIO_MODULES } from './moduleRegistry';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement | undefined;
let root: Root | undefined;
function mount() {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  return { host, root };
}
afterEach(() => {
  if (root) act(() => root?.unmount());
  host?.remove();
  root = undefined;
  host = undefined;
});

const scope = { workspace: '创作空间', project: '现有小说', storyline: '主线', branch: '当前草稿' };
// This is the pre-extension markup, retained only as a renderer regression oracle.
function LegacyContextBar({ scope }: { scope: ScopeLabels }) {
  const fallback = '未选择';
  return <nav className="context-bar" aria-label="当前创作范围">
    <span>创作空间：{scope.workspace || fallback}</span><i>/</i>
    <span>小说：{scope.project || fallback}</span><i>/</i>
    <span>故事线：{scope.storyline || fallback}</span><i>/</i>
    <span>创作分支：{scope.branch || fallback}</span>
  </nav>;
}
function textNodes(element: Element) {
  return [...element.children].map(child => [...child.childNodes].map(node => [node.nodeType, node.nodeValue]));
}
const shellProps = { onModuleChange: vi.fn(), scope, actor: '作者', sidebar: '导航', main: '内容', inspector: '检查', status: '已保存' };

describe('approved optional ContextBar project noun', () => {
  it.each([scope, { workspace: '', project: '', storyline: '', branch: '' }])('preserves exact legacy markup, text nodes and accessibility when omitted', value => {
    const { host, root } = mount();
    act(() => root.render(<LegacyContextBar scope={value} />));
    const markup = host.innerHTML;
    const nodes = textNodes(host.firstElementChild!);
    act(() => root.render(<ContextBar scope={value} />));
    expect(host.innerHTML).toBe(markup);
    expect(textNodes(host.firstElementChild!)).toEqual(nodes);
    expect(host.firstElementChild?.getAttribute('aria-label')).toBe('当前创作范围');
    act(() => root.render(<ContextBar scope={value} projectNoun="小说" />));
    expect(host.innerHTML).toBe(markup);
    expect(textNodes(host.firstElementChild!)).toEqual(nodes);
  });

  it.each(STUDIO_MODULES.map(row => row.id))('keeps the legacy default through AppShell for %s', module => {
    const { host, root } = mount();
    act(() => root.render(<AppShell {...shellProps} module={module} />));
    expect(host.querySelector('.context-bar')?.textContent).toBe('创作空间：创作空间/小说：现有小说/故事线：主线/创作分支：当前草稿');
    expect([...host.querySelectorAll('[data-module-tab]')].map(tab => tab.getAttribute('data-module-tab')))
      .toEqual(['NOVEL', 'IMAGE', 'VIDEO', 'ASSETS', 'AUDIO', 'CONTROL', 'PLUGIN', 'WORKFLOW']);
  });

  it('changes only the project noun when explicitly selected through AppShell', () => {
    const { host, root } = mount();
    act(() => root.render(<AppShell {...shellProps} module="IMAGE" />));
    const legacyMarkup = host.innerHTML;
    act(() => root.render(<AppShell {...shellProps} module="IMAGE" projectNoun="项目" />));
    expect(host.innerHTML).toBe(legacyMarkup.replace('小说：', '项目：'));
    expect(host.querySelector('.context-bar')?.getAttribute('aria-label')).toBe('当前创作范围');
    act(() => root.render(<AppShell {...shellProps} module="IMAGE" />));
    expect(host.innerHTML).toBe(legacyMarkup);
  });

  it('uses current scope values and restores the default without leaking the prior project label', () => {
    const { host, root } = mount();
    act(() => root.render(<AppShell {...shellProps} module="IMAGE" scope={{ ...scope, project: '空白创作 A' }} projectNoun="项目" />));
    expect(host.querySelector('.context-bar')?.textContent).toContain('项目：空白创作 A');
    act(() => root.render(<AppShell {...shellProps} module="NOVEL" scope={{ ...scope, project: '小说 B' }} />));
    expect(host.querySelector('.context-bar')?.textContent).toContain('小说：小说 B');
    expect(host.textContent).not.toContain('空白创作 A');
    act(() => root.render(<AppShell {...shellProps} module="ASSETS" scope={{ workspace: '', project: '', storyline: '', branch: '' }} projectNoun="项目" />));
    expect(host.querySelector('.context-bar')?.textContent).toBe('创作空间：未选择/项目：未选择/故事线：未选择/创作分支：未选择');
    expect(host.textContent).not.toContain('小说 B');
  });
});
