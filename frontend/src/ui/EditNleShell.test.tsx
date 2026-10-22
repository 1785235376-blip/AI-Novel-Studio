// @vitest-environment jsdom
/**
 * [HERMIA-FE-20261022 W-P0-06 / W-UX-09] EDIT shell density + honest readonly / writable-path discovery.
 */
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {EditNleShell, EditNleMediaRail, EditNleInspector, EditNleReadonlyHonesty, demoEditTimeline} from './EditNleShell';
import {NovelWriterDock} from './NovelWriterDock';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement;
afterEach(() => host?.remove());

describe('EditNleShell W-P0-06', () => {
  it('renders hero timeline, monitor, toolbar, zoom — not a toy strip', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const timeline = demoEditTimeline('novel-demo');
    const onPlayhead = vi.fn();
    const onSelect = vi.fn();
    act(() => root.render(
      <EditNleShell
        novelId="novel-demo"
        timeline={timeline}
        playheadMs={1200}
        onPlayhead={onPlayhead}
        selectedClipIds={['c-v1']}
        onSelectClips={onSelect}
      />,
    ));
    expect(host.querySelector('.edit-nle-shell__hero')).toBeTruthy();
    expect(host.querySelector('.edit-nle-shell__monitor')).toBeTruthy();
    expect(host.querySelector('[aria-label="剪辑工具条"]')).toBeTruthy();
    expect(host.querySelector('[data-monitor="source"]')).toBeTruthy();
    expect(host.querySelector('[data-monitor="program"]')).toBeTruthy();
    expect(host.querySelector('[data-edit-density="w-ux-05"]')).toBeTruthy();
    expect(host.textContent).toMatch(/多轨|源监视器|节目监视器/);
    expect(host.textContent).toMatch(/放大|缩小/);
    expect(host.textContent).toMatch(/入点|出点|吸附/);
    expect(host.querySelector('[data-timeline-hero="true"]')).toBeTruthy();
    expect(timeline.tracks.length).toBeGreaterThanOrEqual(3);
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.getAttribute('data-mark') === 'in')?.click();
      [...host.querySelectorAll('button')].find(b => b.getAttribute('data-snap-toggle') === 'true')?.click();
    });
    expect(host.textContent).toMatch(/In 1200|吸附关/);
    act(() => root.unmount());
  });

  it('media rail and inspector avoid empty void', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const timeline = demoEditTimeline('n1');
    act(() => root.render(
      <>
        <EditNleMediaRail novelId="n1" />
        <EditNleInspector novelId="n1" timeline={timeline} selectedClipIds={[]} playheadMs={0} editable={false} />
      </>,
    ));
    expect(host.textContent).toContain('媒体池');
    expect(host.textContent).toContain('避免空白占位');
    expect(host.textContent).toContain('引用');
    expect(host.querySelector('[data-drag-semantics="reference"]')).toBeTruthy();
    expect(host.textContent).not.toMatch(/^\s*$/);
    act(() => root.unmount());
  });
});


describe('EditNleShell W-UX-09 honest readonly + writable path', () => {
  it('marks demo-readonly shell and exposes IndependentStudio write-path discovery', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const timeline = demoEditTimeline('novel-demo');
    act(() => root.render(
      <EditNleShell
        novelId="novel-demo"
        timeline={timeline}
        playheadMs={0}
        onPlayhead={() => {}}
        selectedClipIds={[]}
        onSelectClips={() => {}}
      />,
    ));
    const shell = host.querySelector('.edit-nle-shell');
    expect(shell?.getAttribute('data-edit-shell-mode')).toBe('demo-readonly');
    expect(shell?.getAttribute('data-writable')).toBe('false');
    const honesty = host.querySelector('[data-w-ux="09"]');
    expect(honesty).toBeTruthy();
    expect(honesty?.getAttribute('data-capability-tone')).toBe('neutral');
    expect(honesty?.getAttribute('data-edit-shell-mode')).toBe('demo-readonly');
    expect(host.querySelector('[data-honest-badge="demo-readonly"]')?.textContent).toMatch(/演示/);
    expect(host.querySelector('[data-writable-path="discover"]')).toBeTruthy();
    expect(host.textContent).toMatch(/IndependentStudio|制作操作/);
    expect(host.textContent).toMatch(/StudioTimelineEditor/);
    expect(host.textContent).toMatch(/不会.*trim|不 trim|不可.*trim|不会真实 trim/i);
    expect(host.textContent).not.toMatch(/可写已接通/);
    expect(host.querySelector('[data-honest-badge="demo-readonly"]')).toBeTruthy();
    // honesty copy may mention banned phrases as negation; assert no success tone instead of raw substring ban
    expect(host.querySelector('[data-capability-tone="success"]')).toBeNull();
    expect(host.querySelector('[data-open-writable-nle="true"]')).toBeNull();
    expect(host.querySelector('[data-writable-path-status="guidance-only"]')).toBeTruthy();
    expect(host.querySelector('[data-mark="in"]')?.getAttribute('data-demo-only')).toBe('true');
    act(() => root.unmount());
  });

  it('wires optional onOpenWritablePath without changing default landing', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const open = vi.fn();
    act(() => root.render(
      <EditNleReadonlyHonesty onOpenWritablePath={open} />,
    ));
    const btn = host.querySelector<HTMLButtonElement>('[data-open-writable-nle="true"]');
    expect(btn).toBeTruthy();
    expect(host.querySelector('[data-writable-path-status="guidance-only"]')).toBeNull();
    act(() => { btn!.click(); });
    expect(open).toHaveBeenCalledTimes(1);
    act(() => root.unmount());
  });

  it('media rail and inspector surface writable-path hints', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const timeline = demoEditTimeline('n1');
    act(() => root.render(
      <>
        <EditNleMediaRail novelId="n1" />
        <EditNleInspector novelId="n1" timeline={timeline} selectedClipIds={[]} playheadMs={0} editable={false} />
      </>,
    ));
    expect(host.querySelector('[data-writable-path="rail-hint"]')).toBeTruthy();
    expect(host.querySelector('[data-writable-path="inspector-hint"]')).toBeTruthy();
    expect(host.textContent).toMatch(/制作操作/);
    expect(host.textContent).toMatch(/StudioTimelineEditor/);
    expect(host.textContent).toMatch(/导出真链路未接通/);
    act(() => root.unmount());
  });
});

