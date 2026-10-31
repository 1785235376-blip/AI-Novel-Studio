// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ProductionReceiptReview, ReceiptNavigation } from './ProductionReceiptReview';
import { originalChapterTarget, originalTaskTarget, receiptRecoveryAdvice, receiptRecoveryStage, receiptOutputs } from './productionReceiptReviewHelpers';
afterEach(cleanup);
const clickHandler = (node: HTMLElement) => (node as any)[Object.keys(node).find(key => key.startsWith('__reactProps$'))!].onClick as () => void;
const target = originalTaskTarget('original-task')!;
it('opens an exact original task only after leave consent, with cancel preserving the panel', () => {
  const navigate = vi.fn();
  render(<ProductionReceiptReview manifestId="manifest" manifestVersion={1} receiptIdentity="receipt-1" taskId="original-task" taskVersion={4} pins={[{ kind: 'CHAPTER', id: 'chapter-章', version: 3, digest: 'a'.repeat(64) }]} outputs={[{ proposal_id: 'candidate-1', candidate_index: 0, digest: 'a'.repeat(64) }]} onNavigate={navigate} busy={false} />);
  expect(screen.getByText(/捕获任务 original-task · v4/)).toBeTruthy();
  expect(screen.getByText(/candidate-1/)).toBeTruthy();
  expect(screen.getByText(/未知不能当作已通过、免费或已批准/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '打开确切原媒体任务' }));
  expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '留在此处' }));
  expect(screen.queryByRole('button', { name: '确认离开并打开确切原媒体任务' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '打开确切原媒体任务' }));
  fireEvent.click(screen.getByRole('button', { name: '确认离开并打开确切原媒体任务' }));
  expect(navigate).toHaveBeenCalledTimes(1); expect(navigate).toHaveBeenCalledWith(target);
});
it('chapter navigation passes the captured pin while explicitly disclosing current-body navigation', () => {
  const navigate = vi.fn();
  render(<ProductionReceiptReview manifestId="manifest" manifestVersion={1} receiptIdentity="receipt-1" taskId="task" taskVersion={3} pins={[{ kind: 'CHAPTER', id: '章', version: 7, digest: 'a'.repeat(64) }]} outputs={[]} onNavigate={navigate} busy={false} />);
  fireEvent.click(screen.getByRole('button', { name: '查看当前来源章节 章' }));
  fireEvent.click(screen.getByRole('button', { name: '确认离开并查看当前来源章节 章' }));
  expect(navigate).toHaveBeenCalledTimes(1); expect(navigate).toHaveBeenCalledWith({ kind: 'chapter', id: '章', version: 7 });
});
it('paginates source pins and withholds unavailable source navigation and evidence', () => {
  const pins = Array.from({ length: 21 }, (_, i) => ({ kind: 'CHAPTER', id: `source-${i}`, version: i + 1, digest: 'a'.repeat(64) }));
  render(<ProductionReceiptReview manifestId="manifest" manifestVersion={1} receiptIdentity="receipt-1" taskId="task" taskVersion={3} pins={[...pins, { kind: 'CHAPTER', id: 'hidden', version: 3, digest: 'hidden-digest', state: 'UNAVAILABLE' }]} outputs={[]} onNavigate={vi.fn()} busy={false} />);
  expect(screen.queryByRole('button', { name: '查看当前来源章节 source-20' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '下一页来源' }));
  expect(screen.getByRole('button', { name: '查看当前来源章节 source-20' })).toBeTruthy();
  expect(screen.queryByText(/hidden/)).toBeNull();
  expect(screen.queryByRole('button', { name: '查看当前来源章节 hidden' })).toBeNull();
});
it('invalidates leave consent across changed targets, busy changes, and unmount', () => {
  const navigate = vi.fn();
  const view = render(<ReceiptNavigation target={target} label="打开" onNavigate={navigate} />);
  fireEvent.click(screen.getByRole('button', { name: '打开' }));
  const oldConfirm = clickHandler(screen.getByRole('button', { name: '确认离开并打开' }));
  view.rerender(<ReceiptNavigation target={originalTaskTarget('other')} label="打开" onNavigate={navigate} />);
  act(() => oldConfirm()); expect(navigate).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: '确认离开并打开' })).toBeNull();
  view.rerender(<ReceiptNavigation target={target} label="打开" onNavigate={navigate} />);
  fireEvent.click(screen.getByRole('button', { name: '打开' }));
  view.rerender(<ReceiptNavigation target={target} label="打开" onNavigate={navigate} disabled />);
  expect(screen.queryByRole('button', { name: '确认离开并打开' })).toBeNull();
  act(() => oldConfirm()); view.unmount(); act(() => oldConfirm()); expect(navigate).not.toHaveBeenCalled();
});
it.each([undefined, '', ' ', 4, 'x'.repeat(241)])('does not manufacture task identities (%s)', value => { expect(originalTaskTarget(value)).toBeUndefined(); });
it.each([0, -1, 1.5, NaN, undefined])('does not manufacture chapter versions (%s)', value => { expect(originalChapterTarget({ kind: 'CHAPTER', id: 'c', version: value })).toBeUndefined(); });
it.each([
  ['SOURCE_CHANGED_OR_UNAVAILABLE', '来源与原授权'], ['SOURCE_TASK_CHANGED', '来源与原授权'], ['ORIGIN_AUTHORITY_CHANGED', '来源与原授权'],
  ['ADAPTER_OR_MODEL_CHANGED', '环境与模型'], ['ORIGINAL_RUNTIME_EVIDENCE_MISSING', '环境与模型'],
  ['ORIGINAL_OUTPUT_UNAVAILABLE', '原产物'], ['ORIGINAL_OUTPUT_CHANGED', '原产物'],
  ['MODEL_BROKER_NO_LEGAL_ROUTE', '费用与本次授权'], ['FRESH_CLOUD_AUTHORIZATION_NOT_INTEGRATED', '费用与本次授权'], ['UNKNOWN_CODE', '未分类阻断'],
])('explains %s without inferring a retry or cache hit', (code, stage) => {
  expect(receiptRecoveryStage(code)).toBe(stage); expect(receiptRecoveryAdvice(code).length).toBeGreaterThan(20);
});

