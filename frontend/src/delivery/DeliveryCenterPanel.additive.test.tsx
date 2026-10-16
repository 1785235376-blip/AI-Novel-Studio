// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { DeliveryCenterPanel, type DeliveryCenterPanelProps } from './DeliveryCenterPanel';
import { DELIVERY_ITEM_BYTES_LIMIT, DELIVERY_PACKAGE_BYTES_LIMIT } from './deliveryTypes';

const PROJECT = 'novel-a';
const JOB = '11111111-1111-4111-8111-111111111111';

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

describe('Delivery receipt read feedback', () => {
  it('waits for a completed empty read before claiming no receipt was returned', async () => {
    let resolve!: (value: unknown) => void;
    const pending = new Promise(done => { resolve = done; });
    const { transport } = fakeTransport(() => pending);
    mount({ transport });
    await screen.findByText(/正在读取回执；完成前不能确认当前记录/);
    expect(screen.queryByText('还没有读取到回执')).toBeNull();
    expect(screen.getByLabelText('导出回执与恢复').getAttribute('aria-busy')).toBe('true');
    await act(async () => resolve({ items: [], next_offset: null }));
    await screen.findByText('还没有读取到回执');
    expect(screen.getByLabelText('导出回执与恢复').getAttribute('aria-busy')).toBe('false');
  });

  it('recovers through the existing explicit read after failure without displaying a false empty history', async () => {
    let failed = true;
    const { transport, calls } = fakeTransport(() => {
      if (failed) throw new ApiError({ status: 503, code: 'EXPORT_HISTORY_UNAVAILABLE', message: 'synthetic service unavailable' });
      return { items: [], next_offset: null };
    });
    mount({ transport });
    await screen.findByText(/本次回执读取失败/);
    expect(screen.queryByText('还没有读取到回执')).toBeNull();
    failed = false;
    fireEvent.click(screen.getByRole('button', { name: '重新读取导出回执' }));
    await screen.findByText('还没有读取到回执');
    expect(calls).toHaveLength(2);
    expect(calls.every(call => call.method === 'GET')).toBe(true);
  });
});

describe('Delivery empty page with remaining history', () => {
  it.each([0, 50])('does not describe an empty loaded page with next_offset %s as an empty project history', async next_offset => {
    const { transport, calls } = fakeTransport(() => ({ items: [], next_offset }));
    mount({ transport });
    await screen.findByText(/不能视为完整历史/);
    expect(screen.queryByText(/原导出服务在该项目下还没有记录/)).toBeNull();
    expect(screen.getByText('当前页没有导出回执')).toBeTruthy();
    expect(screen.getByText('当前页为空')).toBeTruthy();
    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe('GET');
  });
});
