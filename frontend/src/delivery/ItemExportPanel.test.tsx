// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ItemExportPanel, type ItemExportPanelProps } from './ItemExportPanel';
import {
  DELIVERY_ITEM_BYTES_LIMIT, DELIVERY_PACKAGE_BYTES_LIMIT,
  type DeliveryEntitlements, type DeliveryItem, type DeliveryItemKind,
} from './deliveryTypes';

const item: DeliveryItem = {
  id: 'chapter-1', novel_id: 'novel-a', kind: 'text', media_type: 'text/plain',
  path: 'chapters/001.md', version: 3, digest: 'a'.repeat(64), size_bytes: 1024,
  visibility: 'VISIBLE', source: '章节原文',
};
const entitlements: DeliveryEntitlements = {
  project_id: 'novel-a', identity: 'file:colleague', can_export: true,
  item_kinds: ['text', 'image'], formats: ['txt', 'json', 'storyboard'],
  max_item_bytes: DELIVERY_ITEM_BYTES_LIMIT, max_package_bytes: DELIVERY_PACKAGE_BYTES_LIMIT,
  max_items: 500,
};

function mount(patch: Partial<ItemExportPanelProps> = {}) {
  const onToggle = vi.fn();
  const onRememberDispatch = vi.fn();
  const onKindChange = vi.fn();
  function Harness() {
    const [kind, setKind] = useState<DeliveryItemKind | ''>(patch.kind ?? '');
    return <ItemExportPanel items={[item]} entitlements={entitlements} selection={[item.id]}
      onToggle={onToggle} onRememberDispatch={onRememberDispatch} {...patch} kind={kind}
      onKindChange={next => { onKindChange(next); setKind(next); }} />;
  }
  render(<Harness />);
  return { onToggle, onRememberDispatch, onKindChange };
}

afterEach(cleanup);

describe('single-item inspection feedback and filter recovery', () => {
  it('clears a prior successful format verdict until the new format is explicitly checked', () => {
    const callbacks = mount();
    fireEvent.click(screen.getByRole('button', { name: '核对这个对象的格式' }));
    expect(screen.getByText(/可以单独导出（文本 → txt）/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('单对象导出格式'), { target: { value: 'json' } });
    expect(screen.queryByText(/可以单独导出（/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '核对这个对象的格式' }));
    expect(screen.getByText(/可以单独导出（文本 → json）/)).toBeTruthy();
    expect(callbacks.onToggle).not.toHaveBeenCalled();
    expect(callbacks.onRememberDispatch).not.toHaveBeenCalled();
  });

  it('clears a format refusal on change without fabricating a fresh success verdict', () => {
    mount();
    fireEvent.change(screen.getByLabelText('单对象导出格式'), { target: { value: 'storyboard' } });
    fireEvent.click(screen.getByRole('button', { name: '核对这个对象的格式' }));
    expect(screen.getByRole('alert')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('单对象导出格式'), { target: { value: 'txt' } });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByText(/可以单独导出（/)).toBeNull();
  });

  it('explains an empty kind filter and restores all items without changing the selection', () => {
    const callbacks = mount({ kind: 'image' });
    expect(screen.getByText('当前种类没有匹配对象')).toBeTruthy();
    expect(screen.queryByText('没有可核对的导出对象')).toBeNull();
    const reset = screen.getByRole('button', { name: '显示全部种类' });
    reset.focus();
    fireEvent.click(reset);
    expect(callbacks.onKindChange).toHaveBeenCalledWith('');
    expect(screen.queryByText('当前种类没有匹配对象')).toBeNull();
    expect(screen.getByText('chapter-1')).toBeTruthy();
    expect(screen.getByRole('button', { name: '已选入交接包' }).getAttribute('aria-pressed')).toBe('true');
    expect(document.activeElement).toBe(screen.getByLabelText('对象种类过滤'));
    expect(callbacks.onToggle).not.toHaveBeenCalled();
    expect(callbacks.onRememberDispatch).not.toHaveBeenCalled();
  });

  it('clears the previous item verdict when the visible kind changes', () => {
    mount();
    fireEvent.click(screen.getByRole('button', { name: '核对这个对象的格式' }));
    expect(screen.getByText(/可以单独导出（文本 → txt）/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('对象种类过滤'), { target: { value: 'image' } });
    expect(screen.queryByText(/可以单独导出（/)).toBeNull();
    expect(screen.getByText('当前种类没有匹配对象')).toBeTruthy();
  });

  it('keeps a truly empty catalog distinct from an empty filter', () => {
    mount({ items: [], kind: 'image' });
    expect(screen.getByText('没有可核对的导出对象')).toBeTruthy();
    expect(screen.queryByText('当前种类没有匹配对象')).toBeNull();
    expect(screen.queryByRole('button', { name: '显示全部种类' })).toBeNull();
  });
});
