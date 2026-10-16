// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { DeliveryCenterPanel, type DeliveryCenterPanelProps } from './DeliveryCenterPanel';
import { DELIVERY_ITEM_BYTES_LIMIT, DELIVERY_PACKAGE_BYTES_LIMIT } from './deliveryTypes';

const PROJECT = 'novel-a';
const JOB = '11111111-1111-4111-8111-111111111111';
const HEX = [...'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789'];
const digest = (seed: string): string => [...(seed.repeat(3) + HEX.join('')).slice(0, 64)]
  .map((character, index) => (/[0-9a-f]/.test(character) ? character : HEX[index % HEX.length])).join('');

type Calls = { url: string; method: string | undefined; body: unknown }[];

function fakeTransport(handler: (url: string, method?: string) => unknown, calls: Calls = []): { transport: StudioGraphTransport; calls: Calls } {
  const transport: StudioGraphTransport = {
    json: async <T,>(url: string, method?: string, body?: unknown): Promise<T> => {
      calls.push({ url, method, body });
      return handler(url, method) as T;
    },
  };
  return { transport, calls };
}

function wireJob(patch: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: JOB, novel_id: PROJECT, format: 'txt', status: 'queued',
    created_at: '2026-10-14T10:00:00Z', updated_at: '2026-10-14T10:00:00Z',
    progress: 0, progress_message: '排队中', retry_of: null, attempt: 1, cancel_requested: false,
    recovery_count: 0, snapshot_id: null, source_versions: {}, captured_at: null,
    missing_resources: [], result: null, error: null,
    ...patch,
  };
}

const grants = (patch: Record<string, unknown> = {}): Record<string, unknown> => ({
  project_id: PROJECT, identity: 'file:colleague', can_export: true,
  item_kinds: ['text', 'screenplay', 'timeline', 'image', 'audio', 'video'],
  formats: ['txt', 'markdown', 'json'], max_item_bytes: DELIVERY_ITEM_BYTES_LIMIT,
  max_package_bytes: DELIVERY_PACKAGE_BYTES_LIMIT, max_items: 500,
  ...patch,
});

function mount(patch: Partial<DeliveryCenterPanelProps> = {}): { calls: Calls; container: HTMLElement } {
  const calls: Calls = [];
  // 默认传输：只回答一页空历史（面板的读取一到就完成），且记录每一次调用。
  const { transport } = fakeTransport(url => (url.startsWith('/api/exports?')
    ? { items: [], next_offset: null } : wireJob()), calls);
  const props: DeliveryCenterPanelProps = {
    projectId: PROJECT, transport, identity: 'file:colleague', active: true, denied: false, busy: false,
    isCurrent: () => true, read: async <T,>(work: () => Promise<T>) => work(),
    mutate: async <T,>(work: () => Promise<T>) => work(),
    items: [], entitlements: grants(), ...patch,
  };
  const { container } = render(<DeliveryCenterPanel {...props} />);
  return { calls, container };
}

afterEach(cleanup);

describe('DeliveryCenterPanel：被拒绝的读取是 DENIED，不是 EMPTY', () => {
  it('403 的读取显示无权限与该码文案，绝不显示"没有记录"', async () => {
    const calls: Calls = [];
    const transport: StudioGraphTransport = {
      json: async <T,>(url: string, method?: string): Promise<T> => {
        calls.push({ url, method, body: undefined });
        throw new ApiError({ status: 403, code: 'PERMISSION_DENIED', message: 'no' });
      },
    };
    const onUnavailable = vi.fn();
    mount({ transport, onUnavailable });
    await waitFor(() => expect(screen.getByText('没有读取导出回执的权限')).toBeTruthy());
    expect(screen.queryByText('还没有导出回执')).toBeNull();
    expect(screen.queryByText('还没有读取到回执')).toBeNull();
    expect(screen.getAllByText('无权限').length).toBeGreaterThan(0);
    expect(screen.getByText(/PERMISSION_DENIED/)).toBeTruthy();
    expect(onUnavailable).toHaveBeenCalled();
    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe('GET');
  });

  it('读成功且真的没有内容时才是"没有记录"', async () => {
    const { calls } = mount({ receipts: { items: [], next_offset: null } });
    await waitFor(() => expect(screen.getByText('没有记录')).toBeTruthy());
    expect(screen.getByText('还没有导出回执')).toBeTruthy();
    expect(screen.queryByText('没有读取导出回执的权限')).toBeNull();
    expect(calls.every(call => call.method === 'GET')).toBe(true);
  });

  it('empty 与 denied 不会互相冒充：denied 挂载时一次请求都不发', async () => {
    const { calls } = mount({ denied: true, receipts: { items: [], next_offset: null } });
    expect(screen.getAllByText('无权限').length).toBeGreaterThan(0);
    expect(screen.queryByText('还没有导出回执')).toBeNull();
    await Promise.resolve();
    expect(calls).toHaveLength(0);
  });
});