describe('NovelWriterDock Lumen §4.4', () => {
  it('always shows primary CTA and useful sections — no empty inspector', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const primary = vi.fn();
    act(() => root.render(
      <NovelWriterDock
        chapterTitle="第一章"
        chapterMeta="第 1 章 · 版本 3"
        saveLabel="已保存"
        primaryCta={{label: '继续写', onClick: primary}}
        secondaryLinks={[{label: '生成草稿', onClick: () => {}}]}
        outlineItems={[{id: 'c1', label: '第 1 章 · 开篇', hint: '当前正在写'}]}
        castItems={[]}
        ai={<p>AI 写作面板占位</p>}
      />,
    ));
    expect(host.querySelector('.novel-writer-dock__primary')?.textContent).toBe('继续写');
    expect(host.querySelector('[data-primary-cta="true"]')).toBeTruthy();
    expect(host.querySelector('[data-a11y-novel-dock="true"]')).toBeTruthy();
    expect(host.textContent).toContain('大纲');
    expect(host.textContent).toContain('AI 写作');
    expect(host.textContent).toContain('角色');
    expect(host.textContent).toContain('状态待核实');
    expect(host.textContent).toContain('AI 写作旁路');
    expect(host.textContent).toContain('工作流编排');
    expect(host.textContent).toContain('生成候选');
    expect(host.querySelector('[data-dual-entry="ai-vs-workflow"]')).toBeTruthy();
    expect(host.querySelector('[data-capability="undetermined"]')).toBeTruthy();
    expect(host.querySelector('[data-capability-tone="success"]')).toBeNull();
    act(() => {
      host.querySelector<HTMLButtonElement>('.novel-writer-dock__primary')!.click();
    });
    expect(primary).toHaveBeenCalled();
    act(() => root.unmount());
  });

  it('N-UX-08 exposes three CTA kinds via data-cta-kind', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const cases = [
      {kind: 'continue', label: '继续写'},
      {kind: 'adopt', label: '采用草稿'},
      {kind: 'continuity', label: '看一致性'},
    ] as const;
    for (const c of cases) {
      act(() => root.render(
        <NovelWriterDock
          chapterTitle="第一章"
          chapterMeta="第 1 章"
          primaryCta={{label: c.label, kind: c.kind, onClick: () => {}}}
          outlineItems={[]}
          castItems={[]}
          ai={<p>AI</p>}
        />,
      ));
      const btn = host.querySelector<HTMLButtonElement>('[data-primary-cta="true"]');
      expect(btn?.getAttribute('data-cta-kind')).toBe(c.kind);
      expect(btn?.textContent).toBe(c.label);
    }
    act(() => root.unmount());
  });

  it('N-UX-05 exposes first-tier panel links without new FL ids', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const openStory = vi.fn();
    const openCheck = vi.fn();
    const openCreation = vi.fn();
    const openOverview = vi.fn();
    const openHistory = vi.fn();
    const openWorkflow = vi.fn();
    act(() => root.render(
      <NovelWriterDock
        chapterTitle="第一章"
        chapterMeta="第 1 章"
        primaryCta={{label: '继续写', onClick: () => {}}}
        outlineItems={[]}
        castItems={[]}
        onOpenStory={openStory}
        onOpenCheck={openCheck}
        onOpenCreation={openCreation}
        onOpenOverview={openOverview}
        onOpenHistory={openHistory}
        onOpenWorkflow={openWorkflow}
        ai={<p>AI</p>}
      />,
    ));
    expect(host.querySelector('[aria-label="第一梯队面板"]')).toBeTruthy();
    expect(host.querySelector('[data-tier1="story"]')).toBeTruthy();
    expect(host.querySelector('[data-tier1="check"]')).toBeTruthy();
    expect(host.querySelector('[data-tier1="creation"]')).toBeTruthy();
    expect(host.querySelector('[data-tier1="overview"]')).toBeTruthy();
    expect(host.querySelector('[data-tier1="history"]')).toBeTruthy();
    act(() => { host.querySelector<HTMLButtonElement>('[data-tier1="check"]')!.click(); });
    expect(openCheck).toHaveBeenCalled();
    act(() => { host.querySelector<HTMLButtonElement>('[data-open="workflow"]')!.click(); });
    expect(openWorkflow).toHaveBeenCalled();
    expect(host.textContent).toContain('PendingCanon');
    act(() => root.unmount());
  });
});
