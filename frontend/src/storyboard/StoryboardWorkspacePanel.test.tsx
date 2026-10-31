// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { StoryboardWorkspacePanel, type StoryboardWorkspacePanelProps } from './StoryboardWorkspacePanel';
import { STORYBOARD_DRAFT_NOTICE } from './storyboardOps';
import {
  copy, directorAdvice, directorDocument, directorProposal, receiptWithDirectorNotes, receiptWithVideo,
  storyboardReceipt,
} from './storyboardWorkspaceFixtures.testFixture';

/**
 * 这些测试断言的是**边界**，不是外观：
 *  - 读失败不等于"暂无分镜"；
 *  - 独立分镜可以在没有小说/导演文档的情况下被编辑；
 *  - "送往…"只形成草稿，永不执行目标模块；
 *  - 陈旧/损坏的引用被如实报告，不会被悄悄丢掉；
 *  - 跨模块动作只发回调，不自己导航。
 */

const DOCUMENT_ID = '89a4c387-9ff4-4b5b-919f-6755259868d5';

type Handlers = {
  storyboard?: () => Promise<unknown>;
  advice?: () => Promise<unknown>;
  document?: () => Promise<unknown>;
  proposals?: () => Promise<unknown>;
};

function transportFor(handlers: Handlers = {}) {
  const json = vi.fn(async (url: string, _method?: string) => {
    if (url.endsWith('/storyboard')) return (handlers.storyboard ?? (async () => copy(storyboardReceipt())))();
    if (url.endsWith('/director-advice')) return (handlers.advice ?? (async () => copy(directorAdvice())))();
    if (url.endsWith('/director-proposals')) return (handlers.proposals ?? (async () => ({ items: [] })))();
    if (url.includes('/documents/')) return (handlers.document ?? (async () => copy(directorDocument())))();
    return {};
  });
  return { transport: { json } as unknown as StudioGraphTransport, json };
}

type Gate = <T>(work: () => Promise<T>) => Promise<T>;

/** `vi.fn` 无法表达多态签名，所以这里把调用记录与多态闸门分开保存。 */
function gate() {
  const calls: (() => Promise<unknown>)[] = [];
  const fn = vi.fn(async (work: () => Promise<unknown>) => { calls.push(work); return work(); });
  return { calls, fn, gate: fn as unknown as Gate };
}

function mount(options: {
  handlers?: Handlers;
  selectedShotId?: string;
  busy?: boolean;
  denied?: boolean;
  active?: boolean;
  isCurrent?: () => boolean;
  onSendTo?: StoryboardWorkspacePanelProps['onSendTo'];
  onSelectShot?: (shotId: string) => void;
} = {}) {
  const { transport, json } = transportFor(options.handlers);
  const readGate = gate(), mutateGate = gate();
  const read = readGate.gate, mutate = mutateGate.gate;
  const onSendTo = options.onSendTo ?? vi.fn();
  const onUnavailable = vi.fn();
  const props: StoryboardWorkspacePanelProps = {
    projectId: 'project-1', transport, identity: `project-1|${DOCUMENT_ID}`,
    active: options.active ?? true, denied: options.denied ?? false, busy: options.busy ?? false,
    isCurrent: options.isCurrent ?? (() => true), read, mutate,
    selectedShotId: options.selectedShotId, onSelectShot: options.onSelectShot,
    onSendTo, onUnavailable,
  };
  let select: (shotId: string) => void = () => undefined;
  function Harness() {
    const [selected, setSelected] = useState<string | undefined>(options.selectedShotId);
    select = setSelected;
    return <StoryboardWorkspacePanel {...props} selectedShotId={selected}
      onSelectShot={shotId => { setSelected(shotId); props.onSelectShot?.(shotId); }} />;
  }
  const view = render(<Harness />);
  return { ...view, json, read: readGate.fn, mutate: mutateGate.fn, onSendTo, onUnavailable, props, select };
}