describe('DeliveryCenterPanel：未知/未终结的回执永远不是成功', () => {
  it('queued / running 的回执只显示原 owner 状态，绝不显示"已完成"', async () => {
    mount({ receipts: { items: [wireJob({ status: 'queued' }), wireJob({ id: '22222222-2222-4222-8222-222222222222', status: 'running', progress: 30 })], next_offset: null } });
    await waitFor(() => expect(screen.getByText('排队中')).toBeTruthy());
    expect(screen.getByText('处理中')).toBeTruthy();
    expect(screen.queryByText('已完成')).toBeNull();
    expect(screen.getAllByText(/没有文件名（未确认完成）/).length).toBe(2);
  });

  it('原 owner 返回未定义状态时显示"结果未知"，不猜测成完成', async () => {
    mount({ receipts: { items: [wireJob({ status: 'SOMETHING_NEW' })], next_offset: null } });
    await waitFor(() => expect(screen.getByText('结果未知')).toBeTruthy());
    expect(screen.queryByText('已完成')).toBeNull();
    expect(screen.getByText(/未定义状态/)).toBeTruthy();
  });

  it('只有真实 succeeded 的回执才出现"已完成"与文件名', async () => {
    mount({ receipts: { items: [wireJob({ status: 'succeeded', progress: 100, result: { format: 'txt', filename: 'novel-a.txt' } })], next_offset: null } });
    await waitFor(() => expect(screen.getByText('已完成')).toBeTruthy());
    expect(screen.getByText('novel-a.txt')).toBeTruthy();
  });

  it('恢复区说明"重新读取原回执"，绝不提供派发按钮', async () => {
    mount({ receipts: { items: [], next_offset: null } });
    await waitFor(() => expect(screen.getByText('还没有读取到回执')).toBeTruthy());
    expect(screen.getByText(/恢复只会重新读取原回执/)).toBeTruthy();
    const labels = screen.getAllByRole('button').map(button => button.textContent ?? '');
    expect(labels.some(label => /派发|创建导出|重新尝试|重试|取消任务/.test(label))).toBe(false);
  });
});

