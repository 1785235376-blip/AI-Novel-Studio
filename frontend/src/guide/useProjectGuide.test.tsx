// @vitest-environment jsdom
/**
 * UX-08 控制器测试：显式状态机、`EMPTY ≠ FAILED ≠ DENIED`、以及"不做 I/O"。
 *
 * 这些用例只调用控制器（没有面板），因此证明的是控制器本身的性质：
 * 它不做任何读取，只消费 props 里已经加载好的投影。
 */
import { cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useProjectGuide, type UseProjectGuideProps } from './useProjectGuide';
import { GUIDE_CODES, GUIDE_NOTICES, GUIDE_VIEW_NAMES } from './projectGuideTypes';
import {
  IDENTITY, PROJECT, assetRows, graphFacts, inboxProjection, projection, storyboardReceipt,
  tasksProjection, timelineFacts,
} from './projectGuideFixtures';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

/** 全部来源可读、且每一项都处于"需要处理"的状态：意图未选、素材为空、时间线为空。 */
const blockedProject = (override: Partial<UseProjectGuideProps> = {}): UseProjectGuideProps => ({
  projectId: PROJECT, identity: IDENTITY, active: true, denied: false,
  workflow: projection(), tasks: tasksProjection(), inbox: inboxProjection(),
  assets: assetRows([]), graph: graphFacts(), timeline: timelineFacts(0, 0), ...override,
});

const hook = (props: UseProjectGuideProps) => renderHook(() => useProjectGuide(props));

describe('useProjectGuide：显式状态机', () => {
  it('未激活时是 IDLE，并且不产生任何提示', () => {
    const { result } = hook(blockedProject({ active: false }));
    expect(result.current.state).toBe('IDLE');
    expect(result.current.hints).toHaveLength(0);
    expect(result.current.notice).toContain('不读取、不轮询');
  });

  it('pending 时是 LOADING，提示为空（提示助手自己不会发起读取）', () => {
    const { result } = hook(blockedProject({ pending: true }));
    expect(result.current.state).toBe('LOADING');
    expect(result.current.hints).toHaveLength(0);
    expect(result.current.notice).toContain('不会发起读取');
  });

  it('读到事实且有需要处理的条目时是 READY', () => {
    const { result } = hook(blockedProject());
    expect(result.current.state).toBe('READY');
    expect(result.current.hints.length).toBeGreaterThan(0);
    expect(result.current.hasFacts).toBe(true);
    expect(result.current.notice).toBe('');
  });

  it('denied 时是 DENIED：既不是 EMPTY 也不是 FAILED，且清空了所有提示', () => {
    const { result } = hook(blockedProject({ denied: true }));
    expect(result.current.state).toBe('DENIED');
    expect(result.current.state).not.toBe('EMPTY');
    expect(result.current.hints).toHaveLength(0);
    expect(result.current.notice).toBe(GUIDE_NOTICES.deniedIsNotUnknownProject);
  });

  it('denied 优先于任何已读到的事实', () => {
    const { result } = hook(blockedProject({ denied: true, pending: false }));
    expect(result.current.state).toBe('DENIED');
    expect(result.current.hasFacts).toBe(true); // 事实仍然被解码出来，但状态是拒绝。
    expect(result.current.refusal?.reason).toContain('被拒绝');
  });

  it('一个来源都读不到时是 FAILED，并且明说"事实不可读"', () => {
    const { result } = hook({ projectId: PROJECT, identity: IDENTITY, active: true, denied: false });
    expect(result.current.state).toBe('FAILED');
    expect(result.current.hasFacts).toBe(false);
    expect(result.current.notice).toBe(GUIDE_NOTICES.unreadable);
    expect(result.current.refusal?.code).toBe(GUIDE_CODES.factsUnreadable);
    expect(result.current.unreadableSources.length).toBe(10);
  });

  it('具名投影不是对象时是 FAILED（fail-closed），不是"空项目"', () => {
    const { result } = hook(blockedProject({ workflow: 'not-an-object' }));
    expect(result.current.state).toBe('FAILED');
    expect(result.current.refusal?.code).toBe(GUIDE_CODES.factsInvalid);
    expect(result.current.state).not.toBe('EMPTY');
  });

  it('EMPTY 与被拒绝是不同状态：EMPTY 时没有任何"无权读取"的字样', () => {
    const reviewed = Object.fromEntries(
      ['director', 'storyboard', 'image', 'video', 'audio', 'timeline', 'asset'].map(id => [id, { status: 'REVIEWED' as const }]),
    );
    const { result } = hook({
      projectId: PROJECT, identity: IDENTITY, active: true, denied: false,
      workflow: projection({ selected: ['novel_writing'], override: reviewed }),
      tasks: tasksProjection([{ id: 'task-1', status: 'COMPLETED', progress: { completed: 1, total: 1, unit: 'node' } }]),
      inbox: inboxProjection(), assets: assetRows([{ id: 'asset-1', media_kind: 'image' }]),
      graph: graphFacts([{ id: 'node-1' }], [{ id: 'edge-1' }], [{ node_id: 'node-1', state: 'CURRENT' }]),
      timeline: timelineFacts(1, 1), storyboard: storyboardReceipt(1, true),
    });
    expect(result.current.state).toBe('EMPTY');
    expect(result.current.notice).toBe(GUIDE_NOTICES.emptyIsNotDenied);
    expect(result.current.notice).not.toContain('无权');
    expect(result.current.hints).toHaveLength(0);
    expect(result.current.hasFacts).toBe(true);
  });
});