const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('StoryboardWorkspacePanel 读取分镜', () => {
  it('挂载后按身份读取一次分镜，并且只做读操作', async () => {
    const state = mount();
    await waitFor(() => expect(screen.getByText('镜头清单')).toBeTruthy());
    await waitFor(() => expect(state.json).toHaveBeenCalledTimes(1));
    expect(state.json.mock.calls[0][1]).toBe('GET');
    expect(state.read).toHaveBeenCalledTimes(1);
    expect(state.mutate).not.toHaveBeenCalled();
    expect(screen.getByText('SHOT 1')).toBeTruthy();
    expect(screen.getByText('SHOT 2')).toBeTruthy();
    expect(screen.getByText('原分镜已批准')).toBeTruthy();
  });

  it('独立分镜不需要小说或导演文档：没有上游来源时一个额外请求都不发', async () => {
    const state = mount();
    await waitFor(() => expect(state.json).toHaveBeenCalledTimes(1));
    const urls = state.json.mock.calls.map(call => call[0] as string);
    expect(urls).toHaveLength(1);
    expect(urls[0].endsWith('/storyboard')).toBe(true);
    expect(urls.some(url => url.includes('/director-advice'))).toBe(false);
    expect(urls.some(url => url.includes('/director-proposals'))).toBe(false);
    expect(urls.some(url => url.includes('/documents/') && !url.endsWith('/storyboard'))).toBe(false);
    expect(screen.queryByText('上游导演文档（只读）')).toBeNull();
  });

  it('读失败绝不显示"暂无分镜"：FAILED 与 EMPTY 是两个状态', async () => {
    const state = mount({ handlers: { storyboard: async () => { throw new Error('network down'); } } });
    await waitFor(() => expect(screen.getAllByText(/分镜读取失败/).length).toBeGreaterThan(0));
    expect(screen.queryByText('这份分镜还没有镜头')).toBeNull();
    expect(screen.getAllByText(/失败不是"暂无分镜"/).length).toBeGreaterThan(0);
    expect(button('重新读取原分镜')).toBeTruthy();
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it('真的空分镜才显示 EMPTY，并说明原文档确实没有镜头', async () => {
    const state = mount({
      handlers: { storyboard: async () => ({ ...copy(storyboardReceipt()), shots: [] }) },
    });
    await waitFor(() => expect(screen.getByText('这份分镜还没有镜头')).toBeTruthy());
    expect(state.json).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/分镜读取失败/)).toBeNull();
  });

  it('拒绝（DENIED）不是失败也不是空', async () => {
    const state = mount({ denied: true });
    expect(screen.getByText(/当前会话被拒绝读取这份分镜/)).toBeTruthy();
    expect(screen.getByText('当前会话无权读取这份分镜。请核对身份与项目范围后重新打开工作区。')).toBeTruthy();
    expect(state.json).not.toHaveBeenCalled();
  });

  it('身份变化会重新读取，并且旧身份的结果不会残留', async () => {
    const state = mount();
    await waitFor(() => expect(state.json).toHaveBeenCalledTimes(1));
    fireEvent.click(button('重新读取'));
    await waitFor(() => expect(state.json).toHaveBeenCalledTimes(2));
    expect(state.json.mock.calls[1][0]).toBe(state.json.mock.calls[0][0]);
  });
});

