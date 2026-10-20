// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ReceiptRecoveryPanel, type ReceiptRecoveryPanelProps } from './ReceiptRecoveryPanel';
import type { DeliveryReceipt } from './deliveryTypes';

const receipt: DeliveryReceipt = {
  id: 'receipt-1', project_id: 'project-1', format: 'txt', status: 'succeeded', raw_status: null,
  created_at: '', updated_at: '', progress: 100, progress_message: '完成', attempt: 1, retry_of: null,
  recovery_count: 0, snapshot_id: null, captured_at: null, source_versions: [], missing_resources: [],
  result_filename: 'story.txt', error: null,
};
function props(patch: Partial<ReceiptRecoveryPanelProps> = {}): ReceiptRecoveryPanelProps {
  return { state: 'READY', page: { items: [receipt], next_offset: null }, attempts: [],
    lastRequest: null, lastRecovery: null, onRecover: vi.fn(), ...patch };
}
afterEach(cleanup);

describe('Loaded receipt read states', () => {
  it.each(['IDLE', 'LOADING', 'FAILED'] as const)('does not describe %s with no page as a successful empty read', state => {
    render(<ReceiptRecoveryPanel {...props({ state, page: undefined })} />);
    expect(screen.queryByText('还没有读取到回执')).toBeNull();
    expect(screen.queryByText(/原导出服务在该项目下没有返回任何回执/)).toBeNull();
    expect(screen.getByLabelText('导出回执与恢复').getAttribute('aria-busy')).toBe(String(state === 'LOADING'));
    expect(screen.getByText(state === 'IDLE' ? /尚未开始读取回执/ : state === 'LOADING' ? /正在读取回执/ : /本次回执读取失败/)).toBeTruthy();
  });

  it('renders the empty receipt message only after a completed empty read', () => {
    render(<ReceiptRecoveryPanel {...props({ state: 'EMPTY', page: { items: [], next_offset: null } })} />);
    expect(screen.getByText('还没有读取到回执')).toBeTruthy();
  });

  it.each(['LOADING', 'FAILED'] as const)('labels retained receipts during %s without removing their known file names', state => {
    const p = props({ state });
    render(<ReceiptRecoveryPanel {...p} />);
    expect(screen.getByText('story.txt')).toBeTruthy();
    expect(screen.getByText(/下方为先前已加载的回执/)).toBeTruthy();
    expect(screen.queryByText('还没有读取到回执')).toBeNull();
    expect(p.onRecover).not.toHaveBeenCalled();
  });

  it.each([0, 50])('labels the displayed page as incomplete when next_offset is %s', next_offset => {
    const p = props({ page: { items: [receipt], next_offset } });
    render(<ReceiptRecoveryPanel {...p} />);
    expect(screen.getByText(/当前只显示已加载的 1 条回执/)).toBeTruthy();
    expect(screen.getByText(/原导出中心继续翻页/)).toBeTruthy();
    expect(p.onRecover).not.toHaveBeenCalled();
  });

  it('distinguishes a completed job with absent file metadata from an unfinished job', () => {
    render(<ReceiptRecoveryPanel {...props({ page: { items: [{ ...receipt, result_filename: null }], next_offset: null } })} />);
    expect(screen.getByText('已完成')).toBeTruthy();
    expect(screen.getByText(/已完成，但原服务未提供文件名/)).toBeTruthy();
    expect(screen.queryByText('没有文件名（未确认完成）')).toBeNull();
  });
});
