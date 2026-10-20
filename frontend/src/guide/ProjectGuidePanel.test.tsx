// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProjectGuidePanel, type ProjectGuidePanelProps } from './ProjectGuidePanel';
import { GUIDE_CODES, GUIDE_NOTICES } from './projectGuideTypes';
import { QINGJIAN_EXTENSION, qingjianAdapterCount, qingjianMentorAvailable, registerQingjianAdapter } from './qingjianExtension';
import {
  IDENTITY, PROJECT, assetRows, graphFacts, inboxProjection, projection, storyboardReceipt,
  tasksProjection, timelineFacts,
} from './projectGuideFixtures';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

/** 一份**完全可读**的事实包：所有落点都指向真实原 owner 投影。 */
const loaded = (override: Partial<ProjectGuidePanelProps> = {}): ProjectGuidePanelProps => ({
  projectId: PROJECT, identity: IDENTITY, active: true, denied: false,
  workflow: projection({ selected: ['novel_writing'] }),
  tasks: tasksProjection(),
  inbox: inboxProjection(),
  assets: assetRows([{ id: 'asset-1', media_kind: 'image' }]),
  graph: graphFacts([{ id: 'node-1' }], [{ id: 'edge-1' }], [{ node_id: 'node-1', state: 'CURRENT' }]),
  timeline: timelineFacts(1, 1),
  facts: { storyboard: storyboardReceipt(1, true) },
  ...override,
});

function renderPanel(override: Partial<ProjectGuidePanelProps> = {}, withNavigate = true) {
  const onNavigate = vi.fn();
  const onUnavailable = vi.fn();
  // 三个门控字段不接受 override：用例总是显式声明它们，避免夹具把门控悄悄覆盖掉。
  const { active: _active, denied: _denied, ...patch } = override;
  const props: ProjectGuidePanelProps = {
    ...loaded(patch),
    ...(override.active === undefined ? {} : { active: override.active }),
    ...(override.denied === undefined ? {} : { denied: override.denied }),
    onUnavailable,
  };
  if (withNavigate) props.onNavigate = onNavigate;
  return { ...render(<ProjectGuidePanel {...props}/>), onNavigate, onUnavailable };
}

const stateOf = (container: HTMLElement): string | null =>
  container.querySelector('.project-guide')?.getAttribute('data-guide-state') ?? null;