it.each(['receipt', 'callback'])('invalidates pending and retained consent when %s changes', change => {
  const navigate = vi.fn(), next = vi.fn();
  const view = render(<ReceiptNavigation target={target} label="打开" onNavigate={navigate} receiptIdentity="manifest-v1" />);
  fireEvent.click(screen.getByRole('button', { name: '打开' }));
  const stale = clickHandler(screen.getByRole('button', { name: '确认离开并打开' }));
  view.rerender(<ReceiptNavigation target={target} label="打开" onNavigate={change === 'callback' ? next : navigate} receiptIdentity={change === 'receipt' ? 'manifest-v2' : 'manifest-v1'} />);
  expect(screen.queryByRole('button', { name: '确认离开并打开' })).toBeNull();
  act(() => stale()); expect(navigate).not.toHaveBeenCalled(); expect(next).not.toHaveBeenCalled();
});
it.each([null, undefined, {}, [null], [42], Array(501).fill(null)])('withholds malformed source/candidate receipts without crashing (%s)', value => {
  render(<ProductionReceiptReview manifestId="m" manifestVersion={3} receiptIdentity="receipt" taskId="task" taskVersion={2} pins={value} outputs={value} onNavigate={vi.fn()} busy={false} />);
  expect(screen.getByText('清单 m · v3')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /查看当前来源章节/ })).toBeNull();
  expect(screen.getByText(/候选回执不完整/)).toBeTruthy();
});
it('withholds duplicate source IDs even when their versions or digests disagree', () => {
  render(<ProductionReceiptReview manifestId="m" manifestVersion={1} receiptIdentity="receipt" taskId="task" taskVersion={2} pins={[{ kind: 'CHAPTER', id: 'same', version: 1, digest: 'a'.repeat(64) }, { kind: 'CHAPTER', id: 'same', version: 2, digest: 'b'.repeat(64) }]} outputs={[]} onNavigate={vi.fn()} busy={false} />);
  expect(screen.queryByRole('button', { name: /查看当前来源章节/ })).toBeNull();
  expect(screen.getAllByText(/存在重复引用/)).toHaveLength(2);
});
it.each(['bad\nidentifier', 'https://wrong.example/task', ' padded ', 'a b'])('withholds malformed owner identifier %s', id => {
  expect(originalTaskTarget(id)).toBeUndefined();
});

it('duplicate candidate IDs or indices cannot become a trustworthy receipt count', () => {
  const row = { proposal_id: 'p', candidate_index: 0, digest: 'a'.repeat(64) };
  expect(receiptOutputs([row, { ...row, candidate_index: 1 }])).toBeNull();
  expect(receiptOutputs([row, { ...row, proposal_id: 'q' }])).toBeNull();
});
it('same chapter ID/version with changed digest invalidates retained confirmation', () => {
  const navigate = vi.fn();
  const props = { manifestId: 'm', manifestVersion: 1, receiptIdentity: 'receipt', taskId: 't', taskVersion: 1, outputs: [], onNavigate: navigate, busy: false };
  const view = render(<ProductionReceiptReview {...props} pins={[{ kind: 'CHAPTER', id: 'c', version: 1, digest: 'a'.repeat(64) }]} />);
  fireEvent.click(screen.getByRole('button', { name: '查看当前来源章节 c' }));
  const stale = clickHandler(screen.getByRole('button', { name: '确认离开并查看当前来源章节 c' }));
  view.rerender(<ProductionReceiptReview {...props} pins={[{ kind: 'CHAPTER', id: 'c', version: 1, digest: 'b'.repeat(64) }]} />);
  act(() => stale()); expect(navigate).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: '确认离开并查看当前来源章节 c' })).toBeNull();
});