describe('useProjectGuide：不做 I/O', () => {
  it('渲染控制器不会调用 fetch / XHR / 定时器', () => {
    const fetchSpy = vi.fn(() => Promise.resolve(new Response('{}')));
    vi.stubGlobal('fetch', fetchSpy);
    const openSpy = vi.fn();
    vi.stubGlobal('XMLHttpRequest', class { open = openSpy; send = vi.fn(); setRequestHeader = vi.fn(); });
    const interval = vi.spyOn(globalThis, 'setInterval');
    const timeout = vi.spyOn(globalThis, 'setTimeout');

    const { rerender, unmount } = hook(blockedProject());
    rerender();
    unmount();

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(openSpy).not.toHaveBeenCalled();
    expect(interval).not.toHaveBeenCalled();
    expect(timeout).not.toHaveBeenCalled();
  });

  it('导航只转发既有视图名，且必须有回调', () => {
    const onNavigate = vi.fn();
    const { result } = hook(blockedProject({ onNavigate }));
    for (const view of GUIDE_VIEW_NAMES) expect(result.current.navigate(view)).toBe(true);
    expect(onNavigate).toHaveBeenCalledTimes(GUIDE_VIEW_NAMES.length);
    expect(onNavigate).toHaveBeenLastCalledWith('STORYBOARD');
    // 运行时的意外取值被拒绝，不会被转发。
    expect(result.current.navigate('NOT_A_VIEW' as never)).toBe(false);
    expect(onNavigate).toHaveBeenCalledTimes(GUIDE_VIEW_NAMES.length);
  });

  it('没有回调时导航返回 false，绝不自己跳转', () => {
    const { result } = hook(blockedProject());
    expect(result.current.navigate('PRODUCTION')).toBe(false);
    expect(window.location.pathname).toBe('/');
  });

  it('暴露的青简扩展点永远不可用', () => {
    const { result } = hook(blockedProject());
    expect(result.current.mentor.available).toBe(false);
    expect(result.current.mentor.reason).toBe(GUIDE_CODES.qingjianUnavailable);
  });

  it('同一批事实重复渲染得到同一组提示（确定性）', () => {
    const { result, rerender } = hook(blockedProject());
    const first = result.current.hints.map(entry => entry.code);
    rerender();
    expect(result.current.hints.map(entry => entry.code)).toEqual(first);
  });
});