describe('拖动的结果：稳定身份与显示序号分开', () => {
  it('上移/下移只改显示序号，身份不变，并明确标成"尚未保存"', async () => {
    const state = mount({ handlers: { storyboard: async () => copy(receiptWithVideo()) } });
    await waitFor(() => expect(screen.getByText('镜头清单')).toBeTruthy());
    // 还没有移动时没有草稿，也没有任何"未保存"提示。
    expect(screen.queryByText('显示顺序草稿尚未保存')).toBeNull();
    fireEvent.click(screen.getAllByRole('button', { name: '移到最后' })[0]);
    await waitFor(() => expect(screen.getAllByText(/显示序号已变/).length).toBeGreaterThan(0));
    expect(screen.getByText('显示顺序草稿尚未保存')).toBeTruthy();
    // 身份仍然是原文档里的身份；只是显示序号前进了。
    const identity = screen.getAllByText(/身份 shot-/);
    expect(identity.length).toBeGreaterThan(0);
    expect(screen.getAllByText(STORYBOARD_DRAFT_NOTICE).length).toBeGreaterThan(0);
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it('放弃顺序草稿恢复原顺序，且没有写入任何内容', async () => {
    const state = mount();
    await waitFor(() => expect(screen.getByText('镜头清单')).toBeTruthy());
    fireEvent.click(screen.getAllByRole('button', { name: '移到最后' })[0]);
    await waitFor(() => expect(screen.getByText('显示顺序草稿尚未保存')).toBeTruthy());
    fireEvent.click(button('放弃顺序草稿，恢复原文档顺序'));
    await waitFor(() => expect(screen.queryByText('显示顺序草稿尚未保存')).toBeNull());
    expect(state.mutate).not.toHaveBeenCalled();
  });
});

describe('送往… 只形成草稿，永不执行目标模块', () => {
  it('形成草稿并按冻结回调形状交给调用方，同时不写、不导航、不调模型', async () => {
    const onSendTo = vi.fn();
    const state = mount({ handlers: { storyboard: async () => copy(receiptWithVideo()) }, onSendTo });
    await waitFor(() => expect(screen.getByText('送往…')).toBeTruthy());
    fireEvent.click(button('形成 图片候选 草稿'));
    await waitFor(() => expect(screen.getByText(/这张草稿会引用的确切原版本/)).toBeTruthy());
    expect(screen.getAllByText(STORYBOARD_DRAFT_NOTICE).length).toBeGreaterThan(0);
    // 草稿里只有原版本，没有请求标识或任务标识。
    expect(screen.queryByText(/request_id/)).toBeNull();
    fireEvent.click(button('交给调用方处理这张草稿（不执行）'));
    await waitFor(() => expect(onSendTo).toHaveBeenCalledTimes(1));
    const [target, draft] = onSendTo.mock.calls[0] as [string, Record<string, unknown>];
    expect(target).toBe('IMAGE');
    expect(draft).toEqual({
      shot_id: 'shot-1', shot_version: 1, document_version: 4,
      source_digest: '6c36bfa51abaaa1bbfb2a671e39f4c5efbbba3fe67032805a4128cdcc6eaa471',
    });
    expect(Object.keys(draft).sort()).toEqual(['document_version', 'shot_id', 'shot_version', 'source_digest']);
    expect(state.mutate).not.toHaveBeenCalled();
    // 本工作区没有执行目标模块，也没有离开当前画面。
    expect(screen.getByText(/草稿已交给调用方/)).toBeTruthy();
    expect(screen.getByText('镜头清单')).toBeTruthy();
  });

  it('没有正式图片的镜头不会形成视频/时间线草稿，并如实说明原因', async () => {
    const unbound = storyboardReceipt({
      shots: row => { row.image_asset = null; },
    });
    mount({ handlers: { storyboard: async () => copy(unbound) } });
    await waitFor(() => expect(screen.getByText('送往…')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('视频候选（VIDEO）'));
    fireEvent.click(button('形成 视频候选 草稿'));
    await waitFor(() => expect(screen.getByText(/还没有绑定正式图片/)).toBeTruthy());
    expect(screen.queryByText(/这张草稿会引用的确切原版本/)).toBeNull();
  });

  it('已绑定视频时草稿列出视频任务针与来源镜头版本', async () => {
    const state = mount({ handlers: { storyboard: async () => copy(receiptWithVideo()) } });
    await waitFor(() => expect(screen.getByText('送往…')).toBeTruthy());
    fireEvent.click(screen.getAllByRole('button', { name: /镜头 2/ })[0]);
    fireEvent.click(screen.getByLabelText('视频候选（VIDEO）'));
    fireEvent.click(button('形成 视频候选 草稿'));
    await waitFor(() => expect(screen.getByText(/video-job/)).toBeTruthy());
    expect(state.mutate).not.toHaveBeenCalled();
  });
});

describe('陈旧/损坏的引用被如实报告', () => {
  it('上游导演文档版本变化时报告证据（而不是假设一致）', async () => {
    const state = mount({
      handlers: {
        storyboard: async () => copy(storyboardReceipt({
          directorSource: { id: 'director-doc', version: 1, digest: 'c'.repeat(64) },
        })),
        document: async () => copy(directorDocument({ version: 2 })),
      },
    });
    await waitFor(() => expect(screen.getByText('镜头清单')).toBeTruthy());
    await waitFor(() => expect(screen.getAllByText('DIRECTOR_SOURCE_CHANGED').length).toBeGreaterThan(0));
    expect(screen.getAllByText(/已经不是原分镜记下的那一版/).length).toBeGreaterThan(0);
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it('上游导演文档读不到时也如实报告，而不是当作没问题', async () => {
    mount({
      handlers: {
        storyboard: async () => copy(storyboardReceipt({
          directorSource: { id: 'director-doc', version: 2, digest: 'c'.repeat(64) },
        })),
        document: async () => { throw new Error('unavailable'); },
      },
    });
    await waitFor(() => expect(screen.getByText('镜头清单')).toBeTruthy());
    await waitFor(() => expect(screen.getAllByText('DIRECTOR_SOURCE_UNAVAILABLE').length).toBeGreaterThan(0));
    expect(screen.getAllByText(/目前读不到/).length).toBeGreaterThan(0);
  });

  it('没有证据时不给任何"连续性没问题"的结论', async () => {
    mount();
    await waitFor(() => expect(screen.getByText(/没有读到有证据的来源不一致/)).toBeTruthy());
    expect(screen.getByText(/这不是"连续性没问题"的保证/)).toBeTruthy();
  });

  it('参考比较只在有绑定素材时给出结果，并且引用原版本', async () => {
    mount({ handlers: { storyboard: async () => copy(receiptWithVideo()) } });
    await waitFor(() => expect(screen.getByText('镜头详情 · SHOT 1')).toBeTruthy());
    fireEvent.click(button('只读比较绑定素材与镜头版本'));
    await waitFor(() => expect(screen.getByText(/与镜头当前版本一致/)).toBeTruthy());
    expect(screen.getAllByText(/68bc2dce-60c3-4285-b8c4-aea92944588f/).length).toBeGreaterThan(0);
  });
});

describe('导演目标：可编辑的目标与 AI 建议分区显示', () => {
  it('独立分镜没有上游导演文档时，目标区明说没有读到，不编造', async () => {
    mount();
    await waitFor(() => expect(screen.getByText('导演目标')).toBeTruthy());
    expect(screen.getByText(/还没有读到导演目标/)).toBeTruthy();
    expect(screen.getByText(/这些是原 owner 的 `director-proposals` 记录/)).toBeTruthy();
  });

  it('有上游导演文档时读出已采用目标，并把待审建议单独列出', async () => {
    const source = { id: 'director-doc', version: 2, digest: 'c'.repeat(64) };
    const state = mount({
      handlers: {
        storyboard: async () => copy(storyboardReceipt({ directorSource: source })),
        document: async () => copy(directorDocument({ source_documents: { 'screenplay-doc': { version: 3, digest: 'b'.repeat(64) } } })),
        proposals: async () => ({ items: [copy(directorProposal())] }),
      },
    });
    await waitFor(() => expect(screen.getByText('上游导演文档（只读）')).toBeTruthy());
    expect(state.json.mock.calls.some(call => (call[0] as string).includes('/director-proposals'))).toBe(true);
    expect(screen.getByText('目标（1 条，来自原文档）')).toBeTruthy();
    expect(screen.getByText('先核对场景目的')).toBeTruthy();
    expect(screen.getByText('NEEDS_REVIEW')).toBeTruthy();
    expect(screen.getByText(/质量核验：HUMAN_REVIEW_REQUIRED/)).toBeTruthy();
    expect(screen.getByText('模型调用：未调用模型')).toBeTruthy();
    expect(screen.getByText(/不会因此获得对其它模块的核心权威/)).toBeTruthy();
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it('编辑目标只形成本地草稿：不写原文档、不覆盖已批准的下游结果', async () => {
    const source = { id: 'director-doc', version: 2, digest: 'c'.repeat(64) };
    const state = mount({
      handlers: {
        storyboard: async () => copy(storyboardReceipt({ directorSource: source })),
        document: async () => copy(directorDocument()),
      },
    });
    await waitFor(() => expect(screen.getByText('目标（1 条，来自原文档）')).toBeTruthy());
    fireEvent.click(button('编辑这条目标（本地草稿）'));
    const duration = screen.getByLabelText(/时长（秒，1–600）/) as HTMLInputElement;
    fireEvent.change(duration, { target: { value: '12' } });
    fireEvent.click(button('采用为本地草稿（不写原文档）'));
    await waitFor(() => expect(screen.getByText(/已形成目标草稿（本地）：note-1/)).toBeTruthy());
    expect(screen.getByText(/原导演文档没有被写入，也没有自动覆盖已批准的下游结果/)).toBeTruthy();
    expect(state.mutate).not.toHaveBeenCalled();
    // 没有任何写请求离开这个视图。
    expect(state.json.mock.calls.every(call => call[1] === 'GET')).toBe(true);
  });

  it('越界的目标草稿被本地拒绝，界面保持编辑状态', async () => {
    const source = { id: 'director-doc', version: 2, digest: 'c'.repeat(64) };
    mount({
      handlers: {
        storyboard: async () => copy(storyboardReceipt({ directorSource: source })),
        document: async () => copy(directorDocument()),
      },
    });
    await waitFor(() => expect(screen.getByText('目标（1 条，来自原文档）')).toBeTruthy());
    fireEvent.click(button('编辑这条目标（本地草稿）'));
    fireEvent.change(screen.getByLabelText(/时长（秒，1–600）/), { target: { value: '1000' } });
    fireEvent.click(button('采用为本地草稿（不写原文档）'));
    expect(screen.queryByText(/已形成目标草稿/)).toBeNull();
    expect(screen.getByText('目标草稿（仅本地）')).toBeTruthy();
  });

  it('镜头与导演目标的继承/覆写只读对比出现在两层界面上', async () => {
    const source = { id: 'director-doc', version: 2, digest: 'c'.repeat(64) };
    mount({
      handlers: {
        storyboard: async () => copy(receiptWithDirectorNotesReceipt(source)),
        document: async () => copy(directorDocument()),
      },
    });
    await waitFor(() => expect(screen.getByText('导演目标 vs 镜头级覆写')).toBeTruthy());
    expect(screen.getAllByText(/继承来源：note-1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/修改导演目标不会改写已经批准的下游结果/).length).toBeGreaterThan(0);
    expect(screen.getByText(/结论：修改导演目标不会自动覆盖已经批准的下游结果。/)).toBeTruthy();
  });
});

/** `receiptWithDirectorNotes` 加上上游来源，让导演文档真的会被读取。 */
function receiptWithDirectorNotesReceipt(source: { id: string; version: number; digest: string }) {
  const base = receiptWithDirectorNotes();
  return { ...base, director_sources: [source] };
}

describe('跨模块动作回到原工作位置', () => {
  it('选择镜头只发 onSelectShot，不导航', async () => {
    const onSelectShot = vi.fn();
    mount({ onSelectShot });
    await waitFor(() => expect(screen.getByText('镜头清单')).toBeTruthy());
    fireEvent.click(screen.getAllByRole('button', { name: /镜头 2/ })[0]);
    expect(onSelectShot).toHaveBeenCalledWith('shot-2');
    expect(screen.getByText('镜头详情 · SHOT 2')).toBeTruthy();
  });

  it('不可用的目标模块只发 onUnavailable，不改变当前视图', async () => {
    const state = mount({ handlers: { storyboard: async () => copy(receiptWithVideo()) } });
    await waitFor(() => expect(screen.getByText('送往…')).toBeTruthy());
    fireEvent.click(button('目标模块不可用'));
    expect(state.onUnavailable).toHaveBeenCalledTimes(1);
    expect(screen.getByText('镜头清单')).toBeTruthy();
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it('不活跃时一个请求都不发', async () => {
    const state = mount({ active: false });
    expect(state.json).not.toHaveBeenCalled();
    expect(state.read).not.toHaveBeenCalled();
    expect(screen.getByLabelText('分镜工作区').getAttribute('data-active')).toBe('false');
  });

  it('忙碌（busy）时读取被挡住，也没有任何写动作', async () => {
    const state = mount({ busy: true, handlers: { storyboard: async () => copy(receiptWithVideo()) } });
    await act(async () => { await Promise.resolve(); });
    expect(state.json).not.toHaveBeenCalled();
    expect(state.mutate).not.toHaveBeenCalled();
    expect(state.read).not.toHaveBeenCalled();
  });
});
