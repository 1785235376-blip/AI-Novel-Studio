// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
// Explicit JSX extension uses TS/Vite's .jsx -> .tsx substitution on case-insensitive Windows.
import { MediaCanvasHistoryCompare } from './MediaCanvasHistoryCompare.jsx';
import type { MediaCanvasHistoryCompareProps } from './MediaCanvasHistoryCompare.jsx';
import type { CanvasDefinition, CanvasReferenceState } from './studioCanvasViewClient';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const a = 'a'.repeat(64), b = 'b'.repeat(64);
function setup(total = 0): MediaCanvasHistoryCompareProps {
  const before: CanvasDefinition = { schema_version: 1, title: 'Current', cards: [], viewport: { x: 0, y: 0, zoom: 1 } };
  const after: CanvasDefinition = { ...before, cards: Array.from({ length: total }, (_, index) => ({ id: `Card${index}`, position: { x: index * 8, y: 0 }, asset: { asset_id: `recorded-asset-${index}`, kind: 'image', version: 4, digest: a } })) };
  const states: CanvasReferenceState[] = after.cards.map(card => ({ card_id: card.id, state: 'CURRENT_METADATA', filename: 'synthetic.png' }));
  return { current: true, isCurrent: () => true, incarnation: 'incarnation-A', targetVersion: 1,
    base: { project_id: 'project', scope: { mode: 'local', novel_id: 'novel' }, id: 'canvas', version: 2, definition_digest: b, definition: before, reference_states: [], created_at: 'created', updated_at: 'updated', execution_authority: false, binary_content_verified: false, capacity: { history_used: 1, record_bytes: 1000 } },
    history: { project_id: 'project', scope: { mode: 'local', novel_id: 'novel' }, id: 'canvas', incarnation: 'incarnation-A', current_version: 2, current_definition_digest: b,
      items: [{ version: 1, definition: after, definition_digest: a, reference_states: states, created_at: 'created', updated_at: 'updated', can_restore: true },
        { version: 2, definition: structuredClone(before), definition_digest: b, reference_states: [], created_at: 'created', updated_at: 'updated', can_restore: false }], restore_policy: 'CURRENT_METADATA_ONLY', execution_authority: false, binary_content_verified: false } };
}
it('renders empty comparison, complete quantities and clearly scoped restore consequences without actions', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); render(<MediaCanvasHistoryCompare {...setup()} />);
  expect(screen.getByLabelText('完整影响数量').textContent).toContain('新增 0；移除 0');
  expect(screen.getByText('没有已记录的布局或资产 pin 差异；恢复仍会创建新版本。')).toBeTruthy();
  expect(screen.getByText(/仅影响此画布/).textContent).toContain('退役旧预览及回流意图');
  expect(screen.getByText(/仅比较元数据/).textContent).toContain('不回滚历史文件');
  expect(screen.getByText(/服务端 can_restore/).textContent).toContain('不授予恢复权限');
  expect(screen.queryByRole('button')).toBeNull(); expect(screen.queryByRole('checkbox')).toBeNull(); expect(fetch).not.toHaveBeenCalled();
});
it('shows recorded exact pins and complete totals while explicitly truncating long detail lists', () => {
  render(<MediaCanvasHistoryCompare {...setup(73)} />);
  expect(screen.getByLabelText('完整影响数量').textContent).toContain('新增 73；移除 0');
  expect(screen.getByText(/仅显示前 40 项/).textContent).toContain('另 33 项明细已截断；以上数量包含全部变更');
  const details = screen.getByRole('list', { name: '差异明细' }); expect(within(details).getAllByRole('listitem')).toHaveLength(40);
  expect(details.textContent).toContain(`recorded-asset-0 · image · v4 · digest ${a}`); expect(details.textContent).not.toContain('recorded-asset-72');
});
it.each(['current-prop', 'owner-callback'] as const)('hides before accessing old getters when retired through %s', kind => {
  const props = { current: kind !== 'current-prop', isCurrent: () => kind !== 'owner-callback' } as MediaCanvasHistoryCompareProps;
  for (const key of ['base', 'history', 'incarnation', 'targetVersion']) Object.defineProperty(props, key, { enumerable: true, get: () => { throw new Error('Old data was read'); } });
  // React spreads would themselves read getters: directly create the element with a props object.
  render(MediaCanvasHistoryCompare(props));
  expect(screen.getByText(/旧版本对比已隐藏/)).toBeTruthy(); expect(screen.queryByLabelText('完整影响数量')).toBeNull();
});
it('hides computed data if ownership expires during the same render', () => {
  const props = setup(2); props.isCurrent = vi.fn().mockReturnValueOnce(true).mockReturnValue(false);
  render(<MediaCanvasHistoryCompare {...props} />); expect(screen.getByText(/旧版本对比已隐藏/)).toBeTruthy(); expect(screen.queryByText(/recorded-asset/)).toBeNull();
});
it.each(['missing-incarnation', 'changed-incarnation', 'changed-scope', 'changed-current', 'missing-selection', 'unknown-state', 'extension'] as const)('does not show pins for %s', kind => {
  const props = setup(1);
  if (kind === 'missing-incarnation') props.incarnation = undefined;
  if (kind === 'changed-incarnation') props.incarnation = 'incarnation-B';
  if (kind === 'changed-scope') props.history.scope = { mode: 'local', novel_id: 'other' };
  if (kind === 'changed-current') props.base.definition_digest = a;
  if (kind === 'missing-selection') props.targetVersion = 3;
  if (kind === 'unknown-state') (props.history.items[0].reference_states[0] as any).state = 'PASS';
  if (kind === 'extension') (props.history.items[0].definition as any).credential = 'SECRET_EXTENSION';
  render(<MediaCanvasHistoryCompare {...props} />);
  expect(screen.queryByLabelText('完整影响数量')).toBeNull(); expect(document.body.textContent).not.toContain('recorded-asset'); expect(document.body.textContent).not.toContain('SECRET_EXTENSION');
});
it('shows unavailable references honestly and never renders a filename or a binding as a credential/proof', () => {
  const props = setup(1), item = props.history.items[0]; delete item.definition.cards[0].asset;
  item.reference_states = [{ card_id: 'Card0', state: 'UNAVAILABLE' }]; item.can_restore = false;
  render(<MediaCanvasHistoryCompare {...props} />);
  expect(screen.getByLabelText('完整影响数量').textContent).toContain('不可用 1');
  expect(screen.getByText(/新增卡片 Card0/).textContent).toContain('原 pin 未提供');
  expect(screen.getByText(/can_restore 为 false/)).toBeTruthy(); expect(document.body.textContent).not.toContain('media-canvas-history-comparison/1');
});