describe('ProjectGuidePanel：不发起任何网络请求', () => {
  it('挂载、重渲染与卸载都不会调用 fetch / XHR / 传输层', () => {
    const fetchSpy = vi.fn(() => Promise.resolve(new Response('{}')));
    vi.stubGlobal('fetch', fetchSpy);
    const openSpy = vi.fn();
    vi.stubGlobal('XMLHttpRequest', class { open = openSpy; send = vi.fn(); setRequestHeader = vi.fn(); });

    const view = renderPanel();
    view.rerender(<ProjectGuidePanel {...loaded()}/>);
    view.unmount();

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('面板的 props 里没有客户端、传输或读取参数', () => {
    const props = loaded();
    expect(Object.keys(props)).not.toContain('client');
    expect(Object.keys(props)).not.toContain('transport');
    expect(Object.keys(props)).not.toContain('read');
    expect(Object.keys(props)).not.toContain('mutate');
  });
});

describe('ProjectGuidePanel：被拒绝绝不等同空项目', () => {
  it('denied 时显示无权读取，且不显示"没有需要处理的条目"', () => {
    const { container } = renderPanel({ denied: true });
    expect(screen.queryByText('没有需要处理的项目条目')).toBeNull();
    expect(screen.getByText('当前会话无权读取这个项目的提示事实')).toBeTruthy();
    expect(screen.getByText(GUIDE_NOTICES.deniedIsNotUnknownProject)).toBeTruthy();
    expect(stateOf(container)).toBe('DENIED');
    expect(container.querySelector('.project-guide')?.getAttribute('data-guide-hints')).toBe('0');
    expect(container.querySelector('.project-guide-hint')).toBeNull();
  });

  it('denied 优先于任何已读到的事实（拒绝就是拒绝）', () => {
    const { container } = renderPanel({ denied: true });
    expect(container.querySelector('[data-guide-state="DENIED"]')).toBeTruthy();
    expect(container.querySelector('[data-guide-state="READY"]')).toBeNull();
  });

  it('一个来源都读不到时状态是 FAILED，并明说"事实不可读"', () => {
    const { container } = renderPanel({ workflow: undefined, tasks: undefined, inbox: undefined,
      assets: undefined, graph: undefined, timeline: undefined, facts: undefined });
    expect(stateOf(container)).toBe('FAILED');
    expect(screen.getByText('项目事实不可读，因此没有建议')).toBeTruthy();
    expect(screen.getByText(GUIDE_NOTICES.unreadable)).toBeTruthy();
    expect(container.querySelector('.project-guide-hint')).toBeNull();
  });

  it('输入形状不合法（不是对象）按失败处理，并给出稳定机器码', () => {
    const { container } = renderPanel({ workflow: 'not-the-owner-projection' });
    expect(stateOf(container)).toBe('FAILED');
    expect(screen.getByText(new RegExp(GUIDE_CODES.factsInvalid))).toBeTruthy();
  });

  it('单个来源形状不合法时是 READY + 明确警告，绝不悄悄当成没问题', () => {
    const { container } = renderPanel({ workflow: { contract: 'not-the-owner-contract' } });
    expect(stateOf(container)).toBe('READY');
    expect(screen.getByText(/部分原 owner 阅读面不可读/)).toBeTruthy();
    const blocked = container.querySelector('.project-guide-hint[data-guide-code="FACTS_PARTIALLY_UNREADABLE"]');
    expect(blocked).toBeTruthy();
    expect(blocked?.textContent).toContain('PRODUCTION_WORKFLOW_PROJECTION');
    // 缺失的阅读面同时出现在说明块里（它必须点名缺了什么）。
    expect(container.querySelector('.project-guide__boundary')?.parentElement?.textContent)
      .toContain('不可读：');
  });

  it('单个来源形状不合法时不会渲染成"空项目"', () => {
    const { container } = renderPanel({ workflow: { contract: 'not-the-owner-contract' } });
    expect(screen.queryByText('没有需要处理的项目条目')).toBeNull();
    expect(stateOf(container)).not.toBe('EMPTY');
    expect(stateOf(container)).not.toBe('DENIED');
  });

  it('未激活时不推导：状态是 IDLE，没有任何提示', () => {
    const { container } = renderPanel({ active: false });
    expect(stateOf(container)).toBe('IDLE');
    expect(container.querySelector('.project-guide-hint')).toBeNull();
  });

  it('facts 信封形状不合法时按失败处理，绝不静默忽略', () => {
    const scalar = renderPanel({ facts: 'not-an-envelope' });
    expect(stateOf(scalar.container)).toBe('FAILED');
    expect(scalar.container.querySelector('.project-guide-blocked')?.getAttribute('data-guide-code'))
      .toBe(GUIDE_CODES.factsInvalid);
    cleanup();
    const unknownKey = renderPanel({ facts: { storyboard: storyboardReceipt(1, true), extra: 1 } });
    expect(stateOf(unknownKey.container)).toBe('FAILED');
    expect(unknownKey.container.textContent).toContain(GUIDE_CODES.factsInvalid);
    expect(unknownKey.container.querySelector('.project-guide-hint')).toBeNull();
  });

  it('facts 信封承载的分镜回执参与推导（未批准会提示批准）', () => {
    const { container } = renderPanel({
      workflow: projection({ selected: ['novel_writing'] }),
      facts: { storyboard: storyboardReceipt(2, false) },
    });
    const hint = container.querySelector('.project-guide-hint[data-guide-code="STORYBOARD_NOT_APPROVED"]');
    expect(hint).toBeTruthy();
    expect(hint?.getAttribute('data-guide-sources')).toBe('fact:storyboard.approved|fact:storyboard.shots');
  });
});

describe('ProjectGuidePanel：每条渲染出来的提示都带来源', () => {
  it('每条提示都显示它引用的 owner 字段', () => {
    const { container } = renderPanel();
    const hints = [...container.querySelectorAll('.project-guide-hint')];
    expect(hints.length).toBeGreaterThanOrEqual(2);
    expect(stateOf(container)).toBe('READY');
    for (const row of hints) {
      const sources = row.getAttribute('data-guide-sources') ?? '';
      expect(sources.startsWith('fact:')).toBe(true);
      expect(within(row as HTMLElement).getByText(/^来源：/)).toBeTruthy();
      expect(row.querySelectorAll('code').length).toBeGreaterThanOrEqual(sources.split('|').length);
    }
  });

  it('具体提示的来源就是真实字段（意图 / 素材 / 时间线 / 任务）', () => {
    const { container } = renderPanel({
      workflow: projection(), assets: assetRows([]), timeline: timelineFacts(0, 0),
    });
    const byCode = (code: string) => container.querySelector(`.project-guide-hint[data-guide-code="${code}"]`);
    expect(byCode('INTENT_NOT_SET')?.getAttribute('data-guide-sources'))
      .toBe('fact:creative_intent.version|fact:creative_intent.values.selected');
    expect(byCode('ASSETS_LIBRARY_EMPTY')?.getAttribute('data-guide-sources')).toContain('fact:asset_overview.total');
    expect(byCode('TIMELINE_UNRENDERED')?.getAttribute('data-guide-sources'))
      .toBe('fact:timeline.track_count|fact:timeline.clip_count');
    expect(byCode('TASKS_NONE_READ')?.getAttribute('data-guide-sources')).toContain('fact:tasks.total');
  });

  it('详情显示 claim、引用事实与精确下一步，并且不出现通用重试文案', () => {
    const { container } = renderPanel({ workflow: projection() });
    const detail = container.querySelector('.project-guide-detail');
    expect(detail).toBeTruthy();
    expect(within(detail as HTMLElement).getByText(/引用的原 owner 字段/)).toBeTruthy();
    expect(within(detail as HTMLElement).getByText('精确的下一步')).toBeTruthy();
    expect(within(detail as HTMLElement).getAllByRole('listitem').length).toBeGreaterThan(0);
    expect(container.textContent).not.toContain('请稍后重试');
  });

  it('被标为阻塞的提示给出具体节点与状态，而不是通用失败', () => {
    const { container, onNavigate } = renderPanel({
      workflow: projection({ selected: ['novel_writing'] }),
      graph: graphFacts([{ id: 'node-1' }], [{ id: 'edge-1' }], [{ node_id: 'node-1', state: 'STALE' }]),
      timeline: timelineFacts(1, 1),
    });
    const blocked = container.querySelector('[data-guide-code="BLOCKED_SOURCE_REFERENCE"]');
    expect(blocked).toBeTruthy();
    expect(blocked?.getAttribute('data-guide-sources')).toBe('fact:graph.reference_states.node:node-1');
    expect(container.textContent).toContain('node-1=STALE');
    const button = screen.getByRole('button', { name: '前往既有视图：GRAPH' });
    button.click();
    expect(onNavigate).toHaveBeenCalledWith('GRAPH');
  });

  it('没有 onNavigate 回调时，点击导航按钮不会跳转也不会抛错', () => {
    const { container } = renderPanel({
      workflow: projection({ selected: ['novel_writing'] }),
      graph: graphFacts([{ id: 'node-1' }], [{ id: 'edge-1' }], [{ node_id: 'node-1', state: 'UNAVAILABLE' }]),
      timeline: timelineFacts(1, 1),
    }, false);
    expect(container.querySelector('[data-guide-code="BLOCKED_SOURCE_REFERENCE"]')).toBeTruthy();
    // 按钮只声明它想去哪个**既有**视图；没有回调时它什么也不会发生。
    const button = screen.getByRole('button', { name: '前往既有视图：GRAPH' });
    expect(() => button.click()).not.toThrow();
    expect(window.location.pathname).toBe('/');
  });

  it('部分不可读时显式列出缺失的阅读面', () => {
    const { container } = renderPanel({ tasks: undefined, assets: undefined });
    expect(stateOf(container)).toBe('READY');
    expect(screen.getByText(/部分原 owner 阅读面不可读/)).toBeTruthy();
  });
});

describe('ProjectGuidePanel：青简什么都不做', () => {
  it('注册永远被拒绝，注册表计数恒为 0，导师永远不可用', () => {
    const registration = registerQingjianAdapter({ adapter_id: 'qingjian', advisory_only: true });
    expect(registration.registered).toBe(false);
    if (!registration.registered) {
      expect(registration.code).toBe(GUIDE_CODES.qingjianUnavailable);
      expect(registration.message).toContain('没有注册任何导师适配器');
    }
    expect(qingjianAdapterCount()).toBe(0);
    expect(qingjianMentorAvailable()).toBe(false);
    expect(QINGJIAN_EXTENSION.available).toBe(false);
  });

  it('界面不显示任何青简内容，也不渲染导师节点', () => {
    const { container } = renderPanel();
    expect(screen.queryByText(/已连接青简/)).toBeNull();
    expect(container.textContent).not.toContain('青简');
    expect(container.textContent).not.toContain('导师建议');
    // 扩展点在 DOM 里没有任何节点（不注册、不渲染、不报告连接）。
    expect(container.querySelector('[data-guide-mentor]')).toBeNull();
    expect(container.querySelectorAll('[class*="qingjian"]').length).toBe(0);
  });

  it('扩展点没有连接状态字段（因此无法被误报为已连接）', () => {
    expect(Object.keys(QINGJIAN_EXTENSION).sort()).toEqual(['available', 'message', 'reason', 'slot']);
    expect(QINGJIAN_EXTENSION).not.toHaveProperty('connected');
  });
});

describe('ProjectGuidePanel：只描述当前具备的能力', () => {
  it('明确声明不包含 Windows 安装、GPU 与重型渲染承诺', () => {
    renderPanel();
    expect(screen.getByText(GUIDE_NOTICES.capabilityBoundary)).toBeTruthy();
    expect(screen.getByText(GUIDE_NOTICES.everyHintCitesOwner)).toBeTruthy();
  });

  it('确实没有需要处理的条目时状态是 EMPTY，并说明这不是"被拒绝"', () => {
    const reviewed = Object.fromEntries(
      ['director', 'storyboard', 'image', 'video', 'audio', 'timeline', 'asset'].map(id => [id, { status: 'REVIEWED' as const }]),
    );
    const { container } = renderPanel({
      workflow: projection({ selected: ['novel_writing'], override: reviewed }),
      tasks: tasksProjection([{ id: 'task-1', status: 'COMPLETED', progress: { completed: 1, total: 1, unit: 'node' } }]),
      inbox: inboxProjection(),
      assets: assetRows([{ id: 'asset-1', media_kind: 'image' }]),
      graph: graphFacts([{ id: 'node-1' }], [{ id: 'edge-1' }], [{ node_id: 'node-1', state: 'CURRENT' }]),
      timeline: timelineFacts(1, 1),
      facts: { storyboard: storyboardReceipt(1, true) },
    });
    expect(stateOf(container)).toBe('EMPTY');
    expect(screen.getByText('没有需要处理的项目条目')).toBeTruthy();
    expect(screen.getByText(GUIDE_NOTICES.emptyIsNotDenied)).toBeTruthy();
    expect(container.querySelector('.project-guide-hint')).toBeNull();
    // EMPTY 与 DENIED 是不同状态：这里没有任何"无权读取"的字样。
    expect(screen.queryByText(/无权读取/)).toBeNull();
  });
});