describe('DeliveryCenterPanel：这个目录发不出第二次派发，也导不出身份没权利导出的对象', () => {
  it('整个面板只发起 GET；没有任何写请求', async () => {
    const { calls } = mount({ receipts: { items: [wireJob({ status: 'running' })], next_offset: null } });
    await waitFor(() => expect(screen.getByText('处理中')).toBeTruthy());
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.every(call => call.method === 'GET')).toBe(true);
    expect(calls.every(call => call.body === undefined)).toBe(true);
    expect(calls.every(call => call.url.startsWith('/api/exports?novel_id='))).toBe(true);
  });

  it('他项目对象与身份没有权利导出的对象都不会进入交接包', async () => {
    mount({
      receipts: { items: [], next_offset: null },
      entitlements: grants({ item_kinds: [], formats: [], can_export: false }),
      items: [
        { id: 'mine', novel_id: PROJECT, kind: 'text', path: 'chapters/1.md', version: 1, digest: digest('a'), size_bytes: 10, visibility: 'VISIBLE' },
        { id: 'foreign', novel_id: 'novel-b', kind: 'text', path: 'chapters/2.md', version: 1, digest: digest('b'), size_bytes: 10, visibility: 'VISIBLE' },
        { id: 'model', novel_id: PROJECT, kind: 'text', path: 'models/x.gguf', version: 1, digest: digest('c'), size_bytes: 10, visibility: 'VISIBLE' },
        { id: 'dep', novel_id: PROJECT, kind: 'text', path: 'node_modules/x/index.js', version: 1, digest: digest('d'), size_bytes: 10, visibility: 'VISIBLE' },
        { id: 'secret', novel_id: PROJECT, kind: 'text', path: 'cfg/token.json', version: 1, digest: digest('e'), size_bytes: 10, visibility: 'VISIBLE' },
      ],
    });
    await waitFor(() => expect(screen.getByText('没有记录')).toBeTruthy());
    // 身份完全没有导出权利：一条都不能被选进交接包。
    expect(screen.getByText('当前身份没有被授予导出权利，因此没有任何对象可以导出。')).toBeTruthy();
    for (const button of screen.getAllByText('选入交接包')) {
      fireEvent.click(button);
    }
    await waitFor(() => expect(screen.getByText('交接包当前为空')).toBeTruthy());
    const flags = screen.getByLabelText('交接包结构保证');
    expect(within(flags).getAllByText(/否（结构上不可能）/).length).toBe(4);
  });

  it('显式勾选后：清单只放行有权导出的对象，模型/依赖/凭据/他项目对象逐条排斥', async () => {
    mount({
      receipts: { items: [], next_offset: null },
      items: [
        { id: 'mine', novel_id: PROJECT, kind: 'text', path: 'chapters/1.md', version: 4, digest: digest('a'), size_bytes: 10, visibility: 'VISIBLE' },
        { id: 'foreign', novel_id: 'novel-b', kind: 'text', path: 'chapters/2.md', version: 1, digest: digest('b'), size_bytes: 10, visibility: 'VISIBLE' },
        { id: 'model', novel_id: PROJECT, kind: 'text', path: 'models/x.gguf', version: 1, digest: digest('c'), size_bytes: 10, visibility: 'VISIBLE' },
        { id: 'dep', novel_id: PROJECT, kind: 'text', path: 'node_modules/x/index.js', version: 1, digest: digest('d'), size_bytes: 10, visibility: 'VISIBLE' },
        { id: 'secret', novel_id: PROJECT, kind: 'text', path: 'cfg/token.json', version: 1, digest: digest('e'), size_bytes: 10, visibility: 'VISIBLE' },
      ],
    });
    await waitFor(() => expect(screen.getByText('没有记录')).toBeTruthy());
    for (const button of screen.getAllByText('选入交接包')) {
      fireEvent.click(button);
    }
    await waitFor(() => expect(screen.getByText('被排斥的对象（默认拒绝）')).toBeTruthy());
    const entries = screen.getByLabelText('工程交接包清单');
    const rows = Array.from(entries.querySelectorAll('.delivery-manifest__row')).map(node => node.textContent ?? '');
    expect(rows).toHaveLength(1);
    expect(rows[0]).toContain('mine');
    for (const hostile of ['foreign', 'model', 'dep', 'secret']) {
      expect(rows.join('|')).not.toContain(hostile);
    }
    for (const reason of ['FOREIGN_PROJECT', 'MODEL_ARTIFACT', 'PATH_FORBIDDEN', 'SECRET_BEARING']) {
      expect(screen.getAllByText(reason).length).toBeGreaterThan(0);
    }
    expect(within(entries).getAllByText(/否（结构上不可能）/).length).toBe(4);
  });

  it('已知实体：有权利的项目的显式勾选对象进入清单；格式与限额照原 owner 显示', async () => {
    mount({
      receipts: { items: [], next_offset: null },
      items: [{ id: 'mine', novel_id: PROJECT, kind: 'text', path: 'chapters/1.md', version: 4, digest: digest('a'), size_bytes: 2048, visibility: 'VISIBLE' }],
    });
    await waitFor(() => expect(screen.getByText('没有记录')).toBeTruthy());
    expect(screen.getByText(/格式、限额、任务状态与恢复次数全部照原导出服务显示/)).toBeTruthy();
    expect(screen.getByText('可单独导出')).toBeTruthy();
    // 限额逐条来自原 owner 的常量。
    expect(screen.getByText(`单对象：${DELIVERY_ITEM_BYTES_LIMIT} 字节`)).toBeTruthy();
    expect(screen.getByText(`整包：${DELIVERY_PACKAGE_BYTES_LIMIT} 字节`)).toBeTruthy();
    expect(screen.getByText('上限是否被上调：否 — 永远不会')).toBeTruthy();
  });
});
